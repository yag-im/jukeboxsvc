from jukeboxsvc.biz.ovh_defs import (
    DC_REGION_TO_OVH_CLOUD_REGION,
    NodeServiceType,
    OvhClusterNodeDescr,
    OvhNodeFlavor,
)
from jukeboxsvc.biz.ovh_utils import (
    build_appstor_image_user_data,
    build_jukebox_image_user_data,
    node_ix_from_instance_name,
    node_ix_to_private_ip,
)
from jukeboxsvc.dto.container import DcRegion
from jukeboxsvc.services.ovh_client import create_cloud_instance as ovh_client_create_cloud_instance
from jukeboxsvc.services.ovh_client import delete_cloud_instance as ovh_client_delete_cloud_instance
from jukeboxsvc.services.ovh_client import get_cloud_instances as ovh_client_get_cloud_instances
from jukeboxsvc.services.ovh_client import get_dedicated_nodes as ovh_client_get_dedicated_nodes


def get_all_nodes() -> list[OvhClusterNodeDescr]:
    return ovh_client_get_dedicated_nodes() + ovh_client_get_cloud_instances()


def create_cloud_instance(
    region: DcRegion,
    flavor: OvhNodeFlavor,
    name: str,
    image: str,
    private_ip: str | None,
    user_data: str | None,
) -> str:
    if private_ip is None or user_data is None:
        # called directly through the external API, for testing purposes only (using fake test values for appstor_num,
        # btrfs_devices etc.)
        node_ix = node_ix_from_instance_name(name)
        if "jukebox" in image.lower():
            private_ip = node_ix_to_private_ip(NodeServiceType.JUKEBOX, region, node_ix)
            user_data = build_jukebox_image_user_data(region, node_ix, appstor_num=1)
        elif "appstor" in image.lower():
            private_ip = node_ix_to_private_ip(NodeServiceType.APPSTOR, region, node_ix)
            user_data = build_appstor_image_user_data(region, node_ix, btrfs_devices="/dev/sdb")
        else:
            raise ValueError(f"Unsupported image name: {image!r}")
    return ovh_client_create_cloud_instance(
        name=name,
        region=DC_REGION_TO_OVH_CLOUD_REGION[region],
        flavor=flavor,
        image_name=image,
        private_ip=private_ip,
        user_data=user_data,
    )


def delete_cloud_instance(instance_id: str) -> None:
    ovh_client_delete_cloud_instance(instance_id=instance_id)
