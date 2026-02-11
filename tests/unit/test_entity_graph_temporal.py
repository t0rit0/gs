"""EntityGraph 时间属性功能测试"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from drhyper.core.graph import EntityGraph
from drhyper.core.temporal_decay import TemporalDecayCalculator
from langchain.schema import HumanMessage


@pytest.fixture
def mock_graph_model():
    """Fixture: Mock graph model"""
    return Mock()


@pytest.fixture
def mock_conv_model():
    """Fixture: Mock conversation model"""
    return Mock()


@pytest.fixture
def entity_graph_init(mock_graph_model, mock_conv_model):
    """Fixture: 初始化 EntityGraph（时间属性版本）"""
    # Mock 初始化实体返回值
    mock_graph_model.invoke = Mock(return_value=Mock(
        content='{"entities": [{"id": "v1", "name": "血压", "description": "血压测量", '
                  '"weight": 1.0, "uncertainty": 0.5, "confidential_level": 0.7}]}'
    ))

    # 创建 EntityGraph 实例
    eg = EntityGraph(
        target='测试',
        graph_model=mock_graph_model,
        conv_model=mock_conv_model,
        working_directory='/tmp/test_graph'
    )

    # 初始化图
    eg.init(save=False)
    return eg


class TestEntityGraphTimeAttributes:
    """测试 EntityGraph 节点时间属性"""

    def test_new_node_has_temporal_attributes(self, entity_graph_init):
        """测试新节点包含所有时间属性"""
        node_id, node_data = list(entity_graph_init.entity_graph.nodes(data=True))[0]

        # 验证所有时间属性存在
        assert "extracted_at" in node_data
        assert "last_updated_at" in node_data
        assert "source" in node_data
        assert "original_confidential_level" in node_data
        assert "temporal_confidence" in node_data
        assert "freshness" in node_data

        # 验证类型
        assert isinstance(node_data["extracted_at"], datetime)
        assert isinstance(node_data["last_updated_at"], datetime)
        assert isinstance(node_data["original_confidential_level"], float)

        # 验证初始值
        assert node_data["source"] == "conversation"
        assert node_data["freshness"] == pytest.approx(1.0, abs=0.01)
        assert node_data["original_confidential_level"] == pytest.approx(0.7, abs=0.01)
        assert node_data["temporal_confidence"] == pytest.approx(0.7, abs=0.01)

    def test_time_attributes_datetime_now(self, entity_graph_init):
        """测试时间属性是当前时间"""
        node_id, node_data = list(entity_graph_init.entity_graph.nodes(data=True))[0]

        now = datetime.now()
        # 允许1秒误差
        assert (node_data["extracted_at"] - now).total_seconds() < 1
        assert (node_data["last_updated_at"] - now).total_seconds() < 1

    def test_original_confidence_matches_confidence(self, entity_graph_init):
        """测试原始置信度与置信度一致"""
        node_id, node_data = list(entity_graph_init.entity_graph.nodes(data=True))[0]

        assert node_data["original_confidential_level"] == pytest.approx(node_data["confidential_level"], abs=0.01)
        assert node_data["temporal_confidence"] == pytest.approx(node_data["confidential_level"], abs=0.01)

    def test_temporal_calculator_initialized(self, entity_graph_init):
        """测试 EntityGraph 包含 TemporalDecayCalculator"""
        assert hasattr(entity_graph_init, 'temporal_calculator')
        assert isinstance(entity_graph_init.temporal_calculator, TemporalDecayCalculator)


class TestEntityGraphMessageProcessing:
    """测试消息处理时的时间属性更新"""

    def test_user_message_updates_time_attributes(self, entity_graph_init):
        """测试用户消息处理更新时间属性"""
        # Mock 用户确认信息
        entity_graph_init.conv_model.invoke = Mock(return_value=Mock(
            content='{"exist_nodes": [{"id": "v1", "value": "140/90", "confidential_level": 0.9}], '
                  '"new_nodes": [], "endpoint": true}'
        ))

        # 处理消息
        entity_graph_init.accept_message(
            hint_message="请问您血压是多少？",
            query_message="请问您血压是多少？",
            user_message="我的血压是140/90 mmHg"
        )

        # 验证更新
        node_data = entity_graph_init.entity_graph.nodes["v1"]
        assert node_data["confidential_level"] == pytest.approx(0.9, abs=0.01)
        assert node_data["original_confidential_level"] == pytest.approx(0.9, abs=0.01)
        assert node_data["temporal_confidence"] == pytest.approx(0.9, abs=0.01)
        assert node_data["freshness"] == pytest.approx(1.0, abs=0.01)

        # 验证时间更新
        assert node_data["last_updated_at"] > node_data["extracted_at"]


class TestTemporalDecayIntegration:
    """测试时间衰减与EntityGraph集成"""

    def test_calculate_freshness_ranges(self):
        """测试新鲜度计算的时间范围"""
        calc = TemporalDecayCalculator()
        now = datetime.now()

        # 24小时内
        assert calc.calculate_freshness(now - timedelta(hours=23), now) == 1.0
        assert calc.calculate_freshness(now - timedelta(hours=24), now) == 1.0

        # 3天内
        assert calc.calculate_freshness(now - timedelta(days=3), now) == pytest.approx(0.8, abs=0.01)
        assert calc.calculate_freshness(now - timedelta(days=3), now) == pytest.approx(0.8, abs=0.01)

        # 7天内
        assert calc.calculate_freshness(now - timedelta(days=7), now) == pytest.approx(0.6, abs=0.01)
        assert calc.calculate_freshness(now - timedelta(days=7), now) == pytest.approx(0.6, abs=0.01)

        # 30天后
        assert calc.calculate_freshness(now - timedelta(days=30), now) == pytest.approx(0.4, abs=0.01)
        assert calc.calculate_freshness(now - timedelta(days=30), now) == pytest.approx(0.4, abs=0.01)

        # 超过30天
        assert calc.calculate_freshness(now - timedelta(days=31), now) == 0.2

    def test_update_node_attributes_with_decay(self):
        """测试节点属性随时间衰减"""
        calc = TemporalDecayCalculator()

        # 场景：4天前的数据（freshness=0.6）
        extracted = datetime.now() - timedelta(days=4)
        updates = calc.update_node_attributes(
            extracted_at=extracted,
            original_confidential_level=0.9
        )

        # 验证衰减后的值
        assert updates["temporal_confidence"] == pytest.approx(0.54, abs=0.01)  # 0.9 * 0.6
        assert updates["status"] == 1  # < 0.7
        assert updates["freshness"] == pytest.approx(0.6, abs=0.01)

    def test_min_confidence_threshold(self):
        """测试最小置信度阈值"""
        calc = TemporalDecayCalculator()

        # 场景：60天前的低置信度数据
        extracted = datetime.now() - timedelta(days=60)
        updates = calc.update_node_attributes(
            extracted_at=extracted,
            original_confidential_level=0.3  # 原始就低
        )

        # 应该被限制在 0.1
        assert updates["temporal_confidence"] == pytest.approx(0.1, abs=0.01)
        assert updates["status"] == 0  # < 0.4

    def test_is_stale_detection(self):
        """测试陈旧数据检测"""
        calc = TemporalDecayCalculator()

        now = datetime.now()

        # 7天内的数据
        assert not calc.is_stale(extracted_at=now - timedelta(days=7))

        # 30天后的数据
        assert calc.is_stale(extracted_at=now - timedelta(days=31))
