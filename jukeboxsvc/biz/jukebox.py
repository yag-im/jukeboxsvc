import concurrent.futures
import json
import logging
import os
import random
import shutil
import typing as t
import uuid
from dataclasses import dataclass
from multiprocessing import Process
from pathlib import Path

import docker
from docker.types import Mount
from fabric import Connection
from invoke.exceptions import UnexpectedExit

from jukeboxsvc.biz.cluster import (
    get_node,
    get_nodes,
)
from jukeboxsvc.biz.container import ContainerRunSpecs
from jukeboxsvc.biz.errors import (
    ClusterOutOfResourcesException,
    JukeboxOpException,
    NodeNotFoundException,
)
from jukeboxsvc.biz.misc import log_input_output
from jukeboxsvc.biz.node import Node
from jukeboxsvc.dto.cluster import (
    ClusterUsageResponseDTO,
    PullContainerImageRequestDTO,
)
from jukeboxsvc.dto.container import (
    GPU_MODELS_SORTED_BY_PERFORMANCE,
    GPU_VENDOR_BY_MODEL,
    VIDEO_ENC_BY_GPU_VENDOR,
    DcRegion,
    GpuModel,
    ResumeContainerRequestDTO,
    RunContainerRequestDTO,
    RunContainerResponseDTO,
    VideoEnc,
    WindowSystem,
)

NUM_CORES_PER_CONTAINER = 1

DOSBOX_DOS_LOADING_DURATION = 2
DOSBOX_WIN_LOADING_DURATION = 5
QEMU_LOADING_DURATION = 5
SCUMMVM_LOADING_DURATION = 0
WINE_LOADING_DURATION = 0
RETROARCH_PHILIPS_CD_I_LOADING_DURATION = 12
RETROARCH_ZXS_LOADING_DURATION = 0
RETROARCH_GENESIS_SLASH_MEGA_DRIVE_LOADING_DURATION = 0

log = logging.getLogger("jukeboxsvc")


@dataclass
class NodeRequirements:
    """Requirements for selecting a node."""

    # TODO: add cpu and memory requirements?
    gpu: GpuModel | None


def _get_node(node_id: str) -> Node:
    node: t.Optional[Node] = get_node(node_id)
    if not node:
        raise NodeNotFoundException()
    return node


@log_input_output
def stop_container(node_id: str, container_id: str) -> None:
    _get_node(node_id).stop_container(container_id)


@log_input_output
def pause_container(node_id: str, container_id: str) -> None:
    _get_node(node_id).pause_container(container_id)


@log_input_output
def resume_container(node_id: str, container_id: str, req: ResumeContainerRequestDTO) -> None:
    """TODO: restarting streamd is required cos stream often hangs on a resume() call. Restart works only in X11,
    Wayland requires some work around pipewire (update restart_streamd.sh script for wayland)
    """
    jukebox_container_user = os.environ["JUKEBOX_CONTAINER_USER"]
    jukebox_container_restart_streamd_script_path = f"/home/{jukebox_container_user}/restart_streamd.sh"
    node = _get_node(node_id)
    node.resume_container(container_id)
    cmd = f"{jukebox_container_restart_streamd_script_path} {req.ws_conn.id} {req.ws_conn.consumer_id}"
    node.exec_run_container(container_id, cmd, user=jukebox_container_user)


@log_input_output
def pick_best_node(region: DcRegion, reqs: NodeRequirements) -> t.Optional[Node]:
    """Picks the oldest node in the cluster (by creation date) with matching resources (so newer nodes remain unused and
    are removed on autoscale). Dedicated nodes are preferred as they are oldest nodes in any cluster.

    Args:
        region:
            The preferred region for node selection.
            Caller (appsvc) ensures it's always the DC with the best latency for a given customer
        reqs:
            Set of requirements for a node.

    Returns:
        Best matching node or None if we're out of resources in selected region :(.
        Hopefully new nodes will be added soon by autoscaler.
    """

    nodes = get_nodes(region=region, init_containers_from_sessions=True)
    sorted_nodes = sorted(
        nodes,
        key=lambda n: n.created_ts,
    )
    for node in sorted_nodes:
        if not node.free_cores():
            continue
        if reqs.gpu is not None:
            min_perf = GPU_MODELS_SORTED_BY_PERFORMANCE.index(reqs.gpu)
            if not any(
                gpu in GPU_MODELS_SORTED_BY_PERFORMANCE and GPU_MODELS_SORTED_BY_PERFORMANCE.index(gpu) >= min_perf
                for gpu in node.hw_specs.gpus
            ):
                continue
        return node
    return None


def _get_clone_subpath(run_specs: RunContainerRequestDTO) -> str:
    return f"{run_specs.user_id}/{run_specs.app_descr.slug}/{run_specs.app_descr.get_app_path_release_uuid()}"


@log_input_output
def clone_app(run_specs: RunContainerRequestDTO, region: str) -> None:
    """Creates an app clone (when needed) in a given DC region.
    Changed parts (game saves) should be synced asynchronously later (TODO?)

    Server-side NFS copy is slow for folders:
    https://lore.kernel.org/linux-nfs/CAAboi9s9=h-ULoTJ4kcTi3S297RWou0JfBz5nTQP90pVpA37bA@mail.gmail.com/

    Therefore using a "true" server-side copy (through the ssh tunnel).
    """
    appstor_nodes = json.loads(os.environ.get("APPSTOR_NODES", "[]"))
    if not appstor_nodes:
        # pure local host setup (for local dev mode only)
        src_path: Path = (
            Path(os.environ["DATA_DIR"])
            / "apps"
            / run_specs.app_descr.slug
            / run_specs.app_descr.get_app_path_release_uuid()
        )
        dst_path: Path = (
            Path(os.environ["DATA_DIR"])
            / "clones"
            / str(run_specs.user_id)
            / run_specs.app_descr.slug
            / run_specs.app_descr.get_app_path_release_uuid()
        )
        if not dst_path.exists():
            shutil.copytree(src_path, dst_path, symlinks=True)
        return
    appstor_user = os.environ["APPSTOR_USER"]
    appstor_instance = next(filter(lambda i: i["region"] == region, appstor_nodes), None)
    if not appstor_instance:
        raise JukeboxOpException(message=f"no appstor instancees in specified region: {region}")
    cmd = f"/opt/yag/appstor/clone_app.sh {run_specs.user_id} {run_specs.app_descr.slug} \
        {run_specs.app_descr.get_app_path_release_uuid()}"
    try:
        with Connection(
            host=appstor_instance["host"],
            user=appstor_user,
            port=appstor_instance["ssh_port"],
            connect_kwargs={"key_filename": "/opt/yag/jukeboxsvc/.ssh/id_ed25519"},
        ) as conn:
            clone_res = conn.run(
                cmd,
                hide=True,
            )
        log.info("clone_app result: %s", clone_res)
    except UnexpectedExit as e:
        raise JukeboxOpException(
            message=f"command: {e.result.command}, return_code: {e.result.return_code}, \
                                 stdout: {e.result.stdout}, stderr: {e.result.stderr}"
        ) from e


def _show_pointer(runner_name: str) -> bool:
    if runner_name == "wine":
        return True
    return False


def get_runner_loading_duration(run_specs: RunContainerRequestDTO) -> int:
    runner_name = run_specs.reqs.container.runner.name
    platform = run_specs.app_descr.platform
    if runner_name == "scummvm":
        return SCUMMVM_LOADING_DURATION
    elif runner_name == "wine":
        return WINE_LOADING_DURATION
    elif runner_name == "qemu":
        return QEMU_LOADING_DURATION
    elif runner_name == "dosbox" or runner_name == "dosbox-staging" or runner_name == "dosbox-x":
        if platform == "dos":
            return DOSBOX_DOS_LOADING_DURATION
        elif platform == "win":
            return DOSBOX_WIN_LOADING_DURATION
    elif runner_name == "retroarch":
        if platform == "philips-cd-i":
            return RETROARCH_PHILIPS_CD_I_LOADING_DURATION
        elif platform == "zxs":
            return RETROARCH_ZXS_LOADING_DURATION
        elif platform == "genesis-slash-megadrive":
            return RETROARCH_GENESIS_SLASH_MEGA_DRIVE_LOADING_DURATION
    return int(os.getenv("JUKEBOX_CONTAINER_STREAMD_LOADING_DURATION", "5"))


@log_input_output
def run_container(run_specs: RunContainerRequestDTO) -> RunContainerResponseDTO:
    """Spins up a new container in the cluster.

    Returns:
        Running container id.
    Raises:
        NodeNotFoundException: when node not found
        ContainerRunFailedException: when container run failed
    """
    fps = int(os.environ["FPS"])
    signaler_auth_token = os.environ["SIGNALER_AUTH_TOKEN"]
    signaler_host = os.environ["SIGNALER_HOST"]
    signaler_uri = os.environ["SIGNALER_URI"]
    stun_uri = os.environ["STUN_URI"]
    jukebox_container_app_path = os.environ["JUKEBOX_CONTAINER_APP_DIR"]
    jukebox_container_env_gst_debug = os.getenv("JUKEBOX_CONTAINER_ENV_GST_DEBUG")
    jukebox_container_streamd_loading_duration = get_runner_loading_duration(run_specs) + (
        run_specs.reqs.app.loading_duration or 0
    )
    jukebox_contaienr_streamd_max_inactivity_duration = int(
        os.getenv("JUKEBOX_CONTAINER_STREAMD_MAX_INACTIVITY_DURATION", "600")
    )
    jukebox_docker_repo_prefix = os.environ["JUKEBOX_DOCKER_REPO_PREFIX"]  # e.g. ghcr.io/yag-im/jukebox

    def _gen_container_name(run_specs: RunContainerRequestDTO) -> str:
        rnd = str(uuid.uuid4())[:8]
        return f"jukebox_{run_specs.user_id}_{run_specs.app_descr.slug}_{rnd}"

    node = pick_best_node(
        region=run_specs.preferred_dcs[0],
        reqs=NodeRequirements(gpu=run_specs.reqs.hw.gpu),
    )
    if not node:
        raise ClusterOutOfResourcesException()
    # choosing a random free core to reduce races
    # running docker container without a cpu affinity significantly degrades performance even of a single running app
    # TODO: investigate why using more than 1 core slows down the app;
    # e.g. in Syberia 1, sound becomes choppy when using more than 1 core.
    free_cores = node.free_cores()
    # reserve core 0 for admin access in US_WEST_1 region
    if os.getenv("RESERVE_ADMIN_CPU_CORE", "0") == "1":
        if node.region == DcRegion.US_WEST_1 and run_specs.user_id != 0:
            if 0 in free_cores:
                free_cores.remove(0)
    cpu_cores = random.sample(list(free_cores), k=NUM_CORES_PER_CONTAINER)  # nosec B311
    cap_add = []
    devices = [
        "/dev/snd/seq:/dev/snd/seq:rwm",
    ]
    device_requests = None
    # TODO: gpu devices should be in sync with gpu requirements, and e.g. WLR_RENDER_DRM_DEVICE
    gpu_card_id = os.getenv("GPU_CARD_ID", "0")
    gpu_render_device_id = os.getenv("GPU_RENDER_DEVICE_ID", "128")
    video_enc = VIDEO_ENC_BY_GPU_VENDOR.get(GPU_VENDOR_BY_MODEL[node.hw_specs.gpus[0]], VideoEnc.CPU)  # TODO: gpus[0]?
    if video_enc == VideoEnc.GPU_INTEL:
        devices.append(f"/dev/dri/card{gpu_card_id}:/dev/dri/card{gpu_card_id}:rwm")
        devices.append(f"/dev/dri/renderD{gpu_render_device_id}:/dev/dri/renderD{gpu_render_device_id}:rwm")
    elif video_enc == VideoEnc.GPU_NVIDIA:
        device_requests = [docker.types.DeviceRequest(count=-1, capabilities=[["gpu"]])]

    if run_specs.reqs.container.runner.name == "qemu":
        devices.append("/dev/kvm:/dev/kvm")
        cap_add.append("SYS_ADMIN")

    if run_specs.reqs.container.runner.window_system == WindowSystem.X11:
        # TODO: can't use a simpler formula (e.g. 10+len(node.containers)) cos it may end up with duplicate displays
        # as our local state is not in sync with a real cluster state
        # :10, :11 etc, they shouldn't intersect!
        env_display = f":{random.randint(100, 50000)}"  # nosec B311
        env_show_pointer = _show_pointer(run_specs.reqs.container.runner.name)
    else:
        env_display = None
        env_show_pointer = None

    clone_app(run_specs, region=node.region)

    image_name_with_tag = run_specs.reqs.container.image_name_with_tag(video_enc)
    docker_image_tag = f"{jukebox_docker_repo_prefix}/{image_name_with_tag}"
    env_vars = {
        "DISPLAY": env_display,
        "SHOW_POINTER": env_show_pointer,
        "COLOR_BITS": run_specs.reqs.app.color_bits,
        "FPS": fps,
        "LOADING_DURATION": jukebox_container_streamd_loading_duration,
        "MAX_INACTIVITY_DURATION": jukebox_contaienr_streamd_max_inactivity_duration,
        "RUN_MIDI_SYNTH": "true" if run_specs.reqs.app.midi else "false",
        "SCREEN_HEIGHT": run_specs.reqs.app.screen_height,
        "SCREEN_WIDTH": run_specs.reqs.app.screen_width,
        "SIGNALER_AUTH_TOKEN": signaler_auth_token,
        "SIGNALER_HOST": signaler_host,
        "SIGNALER_URI": signaler_uri,
        "STUN_URI": stun_uri,
        "WS_CONN_ID": run_specs.ws_conn.id,
        "WS_CONSUMER_ID": run_specs.ws_conn.consumer_id,
        "GST_DEBUG": jukebox_container_env_gst_debug,
    }
    privileged = False
    if video_enc == VideoEnc.GPU_NVIDIA:
        env_vars["NVIDIA_DRIVER_CAPABILITIES"] = "all"
        # TODO: investigate if we can run nvidia-container-runtime without privileged mode,
        # it was possible in Debian 11, but not in 12
        privileged = True
    run_container_res = node.run_container(
        run_specs=ContainerRunSpecs(
            attrs=ContainerRunSpecs.Attrs(
                cpuset_cpus=cpu_cores,
                image_tag=docker_image_tag,
                memory_limit=run_specs.reqs.hw.memory,
                memory_shared=run_specs.reqs.hw.memory_shared,
                name=_gen_container_name(run_specs),
                nanocpus_limit=run_specs.reqs.hw.nanocpus,
            ),
            env_vars=ContainerRunSpecs.EnvVars(**env_vars),  # type: ignore[arg-type]
            labels=ContainerRunSpecs.Labels(
                app_slug=str(run_specs.app_descr.slug),
                app_release_uuid=str(run_specs.app_descr.release_uuid),
                user_id=str(run_specs.user_id),
            ),
        ),
        devices=devices,
        device_requests=device_requests,
        mounts=[
            Mount(
                type="volume",
                target=jukebox_container_app_path,
                source="appstor-vol",
                subpath=str(_get_clone_subpath(run_specs)),
                read_only=False,
            )
        ],
        privileged=privileged,
        cap_add=cap_add,
    )
    return RunContainerResponseDTO.model_validate(run_container_res)


def cluster_status() -> ClusterUsageResponseDTO:
    """Returns cluster usage per region as a ratio of used cores to total cores."""
    nodes = get_nodes(init_containers_from_sessions=True)
    region_cpus: dict[str, int] = {}
    region_used: dict[str, int] = {}
    for node in nodes:
        region_cpus[node.region.value] = region_cpus.get(node.region.value, 0) + node.hw_specs.cpus
        region_used[node.region.value] = region_used.get(node.region.value, 0) + len(node.containers)
    regions = [
        ClusterUsageResponseDTO.RegionUsage(
            region=region,
            usage=region_used.get(region, 0) / cpus if cpus > 0 else 0.0,
        )
        for region, cpus in region_cpus.items()
    ]
    return ClusterUsageResponseDTO(regions=regions)


def _pull_image_proc(image: PullContainerImageRequestDTO) -> None:
    pull_image_max_workers = 20
    avail_nodes = get_nodes()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=pull_image_max_workers) as executor:
            images = list(
                executor.map(
                    lambda n: n.pull_image(image.repository, image.tag),
                    avail_nodes,
                )
            )
            if len(images) != len(avail_nodes):
                log.error("image pull error, expected %d images, got: %d images.", len(avail_nodes), len(images))
    except Exception as e:  # pylint: disable=broad-exception-caught
        log.error(e, exc_info=True)
    else:
        log.info("successfully pulled image: %s on all available nodes", image)


@log_input_output
def pull_image(image: PullContainerImageRequestDTO) -> None:
    """Pull specified image onto the every available node in the cluster.

    Runs in a separate process so the web server can terminate request. TODO: move to asyncjobs?
    """
    p = Process(target=_pull_image_proc, args=(image,))
    p.daemon = True
    p.start()
