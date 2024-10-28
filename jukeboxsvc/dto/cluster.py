import datetime
import typing as t

from marshmallow import Schema
from marshmallow_dataclass import dataclass


@dataclass
class NodeAttrs:
    """Node attributes (from client.info())."""

    igpu: bool  # is integrated GPU present
    dgpu: bool  # is dedicated GPU present
    cpus: int  # number of logical cores
    total_memory: int  # total memory in bytes


@dataclass
class ContainerRunSpecs:
    @dataclass
    class Attrs:
        cpuset_cpus: list[int]
        image_tag: str
        memory_limit: int  # memory required by app (in bytes, includes runners' reqs)
        memory_shared: t.Optional[int]  # shared memory required (if any)
        name: str
        nanocpus_limit: int  # nanocpus required by app (includes runners' reqs)

    @dataclass
    class EnvVars:
        # pylint: disable=invalid-name
        COLOR_BITS: int
        FPS: int
        MAX_INACTIVITY_PERIOD: int
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

    @dataclass
    class Labels:
        app_release_uuid: str
        app_slug: str
        user_id: str

    attrs: Attrs
    env_vars: EnvVars
    labels: Labels


@dataclass
class ContainerStats:
    cpu_throttling_data: dict[str, int]
    cpu_usage_perc: float
    memory_usage_perc: float


@dataclass
class ClusterStateResponseDTO:
    @dataclass
    class Node:
        @dataclass
        class Container:
            created: datetime.datetime
            id: str
            specs: t.Optional[ContainerRunSpecs]  # e.g. not avail for a paused container
            stats: ContainerStats
            status: str

        attrs: NodeAttrs
        api_uri: str
        containers: dict[str, Container]
        id: str
        region: str

    nodes: dict[str, Node]
    Schema: t.ClassVar[t.Type[Schema]] = Schema  # pylint: disable=invalid-name


@dataclass
class PullContainerImageRequestDTO:
    repository: str
    tag: str
    Schema: t.ClassVar[t.Type[Schema]] = Schema  # pylint: disable=invalid-name
