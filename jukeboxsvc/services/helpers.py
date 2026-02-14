import typing as t

import requests
from requests.adapters import (
    HTTPAdapter,
    Retry,
)


def get_http_client_session(
    total: int = 0,
    backoff_factor: int = 3,
    allowed_methods: t.Optional[list[str]] = None,
    status_forcelist: t.Optional[list[int]] = None,
) -> requests.Session:
    # backoff_factor for 3: 5, 10, 20, 40, 80, 160, 320, 640, 1280, 2560
    if not allowed_methods:
        allowed_methods = ["GET", "POST"]
    if not status_forcelist:
        status_forcelist = [429]
    retries = Retry(
        total=total,
        backoff_factor=backoff_factor,
        allowed_methods=frozenset(allowed_methods),
        status_forcelist=status_forcelist,
    )
    sess = requests.Session()
    sess.mount("http://", HTTPAdapter(max_retries=retries))
    sess.mount("https://", HTTPAdapter(max_retries=retries))
    return sess
