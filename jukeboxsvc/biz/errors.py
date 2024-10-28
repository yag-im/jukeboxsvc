import json
import logging
import typing as t

from docker.errors import APIError
from flask import (
    Flask,
    Response,
)
from marshmallow import ValidationError
from werkzeug.exceptions import HTTPException

ERROR_CONTAINER_NOT_FOUND = (1404, "container not found")
ERROR_JUKEBOX_OP = (1409, "jukebox operational error")
ERROR_NODE_NOT_FOUND = (1404, "node not found")
ERROR_CLUSTER_OUT_OF_RESOURCES = (1429, "no resources available in the cluster")
ERROR_UNKNOWN = (1500, "unknown error")

log = logging.getLogger("jukeboxsvc")


class BizException(Exception):
    def __init__(self, code: t.Optional[int] = None, message: t.Optional[t.Any] = None) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class JukeboxOpException(BizException):
    def __init__(self, message: t.Optional[t.Any] = None) -> None:
        code = ERROR_JUKEBOX_OP[0]
        message = message or ERROR_JUKEBOX_OP[1]
        super().__init__(code, message)


class ContainerNotFoundException(BizException):
    def __init__(self) -> None:
        code = ERROR_CONTAINER_NOT_FOUND[0]
        message = ERROR_CONTAINER_NOT_FOUND[1]
        super().__init__(code, message)


class NodeNotFoundException(BizException):
    def __init__(self) -> None:
        code = ERROR_NODE_NOT_FOUND[0]
        message = ERROR_NODE_NOT_FOUND[1]
        super().__init__(code, message)


class ClusterOutOfResourcesException(BizException):
    def __init__(self) -> None:
        code = ERROR_CLUSTER_OUT_OF_RESOURCES[0]
        message = ERROR_CLUSTER_OUT_OF_RESOURCES[1]
        super().__init__(code, message)


def init_app(app: Flask) -> None:
    """Inits error handlers.

    Make sure FLASK_PROPAGATE_EXCEPTIONS is set to `true`, otherwise errorhandlers will be unreachable.
    """

    @app.errorhandler(Exception)
    def handle_exception(e: Exception) -> Response:
        if isinstance(e, HTTPException):
            return e
        res = json.dumps({"code": ERROR_UNKNOWN[0], "message": ERROR_UNKNOWN[1]})
        log.exception(e)
        return Response(res, mimetype="application/json", status=500)

    @app.errorhandler(APIError)  # docker api errors
    def handle_api_error(e: APIError) -> Response:
        res = json.dumps(
            {
                "code": 1500,
                "message": e.explanation,
            }
        )
        log.error(res)
        return Response(res, mimetype="application/json", status=400)

    @app.errorhandler(ValidationError)
    def handle_validation_error(e: ValidationError) -> Response:
        res = json.dumps(
            {
                "code": 1400,
                "message": e.messages,
            }
        )
        log.error(res)
        return Response(res, mimetype="application/json", status=400)

    @app.errorhandler(BizException)
    def handle_biz_exception(e: BizException) -> Response:
        res = json.dumps(
            {
                "code": e.code,
                "message": e.message,
            }
        )
        log.error(res)
        return Response(res, mimetype="application/json", status=409)
