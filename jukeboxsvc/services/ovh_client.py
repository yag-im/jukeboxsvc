import functools
import logging
import os
from typing import Any

import ovh

from jukeboxsvc.biz.ovh_defs import (
    OvhCloudRegion,
    OvhClusterNodeDescr,
    OvhNodeFlavor,
)

log = logging.getLogger("jukeboxsvc")


def _get_client() -> ovh.Client:
    return ovh.Client(
        endpoint=os.environ["OVH_ENDPOINT"],
        application_key=os.environ["OVH_APPLICATION_KEY"],
        application_secret=os.environ["OVH_APPLICATION_SECRET"],
        consumer_key=os.environ["OVH_CONSUMER_KEY"],
    )


@functools.cache
def get_flavor_id(flavor: OvhNodeFlavor, region: OvhCloudRegion) -> str:
    client = _get_client()
    project_id = os.environ["OVH_PROJECT_ID"]
    flavors: list[dict[str, Any]] = client.get(
        f"/cloud/project/{project_id}/flavor",
        region=region.value,
    )
    for f in flavors:
        if f["name"] == flavor.value:
            return f["id"]
    raise ValueError(f"Flavor {flavor.value!r} not found in region {region.value!r}")


@functools.cache
def get_image_id(image_name: str, region: OvhCloudRegion, flavor: OvhNodeFlavor) -> str:
    client = _get_client()
    project_id = os.environ["OVH_PROJECT_ID"]
    images: list[dict[str, Any]] = client.get(
        f"/cloud/project/{project_id}/image",
        flavorType=flavor.value,
        region=region.value,
    )
    for img in images:
        if img["name"] == image_name:
            return img["id"]
    raise ValueError(f"Image {image_name!r} not found in region {region.value!r} for flavor {flavor.value!r}")


def get_dedicated_nodes() -> list[OvhClusterNodeDescr]:
    client = _get_client()
    server_names: list[str] = client.get("/dedicated/server")
    nodes: list[OvhClusterNodeDescr] = []

    for name in server_names:
        info: dict[str, Any] = client.get(f"/dedicated/server/{name}")
        if info["iam"]["state"] == "OK":
            nodes.append(OvhClusterNodeDescr.from_dedicated_instance(info))

    return nodes


def get_cloud_instances() -> list[OvhClusterNodeDescr]:
    client = _get_client()
    project_id = os.environ["OVH_PROJECT_ID"]
    instances: list[dict[str, Any]] = client.get(f"/cloud/project/{project_id}/instance")
    return [OvhClusterNodeDescr.from_cloud_instance(inst) for inst in instances]


def has_cloud_instances_in_build_state() -> bool:
    client = _get_client()
    project_id = os.environ["OVH_PROJECT_ID"]
    instances: list[dict[str, Any]] = client.get(f"/cloud/project/{project_id}/instance")
    return any(inst.get("status") == "BUILD" for inst in instances)


def create_cloud_instance(name: str, region: OvhCloudRegion, flavor: OvhNodeFlavor, image_id: str) -> str:
    client = _get_client()
    project_id = os.environ["OVH_PROJECT_ID"]
    flavor_id = get_flavor_id(flavor, region)
    instance = client.post(
        f"/cloud/project/{project_id}/instance",
        flavorId=flavor_id,
        name=name,
        region=region.value,
        imageId=image_id,
        monthlyBilling=False,
    )
    return instance["id"]


def delete_cloud_instance(instance_id: str) -> None:
    client = _get_client()
    project_id = os.environ["OVH_PROJECT_ID"]
    client.delete(f"/cloud/project/{project_id}/instance/{instance_id}")
