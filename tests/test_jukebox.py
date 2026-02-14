import uuid
from types import MethodType
from unittest import mock
from unittest.mock import MagicMock

import pytest

from jukeboxsvc.biz.container import Container
from jukeboxsvc.biz.jukebox import (
    NodeRequirements,
    pick_best_node,
)
from jukeboxsvc.biz.node import Node
from jukeboxsvc.dto.container import DcRegion


def mock_container(cpu_cpuset: list[int], cpu_usage: float) -> mock.MagicMock:
    container = mock.MagicMock(spec=Container)
    container.specs = MagicMock()
    container.specs.attrs.cpuset_cpus = cpu_cpuset
    container.stats.cpu_usage_perc = cpu_usage
    return container


def mock_node(
    region: DcRegion, num_cpus: int, igpu: bool, dgpu: bool, containers: list[mock.MagicMock]
) -> mock.MagicMock:
    node = mock.MagicMock(spec=Node)
    node.id = uuid.uuid4().hex
    node.attrs = MagicMock()
    node.attrs.cpus = num_cpus
    node.attrs.dgpu = dgpu
    node.attrs.igpu = igpu
    node.region = region
    node.containers = {uuid.uuid4().hex: c for c in containers}
    node.cores_load = MethodType(Node.cores_load, node)
    node.free_cores = MethodType(Node.free_cores, node)
    return node


@pytest.mark.unit
class TestJukebox:
    def test_pick_best_node_cpu(self, monkeypatch: pytest.MonkeyPatch):
        import jukeboxsvc.biz.jukebox as jukebox

        def patch_cluster_state(nodes: list[mock.MagicMock], free_cores_by_id: dict[str, set[int]]) -> None:
            cluster = MagicMock()
            cluster.nodes = {n.id: n for n in nodes}
            monkeypatch.setattr(jukebox, "JUKEBOX_CLUSTER", cluster, raising=True)

            state = MagicMock()

            def get_node(node_id: str):
                if node_id in cluster.nodes:
                    return MagicMock(id=node_id)
                return None

            def get_free_cores(node_id: str):
                return free_cores_by_id.get(node_id, set())

            state.get_node.side_effect = get_node
            state.get_free_cores.side_effect = get_free_cores
            monkeypatch.setattr(jukebox, "get_cluster_state_quick", lambda: state, raising=True)

        # no nodes
        nodes = []
        pref_regions = [DcRegion.US_WEST_1, DcRegion.US_EAST_1, DcRegion.EU_CENTRAL_1]
        reqs = NodeRequirements(dgpu=False, igpu=False)
        patch_cluster_state(nodes, {})
        best_node = pick_best_node(pref_regions, reqs)
        assert best_node is None

        # one node in wrong region, one cpu core
        nodes = [
            mock_node(
                region=DcRegion.US_EAST_1,
                num_cpus=8,
                igpu=True,
                dgpu=False,
                containers=[
                    mock_container(cpu_cpuset=[7], cpu_usage=67.78),
                    mock_container(cpu_cpuset=[6], cpu_usage=99.93),
                    mock_container(cpu_cpuset=[5], cpu_usage=99.93),
                    mock_container(cpu_cpuset=[1], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[2], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[3], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[0], cpu_usage=67.78),
                ],
            ),
        ]
        pref_regions = [DcRegion.US_WEST_1, DcRegion.US_EAST_1, DcRegion.EU_CENTRAL_1]
        reqs = NodeRequirements(dgpu=False, igpu=False)
        patch_cluster_state(nodes, {nodes[0].id: {4}})
        best_node = pick_best_node(pref_regions, reqs)
        assert best_node == nodes[0] and best_node.free_cores() == {4}

        # only node in the desired region is fully loaded
        nodes = [
            mock_node(
                region=DcRegion.US_EAST_1,
                num_cpus=8,
                igpu=True,
                dgpu=False,
                containers=[
                    mock_container(cpu_cpuset=[7], cpu_usage=67.78),
                    mock_container(cpu_cpuset=[6], cpu_usage=99.93),
                    mock_container(cpu_cpuset=[1], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[2], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[3], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[0], cpu_usage=67.78),
                ],
            ),
            mock_node(
                region=DcRegion.US_WEST_1,
                num_cpus=8,
                igpu=True,
                dgpu=False,
                containers=[
                    mock_container(cpu_cpuset=[7], cpu_usage=67.78),
                    mock_container(cpu_cpuset=[6], cpu_usage=99.93),
                    mock_container(cpu_cpuset=[1], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[2], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[3], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[4], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[5], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[0], cpu_usage=12.33),
                ],
            ),
        ]
        pref_regions = [DcRegion.US_WEST_1, DcRegion.US_EAST_1, DcRegion.EU_CENTRAL_1]
        reqs = NodeRequirements(dgpu=False, igpu=False)
        patch_cluster_state(nodes, {nodes[0].id: {4, 5}, nodes[1].id: set()})
        best_node = pick_best_node(pref_regions, reqs)
        assert best_node == nodes[0] and best_node.free_cores() == {4, 5}

        # requesting dgpu node
        nodes = [
            mock_node(
                region=DcRegion.US_WEST_1,
                num_cpus=16,
                igpu=True,
                dgpu=False,
                containers=[],
            ),
            mock_node(
                region=DcRegion.US_EAST_1,
                num_cpus=8,
                igpu=True,
                dgpu=True,
                containers=[
                    mock_container(cpu_cpuset=[7], cpu_usage=67.78),
                    mock_container(cpu_cpuset=[6], cpu_usage=99.93),
                    mock_container(cpu_cpuset=[1], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[2], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[3], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[4], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[0], cpu_usage=67.78),
                ],
            ),
            mock_node(
                region=DcRegion.US_WEST_1,
                num_cpus=8,
                igpu=True,
                dgpu=True,
                containers=[
                    mock_container(cpu_cpuset=[7], cpu_usage=67.78),
                    mock_container(cpu_cpuset=[6], cpu_usage=99.93),
                    mock_container(cpu_cpuset=[1], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[2], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[3], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[0], cpu_usage=67.78),
                ],
            ),
            mock_node(
                region=DcRegion.US_WEST_1,
                num_cpus=8,
                igpu=True,
                dgpu=False,
                containers=[
                    mock_container(cpu_cpuset=[7], cpu_usage=67.78),
                    mock_container(cpu_cpuset=[6], cpu_usage=99.93),
                    mock_container(cpu_cpuset=[1], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[2], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[3], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[4], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[5], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[0], cpu_usage=12.33),
                ],
            ),
        ]
        pref_regions = [DcRegion.US_WEST_1, DcRegion.US_EAST_1, DcRegion.EU_CENTRAL_1]
        reqs = NodeRequirements(dgpu=True, igpu=False)
        patch_cluster_state(nodes, {nodes[2].id: {4, 5}})
        best_node = pick_best_node(pref_regions, reqs)
        assert best_node == nodes[2] and best_node.free_cores() == {4, 5}
