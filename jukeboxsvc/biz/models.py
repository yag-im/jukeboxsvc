from datetime import datetime

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    SmallInteger,
)
from sqlalchemy.dialects.postgresql import (
    ENUM,
    UUID,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
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
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    uuid: Mapped[str] = mapped_column(UUID(as_uuid=False), unique=True, nullable=False)
    region: Mapped[str] = mapped_column(_region_enum, nullable=False)
    service_type: Mapped[str] = mapped_column(_service_type_enum, nullable=False)
    node_ix: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    node_type: Mapped[str] = mapped_column(_node_type_enum, nullable=False)
    node_flavor: Mapped[str] = mapped_column(_node_flavor_enum, nullable=False)
    created_ts: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)

    @property
    def hostname(self) -> str:
        return f"{self.service_type}{self.node_ix}-{self.region}"
