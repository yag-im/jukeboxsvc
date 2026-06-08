from jukeboxsvc.biz.ovh_defs import (
    DC_REGION_TO_OVH_CLOUD_REGION,
    OvhClusterNodeDescr,
    OvhNodeFlavor,
)
from jukeboxsvc.dto.container import DcRegion
from jukeboxsvc.services.ovh_client import create_cloud_instance as ovh_client_create_cloud_instance
from jukeboxsvc.services.ovh_client import delete_cloud_instance as ovh_client_delete_cloud_instance
from jukeboxsvc.services.ovh_client import get_cloud_instances as ovh_client_get_cloud_instances
from jukeboxsvc.services.ovh_client import get_dedicated_nodes as ovh_client_get_dedicated_nodes
from jukeboxsvc.services.ovh_client import get_image_id as ovh_client_get_image_id


def get_all_nodes() -> list[OvhClusterNodeDescr]:
    return ovh_client_get_dedicated_nodes() + ovh_client_get_cloud_instances()


def create_cloud_instance(region: DcRegion, flavor: OvhNodeFlavor, name: str, image: str) -> str:
    image_id = ovh_client_get_image_id(image_name=image, region=DC_REGION_TO_OVH_CLOUD_REGION[region], flavor=flavor)
    return ovh_client_create_cloud_instance(
        name=name, region=DC_REGION_TO_OVH_CLOUD_REGION[region], flavor=flavor, image_id=image_id
    )


def delete_cloud_instance(instance_id: str) -> None:
    ovh_client_delete_cloud_instance(instance_id=instance_id)
