import dataclasses
import datetime
import typing as t

import dateparser
from docker.models.containers import Container as DockerContainer

from jukeboxsvc.dto.cluster import (
    ContainerRunSpecs,
    ContainerStats,
)


class Container:
    """Represents an existing container, created through the Node.run_container() interface."""

    created: t.Optional[datetime.datetime]
    id: str
    status: str
    stats: t.Optional[ContainerStats] = None
    specs: ContainerRunSpecs

    def __init__(self, c: DockerContainer) -> None:
        self.id = c.id
        self.status = c.status
        self.created = dateparser.parse(c.attrs["Created"])
        if self.status == "running":
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
                **{f.name: env_vars[f.name] for f in dataclasses.fields(ContainerRunSpecs.EnvVars)}
            ),
            labels=ContainerRunSpecs.Labels(**c.labels),
        )

    def __repr__(self) -> str:
        return repr(
            dict(
                (key, value) for key, value in self.__dict__.items() if not callable(value) and not key.startswith("__")
            )
        )

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
