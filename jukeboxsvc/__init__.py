import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from jukeboxsvc.api import router
from jukeboxsvc.biz import (
    errors,
    log,
)
from jukeboxsvc.biz.sqldb import sqldb


def _build_db_url() -> str:
    return (
        f'postgresql://{os.environ["SQLDB_USERNAME"]}:{os.environ["SQLDB_PASSWORD"]}'
        f'@{os.environ["SQLDB_HOST"]}:{os.environ["SQLDB_PORT"]}/{os.environ["SQLDB_DBNAME"]}'
    )


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001  # pylint: disable=unused-argument
    database_url = os.environ.get("DATABASE_URL") or _build_db_url()
    sqldb.init_app(database_url)
    yield
    sqldb.session.remove()


def create_app() -> FastAPI:
    app = FastAPI(title="jukeboxsvc", lifespan=_lifespan)
    log.init_app(app)
    errors.init_app(app)
    app.include_router(router)
    logging.getLogger("jukeboxsvc").info("app init completed")
    return app
