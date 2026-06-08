import asyncio
import logging
import os

from jukeboxsvc.biz.container import Container
from jukeboxsvc.biz.models import JukeboxNodeDAO
from jukeboxsvc.biz.node import Node
from jukeboxsvc.dto.container import DcRegion
from jukeboxsvc.services.dto.sessionsvc import (
    GetSessionsResponseDTO,
    SessionDC,
)
from jukeboxsvc.services.sessionsvc import get_sessions

STATE_UPDATE_PERIOD = 60
DOCKER_API_PORT = int(os.environ.get("DOCKER_API_PORT", "2375"))

log = logging.getLogger("jukeboxsvc")


def get_nodes(
    region: DcRegion | None = None, init_containers_from_sessions: bool = False, do_update: bool = False
) -> list[Node]:
    if region is not None:
        rows = JukeboxNodeDAO.query.filter_by(region=region.value).all()
    else:
        rows = JukeboxNodeDAO.query.all()
    if do_update:
        raise RuntimeError("use get_nodes_update() for do_update=True")
    elif init_containers_from_sessions:
        sessions: GetSessionsResponseDTO = get_sessions()
        sessions_by_node_id: dict[str, list[SessionDC]] = {}
        for s in sessions.sessions:
            if s.container is None:
                continue  # session created but not started yet, so no container assigned
            sessions_by_node_id.setdefault(s.container.node_id, []).append(s)
        nodes = []
        for row in rows:
            node = Node.from_jukebox_node_dao(row, do_update=do_update)
            node_sessions = sessions_by_node_id.get(node.id, [])
            node.containers = {
                s.container.id: Container.from_sessiondc(s) for s in node_sessions if s.container is not None
            }
            nodes.append(node)
    else:
        nodes = [Node.from_jukebox_node_dao(row, do_update=do_update) for row in rows]
    return nodes


async def get_nodes_update(region: DcRegion | None = None) -> list[Node]:
    if region is not None:
        rows = JukeboxNodeDAO.query.filter_by(region=region.value).all()
    else:
        rows = JukeboxNodeDAO.query.all()
    return list(await asyncio.gather(*[asyncio.to_thread(Node.from_jukebox_node_dao, row, True) for row in rows]))


def get_node(node_id: str, init_containers_from_sessions: bool = False, do_update: bool = False) -> Node | None:
    row = JukeboxNodeDAO.query.filter_by(uuid=node_id).first()
    if row is None:
        return None
    node = Node.from_jukebox_node_dao(row, do_update=do_update)
    if not do_update and init_containers_from_sessions:
        sessions: GetSessionsResponseDTO = get_sessions(node_id=node_id)
        node.containers = {
            s.container.id: Container.from_sessiondc(s) for s in sessions.sessions if s.container is not None
        }
    return node
