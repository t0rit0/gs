"""
Backend API Server - FastAPI Application

This API server references drhyper/api/server.py endpoint design
But uses database for persistence instead of in-memory management

Main endpoints:
- Patient management: POST/GET/PUT /api/patients
- Conversation management: POST /api/conversations
- Message handling: POST /api/conversations/{id}/chat
- Conversation history: GET /api/conversations/{id}
"""
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel

# Database related
from backend.database.base import get_db
from backend.database.schemas import (
    PatientCreate, PatientResponse, PatientUpdate,
    ConversationResponse,
    MessageResponse
)

# Service layer
from backend.services.patient_service import patient_service
from backend.services.conversation_service import conversation_service

# Logging
from drhyper.utils.logging import get_logger

logger = get_logger("BackendAPI")

# ============================================
# FastAPI Application
# ============================================

app = FastAPI(
    title="Medical Assistant Backend API",
    description="Medical Assistant System Backend API - Integrates DrHyper conversation engine and database",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Need to restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# Request/Response Models
# ============================================

class InitConversationRequest(BaseModel):
    """Create conversation request - Reference drHyper InitConversationRequest"""
    patient_id: str
    target: str = "Hypertension diagnosis"
    model_type: str = "DrHyper"


class InitConversationResponse(BaseModel):
    """Create conversation response"""
    conversation_id: str
    patient_id: str
    ai_message: str
    drhyper_state: dict


class ChatRequest(BaseModel):
    """Chat request - Reference drHyper ChatRequest"""
    message: str
    images: Optional[List[str]] = None  # base64-encoded images


class ChatResponse(BaseModel):
    """Chat response - Reference drHyper ChatResponse"""
    ai_message: str
    accomplish: bool = False
    analysis_report: Optional[dict] = None
    drhyper_state: dict


class EndConversationResponse(BaseModel):
    """End conversation response"""
    message: str
    final_state: dict


# ============================================
# Health Check
# ============================================

@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Medical Assistant Backend Service",
        "version": "2.0.0"
    }


# ============================================
# Patient Management API
# ============================================

@app.post("/api/patients", response_model=PatientResponse, tags=["Patients"])
async def create_patient(
    patient: PatientCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new patient

    Corresponds to: Patient basic information management
    """
    try:
        db_patient = patient_service.create_patient(db, patient)
        logger.info(f"Created patient: {db_patient.patient_id}")
        return db_patient
    except Exception as e:
        logger.error(f"Failed to create patient: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/patients/{patient_id}", response_model=PatientResponse, tags=["Patients"])
async def get_patient(
    patient_id: str,
    db: Session = Depends(get_db)
):
    """Get patient information"""
    patient = patient_service.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@app.get("/api/patients", response_model=List[PatientResponse], tags=["Patients"])
async def list_patients(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get patient list (supports pagination and search)

    - skip: Number of records to skip
    - limit: Maximum number of records to return
    - search: Search by name (optional)
    """
    patients, total = patient_service.list_patients(db, skip, limit, search)
    return patients


@app.put("/api/patients/{patient_id}", response_model=PatientResponse, tags=["Patients"])
async def update_patient(
    patient_id: str,
    update_data: PatientUpdate,
    db: Session = Depends(get_db)
):
    """Update patient information"""
    patient = patient_service.update_patient(db, patient_id, update_data)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@app.delete("/api/patients/{patient_id}", tags=["Patients"])
async def delete_patient(
    patient_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete patient (cascades to related conversations and messages)

    Warning: This operation is irreversible!
    """
    success = patient_service.delete_patient(db, patient_id)
    if not success:
        raise HTTPException(status_code=404, detail="Patient not found")
    return {"message": "Patient deleted successfully"}


# ============================================
# Conversation Management API
# ============================================

@app.post(
    "/api/conversations",
    response_model=InitConversationResponse,
    tags=["Conversations"]
)
async def create_conversation(
    request: InitConversationRequest,
    db: Session = Depends(get_db)
):
    """
    Create a new conversation

    Reference: drhyper POST /init_conversation
    """
    try:
        conversation_id, ai_message, drhyper_state = conversation_service.create_conversation(
            db,
            request.patient_id,
            request.target,
            request.model_type
        )

        logger.info(f"Created conversation: {conversation_id}")

        return InitConversationResponse(
            conversation_id=conversation_id,
            patient_id=request.patient_id,
            ai_message=ai_message,
            drhyper_state=drhyper_state
        )

    except ValueError as e:
        logger.error(f"Value error in create_conversation: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/conversations/{conversation_id}/chat",
    response_model=ChatResponse,
    tags=["Conversations"]
)
async def chat(
    conversation_id: str,
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    Send message and get AI response

    Reference: drhyper POST /chat

    Supports text messages and optional images (base64 encoded)
    """
    try:
        ai_response, accomplish, analysis_report, drhyper_state = conversation_service.process_message(
            db,
            conversation_id,
            request.message,
            request.images
        )

        logger.info(f"Processed message for conversation {conversation_id}")

        return ChatResponse(
            ai_message=ai_response,
            accomplish=accomplish,
            analysis_report=analysis_report,
            drhyper_state=drhyper_state
        )

    except ValueError as e:
        logger.error(f"Value error in chat: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to process chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/conversations/{conversation_id}/end",
    response_model=EndConversationResponse,
    tags=["Conversations"]
)
async def end_conversation(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    """
    End conversation

    Reference: drhyper POST /end_conversation
    """
    try:
        final_state = conversation_service.end_conversation(db, conversation_id)

        logger.info(f"Ended conversation {conversation_id}")

        return EndConversationResponse(
            message="Conversation ended successfully",
            final_state=final_state
        )

    except ValueError as e:
        logger.error(f"Value error in end_conversation: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to end conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/conversations/{conversation_id}",
    response_model=ConversationResponse,
    tags=["Conversations"]
)
async def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    """Get conversation information"""
    from backend.database.crud import conversation_crud

    conv = conversation_crud.get(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return conv


@app.get(
    "/api/conversations/{conversation_id}/messages",
    response_model=List[MessageResponse],
    tags=["Conversations"]
)
async def get_conversation_messages(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    """Get all messages in a conversation"""
    from backend.database.crud import message_crud

    messages = message_crud.list_by_conversation(db, conversation_id)
    return messages


@app.get(
    "/api/patients/{patient_id}/conversations",
    response_model=List[ConversationResponse],
    tags=["Conversations"]
)
async def get_patient_conversations(
    patient_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    Get all conversations for a patient

    Supports pagination
    """
    from backend.database.crud import conversation_crud

    conversations, total = conversation_crud.list_by_patient(
        db, patient_id, skip, limit
    )

    return conversations


# ============================================
# Startup Instructions
# ============================================

if __name__ == "__main__":
    import uvicorn

    logger.info("Starting Medical Assistant Backend API service...")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
