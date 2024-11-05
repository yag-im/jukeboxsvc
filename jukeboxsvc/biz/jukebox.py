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

import rdrand
from docker.types import Mount
from fabric import Connection
from invoke.exceptions import UnexpectedExit

from jukeboxsvc.biz.cluster import (
    JUKEBOX_CLUSTER,
    Cluster,
)
from jukeboxsvc.biz.container import ContainerRunSpecs
from jukeboxsvc.biz.errors import (
    ClusterOutOfResourcesException,
    JukeboxOpException,
    NodeNotFoundException,
)
from jukeboxsvc.biz.misc import log_input_output
from jukeboxsvc.biz.node import Node
from jukeboxsvc.dto.cluster import PullContainerImageRequestDTO
from jukeboxsvc.dto.container import (
    DcRegion,
    ResumeContainerRequestDTO,
    RunContainerRequestDTO,
    RunContainerResponseDTO,
    VideoEnc,
    WindowSystem,
)

log = logging.getLogger("jukeboxsvc")


@dataclass
class NodeRequirements:
    """Requirements for selecting a node."""

    # TODO: add cpu and memory requirements?
    dgpu: bool
    igpu: bool


def _get_node(node_id: str) -> Node:
    node: t.Optional[Node] = JUKEBOX_CLUSTER.nodes.get(node_id, None)
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
def pick_best_node(nodes: list[Node], regions: list[DcRegion], reqs: NodeRequirements) -> t.Optional[Node]:
    """Picks a node with lower resources usage as per requirements.

    The selected node should surpass the other nodes in meeting the provided requirements. Note that region and gpu
    usage requirements should be prioritized over all other requirements. For instance, if a node with region='us-west',
    dgpu=false is requested, function should try to return nodes in this order:
        region=us-west-1,dgpu:false (best match)
        region=us-west-1,dgpu:true (no dgpu-less nodes available, have to waste resources of a valuable dgpu node)
        region=eu-central-1,dgpu:false (no resources in a preferred region, found node in other regions)
        ...

    Args:
        nodes:
            List of all available nodes in the cluster.
        regions:
            List of regions ordered by a preference criteria (e.g. best latency).
        reqs:
            Set of requirements for a node.

    Returns:
        Best matching node or None if we're out of resources in all regions :(.
    """

    regions_weighted = dict(zip(regions, range(1, len(regions) + 1)))
    dgpu_weighted = {reqs.dgpu: 1, not reqs.dgpu: 2}
    igpu_weighted = {reqs.igpu: 1, not reqs.igpu: 2}
    sorted_nodes = sorted(
        nodes,
        key=lambda n: (
            regions_weighted.get(n.region, 1000),
            dgpu_weighted.get(n.attrs.dgpu),
            igpu_weighted.get(n.attrs.igpu),
            len(n.cores_load()),
        ),
    )

    for node in sorted_nodes:
        free_cores = node.free_cores()
        if free_cores:
            return node
    return None


def _get_clone_subpath(run_specs: RunContainerRequestDTO) -> str:
    return f"{run_specs.user_id}/{run_specs.app_descr.slug}/{run_specs.app_descr.release_uuid}"


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
            Path(os.environ["DATA_DIR"]) / "apps" / run_specs.app_descr.slug / run_specs.app_descr.release_uuid
        )
        dst_path: Path = (
            Path(os.environ["DATA_DIR"])
            / "clones"
            / str(run_specs.user_id)
            / run_specs.app_descr.slug
            / run_specs.app_descr.release_uuid
        )
        if not dst_path.exists():
            shutil.copytree(src_path, dst_path, symlinks=True)
        return
    appstor_user = os.environ["APPSTOR_USER"]
    appstor_instance = next(filter(lambda i: i["region"] == region, appstor_nodes), None)
    if not appstor_instance:
        raise JukeboxOpException(message=f"no appstor instancees in specified region: {region}")
    cmd = f"/opt/yag/appstor/clone_app.sh {run_specs.user_id} {run_specs.app_descr.slug} \
        {run_specs.app_descr.release_uuid}"
    try:
        clone_res = Connection(
            host=appstor_instance["host"],
            user=appstor_user,
            port=appstor_instance["ssh_port"],
            connect_kwargs={"key_filename": "/opt/yag/jukeboxsvc/.ssh/id_ed25519"},
        ).run(
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


@log_input_output
def run_container(run_specs: RunContainerRequestDTO) -> RunContainerResponseDTO:
    """Spins up a new container in the cluster.

    Returns:
        Running container id.
    Raises:
        NodeNotFoundException: when node not found
        ContainerRunFailedException: when container run failed
    """
    aws_ecr_host = os.getenv("AWS_ECR_HOST", None)
    docker_image_tag_path = os.getenv("DOCKER_IMAGE_TAG_PATH", "im.acme.yag.jukebox")
    fps = int(os.environ["FPS"])
    signaler_auth_token = os.environ["SIGNALER_AUTH_TOKEN"]
    signaler_host = os.environ["SIGNALER_HOST"]
    signaler_uri = os.environ["SIGNALER_URI"]
    stun_uri = os.environ["STUN_URI"]
    jukebox_container_app_path = os.environ["JUKEBOX_CONTAINER_APP_DIR"]
    jukebox_container_env_gst_debug = os.getenv("JUKEBOX_CONTAINER_ENV_GST_DEBUG")
    jukebox_contaienr_streamd_max_inactivity_period = int(
        os.getenv("JUKEBOX_CONTAINER_STREAMD_MAX_INACTIVITY_PERIOD", "3600")
    )

    def _gen_container_name(run_specs: RunContainerRequestDTO) -> str:
        rnd = str(uuid.uuid4())[:8]
        return f"jukebox_{run_specs.user_id}_{run_specs.app_descr.slug}_{rnd}"

    node = pick_best_node(
        nodes=list(JUKEBOX_CLUSTER.updated().nodes.values()),
        regions=run_specs.preferred_dcs,
        reqs=NodeRequirements(igpu=run_specs.reqs.hw.igpu, dgpu=run_specs.reqs.hw.dgpu),
    )
    if not node:
        raise ClusterOutOfResourcesException()
    # choosing a random free core to reduce races
    # running docker container without a cpu affinity significantly degrades performance even of a single running app
    cpu_core = random.choice(list(node.free_cores()))  # nosec B311
    devices = [
        "/dev/snd/seq:/dev/snd/seq:rwm",
    ]
    # TODO: gpu devices should be in sync with igpu/dgpu requirements, and e.g. WLR_RENDER_DRM_DEVICE
    igpu_card_id = os.getenv("IGPU_CARD_ID", "0")
    igpu_render_device_id = os.getenv("IGPU_RENDER_DEVICE_ID", "128")
    if run_specs.reqs.container.video_enc == VideoEnc.GPU_INTEL:
        devices.append(f"/dev/dri/card{igpu_card_id}:/dev/dri/card{igpu_card_id}:rwm")
        devices.append(f"/dev/dri/renderD{igpu_render_device_id}:/dev/dri/renderD{igpu_render_device_id}:rwm")
    if run_specs.reqs.container.runner.window_system == WindowSystem.X11:
        # TODO: can't use a simpler formula (e.g. 10+len(node.containers)) cos it may end up with duplicate displays
        # as our local state is not in sync with a real cluster state
        r = rdrand.RdRandom()
        env_display = f":{r.randint(100, 50000)}"  # :10, :11 etc, they shouldn't intersect!
        env_show_pointer = _show_pointer(run_specs.reqs.container.runner.name)
    else:
        env_display = None
        env_show_pointer = None

    clone_app(run_specs, region=node.region)

    container_image_tag = run_specs.reqs.container.image_tag()
    docker_image_tag = (
        f"{aws_ecr_host}/{docker_image_tag_path}:{container_image_tag}" if aws_ecr_host else container_image_tag
    )
    run_container_res = node.run_container(
        run_specs=ContainerRunSpecs(
            attrs=ContainerRunSpecs.Attrs(
                cpuset_cpus=[cpu_core],
                image_tag=docker_image_tag,
                memory_limit=run_specs.reqs.hw.memory,
                memory_shared=run_specs.reqs.hw.memory_shared,
                name=_gen_container_name(run_specs),
                nanocpus_limit=run_specs.reqs.hw.nanocpus,
            ),
            env_vars=ContainerRunSpecs.EnvVars(
                DISPLAY=env_display,
                SHOW_POINTER=env_show_pointer,
                COLOR_BITS=run_specs.reqs.app.color_bits,
                FPS=fps,
                MAX_INACTIVITY_PERIOD=jukebox_contaienr_streamd_max_inactivity_period,
                RUN_MIDI_SYNTH="true" if run_specs.reqs.app.midi else "false",
                SCREEN_HEIGHT=run_specs.reqs.app.screen_height,
                SCREEN_WIDTH=run_specs.reqs.app.screen_width,
                SIGNALER_AUTH_TOKEN=signaler_auth_token,
                SIGNALER_HOST=signaler_host,
                SIGNALER_URI=signaler_uri,
                STUN_URI=stun_uri,
                WS_CONN_ID=run_specs.ws_conn.id,
                WS_CONSUMER_ID=run_specs.ws_conn.consumer_id,
                GST_DEBUG=jukebox_container_env_gst_debug,
            ),
            labels=ContainerRunSpecs.Labels(
                app_slug=str(run_specs.app_descr.slug),
                app_release_uuid=str(run_specs.app_descr.release_uuid),
                user_id=str(run_specs.user_id),
            ),
        ),
        devices=devices,
        mounts=[
            Mount(
                type="volume",
                target=jukebox_container_app_path,
                source="appstor-vol",
                subpath=str(_get_clone_subpath(run_specs)),
                read_only=False,
            )
        ],
    )
    return RunContainerResponseDTO.Schema().load(run_container_res)


def cluster_state() -> Cluster:
    return JUKEBOX_CLUSTER.updated()


def _pull_image_proc(image: PullContainerImageRequestDTO) -> None:
    pull_image_max_workers = 20
    avail_nodes = list(JUKEBOX_CLUSTER.updated().nodes.values())
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
