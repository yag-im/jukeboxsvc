from sqlalchemy import create_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    scoped_session,
    sessionmaker,
)


class Base(DeclarativeBase):
    pass


class _Sqldb:
    """Mimics the flask-sqlalchemy interface used across the biz layer."""

    session: scoped_session

    def init_app(self, database_url: str) -> None:
        engine = create_engine(database_url)
        factory = sessionmaker(bind=engine)
        self.session = scoped_session(factory)
        Base.query = self.session.query_property()  # type: ignore[attr-defined]


sqldb = _Sqldb()
