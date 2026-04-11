from sqlalchemy import (
    BigInteger,
    Column,
    String,
)
from sqlalchemy.dialects.postgresql import INET

from jukeboxsvc.biz.sqldb import sqldb


class JukeboxNodeDAO(sqldb.Model):
    __tablename__ = "jukebox_nodes"
    __table_args__ = {"schema": "cluster"}
    id = Column(BigInteger, primary_key=True)
    private_ip = Column(INET, unique=True, nullable=False)
    public_ip = Column(INET, unique=True, nullable=False)
    region = Column(String, nullable=False)
    node_type = Column(String, nullable=False)
    flavor = Column(String, nullable=False)
    dgpu = Column(String, nullable=True)
    igpu = Column(String, nullable=True)
