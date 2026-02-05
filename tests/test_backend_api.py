"""
Backend API Integration Tests

测试 Backend API 的各个端点功能
运行: pytest tests/test_backend_api.py -v
"""
import pytest
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def api_base_url():
    """API 基础 URL"""
    return "http://localhost:8000"


@pytest.fixture
def patient_data():
    """测试患者数据"""
    return {
        "name": "测试患者",
        "age": 45,
        "gender": "male",
        "phone": "13800138000",
        "address": "北京市朝阳区"
    }


@pytest.fixture
def conversation_data():
    """测试对话数据"""
    return {
        "target": "高血压诊断",
        "model_type": "DrHyper"
    }


# ============================================
# Tests
# ============================================

class TestHealthCheck:
    """健康检查测试"""

    def test_health_endpoint(self, api_base_url):
        """测试健康检查端点"""
        import requests

        response = requests.get(f"{api_base_url}/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
        assert "version" in data


class TestPatientsAPI:
    """患者管理 API 测试"""

    def test_create_patient(self, api_base_url, patient_data):
        """测试创建患者"""
        import requests

        response = requests.post(f"{api_base_url}/api/patients", json=patient_data)

        assert response.status_code == 200
        data = response.json()
        assert "patient_id" in data
        assert data["name"] == patient_data["name"]
        assert data["age"] == patient_data["age"]
        assert data["gender"] == patient_data["gender"]

    def test_get_patient(self, api_base_url, patient_data):
        """测试获取患者信息"""
        import requests

        # 先创建患者
        create_response = requests.post(f"{api_base_url}/api/patients", json=patient_data)
        patient_id = create_response.json()["patient_id"]

        # 获取患者信息
        response = requests.get(f"{api_base_url}/api/patients/{patient_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["patient_id"] == patient_id
        assert data["name"] == patient_data["name"]

    def test_list_patients(self, api_base_url):
        """测试列出患者"""
        import requests

        response = requests.get(f"{api_base_url}/api/patients")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_update_patient(self, api_base_url, patient_data):
        """测试更新患者信息"""
        import requests

        # 先创建患者
        create_response = requests.post(f"{api_base_url}/api/patients", json=patient_data)
        patient_id = create_response.json()["patient_id"]

        # 更新患者
        update_data = {"age": 50}
        response = requests.put(
            f"{api_base_url}/api/patients/{patient_id}",
            json=update_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["age"] == 50

    def test_delete_patient(self, api_base_url, patient_data):
        """测试删除患者"""
        import requests

        # 先创建患者
        create_response = requests.post(f"{api_base_url}/api/patients", json=patient_data)
        patient_id = create_response.json()["patient_id"]

        # 删除患者
        response = requests.delete(f"{api_base_url}/api/patients/{patient_id}")

        assert response.status_code == 200

        # 验证已删除
        get_response = requests.get(f"{api_base_url}/api/patients/{patient_id}")
        assert get_response.status_code == 404


class TestConversationsAPI:
    """对话管理 API 测试"""

    @pytest.fixture(autouse=True)
    def setup_patient(self, api_base_url, patient_data):
        """每个测试前创建一个患者"""
        import requests

        response = requests.post(f"{api_base_url}/api/patients", json=patient_data)
        self.patient_id = response.json()["patient_id"]

    def test_create_conversation(self, api_base_url, conversation_data):
        """测试创建对话"""
        import requests

        request_data = {
            "patient_id": self.patient_id,
            **conversation_data
        }

        response = requests.post(
            f"{api_base_url}/api/conversations",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert "conversation_id" in data
        assert data["patient_id"] == self.patient_id
        assert "ai_message" in data
        assert "drhyper_state" in data

    def test_create_conversation_invalid_patient(self, api_base_url, conversation_data):
        """测试使用无效 patient_id 创建对话"""
        import requests

        request_data = {
            "patient_id": "invalid-uuid",
            **conversation_data
        }

        response = requests.post(
            f"{api_base_url}/api/conversations",
            json=request_data
        )

        assert response.status_code == 404

    def test_get_conversation(self, api_base_url, conversation_data):
        """测试获取对话信息"""
        import requests

        # 先创建对话
        create_data = {
            "patient_id": self.patient_id,
            **conversation_data
        }
        create_response = requests.post(
            f"{api_base_url}/api/conversations",
            json=create_data
        )
        conversation_id = create_response.json()["conversation_id"]

        # 获取对话
        response = requests.get(f"{api_base_url}/api/conversations/{conversation_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["conversation_id"] == conversation_id
        assert data["target"] == conversation_data["target"]

    def test_chat(self, api_base_url, conversation_data):
        """测试发送消息"""
        import requests

        # 先创建对话
        create_data = {
            "patient_id": self.patient_id,
            **conversation_data
        }
        create_response = requests.post(
            f"{api_base_url}/api/conversations",
            json=create_data
        )
        conversation_id = create_response.json()["conversation_id"]

        # 发送消息
        chat_data = {
            "message": "我最近血压有点高",
            "images": None
        }
        response = requests.post(
            f"{api_base_url}/api/conversations/{conversation_id}/chat",
            json=chat_data
        )

        assert response.status_code == 200
        data = response.json()
        assert "ai_message" in data
        assert "accomplish" in data
        assert "drhyper_state" in data
        assert isinstance(data["accomplish"], bool)

    def test_get_conversation_messages(self, api_base_url, conversation_data):
        """测试获取对话消息历史"""
        import requests

        # 先创建对话
        create_data = {
            "patient_id": self.patient_id,
            **conversation_data
        }
        create_response = requests.post(
            f"{api_base_url}/api/conversations",
            json=create_data
        )
        conversation_id = create_response.json()["conversation_id"]

        # 获取消息历史
        response = requests.get(
            f"{api_base_url}/api/conversations/{conversation_id}/messages"
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # 至少有一条初始化消息
        assert len(data) >= 1

    def test_end_conversation(self, api_base_url, conversation_data):
        """测试结束对话"""
        import requests

        # 先创建对话
        create_data = {
            "patient_id": self.patient_id,
            **conversation_data
        }
        create_response = requests.post(
            f"{api_base_url}/api/conversations",
            json=create_data
        )
        conversation_id = create_response.json()["conversation_id"]

        # 结束对话
        response = requests.post(
            f"{api_base_url}/api/conversations/{conversation_id}/end"
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "final_state" in data

    def test_get_patient_conversations(self, api_base_url):
        """测试获取患者的对话列表"""
        import requests

        response = requests.get(
            f"{api_base_url}/api/patients/{self.patient_id}/conversations"
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_delete_conversation(self, api_base_url, conversation_data):
        """测试删除对话"""
        import requests

        # 先创建对话
        create_data = {
            "patient_id": self.patient_id,
            **conversation_data
        }
        create_response = requests.post(
            f"{api_base_url}/api/conversations",
            json=create_data
        )
        conversation_id = create_response.json()["conversation_id"]

        # 删除对话
        response = requests.delete(
            f"{api_base_url}/api/conversations/{conversation_id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data

        # 验证已删除
        get_response = requests.get(
            f"{api_base_url}/api/conversations/{conversation_id}"
        )
        assert get_response.status_code == 404

    def test_delete_conversation_invalid_id(self, api_base_url):
        """测试删除不存在的对话"""
        import requests

        response = requests.delete(
            f"{api_base_url}/api/conversations/invalid-conversation-id"
        )

        assert response.status_code == 404

    def test_delete_conversation_cascade_messages(self, api_base_url, conversation_data):
        """测试删除对话时级联删除消息"""
        import requests

        # 先创建对话
        create_data = {
            "patient_id": self.patient_id,
            **conversation_data
        }
        create_response = requests.post(
            f"{api_base_url}/api/conversations",
            json=create_data
        )
        conversation_id = create_response.json()["conversation_id"]

        # 验证初始消息存在（创建对话时会自动生成一条欢迎消息）
        messages_before = requests.get(
            f"{api_base_url}/api/conversations/{conversation_id}/messages"
        )
        assert messages_before.status_code == 200
        initial_message_count = len(messages_before.json())
        assert initial_message_count >= 1  # 至少有一条初始化消息

        # 删除对话
        delete_response = requests.delete(
            f"{api_base_url}/api/conversations/{conversation_id}"
        )
        assert delete_response.status_code == 200

        # 验证对话已被删除
        conv_response = requests.get(
            f"{api_base_url}/api/conversations/{conversation_id}"
        )
        assert conv_response.status_code == 404

        # 验证消息也无法访问（对话不存在时返回404）
        messages_response = requests.get(
            f"{api_base_url}/api/conversations/{conversation_id}/messages"
        )
        # 对话不存在，消息API也应该返回404
        assert messages_response.status_code == 404


class TestAPIIntegration:
    """API 集成测试 - 完整流程"""

    def test_complete_conversation_flow(self, api_base_url):
        """测试完整的对话流程"""
        import requests

        # 1. 创建患者
        patient_data = {
            "name": "流程测试患者",
            "age": 50,
            "gender": "male"
        }
        patient_response = requests.post(
            f"{api_base_url}/api/patients",
            json=patient_data
        )
        assert patient_response.status_code == 200
        patient_id = patient_response.json()["patient_id"]

        # 2. 创建对话
        conv_data = {
            "patient_id": patient_id,
            "target": "高血压诊断"
        }
        conv_response = requests.post(
            f"{api_base_url}/api/conversations",
            json=conv_data
        )
        assert conv_response.status_code == 200
        conversation_id = conv_response.json()["conversation_id"]
        assert "ai_message" in conv_response.json()

        # 3. 发送第一条消息
        chat_response1 = requests.post(
            f"{api_base_url}/api/conversations/{conversation_id}/chat",
            json={"message": "我血压有点高", "images": None}
        )
        assert chat_response1.status_code == 200
        assert "ai_message" in chat_response1.json()

        # 4. 发送第二条消息
        chat_response2 = requests.post(
            f"{api_base_url}/api/conversations/{conversation_id}/chat",
            json={"message": "大概150/95左右", "images": None}
        )
        assert chat_response2.status_code == 200
        assert "ai_message" in chat_response2.json()

        # 5. 获取消息历史
        messages_response = requests.get(
            f"{api_base_url}/api/conversations/{conversation_id}/messages"
        )
        assert messages_response.status_code == 200
        messages = messages_response.json()
        # 初始消息 + 2条用户消息 + 2条AI回复
        assert len(messages) >= 5

        # 6. 结束对话
        end_response = requests.post(
            f"{api_base_url}/api/conversations/{conversation_id}/end"
        )
        assert end_response.status_code == 200

        # 7. 验证对话状态
        conv = requests.get(f"{api_base_url}/api/conversations/{conversation_id}").json()
        assert conv["status"] == "completed"


# ============================================
# Run Tests
# ============================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
