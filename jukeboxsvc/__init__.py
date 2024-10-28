from flask import Flask

from jukeboxsvc.api import api
from jukeboxsvc.biz import (
    errors,
    log,
)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_prefixed_env()

    # init extensions
    api.init_app(app)
    errors.init_app(app)
    log.init_app(app)

    app.logger.info("app init completed")

    return app
