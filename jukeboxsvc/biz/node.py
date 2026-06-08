import logging
import os
import typing as t
from datetime import datetime

import docker
from docker.errors import (
    APIError,
    NotFound,
)
from docker.models.containers import Container as DockerContainer
from docker.models.images import Image
from docker.types import Mount
from pydantic import BaseModel
from requests import JSONDecodeError

from jukeboxsvc.biz.container import (
    Container,
    ContainerRunSpecs,
)
from jukeboxsvc.biz.errors import ContainerNotFoundException
from jukeboxsvc.biz.misc import (
    get_cluster_client,
    log_input_output,
)
from jukeboxsvc.biz.models import JukeboxNodeDAO
from jukeboxsvc.biz.ovh_defs import (
    CPUS_BY_FLAVOR,
    GPUS_BY_FLAVOR,
    MEMORY_BY_FLAVOR,
    GpuModel,
    OvhNodeFlavor,
    OvhNodeType,
)
from jukeboxsvc.dto.container import DcRegion

STOP_CONTAINER_GRACEFULL_TIMEOUT = 5

log = logging.getLogger("jukeboxsvc")


class Node:
    class NodeHwSpecs(BaseModel):
        """Node hardware specs"""

        gpus: list[GpuModel]
        cpus: int  # number of logical cores
        total_memory: int  # total memory in bytes

    id: str  # OVH UUID
    docker_api_uri: str
    hw_specs: NodeHwSpecs
    containers: dict[str, Container]
    flavor: OvhNodeFlavor
    region: DcRegion
    created_ts: datetime

    cpu_usage_total: float = 0
    memory_usage_total: float = 0
    _collect_stats: bool = False

    def __init__(
        self,
        region: DcRegion,
        docker_api_uri: str,
        flavor: OvhNodeFlavor,
        node_id: str,
        created_ts: datetime,
        do_update: bool = False,
    ) -> None:
        self.region = region
        self.docker_api_uri = docker_api_uri
        self.flavor = flavor
        self.id = node_id
        self.created_ts = created_ts
        self.hw_specs = Node.NodeHwSpecs(
            gpus=GPUS_BY_FLAVOR.get(OvhNodeFlavor(self.flavor), []),
            cpus=CPUS_BY_FLAVOR[OvhNodeFlavor(self.flavor)],
            total_memory=MEMORY_BY_FLAVOR[OvhNodeFlavor(self.flavor)],
        )
        self._client = get_cluster_client(self.docker_api_uri, timeout=55)
        if do_update:
            self._update()

    @classmethod
    def from_jukebox_node_dao(cls, dao: JukeboxNodeDAO, do_update: bool = False) -> "Node":
        docker_api_port = int(os.environ.get("DOCKER_API_PORT", "2375"))
        flavor = OvhNodeFlavor(dao.flavor.upper() if dao.node_type == OvhNodeType.DEDICATED.value else dao.flavor)
        node = cls(
            region=DcRegion(dao.region),
            docker_api_uri=f"http://{dao.private_ip}:{docker_api_port}",
            flavor=flavor,
            node_id=dao.uuid,
            created_ts=dao.created_ts,
        )
        if do_update:
            node._update()
        return node

    def __repr__(self) -> str:
        container_ids = list(self.containers.keys()) if hasattr(self, "containers") else []
        return (
            f"Node(docker_api_uri={getattr(self, 'docker_api_uri', None)}, region={self.region}, "
            f"containers={len(container_ids)}, container_ids={container_ids}, "
            f"hw_specs={getattr(self, 'hw_specs', None)})"
        )

    def _get_container(self, container_id: str) -> DockerContainer:
        """Gets container by id from the cluster.

        This function allows us to keep a good balance between performance and complexity of the implementation.
        While maintaining a real-time local cluster state is an option, it is less reliable and potentially more costly
        compared to calling the cluster whenever we require a container instance.
        """
        try:
            c: DockerContainer = self._client.containers.get(container_id)
        except NotFound as ex:
            raise ContainerNotFoundException() from ex
        return c

    @log_input_output
    def run_container(
        self,
        run_specs: ContainerRunSpecs,
        auto_remove: bool = True,
        detach: bool = True,
        devices: t.Optional[list[str]] = None,
        device_requests: t.Optional[list[docker.types.DeviceRequest]] = None,
        mounts: t.Optional[list[Mount]] = None,
        network_mode: str = "host",  # cos webrtc requires a lot of UDP ports
        privileged: bool = False,
        cap_add: t.Optional[list[str]] = None,
    ) -> dict[str, t.Any]:
        c = self._client.containers.run(
            auto_remove=auto_remove,
            cpuset_cpus=",".join(map(str, run_specs.attrs.cpuset_cpus)),
            detach=detach,
            devices=devices,
            device_requests=device_requests,
            environment=run_specs.env_vars.model_dump(),
            image=run_specs.attrs.image_tag,
            labels=run_specs.labels.model_dump(),
            mem_limit=run_specs.attrs.memory_limit,
            nano_cpus=run_specs.attrs.nanocpus_limit,
            name=run_specs.attrs.name,
            network_mode=network_mode,
            privileged=privileged,
            remove=auto_remove,  # TODO: double?
            shm_size=run_specs.attrs.memory_shared,
            mounts=mounts,
            cap_add=cap_add,
        )

        return {
            "node": {"api_uri": self.docker_api_uri, "id": self.id, "region": self.region},
            "container": {"id": c.id, "cpuset_cpus": run_specs.attrs.cpuset_cpus},
        }

    def stop_container(self, container_id: str) -> None:
        try:
            self._get_container(container_id).stop(timeout=STOP_CONTAINER_GRACEFULL_TIMEOUT)
        except ContainerNotFoundException:  # this one comes from _get_container()
            log.warning("container %s was already stopped", container_id)
        except APIError as e:  # this one comes from stop()
            if e.status_code == 404:
                log.warning("container %s was already stopped", container_id)
            else:
                raise e

    def pause_container(self, container_id: str) -> None:
        try:
            self._get_container(container_id).pause()
        except APIError as e:
            if e.response.status_code == 409:  # conflict (already paused)
                log.warning(e.explanation)
            else:
                raise e

    def resume_container(self, container_id: str) -> None:
        self._get_container(container_id).unpause()

    @log_input_output
    def exec_run_container(self, container_id: str, cmd: str, user: str, detach: bool = True) -> None:
        self._get_container(container_id).exec_run(cmd=cmd, user=user, detach=detach)

    def pull_image(self, repository: str, tag: str) -> Image:
        client = get_cluster_client(self.docker_api_uri)
        return client.images.pull(repository, tag)

    def _update(self) -> None:
        """Updates state of the node direclty from the cluster."""

        client = get_cluster_client(self.docker_api_uri)

        self.containers = {}
        for c in client.containers.list():
            if "jukebox_" in c.name:
                try:
                    self.containers[c.id] = Container(c, collect_stats=self._collect_stats)
                except JSONDecodeError as e:
                    # this happens quite often due to a delayed sync between local and remote states
                    # (e.g. for non-existing container)
                    log.error("error while getting stats from container %s: %s", c.id, e)
        if self._collect_stats:
            for c in list(v for v in self.containers.values() if v.status == "running"):
                self.cpu_usage_total += c.stats.cpu_usage_perc  # type: ignore[union-attr]
                self.memory_usage_total += c.stats.memory_usage_perc  # type: ignore[union-attr]

        # info = client.info()
        # self.id = info["ID"]
        # self.hw_specs = Node.NodeHwSpecs(
        #     gpus=GPUS_BY_FLAVOR.get(OvhNodeFlavor(self.flavor), []), # TODO: get from physical node
        #     cpus=info["NCPU"],
        #     total_memory=info["MemTotal"],
        # )

    def cores_load(self) -> dict[int, float]:
        res = {}
        for c in self.containers.values():
            res[c.specs.attrs.cpuset_cpus[0]] = c.stats.cpu_usage_perc if c.stats else 0
        return res

    def busy_cores(self) -> set[int]:
        busy_cores: set[int] = set()
        for c in self.containers.values():
            busy_cores.update(c.specs.attrs.cpuset_cpus)
        return busy_cores

    def free_cores(self) -> set[int]:
        all_cores = set(range(0, self.hw_specs.cpus))
        busy_cores = self.busy_cores()
        return all_cores - busy_cores
