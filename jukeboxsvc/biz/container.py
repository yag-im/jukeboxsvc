import datetime
import typing as t

import dateparser
from docker.models.containers import Container as DockerContainer
from pydantic import (
    BaseModel,
    ConfigDict,
)

from jukeboxsvc.services.dto.sessionsvc import SessionDC


class ContainerRunSpecs(BaseModel):
    class Attrs(BaseModel):
        cpuset_cpus: list[int]
        image_tag: str
        memory_limit: int  # memory required by app (in bytes, includes runners' reqs)
        memory_shared: t.Optional[int] = None  # shared memory required (if any)
        name: str
        nanocpus_limit: int  # nanocpus required by app (includes runners' reqs)

    class EnvVars(BaseModel):
        # pylint: disable=invalid-name
        COLOR_BITS: int
        FPS: int
        LOADING_DURATION: int
        MAX_INACTIVITY_DURATION: int
        RUN_MIDI_SYNTH: str
        SIGNALER_AUTH_TOKEN: str
        SIGNALER_HOST: str
        SIGNALER_URI: str
        SCREEN_HEIGHT: int
        SCREEN_WIDTH: int
        STUN_URI: str
        WS_CONN_ID: str
        WS_CONSUMER_ID: str
        # optional vars
        GST_DEBUG: t.Optional[str] = None
        # x11-specific vars
        DISPLAY: t.Optional[str] = None
        SHOW_POINTER: t.Optional[bool] = None
        NVIDIA_DRIVER_CAPABILITIES: t.Optional[str] = None

    class Labels(BaseModel):
        model_config = ConfigDict(extra="ignore")

        app_release_uuid: str
        app_slug: str
        user_id: str

    attrs: Attrs
    env_vars: EnvVars
    labels: Labels


class ContainerStats(BaseModel):
    cpu_throttling_data: dict[str, int]
    cpu_usage_perc: float
    memory_usage_perc: float


class Container:
    """Represents an existing container, created through the Node.run_container() interface."""

    created: t.Optional[datetime.datetime]
    id: str
    status: str
    stats: t.Optional[ContainerStats] = None
    specs: ContainerRunSpecs

    def __init__(self, c: DockerContainer, collect_stats: bool = False) -> None:
        self.id = c.id
        self.status = c.status
        self.created = dateparser.parse(c.attrs["Created"])
        if collect_stats and self.status == "running":
            stats = c.stats(stream=False)
            self.stats = ContainerStats(
                cpu_throttling_data=stats["cpu_stats"]["throttling_data"],
                cpu_usage_perc=self._calc_cpu_usage(stats),
                memory_usage_perc=self._calc_memory_usage(stats),
            )
        env_vars = {}
        for kv in [var.split("=", 1) for var in c.attrs["Config"]["Env"]]:
            if len(kv) == 2:
                env_vars[kv[0]] = kv[1]
            else:
                env_vars[kv[0]] = None
        cpuset_cpus = c.attrs["HostConfig"]["CpusetCpus"]
        if cpuset_cpus:
            cpuset_cpus = [int(x) for x in cpuset_cpus.split(",")]
        self.specs = ContainerRunSpecs(
            attrs=ContainerRunSpecs.Attrs(
                cpuset_cpus=cpuset_cpus,
                image_tag=c.image.attrs["RepoTags"][0],
                name=c.name,
                nanocpus_limit=c.attrs["HostConfig"]["NanoCpus"],
                memory_limit=c.attrs["HostConfig"]["Memory"],
                memory_shared=c.attrs["HostConfig"]["ShmSize"],
            ),
            env_vars=ContainerRunSpecs.EnvVars(
                **{name: env_vars.get(name, None) for name in ContainerRunSpecs.EnvVars.model_fields}
            ),
            labels=ContainerRunSpecs.Labels(**c.labels),
        )

    def __repr__(self) -> str:
        return repr(
            dict(
                (key, value) for key, value in self.__dict__.items() if not callable(value) and not key.startswith("__")
            )
        )

    @classmethod
    def from_sessiondc(cls, session_dc: "SessionDC") -> "Container":
        """Create a Container from a SessionDC instance."""
        obj = object.__new__(cls)
        container = session_dc.container
        if container is None:
            raise ValueError("SessionDC has no container")
        obj.id = container.id
        obj.status = str(session_dc.status) if session_dc.status else ""
        obj.created = None
        obj.stats = None
        obj.specs = ContainerRunSpecs(
            attrs=ContainerRunSpecs.Attrs(
                cpuset_cpus=container.cpuset_cpus,
                image_tag="",
                name="",
                nanocpus_limit=0,
                memory_limit=0,
                memory_shared=None,
            ),
            env_vars=ContainerRunSpecs.EnvVars(
                **t.cast(dict[str, t.Any], {name: None for name in ContainerRunSpecs.EnvVars.model_fields})
            ),
            labels=ContainerRunSpecs.Labels(
                app_release_uuid=session_dc.app_release_uuid,
                app_slug="",
                user_id=str(session_dc.user_id),
            ),
        )
        return obj

    def _calc_cpu_usage(self, stats: dict) -> float:
        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        system_cpu_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
        number_cpus = stats["cpu_stats"]["online_cpus"]
        return (cpu_delta / system_cpu_delta) * number_cpus * 100.0

    def _calc_memory_usage(self, stats: dict) -> float:
        # TODO: this is within a container memory limit which we assume is not defined and therefore is equal to the
        # system memory
        used_memory = stats["memory_stats"]["usage"]
        available_memory = stats["memory_stats"]["limit"]
        return (used_memory / available_memory) * 100.0
