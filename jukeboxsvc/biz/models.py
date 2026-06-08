from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Column,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import (
    INET,
    UUID,
)

from jukeboxsvc.biz.sqldb import Base


class JukeboxNodeDAO(Base):
    __tablename__ = "jukebox_nodes"
    __table_args__ = {"schema": "cluster"}
    id = Column(BigInteger, primary_key=True)
    uuid = Column(UUID(as_uuid=False), unique=True, nullable=False)
    private_ip = Column(INET, unique=True, nullable=False)
    public_ip = Column(INET, unique=True, nullable=False)
    region = Column(String, nullable=False)
    node_type = Column(String, nullable=False)
    flavor = Column(String, nullable=False)
    created_ts = Column(TIMESTAMP, nullable=False)


class AppstorNodeDAO(Base):
    __tablename__ = "appstor_nodes"
    __table_args__ = {"schema": "cluster"}
    id = Column(BigInteger, primary_key=True)
    uuid = Column(UUID(as_uuid=False), unique=True, nullable=False)
    private_ip = Column(INET, unique=True, nullable=False)
    region = Column(String, nullable=False)
    node_type = Column(String, nullable=False)
    flavor = Column(String, nullable=False)
    share_id = Column(Integer, nullable=False)
    created_ts = Column(TIMESTAMP, nullable=False)
