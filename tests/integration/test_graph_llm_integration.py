"""EntityGraph LLM集成测试

直接使用config中的真实LLM进行测试，不使用mock。
"""
import pytest
import os
import tempfile
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from drhyper.core.graph import EntityGraph
from drhyper.config.settings import ConfigManager
from drhyper.utils.llm_loader import load_chat_model
from backend.services.patient_context_builder import PatientContextBuilder
from backend.database.models import Base, Patient


@pytest.fixture(scope="module")
def real_llm_models():
    """使用真实LLM配置"""
    config = ConfigManager()

    # 使用项目的load_chat_model创建实际的LLM实例
    graph_llm = load_chat_model(
        provider=config.graph_llm.provider,
        model_name=config.graph_llm.model,
        api_key=config.graph_llm.api_key,
        base_url=config.graph_llm.base_url,
        temperature=config.graph_llm.temperature,
        max_tokens=config.graph_llm.max_tokens,
    )

    conv_llm = load_chat_model(
        provider=config.conversation_llm.provider,
        model_name=config.conversation_llm.model,
        api_key=config.conversation_llm.api_key,
        base_url=config.conversation_llm.base_url,
        temperature=config.conversation_llm.temperature,
        max_tokens=config.conversation_llm.max_tokens,
    )

    return graph_llm, conv_llm


@pytest.fixture
def temp_db():
    """创建临时数据库"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    # 创建测试患者
    patient = Patient(
        patient_id="test_001",
        name="张三",
        age=35,
        gender="男",
        phone="13800138000",
        address="北京市朝阳区",
        medical_history="高血压病史3年，糖尿病病史2年",
        allergies="青霉素过敏",
        medications="二甲双胍500mg 每日两次;降压药0号 每日一次",
        family_history="父亲有高血压，母亲有糖尿病",
        health_metrics="BMI 26.5，血压140/90mmHg"
    )
    db.add(patient)
    db.commit()

    yield db

    db.close()


@pytest.fixture
def working_dir():
    """创建临时工作目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestEntityGraphLLMIntegration:
    """测试EntityGraph与真实LLM的集成"""

    def test_graph_initialization_with_patient_context(
        self, real_llm_models, temp_db, working_dir
    ):
        """测试使用真实LLM和患者上下文初始化图"""
        graph_llm, conv_llm = real_llm_models

        # 构建患者上下文
        context_builder = PatientContextBuilder()
        patient_context = context_builder.build(temp_db, "test_001")

        # 验证患者上下文构建正确
        assert patient_context.patient_id == "test_001"
        assert patient_context.basic_info["name"] == "张三"
        assert len(patient_context.patient_text_records) > 0
        assert "medical_history" in patient_context.patient_text_records

        # 使用患者上下文初始化图
        graph = EntityGraph(
            target="收集患者的基本健康信息",
            graph_model=graph_llm,
            conv_model=conv_llm,
            working_directory=working_dir,
            language="中文"
        )

        # 测试初始化（使用患者上下文）
        log_messages = graph.init(save=False, patient_context={
            "patient_text_records": patient_context.patient_text_records
        })

        # 验证图已创建
        assert graph.entity_graph is not None
        assert graph.relation_graph is not None

        # 验证时间衰减计算器已初始化
        assert graph.temporal_calculator is not None

        # 验证图中有节点（LLM应该根据目标生成了实体）
        node_count = graph.entity_graph.number_of_nodes()
        assert node_count > 0, f"Expected at least 1 node, got {node_count}"


class TestPatientContextRealLLM:
    """测试PatientContextBuilder与真实数据库的集成"""

    def test_build_patient_context_from_real_db(self, temp_db):
        """测试从真实数据库构建患者上下文"""
        context_builder = PatientContextBuilder()
        patient_context = context_builder.build(temp_db, "test_001")

        # 验证基本信息
        assert patient_context.patient_id == "test_001"
        assert patient_context.basic_info["name"] == "张三"
        assert patient_context.basic_info["age"] == 35
        assert patient_context.basic_info["gender"] == "男"

        # 验证文本记录
        assert "medical_history" in patient_context.patient_text_records
        assert "allergies" in patient_context.patient_text_records
        assert "medications" in patient_context.patient_text_records

        # 验证内容
        assert "高血压" in patient_context.patient_text_records["medical_history"]
        assert "青霉素" in patient_context.patient_text_records["allergies"]
        assert "二甲双胍" in patient_context.patient_text_records["medications"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
