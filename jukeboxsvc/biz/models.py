from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Column,
    SmallInteger,
)
from sqlalchemy.dialects.postgresql import (
    ENUM,
    UUID,
)

from jukeboxsvc.biz.sqldb import Base

_region_enum = ENUM("eu-central-1", "us-east-1", "us-west-1", name="region", schema="cluster", create_type=False)
_service_type_enum = ENUM("jukebox", "appstor", name="service_type", schema="cluster", create_type=False)
_node_type_enum = ENUM("dedicated", "public-cloud-instance", name="node_type", schema="cluster", create_type=False)
_node_flavor_enum = ENUM(
    "custom-1",
    "rise-3",
    "b2-7",
    "b3-8",
    "d2-2",
    "d2-8",
    "l4-90",
    "l4-180",
    "t2-le-45",
    "t2-le-90",
    name="node_flavor",
    schema="cluster",
    create_type=False,
)


class NodeDAO(Base):
    __tablename__ = "nodes"
    __table_args__ = {"schema": "cluster"}
    id = Column(BigInteger, primary_key=True)
    uuid = Column(UUID(as_uuid=False), unique=True, nullable=False)
    region = Column(_region_enum, nullable=False)
    service_type = Column(_service_type_enum, nullable=False)
    node_ix = Column(SmallInteger, nullable=False)
    node_type = Column(_node_type_enum, nullable=False)
    node_flavor = Column(_node_flavor_enum, nullable=False)
    created_ts = Column(TIMESTAMP, nullable=False)

    @property
    def hostname(self) -> str:
        return f"{self.service_type}{self.node_ix}-{self.region}"
