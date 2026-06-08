import os

from jukeboxsvc.biz.errors import BizException
from jukeboxsvc.services.dto.sessionsvc import GetSessionsResponseDTO
from jukeboxsvc.services.helpers import get_http_client_session

REQUESTS_TIMEOUT_CONN_READ = (3, 10)
SESSIONSVC_URL = os.environ["SESSIONSVC_URL"]


def get_sessions(node_id: str | None = None) -> GetSessionsResponseDTO:
    s = get_http_client_session()
    url = f"{SESSIONSVC_URL}/sessions"
    if node_id is not None:
        url += f"?node_id={node_id}"
    res = s.get(
        url=url,
        timeout=REQUESTS_TIMEOUT_CONN_READ,
    )
    if res.status_code != 200:
        raise BizException(message=res.text)
    return GetSessionsResponseDTO.Schema().load(data=res.json())
