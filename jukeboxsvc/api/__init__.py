from flask_restful import Api

from jukeboxsvc.api.cluster import (
    ClusterPullImage,
    ClusterState,
)
from jukeboxsvc.api.container import (
    ContainerPause,
    ContainerResume,
    ContainerRun,
    ContainerStop,
)

api = Api()

# setup routing
api.add_resource(ContainerPause, "/nodes/<string:node_id>/containers/<string:container_id>/pause")  # POST
api.add_resource(ContainerRun, "/containers/run")  # POST
api.add_resource(ContainerStop, "/nodes/<string:node_id>/containers/<string:container_id>/stop")  # POST
api.add_resource(ContainerResume, "/nodes/<string:node_id>/containers/<string:container_id>/resume")  # POST
api.add_resource(ClusterState, "/cluster/state")  # GET
api.add_resource(ClusterPullImage, "/cluster/pull_image")  # POST
