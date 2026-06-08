import uuid
from datetime import datetime
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
from jukeboxsvc.dto.container import (
    DcRegion,
    GpuModel,
)

NUM_CPUS_PER_NODE = 8


def mock_container(cpu_cpuset: list[int], cpu_usage: float) -> mock.MagicMock:
    container = mock.MagicMock(spec=Container)
    container.specs = MagicMock()
    container.specs.attrs.cpuset_cpus = cpu_cpuset
    container.stats.cpu_usage_perc = cpu_usage
    return container


def mock_node(region: DcRegion, num_cpus: int, gpu: GpuModel, containers: list[mock.MagicMock]) -> mock.MagicMock:
    node = mock.MagicMock(spec=Node)
    node.id = uuid.uuid4().hex
    node.hw_specs = MagicMock()
    node.hw_specs.cpus = num_cpus
    node.hw_specs.gpus = [gpu]
    node.region = region
    node.created_ts = datetime.now()
    node.containers = {uuid.uuid4().hex: c for c in containers}
    node.cores_load = MethodType(Node.cores_load, node)
    node.busy_cores = MethodType(Node.busy_cores, node)
    node.free_cores = MethodType(Node.free_cores, node)
    return node


@pytest.mark.unit
class TestJukebox:
    def test_pick_best_node(self, monkeypatch: pytest.MonkeyPatch):
        import jukeboxsvc.biz.jukebox as jukebox

        def patch_cluster_state(nodes: list[mock.MagicMock]) -> None:
            nodes_by_region: dict[DcRegion, list[mock.MagicMock]] = {}
            for n in nodes:
                nodes_by_region.setdefault(n.region, []).append(n)

            def mock_get_nodes(region=None, init_containers_from_sessions=False, do_update=False):
                if region is None:
                    return nodes
                return nodes_by_region.get(region, [])

            monkeypatch.setattr(jukebox, "get_nodes", mock_get_nodes, raising=True)

        # no nodes
        nodes = []
        region = DcRegion.US_WEST_1
        reqs = NodeRequirements(gpu=None)
        patch_cluster_state(nodes)
        best_node = pick_best_node(region, reqs)
        assert best_node is None

        # one node in wrong region, one cpu core
        nodes = [
            mock_node(
                region=DcRegion.US_EAST_1,
                num_cpus=NUM_CPUS_PER_NODE,
                gpu=GpuModel.INTEL_UHD_750,
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
        region = DcRegion.US_WEST_1
        reqs = NodeRequirements(gpu=None)
        patch_cluster_state(nodes)
        best_node = pick_best_node(region, reqs)
        assert best_node is None

        # only node in the desired region is fully loaded (negative)
        nodes = [
            mock_node(
                region=DcRegion.US_EAST_1,
                num_cpus=NUM_CPUS_PER_NODE,
                gpu=GpuModel.INTEL_UHD_750,
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
                num_cpus=NUM_CPUS_PER_NODE,
                gpu=GpuModel.INTEL_UHD_750,
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
        region = DcRegion.US_WEST_1
        reqs = NodeRequirements(gpu=None)
        patch_cluster_state(nodes)
        best_node = pick_best_node(region, reqs)
        assert best_node is None

        # requesting node with dedicated GPU
        nodes = [
            mock_node(
                region=DcRegion.US_WEST_1,
                num_cpus=NUM_CPUS_PER_NODE,
                gpu=GpuModel.INTEL_UHD_750,
                containers=[],
            ),
            mock_node(
                region=DcRegion.US_EAST_1,
                num_cpus=NUM_CPUS_PER_NODE,
                gpu=GpuModel.NVIDIA_TESLA_V100S,
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
                num_cpus=NUM_CPUS_PER_NODE,
                gpu=GpuModel.NVIDIA_TESLA_V100S,
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
                num_cpus=NUM_CPUS_PER_NODE,
                gpu=GpuModel.INTEL_UHD_750,
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
        region = DcRegion.US_WEST_1
        reqs = NodeRequirements(gpu=GpuModel.NVIDIA_TESLA_V100S)
        patch_cluster_state(nodes)
        best_node = pick_best_node(region, reqs)
        assert best_node == nodes[2] and best_node.free_cores() == {4, 5}

        # stick to a single DC (negative)
        nodes = [
            mock_node(
                region=DcRegion.US_WEST_1,
                num_cpus=NUM_CPUS_PER_NODE,
                gpu=GpuModel.INTEL_UHD_750,
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
            mock_node(
                region=DcRegion.US_EAST_1,
                num_cpus=NUM_CPUS_PER_NODE,
                gpu=GpuModel.INTEL_UHD_750,
                containers=[
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
        region = DcRegion.US_WEST_1
        reqs = NodeRequirements(gpu=None)
        patch_cluster_state(nodes)
        best_node = pick_best_node(region, reqs)
        assert best_node is None

        # stick to a single DC (positive)
        nodes = [
            mock_node(
                region=DcRegion.US_WEST_1,
                num_cpus=NUM_CPUS_PER_NODE,
                gpu=GpuModel.INTEL_UHD_750,
                containers=[
                    mock_container(cpu_cpuset=[6], cpu_usage=99.93),
                    mock_container(cpu_cpuset=[1], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[2], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[3], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[4], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[5], cpu_usage=12.33),
                    mock_container(cpu_cpuset=[0], cpu_usage=12.33),
                ],
            ),
            mock_node(
                region=DcRegion.US_EAST_1,
                num_cpus=NUM_CPUS_PER_NODE,
                gpu=GpuModel.INTEL_UHD_750,
                containers=[
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
        region = DcRegion.US_WEST_1
        reqs = NodeRequirements(gpu=None)
        patch_cluster_state(nodes)
        best_node = pick_best_node(region, reqs)
        assert best_node == nodes[0] and best_node.free_cores() == {7}
