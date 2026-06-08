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
    """Creates a new node in the OVH cluster."""
    instance_id = create_cloud_instance(region=req.region, flavor=req.flavor, name=req.name, image=req.image)
    return CreateCloudInstanceResponseDTO(id=instance_id)


@router.post("/ovh/cluster/nodes/{node_id}/delete", status_code=204, operation_id="delete_ovh_cluster_node")
def ovh_cluster_node_delete(node_id: str) -> None:
    """Deletes a node from the OVH cluster."""
    delete_cloud_instance(instance_id=node_id)
