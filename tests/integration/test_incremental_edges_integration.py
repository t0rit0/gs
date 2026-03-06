"""
增量连边功能集成测试

使用真实 LLM API 测试增量连边功能。

运行前请确保：
1. 配置文件中已设置正确的 API key 和 base_url
2. 网络连接正常

运行命令：
    uv run pytest tests/integration/test_incremental_edges_integration.py -v

标记：
    @pytest.mark.integration - 集成测试标记
    @pytest.mark.slow - 慢速测试标记（因为需要调用 API）
"""
import pytest
import os
from pathlib import Path

# 检查是否配置了 API key
API_KEY = os.getenv("OPENAI_API_KEY")
BASE_URL = os.getenv("OPENAI_BASE_URL")

# 如果没有配置 API key，跳过所有测试
pytestmark = pytest.mark.skipif(
    not API_KEY,
    reason="需要 OPENAI_API_KEY 环境变量"
)


class TestIncrementalEdgesIntegration:
    """增量连边集成测试类"""

    @pytest.fixture
    def real_entity_graph(self):
        """创建使用真实 LLM 的 EntityGraph 实例"""
        from langchain_openai import ChatOpenAI
        from drhyper.core.graph import EntityGraph
        import networkx as nx

        # 创建真实的 LLM 模型
        graph_model = ChatOpenAI(
            model="qwen3.5-plus",  # 或你的模型
            api_key=API_KEY,
            base_url=BASE_URL,
            temperature=0.7
        )

        conv_model = ChatOpenAI(
            model="qwen3.5-plus",
            api_key=API_KEY,
            base_url=BASE_URL,
            temperature=0.7
        )

        # 创建 EntityGraph
        eg = EntityGraph(
            target="高血压诊断",
            graph_model=graph_model,
            conv_model=conv_model,
            language="中文"
        )

        # 初始化 relation_graph
        eg.relation_graph = nx.DiGraph()

        return eg

    @pytest.fixture
    def sample_medical_graph(self):
        """创建示例医疗图谱"""
        import networkx as nx

        graph = nx.DiGraph()

        # 添加高血压诊断相关节点
        graph.add_node("node_1", name="收缩压", description="收缩压测量值",
                      value="160 mmHg", status=2, community=0)
        graph.add_node("node_2", name="舒张压", description="舒张压测量值",
                      value="100 mmHg", status=2, community=0)
        graph.add_node("node_3", name="头痛", description="患者主诉症状",
                      value="持续性胀痛", status=2, community=0)
        graph.add_node("node_4", name="眼底检查", description="眼底动脉检查",
                      value="动脉变细", status=2, community=0)
        graph.add_node("node_5", name="吸烟史", description="吸烟习惯",
                      value="20 年，每天 1 包", status=2, community=0)

        # 添加一些现有边
        graph.add_edge("node_1", "node_4", relation="causes", weight=0.8)
        graph.add_edge("node_3", "node_1", relation="suggests", weight=0.6)

        return graph

    @pytest.mark.integration
    @pytest.mark.slow
    def test_create_incremental_edges_with_real_api(self, real_entity_graph, sample_medical_graph):
        """测试使用真实 API 创建增量边"""
        # 设置 relation_graph
        real_entity_graph.relation_graph = sample_medical_graph

        # 添加新节点（新症状）
        new_nodes = [
            {
                "id": "node_6",
                "name": "头晕",
                "description": "患者主诉的头晕症状",
                "value": "间歇性头晕，持续 1 周",
                "community": 0
            }
        ]

        # 调用增量连边
        edges, logs = real_entity_graph._create_incremental_edges(
            new_nodes=new_nodes,
            max_candidates=5
        )

        # 验证结果
        assert isinstance(edges, list)
        assert len(edges) > 0, "应该创建至少一条边"

        # 验证边的格式
        for edge in edges:
            assert "source" in edge
            assert "target" in edge
            assert "relation" in edge
            assert "weight" in edge
            assert 0 <= edge["weight"] <= 1

        # 验证边涉及新节点
        edge_nodes = set()
        for edge in edges:
            edge_nodes.add(edge["source"])
            edge_nodes.add(edge["target"])
        assert "node_6" in edge_nodes, "新节点应该在边中"

    @pytest.mark.integration
    @pytest.mark.slow
    def test_select_candidate_nodes_medical_context(self, real_entity_graph, sample_medical_graph):
        """测试在医疗上下文中选择候选节点"""
        real_entity_graph.relation_graph = sample_medical_graph

        # 新节点：与血压相关的症状
        new_node = {
            "id": "node_7",
            "name": "心悸",
            "description": "心跳加速或不规则",
            "community": 0
        }

        candidates = real_entity_graph._select_candidate_nodes(
            new_node=new_node,
            max_candidates=3
        )

        # 验证返回的候选节点
        assert isinstance(candidates, list)
        assert len(candidates) <= 3
        assert all(c in sample_medical_graph.nodes for c in candidates)

    @pytest.mark.integration
    @pytest.mark.slow
    def test_full_workflow_with_real_api(self, real_entity_graph):
        """测试完整的增量连边工作流程（真实 API）"""
        # 1. 初始化简单的 relation_graph
        real_entity_graph.relation_graph = nx.DiGraph()
        real_entity_graph.relation_graph.add_node("node_1", name="血压", community=0)
        real_entity_graph.relation_graph.add_node("node_2", name="心率", community=0)
        real_entity_graph.relation_graph.add_edge("node_1", "node_2", relation="correlates", weight=0.7)

        # 2. 添加新节点
        new_nodes = [
            {
                "id": "node_3",
                "name": "头晕",
                "description": "头晕症状",
                "community": 0
            }
        ]
        real_entity_graph.relation_graph.add_node("node_3", **new_nodes[0])

        # 3. 创建增量边
        edges, logs = real_entity_graph._create_incremental_edges(
            new_nodes=new_nodes,
            max_candidates=2
        )

        # 4. 添加边到图
        if edges:
            real_entity_graph._add_incremental_edges_to_graphs(edges)

        # 5. 验证新节点有边了
        degree = real_entity_graph.relation_graph.degree("node_3")
        assert degree > 0, "新节点应该有边连接到现有图"

        # 6. 验证边的存在
        has_edges = any(
            real_entity_graph.relation_graph.has_edge("node_3", n) or
            real_entity_graph.relation_graph.has_edge(n, "node_3")
            for n in ["node_1", "node_2"]
        )
        assert has_edges, "新节点应该与现有节点有边连接"

    @pytest.mark.integration
    @pytest.mark.slow
    def test_multiple_new_nodes(self, real_entity_graph, sample_medical_graph):
        """测试多个新节点同时创建边"""
        real_entity_graph.relation_graph = sample_medical_graph

        # 添加多个新节点
        new_nodes = [
            {
                "id": "node_8",
                "name": "恶心",
                "description": "恶心症状",
                "community": 0
            },
            {
                "id": "node_9",
                "name": "视力模糊",
                "description": "视力模糊症状",
                "community": 0
            }
        ]

        # 添加新节点到图
        for node in new_nodes:
            real_entity_graph.relation_graph.add_node(node["id"], **node)

        # 创建增量边
        edges, logs = real_entity_graph._create_incremental_edges(
            new_nodes=new_nodes,
            max_candidates=5
        )

        # 验证结果
        assert isinstance(edges, list)
        # 至少有一个节点创建了边
        assert len(edges) > 0

    @pytest.mark.integration
    @pytest.mark.slow
    def test_edge_relation_types(self, real_entity_graph, sample_medical_graph):
        """测试创建的边关系类型是否合理"""
        real_entity_graph.relation_graph = sample_medical_graph

        # 新节点：实验室检查结果
        new_nodes = [
            {
                "id": "node_10",
                "name": "血钾异常",
                "description": "血钾水平异常",
                "value": "3.2 mmol/L (低)",
                "community": 0
            }
        ]
        real_entity_graph.relation_graph.add_node("node_10", **new_nodes[0])

        edges, logs = real_entity_graph._create_incremental_edges(
            new_nodes=new_nodes,
            max_candidates=5
        )

        # 验证关系类型
        valid_relations = {"causes", "suggests", "confirms", "rules_out",
                          "co_occurs", "differentiates", "correlates", "related"}

        for edge in edges:
            relation = edge.get("relation", "")
            assert relation in valid_relations, f"关系类型 '{relation}' 不在有效范围内"
