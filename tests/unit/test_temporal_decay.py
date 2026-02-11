"""时间衰减计算器单元测试"""
import pytest
from datetime import datetime, timedelta

from drhyper.core.temporal_decay import (
    TemporalDecayConfig,
    TemporalDecayCalculator
)


class TestTemporalDecayConfig:
    """测试时间衰减配置"""

    def test_freshness_scores(self):
        """验证新鲜度评分表配置正确"""
        config = TemporalDecayConfig()

        assert len(config.FRESHNESS_SCORES) == 4
        assert config.DEFAULT_FRESHNESS == 0.2
        assert config.MIN_CONFIDENTIAL_LEVEL == 0.1
        assert config.FRESHNESS_THRESHOLD == 0.4


class TestCalculateFreshness:
    """测试新鲜度计算"""

    def test_24_hours_freshness(self):
        """24小时内数据新鲜度为1.0"""
        calc = TemporalDecayCalculator()
        extracted = datetime(2024, 1, 1, 10, 0)
        reference = datetime(2024, 1, 2, 9, 0)  # 23小时后

        result = calc.calculate_freshness(extracted, reference)

        assert result == 1.0

    def test_3_days_freshness(self):
        """3天内数据新鲜度为0.8"""
        calc = TemporalDecayCalculator()
        extracted = datetime(2024, 1, 1, 10, 0)
        reference = datetime(2024, 1, 4, 10, 0)  # 3天后

        result = calc.calculate_freshness(extracted, reference)

        assert result == 0.8

    def test_7_days_freshness(self):
        """7天内数据新鲜度为0.6"""
        calc = TemporalDecayCalculator()
        extracted = datetime(2024, 1, 1, 10, 0)
        reference = datetime(2024, 1, 8, 10, 0)  # 7天后

        result = calc.calculate_freshness(extracted, reference)

        assert result == 0.6

    def test_30_days_freshness(self):
        """30天内数据新鲜度为0.4"""
        calc = TemporalDecayCalculator()
        extracted = datetime(2024, 1, 1, 10, 0)
        reference = datetime(2024, 1, 31, 10, 0)  # 30天后

        result = calc.calculate_freshness(extracted, reference)

        assert result == 0.4

    def test_over_30_days_freshness(self):
        """超过30天数据新鲜度为0.2"""
        calc = TemporalDecayCalculator()
        extracted = datetime(2024, 1, 1, 10, 0)
        reference = datetime(2024, 2, 1, 10, 0)  # 31天后

        result = calc.calculate_freshness(extracted, reference)

        assert result == 0.2

    def test_future_time_freshness(self):
        """未来时间（提取时间晚于参考时间）返回1.0"""
        calc = TemporalDecayCalculator()
        extracted = datetime(2024, 1, 5, 10, 0)
        reference = datetime(2024, 1, 1, 10, 0)  # 提取时间在未来

        result = calc.calculate_freshness(extracted, reference)

        assert result == 1.0

    def test_default_reference_time(self):
        """不提供参考时间时使用当前时间"""
        import time
        calc = TemporalDecayCalculator()

        # 刚创建的数据
        extracted = datetime.now()
        result = calc.calculate_freshness(extracted)

        assert result == 1.0


class TestUpdateNodeAttributes:
    """测试节点属性更新"""

    def test_high_confidence_status(self):
        """高置信度数据 (>=0.7) 状态为2"""
        calc = TemporalDecayCalculator()

        updates = calc.update_node_attributes(
            extracted_at=datetime.now(),
            original_confidential_level=0.9
        )

        assert updates["temporal_confidence"] == pytest.approx(0.9, abs=0.001)
        assert updates["uncertainty"] == pytest.approx(0.1, abs=0.001)
        assert updates["status"] == 2
        assert updates["freshness"] == 1.0

    def test_medium_confidence_status(self):
        """中等置信度数据 (0.4-0.7) 状态为1"""
        calc = TemporalDecayCalculator()

        updates = calc.update_node_attributes(
            extracted_at=datetime(2024, 1, 1),
            original_confidential_level=0.9,
            reference_time=datetime(2024, 1, 5)  # 4天后，freshness=0.6
        )

        # 0.9 * 0.6 = 0.54
        assert updates["temporal_confidence"] == pytest.approx(0.54, abs=0.001)
        assert updates["uncertainty"] == pytest.approx(0.46, abs=0.001)
        assert updates["status"] == 1  # 0.54 < 0.7
        assert updates["freshness"] == 0.6

    def test_low_confidence_status(self):
        """低置信度数据 (<0.4) 状态为0"""
        calc = TemporalDecayCalculator()

        updates = calc.update_node_attributes(
            extracted_at=datetime(2024, 1, 1),
            original_confidential_level=0.9,
            reference_time=datetime(2024, 1, 20)  # 19天后，freshness=0.4
        )

        # 0.9 * 0.4 = 0.36
        assert updates["temporal_confidence"] == pytest.approx(0.36, abs=0.001)
        assert updates["uncertainty"] == pytest.approx(0.64, abs=0.001)
        assert updates["status"] == 0  # 0.36 < 0.4
        assert updates["freshness"] == 0.4

    def test_min_confidence_threshold(self):
        """置信度不会低于 MIN_CONFIDENTIAL_LEVEL (0.1)"""
        calc = TemporalDecayCalculator()

        # 60天后，freshness=0.2，原始置信度很低
        updates = calc.update_node_attributes(
            extracted_at=datetime(2024, 1, 1),
            original_confidential_level=0.3,  # 原始就低
            reference_time=datetime(2024, 3, 1)  # 60天后
        )

        # 0.3 * 0.2 = 0.06，但应该被限制为 0.1
        assert updates["temporal_confidence"] == 0.1
        assert updates["uncertainty"] == 0.9
        assert updates["status"] == 0

    def test_uncertainty_is_inverse(self):
        """不确定性是置信度的反向"""
        calc = TemporalDecayCalculator()

        updates = calc.update_node_attributes(
            extracted_at=datetime.now(),
            original_confidential_level=0.8
        )

        assert updates["uncertainty"] == pytest.approx(0.2, abs=0.001)  # 1 - 0.8


class TestIsStale:
    """测试陈旧数据判断"""

    def test_fresh_data_not_stale(self):
        """7天内的数据不算陈旧"""
        calc = TemporalDecayCalculator()

        assert not calc.is_stale(
            extracted_at=datetime(2024, 1, 1),
            reference_time=datetime(2024, 1, 7)  # freshness=0.6 >= 0.4
        )

    def test_30_days_not_stale(self):
        """30天的数据不算陈旧（刚好在阈值）"""
        calc = TemporalDecayCalculator()

        assert not calc.is_stale(
            extracted_at=datetime(2024, 1, 1),
            reference_time=datetime(2024, 1, 31)  # freshness=0.4
        )

    def test_over_30_days_is_stale(self):
        """超过30天的数据算陈旧"""
        calc = TemporalDecayCalculator()

        assert calc.is_stale(
            extracted_at=datetime(2024, 1, 1),
            reference_time=datetime(2024, 2, 1)  # freshness=0.2 < 0.4
        )
