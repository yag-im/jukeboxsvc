from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Column,
    Integer,
)
from sqlalchemy.dialects.postgresql import (
    ENUM,
    INET,
    UUID,
)

from jukeboxsvc.biz.sqldb import Base

_region_enum = ENUM("eu-central-1", "us-east-1", "us-west-1", name="region", schema="cluster", create_type=False)
_node_type_enum = ENUM("dedicated", "public-cloud-instance", name="node_type", schema="cluster", create_type=False)
_flavor_enum = ENUM(
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


class JukeboxNodeDAO(Base):
    __tablename__ = "jukebox_nodes"
    __table_args__ = {"schema": "cluster"}
    id = Column(BigInteger, primary_key=True)
    uuid = Column(UUID(as_uuid=False), unique=True, nullable=False)
    private_ip = Column(INET, unique=True, nullable=False)
    public_ip = Column(INET, unique=True, nullable=False)
    region = Column(_region_enum, nullable=False)
    node_type = Column(_node_type_enum, nullable=False)
    flavor = Column(_flavor_enum, nullable=False)
    created_ts = Column(TIMESTAMP, nullable=False)


class AppstorNodeDAO(Base):
    __tablename__ = "appstor_nodes"
    __table_args__ = {"schema": "cluster"}
    id = Column(BigInteger, primary_key=True)
    uuid = Column(UUID(as_uuid=False), unique=True, nullable=False)
    private_ip = Column(INET, unique=True, nullable=False)
    region = Column(_region_enum, nullable=False)
    node_type = Column(_node_type_enum, nullable=False)
    flavor = Column(_flavor_enum, nullable=False)
    share_id = Column(Integer, nullable=False)
    created_ts = Column(TIMESTAMP, nullable=False)
