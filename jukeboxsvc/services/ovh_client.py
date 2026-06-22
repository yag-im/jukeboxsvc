import base64
import functools
import logging
import os
from datetime import datetime
from typing import Any

import openstack
import openstack.connection
import ovh

from jukeboxsvc.biz.ovh_defs import (
    OVH_PRIVATE_NETWORK_NAME,
    OvhCloudRegion,
    OvhClusterNodeDescr,
    OvhNodeFlavor,
    OvhNodeStatus,
    OvhNodeType,
    normalize_region,
)

log = logging.getLogger("jukeboxsvc")


# OVH REST client — kept only for dedicated server API (no OpenStack equivalent)
def _get_ovh_client() -> ovh.Client:
    return ovh.Client(
        endpoint=os.environ["OVH_ENDPOINT"],
        application_key=os.environ["OVH_APPLICATION_KEY"],
        application_secret=os.environ["OVH_APPLICATION_SECRET"],
        consumer_key=os.environ["OVH_CONSUMER_KEY"],
    )


# using openstack as OVH API doesn't allow to create instances from 12.x and 13.x pools
# (only from 1.x and 2.x ranges defined in terraform)
@functools.cache
def _get_os_connection(region: OvhCloudRegion) -> openstack.connection.Connection:
    return openstack.connect(
        auth_url=os.environ["OS_AUTH_URL"],
        username=os.environ["OS_USERNAME"],
        password=os.environ["OS_PASSWORD"],
        project_id=os.environ["OVH_PROJECT_ID"],
        user_domain_name=os.environ.get("OS_USER_DOMAIN_NAME", "Default"),
        region_name=region.value,
    )


@functools.cache
def get_flavor_id(flavor: OvhNodeFlavor, region: OvhCloudRegion) -> str:
    conn = _get_os_connection(region)
    f = conn.compute.find_flavor(flavor.value)
    if f is None:
        raise ValueError(f"Flavor {flavor.value!r} not found in region {region.value!r}")
    return f.id


@functools.cache
def get_image_id(image_name: str, region: OvhCloudRegion, flavor: OvhNodeFlavor) -> str:
    conn = _get_os_connection(region)
    img = conn.image.find_image(name_or_id=image_name)
    if img is None:
        raise ValueError(f"Image {image_name!r} not found in region {region.value!r} for flavor {flavor.value!r}")
    return img.id


@functools.cache
def get_public_network_id(region: OvhCloudRegion) -> str:
    conn = _get_os_connection(region)
    net = conn.network.find_network("Ext-Net")
    if net is None:
        raise ValueError(f"Public network 'Ext-Net' not found in region {region.value!r}")
    return net.id


@functools.cache
def get_private_network_id(network_name: str, region: OvhCloudRegion) -> str:
    conn = _get_os_connection(region)
    net = conn.network.find_network(network_name)
    if net is None:
        raise ValueError(f"Private network {network_name!r} not found in region {region.value!r}")
    return net.id


def _node_from_os_server(server: Any, region: OvhCloudRegion) -> OvhClusterNodeDescr:
    private_ip: str | None = None
    public_ip: str | None = None
    for net_name, addrs in (server.addresses or {}).items():
        for addr in addrs:
            if addr["version"] != 4:
                continue
            if net_name == "Ext-Net":
                public_ip = addr["addr"]
            else:
                private_ip = addr["addr"]
    flavor_name = (server.flavor or {}).get("original_name", "")
    ovh_flavor = OvhNodeFlavor(flavor_name)
    status = OvhNodeStatus(server.status)
    return OvhClusterNodeDescr(
        id=server.id,
        name=server.name,
        private_ip=private_ip,
        public_ip=public_ip,
        region=normalize_region(region.value),
        node_type=OvhNodeType.PUBLIC_CLOUD_INSTANCE,
        flavor=ovh_flavor,
        status=status,
        created_ts=datetime.fromisoformat(server.created_at),
    )


def get_dedicated_nodes() -> list[OvhClusterNodeDescr]:
    client = _get_ovh_client()
    server_names: list[str] = client.get("/dedicated/server")
    nodes: list[OvhClusterNodeDescr] = []
    for name in server_names:
        info: dict[str, Any] = client.get(f"/dedicated/server/{name}")
        if info["iam"]["state"] == "OK":
            nodes.append(OvhClusterNodeDescr.from_dedicated_instance(info))
    return nodes


def get_cloud_instances() -> list[OvhClusterNodeDescr]:
    nodes: list[OvhClusterNodeDescr] = []
    for region in OvhCloudRegion:
        conn = _get_os_connection(region)
        for server in conn.compute.servers():
            nodes.append(_node_from_os_server(server, region))
    return nodes


def create_cloud_instance(
    name: str, region: OvhCloudRegion, flavor: OvhNodeFlavor, image_name: str, private_ip: str, user_data: str
) -> str:
    conn = _get_os_connection(region)
    flavor_id = get_flavor_id(flavor, region)
    image_id = get_image_id(image_name, region, flavor)
    public_network_id = get_public_network_id(region)
    private_network_id = get_private_network_id(OVH_PRIVATE_NETWORK_NAME, region)
    server = conn.compute.create_server(
        name=name,
        flavor_id=flavor_id,
        image_id=image_id,
        networks=[
            {"uuid": public_network_id},
            {"uuid": private_network_id, "fixed_ip": private_ip},
        ],
        user_data=base64.b64encode(user_data.encode()).decode(),
    )
    print(base64.b64decode(server.user_data).decode())
    return server.id


def delete_cloud_instance(instance_id: str) -> None:
    for region in OvhCloudRegion:
        conn = _get_os_connection(region)
        server = conn.compute.find_server(instance_id)
        if server is not None:
            conn.compute.delete_server(instance_id)
            return
    raise ValueError(f"Instance {instance_id!r} not found in any region")
