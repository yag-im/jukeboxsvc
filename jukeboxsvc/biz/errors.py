import json
import logging
import typing as t

from docker.errors import APIError
from fastapi import (
    FastAPI,
    Request,
)
from fastapi.responses import JSONResponse
from pydantic import ValidationError

ERROR_CONTAINER_NOT_FOUND = (1404, "container not found")
ERROR_JUKEBOX_OP = (1409, "jukebox operational error")
ERROR_NODE_NOT_FOUND = (1404, "node not found")
ERROR_CLUSTER_OUT_OF_RESOURCES = (1429, "no resources available in the cluster")
ERROR_CLOUD_INSTANCE_BUILD_IN_PROGRESS = (1409, "a cloud instance is already being built")
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


def init_app(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def handle_exception(request: Request, e: Exception) -> JSONResponse:  # pylint: disable=unused-argument
        res = {"code": ERROR_UNKNOWN[0], "message": ERROR_UNKNOWN[1]}
        log.exception(e)
        return JSONResponse(content=res, status_code=500)

    @app.exception_handler(APIError)
    async def handle_api_error(request: Request, e: APIError) -> JSONResponse:  # pylint: disable=unused-argument
        res = {"code": 1500, "message": e.explanation}
        log.error(json.dumps(res))
        return JSONResponse(content=res, status_code=400)

    @app.exception_handler(ValidationError)
    async def handle_validation_error(
        request: Request,  # pylint: disable=unused-argument
        e: ValidationError,
    ) -> JSONResponse:
        res = {"code": 1400, "message": e.errors()}
        log.error(json.dumps(res))
        return JSONResponse(content=res, status_code=400)

    @app.exception_handler(BizException)
    async def handle_biz_exception(
        request: Request,  # pylint: disable=unused-argument
        e: BizException,
    ) -> JSONResponse:
        res = {"code": e.code, "message": e.message}
        log.error(json.dumps(res))
        return JSONResponse(content=res, status_code=409)
