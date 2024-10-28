import concurrent.futures
import copy
import json
import logging
import os
import threading
from dataclasses import dataclass

# from jukeboxsvc.biz.misc import log_input_output
from jukeboxsvc.biz.node import Node

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


JUKEBOX_CLUSTER = Cluster(JUKEBOX_NODES)
