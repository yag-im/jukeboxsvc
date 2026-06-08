import os

from jukeboxsvc.biz.ovh_defs import (
    NodeServiceType,
    OvhNodeFlavor,
)
from jukeboxsvc.dto.container import DcRegion

OVH_IMAGE_ID_US_WEST_1_NVIDIA_L4 = os.environ["OVH_IMAGE_ID_US_WEST_1_NVIDIA_L4"]
OVH_IMAGE_ID_US_EAST_1_NVIDIA_L4 = os.environ["OVH_IMAGE_ID_US_EAST_1_NVIDIA_L4"]


def get_cloud_instance_image_id(node_service: NodeServiceType, region: DcRegion, flavor: OvhNodeFlavor) -> str:
    image_id_by_service: dict[NodeServiceType, dict[DcRegion, dict[OvhNodeFlavor, str]]] = {
        NodeServiceType.JUKEBOX: {
            DcRegion.US_EAST_1: {
                OvhNodeFlavor.L4_90: OVH_IMAGE_ID_US_EAST_1_NVIDIA_L4,
            },
            DcRegion.US_WEST_1: {
                OvhNodeFlavor.L4_90: OVH_IMAGE_ID_US_WEST_1_NVIDIA_L4,
            },
        },
        NodeServiceType.APPSTOR: {
            DcRegion.US_EAST_1: {
                OvhNodeFlavor.L4_90: OVH_IMAGE_ID_US_EAST_1_NVIDIA_L4,
            },
            DcRegion.US_WEST_1: {
                OvhNodeFlavor.L4_90: OVH_IMAGE_ID_US_WEST_1_NVIDIA_L4,
            },
        },
    }
    return image_id_by_service[node_service][region][flavor]


# dedicated/public OVH region → DcRegion
