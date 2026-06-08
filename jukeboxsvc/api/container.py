from fastapi import APIRouter

from jukeboxsvc.biz.jukebox import (
    pause_container,
    resume_container,
    run_container,
    stop_container,
)
from jukeboxsvc.dto.container import (
    ResumeContainerRequestDTO,
    RunContainerRequestDTO,
    RunContainerResponseDTO,
)

router = APIRouter()


@router.post("/nodes/{node_id}/containers/{container_id}/pause", status_code=200, operation_id="pause_container")
def container_pause(node_id: str, container_id: str) -> None:
    """Pauses a running container."""
    pause_container(node_id, container_id)


@router.post("/containers/run", response_model=RunContainerResponseDTO, operation_id="run_container")
def container_run(run_specs: RunContainerRequestDTO) -> RunContainerResponseDTO:
    """Runs a new container on the most suitable cluster node."""
    return run_container(run_specs)


@router.post("/nodes/{node_id}/containers/{container_id}/stop", status_code=200, operation_id="stop_container")
def container_stop(node_id: str, container_id: str) -> None:
    """Stops a running container."""
    stop_container(node_id, container_id)


@router.post("/nodes/{node_id}/containers/{container_id}/resume", status_code=200, operation_id="resume_container")
def container_resume(node_id: str, container_id: str, req: ResumeContainerRequestDTO) -> None:
    """Resumes a paused container."""
    resume_container(node_id, container_id, req)
