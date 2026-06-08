import typing as t
from datetime import datetime

from pydantic import BaseModel

from jukeboxsvc.biz.container import (  # noqa: F401
    Container,
    ContainerRunSpecs,
    ContainerStats,
)
from jukeboxsvc.biz.node import Node


class ClusterUsageResponseDTO(BaseModel):
    class RegionUsage(BaseModel):
        region: str
        usage: float

    regions: list[RegionUsage]


class ContainerDTO(BaseModel):
    id: str
    status: str
    specs: ContainerRunSpecs
    created: t.Optional[datetime] = None
    stats: t.Optional[ContainerStats] = None

    @classmethod
    def from_container(cls, c: Container) -> "ContainerDTO":
        return cls(
            id=c.id,
            status=c.status,
            specs=c.specs,
            created=getattr(c, "created", None),
            stats=getattr(c, "stats", None),
        )


class NodeDTO(BaseModel):
    id: str
    region: str
    flavor: str
    hw_specs: Node.NodeHwSpecs
    created_ts: datetime
    cpu_usage_total: float
    memory_usage_total: float
    containers: list[ContainerDTO]

    @classmethod
    def from_node(cls, n: Node) -> "NodeDTO":
        return cls(
            id=n.id,
            region=str(n.region),
            flavor=str(n.flavor),
            hw_specs=n.hw_specs,
            created_ts=n.created_ts,
            cpu_usage_total=n.cpu_usage_total,
            memory_usage_total=n.memory_usage_total,
            containers=[ContainerDTO.from_container(c) for c in n.containers.values()],
        )


class ClusterStateResponseDTO(BaseModel):
    nodes: list[NodeDTO]


class PullContainerImageRequestDTO(BaseModel):
    repository: str
    tag: str
