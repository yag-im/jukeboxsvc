import concurrent.futures
import copy
import json
import logging
import os
import threading
from dataclasses import dataclass

# from jukeboxsvc.biz.misc import log_input_output
from jukeboxsvc.biz.node import Node
from jukeboxsvc.services.dto.sessionsvc import GetSessionsResponseDTO
from jukeboxsvc.services.sessionsvc import get_sessions

STATE_UPDATE_MAX_WORKERS = 50
STATE_UPDATE_PERIOD = 60

JUKEBOX_NODES = os.environ["JUKEBOX_NODES"]


log = logging.getLogger("jukeboxsvc")


@dataclass
class NodeConnInfo:
    """Node connection info (from a local storage)."""

    api_uri: str
    region: str


class Cluster:
    _nodes: dict[str, Node]
    _nodes_conn_info: list[NodeConnInfo]  # this comes from the local resource
    _lock = threading.Lock()

    def __init__(self, cluster_nodes: str) -> None:
        self._nodes_conn_info = [NodeConnInfo(**ci) for ci in json.loads(cluster_nodes)]
        self.update()  # the very first update is synchronous
        # TODO: do we need to update state periodically?
        # upd_thread = threading.Timer(interval=STATE_UPDATE_PERIOD, function=self.update)
        # upd_thread.daemon = True  # daemonizing is required so pytest doesn't hang on exit
        # upd_thread.start()

    @property
    def nodes(self) -> dict[str, Node]:
        with self._lock:
            return copy.deepcopy(self._nodes)

    # @log_input_output
    def update(self) -> None:
        """Updates current state of the cluster."""

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=STATE_UPDATE_MAX_WORKERS) as executor:
                nodes = list(
                    executor.map(
                        lambda ci: Node(ci.region, ci.api_uri),  # calls docker API
                        self._nodes_conn_info,
                    )
                )
                if len(nodes) != len(self._nodes_conn_info):
                    log.error(
                        "cluster state updating error, expected %d nodes, got: %d nodes.",
                        len(self._nodes_conn_info),
                        len(nodes),
                    )
            with self._lock:
                self._nodes = {n.id: n for n in nodes}
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error(e, exc_info=True)

    def updated(self) -> "Cluster":
        self.update()
        return self


@dataclass
class ClusterStateLight:
    @dataclass
    class Node:
        @dataclass
        class Container:
            id: str
            node_id: str
            cpuset_cpus: set[int]

        id: str
        region: str
        containers: list[Container]
        cpus: int

    nodes: dict[str, Node]

    def get_free_cores(self, node_id: str) -> set[int]:
        node = self.nodes.get(node_id)
        if not node:
            raise ValueError(f"node with id {node_id} not found in the cluster")
        used_cores = set()
        for c in node.containers:
            used_cores.update(c.cpuset_cpus)
        return set(range(node.cpus)) - used_cores

    def get_node(self, node_id: str) -> Node | None:
        return self.nodes.get(node_id)


def get_cluster_state_quick() -> ClusterStateLight:
    """
    Quick and dirty way to get nodes state (cpu and memory usage) by parsing sessions list. This is required for better
    scheduling decisions. The alternative way is to call each node for its state (JUKEBOX_CLUSTER.updated()), but it is
    pretty heavy and time consuming, especially when the number of containers running is large.
    """
    cluster = ClusterStateLight(nodes={})
    for n in JUKEBOX_CLUSTER.nodes.values():
        cluster.nodes[n.id] = ClusterStateLight.Node(id=n.id, containers=[], cpus=n.attrs.cpus, region=n.region)

    sessions: GetSessionsResponseDTO = get_sessions()
    for s in sessions.sessions:
        if s.container is None:
            continue  # session created but not started yet, so no container assigned
        node_id = s.container.node_id
        node = cluster.nodes.get(node_id)
        if node is None:
            log.error("session %s has container assigned to node %s, but no such node in the cluster", s.id, node_id)
            continue
        node.containers.append(ClusterStateLight.Node.Container(s.container.id, node_id, set(s.container.cpuset_cpus)))
    return cluster


JUKEBOX_CLUSTER = Cluster(JUKEBOX_NODES)
