from fastapi import APIRouter

from jukeboxsvc.biz.ovh_cluster import (
    create_cloud_instance,
    delete_cloud_instance,
    get_all_nodes,
)
from jukeboxsvc.biz.ovh_defs import OvhClusterNodeDescr
from jukeboxsvc.dto.ovh_cluster import (
    CreateCloudInstanceRequestDTO,
    CreateCloudInstanceResponseDTO,
)

router = APIRouter()


@router.get("/ovh/cluster/nodes", response_model=list[OvhClusterNodeDescr], operation_id="get_ovh_cluster_nodes")
def ovh_cluster_nodes() -> list[OvhClusterNodeDescr]:
    """Returns list of all nodes in the OVH cluster."""
    return get_all_nodes()


@router.post(
    "/ovh/cluster/nodes/create", response_model=CreateCloudInstanceResponseDTO, operation_id="create_ovh_cluster_node"
)
def ovh_cluster_node_create(req: CreateCloudInstanceRequestDTO) -> CreateCloudInstanceResponseDTO:
    """Creates a new cloud instance in the OVH cluster.
    Only jukebox nodes can be created that way;
    appstor node requirements are handled differently (e.g. block storage creation and volume attach), so use infra's
    add_appstor.sh script.
    """
    instance_id = create_cloud_instance(
        region=req.region,
        flavor=req.flavor,
        name=req.name,
        image=req.image,
        private_ip=None,
        user_data=None,
    )
    return CreateCloudInstanceResponseDTO(id=instance_id)


@router.post("/ovh/cluster/nodes/{node_id}/delete", status_code=204, operation_id="delete_ovh_cluster_node")
def ovh_cluster_node_delete(node_id: str) -> None:
    """Deletes a node from the OVH cluster."""
    delete_cloud_instance(instance_id=node_id)
