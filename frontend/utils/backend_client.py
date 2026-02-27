# Backend API Client for Medical Assistant System

from datetime import datetime
from typing import Any
import requests

from ..config import BACKEND_API_BASE


class BackendClient:
    """Client for interacting with the Medical Assistant Backend API"""

    def __init__(self, base_url: str = BACKEND_API_BASE):
        self.base_url = base_url.rstrip('/')
        self.timeout = 3600.0

    def _request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        """Internal request handler with error handling"""
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.request(
                method,
                url,
                timeout=self.timeout,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response is not None:
                error_detail = e.response.json().get("detail", str(e))
                raise Exception(error_detail) from e
            raise Exception(str(e)) from e
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error: {str(e)}") from e

    # ============================================
    # Health Check
    # ============================================

    def health_check(self) -> dict[str, Any]:
        """Check backend health"""
        return self._request("GET", "/health")

    # ============================================
    # Patient Management
    # ============================================

    def create_patient(self, patient_data: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new patient

        Args:
            patient_data: Patient information dict

        Returns:
            Created patient response with patient_id
        """
        return self._request("POST", "/api/patients", json=patient_data)

    def get_patient(self, patient_id: str) -> dict[str, Any]:
        """Get patient by ID"""
        return self._request("GET", f"/api/patients/{patient_id}")

    def list_patients(
        self,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None
    ) -> list[dict[str, Any]]:
        """
        List patients with pagination and search

        Args:
            skip: Number of records to skip
            limit: Maximum records to return
            search: Optional search term for patient name

        Returns:
            List of patient dicts
        """
        params = {"skip": skip, "limit": limit}
        if search:
            params["search"] = search
        return self._request("GET", "/api/patients", params=params)

    def update_patient(self, patient_id: str, update_data: dict[str, Any]) -> dict[str, Any]:
        """Update patient information"""
        return self._request("PUT", f"/api/patients/{patient_id}", json=update_data)

    def delete_patient(self, patient_id: str) -> dict[str, Any]:
        """Delete a patient (cascades to conversations)"""
        return self._request("DELETE", f"/api/patients/{patient_id}")

    # ============================================
    # Conversation Management
    # ============================================

    def create_conversation(
        self,
        patient_id: str,
        target: str = "Hypertension diagnosis",
        model_type: str = "DrHyper"
    ) -> dict[str, Any]:
        """
        Create a new conversation

        Args:
            patient_id: Patient ID
            target: Conversation goal/diagnosis target
            model_type: Model type (default: "DrHyper")

        Returns:
            Conversation response with conversation_id, ai_message, drhyper_state
        """
        payload = {
            "patient_id": patient_id,
            "target": target,
            "model_type": model_type
        }
        return self._request("POST", "/api/conversations", json=payload)

    def get_conversation(self, conversation_id: str) -> dict[str, Any]:
        """Get conversation details"""
        return self._request("GET", f"/api/conversations/{conversation_id}")

    def get_conversation_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        """Get all messages in a conversation"""
        return self._request("GET", f"/api/conversations/{conversation_id}/messages")

    def get_patient_conversations(
        self,
        patient_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get all conversations for a patient"""
        params = {"skip": skip, "limit": limit}
        return self._request("GET", f"/api/patients/{patient_id}/conversations", params=params)

    def chat(
        self,
        conversation_id: str,
        message: str,
        images: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Send a message in a conversation

        Args:
            conversation_id: Conversation ID
            message: User message
            images: Optional list of base64-encoded images

        Returns:
            Chat response with ai_message, accomplish, analysis_report, drhyper_state
        """
        payload = {"message": message}
        if images:
            payload["images"] = images
        return self._request("POST", f"/api/conversations/{conversation_id}/chat", json=payload)

    def end_conversation(self, conversation_id: str) -> dict[str, Any]:
        """End a conversation"""
        return self._request("POST", f"/api/conversations/{conversation_id}/end")

    def delete_conversation(self, conversation_id: str) -> dict[str, Any]:
        """Delete a conversation (cascades to messages and images)"""
        return self._request("DELETE", f"/api/conversations/{conversation_id}")

    # ============================================
    # Medical Report Management
    # ============================================

    def get_report(self, conversation_id: str) -> dict[str, Any]:
        """Get report for a conversation"""
        return self._request("GET", f"/api/conversations/{conversation_id}/report")

    def create_report(
        self,
        conversation_id: str,
        patient_id: str,
        report_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a new medical report"""
        payload = {
            "patient_id": patient_id,
            "conversation_id": conversation_id,
            **report_data
        }
        return self._request("POST", f"/api/conversations/{conversation_id}/report", json=payload)

    def approve_report(
        self,
        conversation_id: str,
        approved: bool,
        notes: str | None = None
    ) -> dict[str, Any]:
        """
        Approve or reject a report

        Args:
            conversation_id: Conversation ID
            approved: True to approve, False to reject
            notes: Optional notes about the decision
        """
        payload = {"approved": approved}
        if notes:
            payload["notes"] = notes
        return self._request("POST", f"/api/conversations/{conversation_id}/approve-report", json=payload)

    def update_report(
        self,
        conversation_id: str,
        report_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update report content before approval"""
        return self._request("PUT", f"/api/conversations/{conversation_id}/report", json=report_data)

    def get_patient_reports(
        self,
        patient_id: str,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get all reports for a patient"""
        return self._request("GET", f"/api/patients/{patient_id}/reports", params={"limit": limit})

    def get_pending_operations(self, conversation_id: str) -> dict[str, Any]:
        """Get pending database operations for a conversation"""
        return self._request("GET", f"/api/conversations/{conversation_id}/pending-operations")

    def approve_operations(
        self,
        conversation_id: str,
        confirm: bool = True
    ) -> dict[str, Any]:
        """
        Approve or reject pending database operations

        Args:
            conversation_id: Conversation ID
            confirm: True to approve and execute, False to reject

        Returns:
            Result with executed_count on success
        """
        payload = {"confirm": confirm}
        return self._request("POST", f"/api/conversations/{conversation_id}/approve-operations", json=payload)
