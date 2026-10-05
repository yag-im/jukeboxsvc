import threading
import typing as t
from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy import create_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Query,
    scoped_session,
    sessionmaker,
)
from starlette.types import (
    ASGIApp,
    Receive,
    Scope,
    Send,
)

# Per-request/task session scope key. ContextVars propagate into run_in_threadpool / asyncio.to_thread,
# so sync endpoints and worker threads spawned by a request share the request's session.
_session_scope: ContextVar[t.Optional[object]] = ContextVar("sqldb_session_scope", default=None)


def _scopefunc() -> t.Hashable:
    scope = _session_scope.get()
    return scope if scope is not None else threading.get_ident()


class Base(DeclarativeBase):
    query: t.ClassVar[Query[t.Any]]


class _Sqldb:
    """Mimics the flask-sqlalchemy interface used across the biz layer."""

    session: scoped_session

    def init_app(self, database_url: str) -> None:
        # pool_pre_ping transparently replaces connections dropped by the server/network
        engine = create_engine(database_url, pool_pre_ping=True)
        factory = sessionmaker(bind=engine)
        self.session = scoped_session(factory, scopefunc=_scopefunc)
        Base.query = self.session.query_property()  # type: ignore[attr-defined]

    @contextmanager
    def session_scope(self) -> t.Iterator[None]:
        """Binds a fresh session to the current context and closes it on exit.

        Closing releases the connection back to the pool and discards any failed/invalidated transaction,
        so an error in one request can't poison subsequent ones (PendingRollbackError).
        """
        token = _session_scope.set(object())
        try:
            yield
        finally:
            try:
                self.session.remove()
            finally:
                _session_scope.reset(token)


sqldb = _Sqldb()


class SqldbSessionMiddleware:
    """ASGI middleware providing a request-scoped SQL session."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        with sqldb.session_scope():
            await self.app(scope, receive, send)
