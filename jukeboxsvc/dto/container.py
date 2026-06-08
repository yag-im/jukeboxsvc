from enum import StrEnum

from pydantic import BaseModel


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
    SEGA_GENESIS = "genesis-slash-megadrive"
    WINDOWS = "win"
    ZX_SPECTRUM = "zxs"


class GpuModel(StrEnum):
    INTEL_UHD_P630 = "intel-uhd-p630"  # RISE-3
    INTEL_UHD_750 = "intel-uhd-750"  # PC-CUSTOM-1
    NVIDIA_GTX_1060 = "nvidia-gtx-1060"  # PC-CUSTOM-1
    NVIDIA_TESLA_V100S = "nvidia-tesla-v100s"  # OVH t2-*
    NVIDIA_L4 = "nvidia-l4"  # OVH l4-*


class GpuVendor(StrEnum):
    INTEL = "intel"
    NVIDIA = "nvidia"


GPU_VENDOR_BY_MODEL: dict[GpuModel, GpuVendor] = {
    GpuModel.INTEL_UHD_P630: GpuVendor.INTEL,
    GpuModel.INTEL_UHD_750: GpuVendor.INTEL,
    GpuModel.NVIDIA_GTX_1060: GpuVendor.NVIDIA,
    GpuModel.NVIDIA_TESLA_V100S: GpuVendor.NVIDIA,
    GpuModel.NVIDIA_L4: GpuVendor.NVIDIA,
}

VIDEO_ENC_BY_GPU_VENDOR: dict[GpuVendor, VideoEnc] = {
    GpuVendor.INTEL: VideoEnc.GPU_INTEL,
    GpuVendor.NVIDIA: VideoEnc.GPU_NVIDIA,
}

GPU_MODELS_SORTED_BY_PERFORMANCE = [
    GpuModel.INTEL_UHD_P630,
    GpuModel.INTEL_UHD_750,
    GpuModel.NVIDIA_GTX_1060,
    GpuModel.NVIDIA_TESLA_V100S,
    GpuModel.NVIDIA_L4,
]


class WsConnDC(BaseModel):
    """Websocket connection (sigsvc) parameters."""

    consumer_id: str  # peer_id of the party awaiting for a stream
    id: str  # unique ws connection id (used as a sticky session cookie value)


class RunContainerRequestDTO(BaseModel):
    class AppDescr(BaseModel):
        # slug and release_uuid are also parts of an app path in appstor
        slug: str  # igdb slug, e.g. the-pink-panther-hokus-pokus-pink
        release_uuid: str  # unique release id, e.g.: 019c887a-f4e2-7dcc-a793-678c0e0b9f6e
        release_uuidv4: str | None  # legacy release uuid; part of app path in appstor for older releases
        platform: AppPlatform

        def get_app_path_release_uuid(self) -> str:
            return self.release_uuidv4 or self.release_uuid

    class Requirements(BaseModel):
        class AppRequirements(BaseModel):
            color_bits: int
            midi: bool
            screen_height: int
            screen_width: int
            loading_duration: int | None = None  # in seconds

        class ContainerSpecs(BaseModel):
            class Runner(BaseModel):
                name: str
                ver: str
                window_system: WindowSystem

            runner: Runner

            def image_name_with_tag(self, video_enc: VideoEnc) -> str:
                res = "{}_{}_{}:{}".format(  # pylint: disable=consider-using-f-string
                    self.runner.window_system,
                    video_enc,
                    self.runner.name,
                    self.runner.ver,
                )
                return res

        # TODO: dup of jukebox.core.node.NodeRequirements
        class HardwareRequirements(BaseModel):
            gpu: GpuModel | None  # could be for either app (3D game) or streamd (powerful codec / highres)
            memory: int  # memory required by apps running inside a container (game, runner and streamd)
            memory_shared: int | None = None  # shared memory required by apps (in bytes)
            nanocpus: int  # nanocpus required by apps running inside a container (game, runner and streamd)

        app: AppRequirements
        container: ContainerSpecs
        hw: HardwareRequirements

    app_descr: AppDescr
    preferred_dcs: list[DcRegion]
    reqs: Requirements
    user_id: int
    ws_conn: WsConnDC


class RunContainerResponseDTO(BaseModel):
    class NodeDescr(BaseModel):
        id: str
        api_uri: str
        region: DcRegion

    class ContainerDescr(BaseModel):
        id: str
        cpuset_cpus: list[int]

    node: NodeDescr
    container: ContainerDescr


class ResumeContainerRequestDTO(BaseModel):
    ws_conn: WsConnDC
