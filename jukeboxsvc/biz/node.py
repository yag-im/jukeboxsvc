import dataclasses
import logging
import typing as t

import docker
from docker.errors import (
    APIError,
    NotFound,
)
from docker.models.containers import Container as DockerContainer
from docker.models.images import Image
from docker.types import Mount
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
from jukeboxsvc.dto.cluster import NodeAttrs
from jukeboxsvc.dto.container import DcRegion

STOP_CONTAINER_GRACEFULL_TIMEOUT = 5

log = logging.getLogger("jukeboxsvc")


class Node:
    api_uri: str
    attrs: NodeAttrs
    containers: dict[str, Container]
    id: str
    region: DcRegion
    cpu_usage_total: float = 0
    memory_usage_total: float = 0

    def __init__(self, region: DcRegion, api_uri: str) -> None:
        self.region = region
        self.api_uri = api_uri
        self._update()

    def __repr__(self) -> str:
        return repr(
            dict(
                (key, value) for key, value in self.__dict__.items() if not callable(value) and not key.startswith("__")
            )
        )

    def _get_container(self, container_id: str) -> DockerContainer:
        """Gets container by id from the cluster.

        This function allows us to keep a good balance between performance and complexity of the implementation.
        While maintaining a real-time local cluster state is an option, it is less reliable and potentially more costly
        compared to calling the cluster whenever we require a container instance.
        """
        client = get_cluster_client(self.api_uri)
        try:
            c: DockerContainer = client.containers.get(container_id)
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
        client = get_cluster_client(self.api_uri, timeout=55)
        c = client.containers.run(
            auto_remove=auto_remove,
            cpuset_cpus=",".join(map(str, run_specs.attrs.cpuset_cpus)),
            detach=detach,
            devices=devices,
            device_requests=device_requests,
            environment=dataclasses.asdict(run_specs.env_vars),
            image=run_specs.attrs.image_tag,
            labels=dataclasses.asdict(run_specs.labels),
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
            "node": {"api_uri": self.api_uri, "id": self.id, "region": self.region},
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
        client = get_cluster_client(self.api_uri)
        return client.images.pull(repository, tag)

    def _update(self) -> None:
        """Updates state of the node direclty from the cluster.

        Avoid invoking this function from any methods in this class (except in __init__()), as changes will not be
        applied. The state here is deeply copied from a global CLUSTER.nodes() state and will be discarded upon exit.
        """

        client = get_cluster_client(self.api_uri)
        info = client.info()
        self.id = info["ID"]
        self.containers = {}
        for c in client.containers.list():
            if "jukebox_" in c.name:
                try:
                    self.containers[c.id] = Container(c)
                except JSONDecodeError as e:
                    # this happens quite often due to a delayed sync between local and remote states
                    # (e.g. for non-existing container)
                    log.error("error while getting stats from container %s: %s", c.id, e)
        for c in list(v for v in self.containers.values() if v.status == "running"):
            self.cpu_usage_total += c.stats.cpu_usage_perc  # type: ignore[union-attr]
            self.memory_usage_total += c.stats.memory_usage_perc  # type: ignore[union-attr]

        self.attrs = NodeAttrs(
            igpu=True,  # TODO: fetch from node
            dgpu=False,  # TODO: fetch from node
            cpus=info["NCPU"],
            total_memory=info["MemTotal"],
        )

    def cores_load(self) -> dict[int, float]:
        res = {}
        for c in self.containers.values():
            res[c.specs.attrs.cpuset_cpus[0]] = c.stats.cpu_usage_perc if c.stats else 0
        return res

    def free_cores(self) -> set[int]:
        all_cores = set(range(0, self.attrs.cpus))
        busy_cores = self.cores_load().keys()
        return all_cores - busy_cores
