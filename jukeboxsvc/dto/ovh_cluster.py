from pydantic import BaseModel

from jukeboxsvc.biz.ovh_defs import OvhNodeFlavor
from jukeboxsvc.dto.container import DcRegion


class CreateCloudInstanceRequestDTO(BaseModel):
    flavor: OvhNodeFlavor
    image: str
    name: str
    region: DcRegion


class CreateCloudInstanceResponseDTO(BaseModel):
    id: str
