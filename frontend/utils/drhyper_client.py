# DrHyper API Client

from typing import Any

import requests

from ..config import DRHYPER_API_BASE


class DrHyperClient:
    """Client for interacting with DrHyper API"""

    def __init__(self, base_url: str = DRHYPER_API_BASE):
        self.base_url = base_url.rstrip('/')
        # Use synchronous requests for Streamlit compatibility
        self.timeout = 120.0

    def init_conversation(
        self,
        patient_info: dict[str, Any],
        model: str = "DrHyper"
    ) -> dict[str, Any]:
        """
        Initialize a new conversation with DrHyper

        Args:
            patient_info: Patient information dict with keys: name, age, gender
            model: Model to use (default: "DrHyper")

        Returns:
            Conversation initialization response with conversation_id and ai_message
        """
        response = requests.post(
            f"{self.base_url}/init_conversation",
            json={
                "name": patient_info.get("name"),
                "age": patient_info.get("age"),
                "gender": patient_info.get("gender"),
                "model": model
            },
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def chat(
        self,
        conversation_id: str,
        message: str,
        images: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Send a message in the conversation with optional images

        Args:
            conversation_id: Conversation ID
            message: User message
            images: Optional list of base64-encoded images (format: "data:image/type;base64,...")

        Returns:
            Chat response with ai_message and accomplish status
        """
        payload = {
            "conversation_id": conversation_id,
            "human_message": message
        }

        # Only include images if they exist
        if images:
            payload["images"] = images

        response = requests.post(
            f"{self.base_url}/chat",
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def end_conversation(
        self,
        conversation_id: str,
        in_memory: bool = False
    ) -> dict[str, Any]:
        """
        End a conversation

        Args:
            conversation_id: Conversation ID
            in_memory: Whether to keep in memory after ending

        Returns:
            End conversation response
        """
        response = requests.post(
            f"{self.base_url}/end_conversation",
            json={
                "conversation_id": conversation_id,
                "in_memory": in_memory
            },
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()

    def save_conversation(self, conversation_id: str) -> dict[str, Any]:
        """
        Save a conversation to disk

        Args:
            conversation_id: Conversation ID

        Returns:
            Save conversation response
        """
        response = requests.post(
            f"{self.base_url}/save_conversation",
            params={"conversation_id": conversation_id},
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()

    def load_conversation(self, conversation_id: str) -> dict[str, Any]:
        """
        Load a conversation from disk

        Args:
            conversation_id: Conversation ID

        Returns:
            Load conversation response
        """
        response = requests.post(
            f"{self.base_url}/load_conversation",
            params={"conversation_id": conversation_id},
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()

    def list_conversations(self) -> dict[str, Any]:
        """
        List all conversations

        Returns:
            Dict with in_memory and on_disk conversation lists
        """
        response = requests.get(
            f"{self.base_url}/list_conversations",
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()

    def update_settings(
        self,
        component: str,
        parameter: str,
        value: Any
    ) -> dict[str, Any]:
        """
        Update system settings

        Args:
            component: Component to update (e.g., "SYSTEM", "GRAPH")
            parameter: Parameter name
            value: New value

        Returns:
            Update settings response
        """
        response = requests.post(
            f"{self.base_url}/update_settings",
            json={
                "component": component,
                "parameter": parameter,
                "value": value
            },
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()
