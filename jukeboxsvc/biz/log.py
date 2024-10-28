import logging

from flask import Flask


def init_app(app: Flask) -> None:
    # log setup
    # TODO: use app.config["DEBUG"] flag for log_level
    log_level = logging.DEBUG

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"))

    app.logger.handlers.clear()
    app.logger.addHandler(handler)
    app.logger.setLevel(log_level)

    app_log = logging.getLogger("jukeboxsvc")
    app_log.handlers.clear()
    app_log.addHandler(handler)
    app_log.setLevel(log_level)
    app_log.propagate = False

    root_log = logging.getLogger()
    root_log.handlers.clear()
    root_log.addHandler(handler)
    root_log.setLevel(log_level)
    root_log.propagate = False

    # talkative modules:
    logging.getLogger("botocore").setLevel(logging.INFO)
    logging.getLogger("docker").setLevel(logging.INFO)
    logging.getLogger("fabric").setLevel(logging.INFO)
    logging.getLogger("invoke").setLevel(logging.INFO)
    logging.getLogger("paramiko").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.INFO)
