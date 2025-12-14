import typing as t
from dataclasses import field
from enum import StrEnum

from marshmallow import Schema
from marshmallow_dataclass import dataclass


class DcRegion(StrEnum):
    EU_CENTRAL_1 = "eu-central-1"
    US_EAST_1 = "us-east-1"
    US_WEST_1 = "us-west-1"


class WindowSystem(StrEnum):
    X11 = "x11"
    WAYLAND = "wayland"


class VideoEnc(StrEnum):
    CPU = "cpu"
    GPU_INTEL = "gpu-intel"
    GPU_NVIDIA = "gpu-nvidia"


class AppPlatform(StrEnum):
    DOS = "dos"
    MAC = "mac"
    PHILIPS_CD_I = "philips-cd-i"
    WINDOWS = "win"
    ZX_SPECTRUM = "zxs"


@dataclass
class WsConnDC:
    """Websocket connection (sigsvc) parameters."""

    consumer_id: str  # peer_id of the party awaiting for a stream
    id: str  # unique ws connection id (used as a sticky session cookie value)


@dataclass
class RunContainerRequestDTO:
    @dataclass
    class AppDescr:
        # slug and release_uuid are also parts of an app path in appstor
        slug: str  # igdb slug, e.g. the-pink-panther-hokus-pokus-pink
        release_uuid: str  # unique release id, e.g.: 653cc955-8e32-4fb6-b44c-5d43897e0219
        platform: AppPlatform = field(metadata={"by_value": True})

    @dataclass
    class Requirements:
        @dataclass
        class AppRequirements:
            color_bits: int
            midi: bool
            screen_height: int
            screen_width: int
            loading_duration: t.Optional[int]  # in seconds

        @dataclass
        class ContainerSpecs:
            @dataclass
            class Runner:
                name: str
                ver: str
                window_system: WindowSystem = field(metadata={"by_value": True})

            runner: Runner
            video_enc: VideoEnc = field(metadata={"by_value": True})  # streamd requirement

            def image_name_with_tag(self) -> str:
                res = "{}_{}_{}:{}".format(  # pylint: disable=consider-using-f-string
                    self.runner.window_system,
                    self.video_enc,
                    self.runner.name,
                    self.runner.ver,
                )
                return res

        # TODO: dup of jukebox.core.node.NodeRequirements
        @dataclass
        class HardwareRequirements:
            dgpu: bool  # could be for either app (3D game) or streamd (powerfull codec / highres)
            igpu: bool  # mostly for streamd, but can also be used by some games
            memory: int  # memory required by apps running inside a container (game, runner and streamd)
            memory_shared: t.Optional[int]  # shared memory required by apps (in bytes)
            nanocpus: int  # nanocpus required by apps running inside a container (game, runner and streamd)

        app: AppRequirements
        container: ContainerSpecs
        hw: HardwareRequirements

    app_descr: AppDescr
    # TODO: add DcRegion enum into "preferred_dcs" and validation:
    # https://github.com/lovasoa/marshmallow_dataclass/issues/255
    preferred_dcs: list[str]
    reqs: Requirements
    user_id: int
    ws_conn: WsConnDC
    Schema: t.ClassVar[t.Type[Schema]] = Schema  # pylint: disable=invalid-name


@dataclass
class RunContainerResponseDTO:
    @dataclass
    class NodeDescr:
        id: str
        api_uri: str
        region: DcRegion = field(metadata={"by_value": True})

    @dataclass
    class ContainerDescr:
        id: str

    node: NodeDescr
    container: ContainerDescr
    Schema: t.ClassVar[t.Type[Schema]] = Schema  # pylint: disable=invalid-name


@dataclass
class ResumeContainerRequestDTO:
    ws_conn: WsConnDC
    Schema: t.ClassVar[t.Type[Schema]] = Schema  # pylint: disable=invalid-name
