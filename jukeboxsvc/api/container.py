from flask import (
    Response,
    request,
)
from flask_restful import Resource

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


class ContainerPause(Resource):
    def post(self, node_id: str, container_id: str) -> Response:
        """Pauses a running container."""

        pause_container(node_id, container_id)
        return "", 200


class ContainerRun(Resource):
    def post(self) -> Response:
        """Runs a new container."""

        run_specs: RunContainerRequestDTO = RunContainerRequestDTO.Schema().load(data=request.get_json())
        res = run_container(run_specs)
        return RunContainerResponseDTO.Schema().dump(res), 200


class ContainerStop(Resource):
    def post(self, node_id: str, container_id: str) -> Response:
        """Stops a running container."""

        stop_container(node_id, container_id)
        return "", 200


class ContainerResume(Resource):
    def post(self, node_id: str, container_id: str) -> Response:
        """Resumes a paused container."""

        req: ResumeContainerRequestDTO = ResumeContainerRequestDTO.Schema().load(data=request.get_json())
        resume_container(node_id, container_id, req)
        return "", 200
