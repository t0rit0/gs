# DrHyper API Client

from typing import Any

import httpx

from ..config import DRHYPER_API_BASE, DRHYPER_API_KEY


class DrHyperClient:
    """Client for interacting with DrHyper API"""

    def __init__(self, api_key: str = DRHYPER_API_KEY, base_url: str = DRHYPER_API_BASE):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    async def init_conversation(
        self,
        patient_info: dict[str, Any],
        target: str = "diagnosis"
    ) -> dict[str, Any]:
        """
        Initialize a new conversation with DrHyper

        Args:
            patient_info: Patient information dict
            target: Conversation target (diagnosis, followup, etc.)

        Returns:
            Conversation initialization response
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/conversation/init",
                headers=self.headers,
                json={
                    "patient_info": patient_info,
                    "target": target
                },
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def chat(
        self,
        conversation_id: str,
        message: str,
        image_refs: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Send a message in the conversation

        Args:
            conversation_id: Conversation ID
            message: User message
            image_refs: Optional list of image references

        Returns:
            Chat response with AI reply
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/conversation/chat",
                headers=self.headers,
                json={
                    "conversation_id": conversation_id,
                    "message": message,
                    "image_refs": image_refs or []
                },
                timeout=60.0
            )
            response.raise_for_status()
            return response.json()

    async def get_conversation(self, conversation_id: str) -> dict[str, Any]:
        """
        Get conversation details

        Args:
            conversation_id: Conversation ID

        Returns:
            Conversation details
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/conversation/{conversation_id}",
                headers=self.headers,
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()

    async def upload_image(self, image_path: str) -> dict[str, Any]:
        """
        Upload an image for analysis

        Args:
            image_path: Path to image file

        Returns:
            Image upload response with reference
        """
        async with httpx.AsyncClient() as client:
            with open(image_path, 'rb') as f:
                files = {'file': f}
                response = await client.post(
                    f"{self.base_url}/api/images/upload",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files=files,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()

    async def analyze_image(
        self,
        image_path: str,
        query: str,
        patient_context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Analyze a medical image

        Args:
            image_path: Path to image file
            query: Analysis query
            patient_context: Optional patient context

        Returns:
            Image analysis result
        """
        async with httpx.AsyncClient() as client:
            with open(image_path, 'rb') as f:
                files = {'file': f}
                data = {
                    'query': query,
                    'patient_context': str(patient_context) if patient_context else ''
                }
                response = await client.post(
                    f"{self.base_url}/api/images/analyze",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files=files,
                    data=data,
                    timeout=60.0
                )
                response.raise_for_status()
                return response.json()
