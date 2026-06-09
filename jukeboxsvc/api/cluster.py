import asyncio

from fastapi import APIRouter

from jukeboxsvc.biz.cluster import get_nodes_update
from jukeboxsvc.biz.cluster_scaler import (
    scale_jukebox_cluster,
    sync_cluster_state,
)
from jukeboxsvc.biz.jukebox import (
    cluster_status,
    pull_image,
)
from jukeboxsvc.dto.cluster import (
    ClusterStateResponseDTO,
    ClusterUsageResponseDTO,
    NodeDTO,
    PullContainerImageRequestDTO,
)

router = APIRouter()


@router.get("/cluster/status", response_model=ClusterUsageResponseDTO, operation_id="get_cluster_status")
def cluster_status_endpoint() -> ClusterUsageResponseDTO:
    """Returns cluster usage per region."""
    return cluster_status()


@router.post("/cluster/pull_image", status_code=200, operation_id="pull_cluster_image")
async def cluster_pull_image(image: PullContainerImageRequestDTO) -> None:
    """Pulls specified image onto all available cluster nodes."""
    asyncio.create_task(pull_image(image))


@router.get("/cluster/state", response_model=ClusterStateResponseDTO, operation_id="get_cluster_state")
async def cluster_state() -> ClusterStateResponseDTO:
    """Returns current state of all jukebox cluster nodes,
    fetched directly from Docker daemons on all jukebox nodes."""
    nodes = await get_nodes_update()
    return ClusterStateResponseDTO(nodes=[NodeDTO.from_node(n) for n in nodes])


@router.post("/cluster/scale", status_code=200, operation_id="scale_cluster")
def cluster_scale() -> None:
    """Scales the jukebox cluster: adds nodes when CPU utilization exceeds threshold,
    removes old underutilized nodes, and syncs the OVH cluster state with SQL cluster schema."""
    scale_jukebox_cluster()


@router.post("/cluster/state/sync", status_code=200, operation_id="sync_cluster_state")
def cluster_state_sync() -> None:
    """Syncs cluster state with OVH API: updates SQL tables in "cluster" schema with the current list of nodes."""
    sync_cluster_state()
