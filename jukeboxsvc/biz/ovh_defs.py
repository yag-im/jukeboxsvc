import re
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from jukeboxsvc.dto.container import (
    DcRegion,
    GpuModel,
)


class NodeServiceType(StrEnum):
    JUKEBOX = "jukebox"
    APPSTOR = "appstor"


class OvhNodeType(StrEnum):
    DEDICATED = "dedicated"
    PUBLIC_CLOUD_INSTANCE = "public-cloud-instance"


class OvhNodeFlavor(StrEnum):
    # dedicated (uppercase)
    CUSTOM_1 = "CUSTOM-1"  # desktop simulator, 1x Intel UHD 750, 1x NVIDIA GTX 1060
    RISE_3 = "RISE-3"
    # public cloud instance (lowercase)
    B2_7 = "b2-7"
    B3_8 = "b3-8"
    D2_2 = "d2-2"
    D2_8 = "d2-8"
    L4_90 = "l4-90"
    L4_180 = "l4-180"
    T2_LE_45 = "t2-le-45"
    T2_LE_90 = "t2-le-90"


class OvhNodeStatus(StrEnum):
    ACTIVE = "ACTIVE"
    BUILD = "BUILD"
    BUILDING = "BUILDING"
    DELETED = "DELETED"
    DELETING = "DELETING"
    ERROR = "ERROR"


class OvhCloudRegion(StrEnum):
    US_EAST_VA_1 = "US-EAST-VA-1"
    US_WEST_OR_1 = "US-WEST-OR-1"


class OvhDedicatedRegion(StrEnum):
    US_EAST_VIN = "us-east-vin"
    US_WEST_HIL = "us-west-hil"


GPU_BY_CPU: dict[str, GpuModel] = {
    "XeonE-2288G": GpuModel.INTEL_UHD_P630,
}

GPUS_BY_FLAVOR: dict[OvhNodeFlavor, list[GpuModel]] = {
    OvhNodeFlavor.CUSTOM_1: [GpuModel.NVIDIA_GTX_1060, GpuModel.INTEL_UHD_750],
    # OvhNodeFlavor.CUSTOM_1: [GpuModel.INTEL_UHD_750, GpuModel.NVIDIA_GTX_1060],
    OvhNodeFlavor.RISE_3: [GpuModel.INTEL_UHD_P630],
    OvhNodeFlavor.T2_LE_45: [GpuModel.NVIDIA_TESLA_V100S],
    OvhNodeFlavor.L4_90: [GpuModel.NVIDIA_L4],
    OvhNodeFlavor.L4_180: [GpuModel.NVIDIA_L4, GpuModel.NVIDIA_L4],
}

CPUS_BY_FLAVOR: dict[OvhNodeFlavor, int] = {
    OvhNodeFlavor.CUSTOM_1: 8,
    OvhNodeFlavor.RISE_3: 8,
    OvhNodeFlavor.B2_7: 2,
    OvhNodeFlavor.B3_8: 2,
    OvhNodeFlavor.D2_2: 1,
    OvhNodeFlavor.D2_8: 4,
    OvhNodeFlavor.T2_LE_45: 15,
    OvhNodeFlavor.T2_LE_90: 30,
    OvhNodeFlavor.L4_90: 22,
    OvhNodeFlavor.L4_180: 45,
}

MEMORY_BY_FLAVOR: dict[OvhNodeFlavor, int] = {
    OvhNodeFlavor.CUSTOM_1: 64 * 1024**3,
    OvhNodeFlavor.RISE_3: 32 * 1024**3,
    OvhNodeFlavor.B2_7: 7 * 1024**3,
    OvhNodeFlavor.B3_8: 8 * 1024**3,
    OvhNodeFlavor.D2_2: 2 * 1024**3,
    OvhNodeFlavor.D2_8: 8 * 1024**3,
    OvhNodeFlavor.T2_LE_45: 45 * 1024**3,
    OvhNodeFlavor.T2_LE_90: 90 * 1024**3,
    OvhNodeFlavor.L4_90: 90 * 1024**3,
    OvhNodeFlavor.L4_180: 180 * 1024**3,
}

DC_REGION_TO_OVH_CLOUD_REGION: dict[DcRegion, OvhCloudRegion] = {
    DcRegion.US_EAST_1: OvhCloudRegion.US_EAST_VA_1,
    DcRegion.US_WEST_1: OvhCloudRegion.US_WEST_OR_1,
}


def normalize_region(raw_ovh_region: str) -> DcRegion:
    regions_map: dict[str, DcRegion] = {
        # dedicated regions
        OvhDedicatedRegion.US_EAST_VIN.value: DcRegion.US_EAST_1,
        OvhDedicatedRegion.US_WEST_HIL.value: DcRegion.US_WEST_1,
        # cloud regions
        OvhCloudRegion.US_EAST_VA_1.value: DcRegion.US_EAST_1,
        OvhCloudRegion.US_WEST_OR_1.value: DcRegion.US_WEST_1,
    }
    region = regions_map.get(raw_ovh_region)
    if region is None:
        raise ValueError(f"unknown OVH region: {raw_ovh_region}")
    return region


class OvhClusterNodeDescr(BaseModel):
    id: str  # OVH UUID
    name: str
    region: DcRegion
    node_type: OvhNodeType
    flavor: OvhNodeFlavor
    status: OvhNodeStatus
    private_ip: str | None = None
    public_ip: str | None = None
    created_ts: datetime | None = None  # dedicated nodes have no creation time

    @classmethod
    def from_cloud_instance(cls, inst: dict[str, Any]) -> "OvhClusterNodeDescr":
        private_ip: str | None = None
        public_ip: str | None = None
        for addr in inst.get("ipAddresses", []):
            if addr["version"] == 4 and addr["type"] == "private":
                private_ip = addr["ip"]
            elif addr["version"] == 4 and addr["type"] == "public":
                public_ip = addr["ip"]
        return cls(
            id=inst["id"],
            name=inst["name"],
            private_ip=private_ip,
            public_ip=public_ip,
            region=normalize_region(inst["region"]),
            node_type=OvhNodeType.PUBLIC_CLOUD_INSTANCE,
            flavor=OvhNodeFlavor(inst["planCode"].split(".")[0]),
            status=OvhNodeStatus(inst["status"]),
            created_ts=datetime.fromisoformat(inst["created"]),
        )

    @classmethod
    def from_dedicated_instance(cls, info: dict[str, Any]) -> "OvhClusterNodeDescr":
        return cls(
            id=info["iam"]["id"],
            name=info["iam"]["displayName"],
            private_ip=None,  # dedicated nodes hide private IPs
            public_ip=info["ip"],
            region=normalize_region(info["region"]),
            node_type=OvhNodeType.DEDICATED,
            flavor=OvhNodeFlavor(info["commercialRange"]),
            status=OvhNodeStatus.ACTIVE,  # no "status" field for dedicated nodes; OK state implies "active"
            created_ts=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),  # dedicated nodes have no creation time
        )

    @property
    def node_ix(self) -> int:
        # TODO: drop private_ip parsing once all instance names are standartized (current appstor nodes are not)
        if self.node_type == OvhNodeType.DEDICATED:
            # Dedicated nodes have no private IP; extract index from name (e.g. "jukebox0-us-east-1" -> 0)
            match = re.search(r"(\d+)", self.name)
            if match is None:
                raise ValueError(f"node '{self.name}' has no index in name; cannot determine node index")
            return int(match.group(1))
        if self.private_ip is None:
            raise ValueError(f"node '{self.name}' has no private IP; cannot determine node index")
        last_octet = int(self.private_ip.split(".")[-1])
        if NodeServiceType.JUKEBOX.value in self.name:
            return last_octet - 2
        else:
            return last_octet % 200
