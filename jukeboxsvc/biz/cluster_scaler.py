import logging
import time
from datetime import (
    datetime,
    timezone,
)

from jukeboxsvc.biz.cluster import get_jukebox_nodes
from jukeboxsvc.biz.models import NodeDAO
from jukeboxsvc.biz.node import Node
from jukeboxsvc.biz.ovh_cluster import (
    create_cloud_instance,
    delete_cloud_instance,
    get_all_nodes,
)
from jukeboxsvc.biz.ovh_defs import (
    NodeServiceType,
    OvhClusterNodeDescr,
    OvhNodeFlavor,
    OvhNodeStatus,
    OvhNodeType,
)
from jukeboxsvc.biz.sqldb import sqldb
from jukeboxsvc.dto.container import DcRegion

STATE_UPDATE_MIN_INTERVAL = 5  # seconds, interval for update()
CLUSTER_SCALE_CPU_UTILIZATION_THRESHOLD = 0.95
NODE_SCALE_DOWN_AGE_SECS = 55 * 60  # 55 minutes (billing is hourly)
JUKEBOX_NODE_FLAVOR = OvhNodeFlavor.L4_90
JUKEBOX_NODE_IMAGE_NAME = "debian13-jukebox-gpu-nvidia"

log = logging.getLogger("jukeboxsvc")


def _get_ovh_nodes_by_service(service: NodeServiceType) -> list[OvhClusterNodeDescr]:
    return [n for n in get_all_nodes() if n.name.startswith(service.value)]


def sync_cluster_state() -> None:
    """Syncs cluster state with OVH API: updates SQL table cluster.nodes with the current list of nodes"""
    for service_type in (NodeServiceType.JUKEBOX, NodeServiceType.APPSTOR):
        active_ovh_cloud_nodes = [
            n for n in _get_ovh_nodes_by_service(service_type) if n.status == OvhNodeStatus.ACTIVE
        ]
        known_nodes: list[NodeDAO] = NodeDAO.query.filter(
            NodeDAO.service_type == service_type.value,
        ).all()
        existing_by_id: dict[str, NodeDAO] = {row.uuid: row for row in known_nodes}
        ovh_ids: set[str] = {n.id for n in active_ovh_cloud_nodes}

        added: list[OvhClusterNodeDescr] = []
        removed: list[NodeDAO] = []

        for node in active_ovh_cloud_nodes:
            if node.id not in existing_by_id:
                sqldb.session.add(
                    NodeDAO(
                        uuid=node.id,
                        region=node.region.value,
                        service_type=service_type.value,
                        node_ix=node.node_ix,
                        node_type=node.node_type.value,
                        node_flavor=node.flavor.value.lower(),
                        created_ts=node.created_ts,
                    )
                )
                added.append(node)

        for node_id, row in existing_by_id.items():
            if node_id not in ovh_ids:
                sqldb.session.delete(row)
                removed.append(row)

        sqldb.session.commit()

        log.info(
            "sync_cluster_state[%s]: added %d node(s) %s, removed %d node(s) %s",
            service_type.value,
            len(added),
            [{"region": n.region.value, "flavor": n.flavor.value} for n in added],
            len(removed),
            [{"region": r.region, "node_flavor": r.node_flavor} for r in removed],
        )


def add_jukebox_node(region: DcRegion) -> None:
    """Creates a new jukebox cloud node in the given region. Check if no nodes are already pending creation."""
    jukebox_nodes = _get_ovh_nodes_by_service(NodeServiceType.JUKEBOX)
    building = [n for n in jukebox_nodes if n.status in (OvhNodeStatus.BUILD, OvhNodeStatus.BUILDING)]
    if building:
        log.warning("add_jukebox_node: %d node(s) already in build state, skipping creation", len(building))
        return
    name = f"jukebox-instance-{int(time.time())}"
    ovh_id = create_cloud_instance(region=region, flavor=JUKEBOX_NODE_FLAVOR, name=name, image=JUKEBOX_NODE_IMAGE_NAME)
    log.info(
        "add_jukebox_node: created new jukebox node '%s' in region %s (OVH id: %s)",
        name,
        region.value,
        ovh_id,
    )


def scale_jukebox_cluster() -> None:
    """Scales the jukebox cluster up or down based on CPU utilization, then syncs cluster state."""
    nodes = get_jukebox_nodes(init_containers_from_sessions=True)

    # Scale up: add a node in any region whose CPU utilization exceeds the threshold
    if nodes:
        region_usage: dict[DcRegion, tuple[int, int]] = {}  # region -> (total_cpus, used_cpus)
        for node in nodes:
            used = node.hw_specs.cpus - len(node.free_cores())
            prev_total, prev_used = region_usage.get(node.region, (0, 0))
            region_usage[node.region] = (prev_total + node.hw_specs.cpus, prev_used + used)

        for region, (total_cpus, used_cpus) in region_usage.items():
            utilization = used_cpus / total_cpus if total_cpus > 0 else 0.0
            log.info(
                "scale_jukebox_cluster: region %s CPU utilization %.2f%% (%d/%d cores used)",
                region.value,
                utilization * 100,
                used_cpus,
                total_cpus,
            )
            if utilization > CLUSTER_SCALE_CPU_UTILIZATION_THRESHOLD:
                log.info(
                    "scale_jukebox_cluster: region %s utilization %.2f%% exceeds threshold, adding node",
                    region.value,
                    utilization * 100,
                )
                add_jukebox_node(region)

    # Scale down: remove active cloud nodes that are old enough and have no containers
    jukebox_ovh_nodes = _get_ovh_nodes_by_service(NodeServiceType.JUKEBOX)
    active_cloud_nodes = [
        n for n in jukebox_ovh_nodes if n.node_type != OvhNodeType.DEDICATED and n.status == OvhNodeStatus.ACTIVE
    ]

    # Build mapping: OVH id -> Node for container count lookup
    id_to_node: dict[str, Node] = {node.id: node for node in nodes}

    now = datetime.now(timezone.utc)
    nodes_removed = 0
    for ovh_node in active_cloud_nodes:
        age_secs = (now - ovh_node.created_ts).total_seconds()  # type: ignore[operator]
        if age_secs < NODE_SCALE_DOWN_AGE_SECS:
            continue
        cluster_node = id_to_node.get(ovh_node.id)
        if cluster_node is not None and len(cluster_node.containers) > 0:
            continue  # node is in use
        log.info(
            "scale_jukebox_cluster: removing underutilized node %s (age: %.1fmin, region: %s)",
            ovh_node.id,
            age_secs / 60,
            ovh_node.region.value,
        )
        delete_cloud_instance(ovh_node.id)
        nodes_removed += 1

    if nodes_removed > 0:
        log.info("scale_jukebox_cluster: removed %d underutilized node(s), syncing cluster state", nodes_removed)

    sync_cluster_state()
