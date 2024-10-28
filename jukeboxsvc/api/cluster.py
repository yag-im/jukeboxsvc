from flask import (
    Response,
    request,
)
from flask_restful import Resource

from jukeboxsvc.biz.jukebox import (
    cluster_state,
    pull_image,
)
from jukeboxsvc.dto.cluster import (
    ClusterStateResponseDTO,
    PullContainerImageRequestDTO,
)


class ClusterState(Resource):
    def get(self) -> Response:
        """Returns clusters' current state."""
        res: dict = ClusterStateResponseDTO.Schema().dump(cluster_state())
        return res, 200


class ClusterPullImage(Resource):
    def post(self) -> Response:
        """Pulls specified image onto all available cluster nodes (asynchronously)."""

        image: PullContainerImageRequestDTO = PullContainerImageRequestDTO.Schema().load(data=request.get_json())
        pull_image(image)
        return "", 200
