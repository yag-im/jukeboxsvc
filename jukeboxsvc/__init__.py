import os

from flask import Flask

from jukeboxsvc.api import api
from jukeboxsvc.biz import (
    errors,
    log,
)
from jukeboxsvc.biz.cluster import JUKEBOX_CLUSTER
from jukeboxsvc.biz.sqldb import sqldb


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_prefixed_env()
    app.config.from_prefixed_env()
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f'postgresql://{os.environ["SQLDB_USERNAME"]}:{os.environ["SQLDB_PASSWORD"]}@{os.environ["SQLDB_HOST"]}:\
        {os.environ["SQLDB_PORT"]}/{os.environ["SQLDB_DBNAME"]}'
    )

    # init extensions
    api.init_app(app)
    sqldb.init_app(app)
    log.init_app(app)
    errors.init_app(app)

    with app.app_context():
        JUKEBOX_CLUSTER.update(force=True)  # the very first update is synchronous

    app.logger.info("app init completed")

    return app
