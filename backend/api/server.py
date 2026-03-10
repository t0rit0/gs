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
    ConversationResponse, ConversationUpdate,
    MessageResponse,
    ReportCreate, ReportResponse, ReportUpdate, ReportApproval
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


# ============================================
# Startup Event - Auto Initialize Database
# ============================================

@app.on_event("startup")
async def startup_event():
    """
    Initialize database on application startup
    
    This ensures all tables are created before handling any requests.
    Prevents 'no such table' errors on first run.
    """
    from backend.database.base import get_database_info, init_database
    
    logger.info("=" * 60)
    logger.info("Starting Medical Assistant Backend API")
    logger.info("=" * 60)
    
    logger.info("Initializing database on startup...")
    init_database()
    
    db_info = get_database_info()
    logger.info(f"Database: {db_info['url']}")
    logger.info(f"Tables: {', '.join(db_info['tables'])}")
    logger.info("✅ Database initialized successfully")
    logger.info("=" * 60)

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
        logger.exception(f"Failed to process chat: {e}")
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
    from backend.database.crud import message_crud, conversation_crud

    # Check if conversation exists first
    conv = conversation_crud.get(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

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


@app.delete(
    "/api/conversations/{conversation_id}",
    tags=["Conversations"]
)
async def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete conversation (cascades to messages and images)

    Warning: This operation is irreversible!
    """
    try:
        success = conversation_service.delete_conversation(db, conversation_id)
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"message": "Conversation deleted successfully"}
    except ValueError as e:
        logger.error(f"Value error in delete_conversation: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# MainAgent API (LangGraph-based)
# ============================================

# Initialize MainAgent singleton
_main_agent_instance = None


def get_main_agent():
    """Get or create MainAgent singleton instance"""
    global _main_agent_instance
    if _main_agent_instance is None:
        from backend.agents.main_agent import MainAgent
        _main_agent_instance = MainAgent()
        logger.info("MainAgent singleton initialized")
    return _main_agent_instance


class AgentConversationRequest(BaseModel):
    """Create agent conversation request"""
    patient_id: str
    target: str = "Hypertension diagnosis"


class AgentConversationResponse(BaseModel):
    """Create agent conversation response"""
    conversation_id: str
    patient_id: str
    first_message: str


class AgentChatRequest(BaseModel):
    """Agent chat request"""
    message: str


class AgentChatResponse(BaseModel):
    """Agent chat response"""
    ai_message: str
    accomplish: bool = False
    report: Optional[str] = None
    has_pending_operations: bool = False


class AgentEndConversationResponse(BaseModel):
    """Agent end conversation response"""
    message: str
    has_pending_operations: bool = False
    pending_operations: Optional[List[dict]] = None
    report: Optional[str] = None


class ApproveOperationsRequest(BaseModel):
    """Approve pending operations request"""
    confirm: bool = True


class ApproveOperationsResponse(BaseModel):
    """Approve pending operations response"""
    success: bool
    message: str
    executed_count: int = 0
    error: Optional[str] = None


@app.post(
    "/api/conversations/agent",
    response_model=AgentConversationResponse,
    tags=["MainAgent"]
)
async def create_agent_conversation(
    request: AgentConversationRequest,
    db: Session = Depends(get_db)
):
    """
    Create new conversation using MainAgent (LangGraph-based)

    Uses conversation_id as thread_id for LangGraph checkpointer.
    State is automatically persisted to checkpoint store.

    MainAgent replaces IntentRouter and provides:
    - Structured diagnostic data collection
    - Integration with EntityGraph
    - Sandbox-aware database queries via DataManagerCodeAgent
    """
    try:
        # Verify patient exists
        patient = patient_service.get_patient(db, request.patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail=f"Patient {request.patient_id} not found")

        # Get MainAgent instance
        agent = get_main_agent()

        # Generate unique conversation ID
        import uuid
        conversation_id = str(uuid.uuid4())

        # Start conversation via MainAgent
        first_message = await agent.astart_conversation(
            conversation_id=conversation_id,
            patient_id=request.patient_id,
            target=request.target
        )

        # Create database record
        from backend.database.crud import conversation_crud
        import datetime

        db_conv = conversation_crud.create(db, {
            "conversation_id": conversation_id,
            "patient_id": request.patient_id,
            "target": request.target,
            "model_type": "MainAgent",
            "created_at": datetime.datetime.now(datetime.UTC),
            "updated_at": datetime.datetime.now(datetime.UTC)
        })

        logger.info(f"Created MainAgent conversation: {conversation_id}")

        return AgentConversationResponse(
            conversation_id=conversation_id,
            patient_id=request.patient_id,
            first_message=first_message
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create agent conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/conversations/{conversation_id}/agent-chat",
    response_model=AgentChatResponse,
    tags=["MainAgent"]
)
async def agent_chat(
    conversation_id: str,
    request: AgentChatRequest,
    db: Session = Depends(get_db)
):
    """
    Send message to MainAgent

    State is automatically loaded/saved via thread_id by checkpointer.
    No manual state management required.

    Returns AI response along with:
    - accomplish: Whether data collection is complete
    - report: Generated diagnostic report (if complete)
    - has_pending_operations: Whether there are pending DB changes
    """
    try:
        # Verify conversation exists
        from backend.database.crud import conversation_crud
        conv = conversation_crud.get(db, conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")

        # Get MainAgent instance
        agent = get_main_agent()

        # Process message via MainAgent
        ai_message, accomplish, report = await agent.aprocess_message(
            conversation_id=conversation_id,
            user_message=request.message
        )

        # Check for pending operations
        has_pending = agent.has_pending_operations(conversation_id)

        logger.info(f"Processed agent message for {conversation_id}, accomplish={accomplish}")

        return AgentChatResponse(
            ai_message=ai_message,
            accomplish=accomplish,
            report=report,
            has_pending_operations=has_pending
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process agent chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/conversations/{conversation_id}/agent-end",
    response_model=AgentEndConversationResponse,
    tags=["MainAgent"]
)
async def end_agent_conversation(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    """
    End MainAgent conversation

    Checks for pending database operations and provides summary.
    User should be prompted to approve pending operations separately.
    """
    try:
        # Verify conversation exists
        from backend.database.crud import conversation_crud
        conv = conversation_crud.get(db, conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")

        # Get MainAgent instance
        agent = get_main_agent()

        # End conversation and get final state
        message, has_pending, pending_ops, report = await agent.end_conversation(
            conversation_id=conversation_id
        )

        logger.info(f"Ended agent conversation {conversation_id}, has_pending={has_pending}")

        return AgentEndConversationResponse(
            message=message,
            has_pending_operations=has_pending,
            pending_operations=pending_ops,
            report=report
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to end agent conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/conversations/{conversation_id}/pending-operations",
    tags=["MainAgent"]
)
async def get_pending_operations(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    """
    Get pending database operations for a conversation

    Returns a list of operations that were recorded in the sandbox
    and are awaiting user approval.
    """
    try:
        # Verify conversation exists
        from backend.database.crud import conversation_crud
        conv = conversation_crud.get(db, conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")

        # Get MainAgent instance
        agent = get_main_agent()

        # Get pending operations
        pending_ops = agent.get_pending_operations(conversation_id)

        return {
            "conversation_id": conversation_id,
            "has_pending": len(pending_ops) > 0,
            "pending_operations": pending_ops,
            "count": len(pending_ops)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pending operations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/conversations/{conversation_id}/approve-operations",
    response_model=ApproveOperationsResponse,
    tags=["MainAgent"]
)
async def approve_pending_operations(
    conversation_id: str,
    request: ApproveOperationsRequest,
    db: Session = Depends(get_db)
):
    """
    Approve and execute pending database operations

    This commits the sandbox operations to the actual database.
    Should be called after user reviews and confirms the pending changes.
    """
    try:
        # Verify conversation exists
        from backend.database.crud import conversation_crud
        conv = conversation_crud.get(db, conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")

        if not request.confirm:
            return ApproveOperationsResponse(
                success=False,
                message="Approval cancelled by user",
                executed_count=0
            )

        # Get MainAgent instance
        agent = get_main_agent()

        # Approve and execute pending operations
        result = agent.approve_and_execute_pending_operations(conversation_id)

        if result.get("success"):
            executed_count = result.get("executed_count", 0)
            logger.info(f"Approved and executed {executed_count} operations for {conversation_id}")

            return ApproveOperationsResponse(
                success=True,
                message=f"Successfully approved and executed {executed_count} database operation(s)",
                executed_count=executed_count
            )
        else:
            error = result.get("error", "Unknown error")
            logger.error(f"Failed to approve operations: {error}")

            return ApproveOperationsResponse(
                success=False,
                message="Failed to execute pending operations",
                executed_count=0,
                error=error
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to approve operations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Medical Report API
# ============================================

@app.get(
    "/api/conversations/{conversation_id}/report",
    response_model=ReportResponse,
    tags=["Reports"]
)
async def get_conversation_report(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    """
    Get the medical report for a conversation

    Returns the report if one has been generated for this conversation.
    """
    from backend.database.crud import report_crud, conversation_crud

    # Verify conversation exists
    conv = conversation_crud.get(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    report = report_crud.get_by_conversation(db, conversation_id)
    if not report:
        raise HTTPException(status_code=404, detail="No report found for this conversation")

    return report


@app.post(
    "/api/conversations/{conversation_id}/report",
    response_model=ReportResponse,
    tags=["Reports"]
)
async def create_conversation_report(
    conversation_id: str,
    report_data: ReportCreate,
    db: Session = Depends(get_db)
):
    """
    Create a medical report for a conversation

    This is typically called automatically when a report is generated,
    but can also be called manually if needed.
    """
    from backend.database.crud import report_crud, conversation_crud

    # Verify conversation exists
    conv = conversation_crud.get(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if report already exists
    existing = report_crud.get_by_conversation(db, conversation_id)
    if existing:
        raise HTTPException(status_code=400, detail="Report already exists for this conversation")

    # Create report
    report = report_crud.create(db, report_data)

    # Update conversation report_status
    conversation_crud.update(db, conversation_id, ConversationUpdate(report_status='generated'))

    logger.info(f"Created report {report.report_id} for conversation {conversation_id}")

    return report


@app.post(
    "/api/conversations/{conversation_id}/approve-report",
    response_model=ReportResponse,
    tags=["Reports"]
)
async def approve_conversation_report(
    conversation_id: str,
    approval: ReportApproval,
    db: Session = Depends(get_db)
):
    """
    Approve or reject a medical report

    After approval, the report is stored permanently and can be used
    for future consultation context.

    Args:
        approved: True to approve, False to reject
        notes: Optional notes about the approval/rejection
    """
    from backend.database.crud import report_crud, conversation_crud

    # Verify conversation exists
    conv = conversation_crud.get(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get report
    report = report_crud.get_by_conversation(db, conversation_id)
    if not report:
        raise HTTPException(status_code=404, detail="No report found for this conversation")

    if report.status != "pending":
        raise HTTPException(status_code=400, detail=f"Report already {report.status}")

    # Approve or reject
    updated_report = report_crud.approve(db, report.report_id, approval)

    # Update conversation report_status
    new_status = "approved" if approval.approved else "rejected"
    conversation_crud.update(db, conversation_id, ConversationUpdate(report_status=new_status))

    logger.info(f"Report {report.report_id} {new_status} for conversation {conversation_id}")

    return updated_report


@app.get(
    "/api/patients/{patient_id}/reports",
    response_model=List[ReportResponse],
    tags=["Reports"]
)
async def get_patient_reports(
    patient_id: str,
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get all medical reports for a patient

    Returns reports ordered by creation date (newest first).
    """
    from backend.database.crud import report_crud, patient_crud

    # Verify patient exists
    patient = patient_crud.get(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    reports, total = report_crud.list_by_patient(db, patient_id, limit=limit)
    return reports


@app.get(
    "/api/reports/{report_id}",
    response_model=ReportResponse,
    tags=["Reports"]
)
async def get_report(
    report_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific medical report by ID"""
    from backend.database.crud import report_crud

    report = report_crud.get(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return report


@app.put(
    "/api/reports/{report_id}",
    response_model=ReportResponse,
    tags=["Reports"]
)
async def update_report(
    report_id: str,
    update_data: ReportUpdate,
    db: Session = Depends(get_db)
):
    """
    Update report content

    Can only update reports that are in 'pending' status.
    """
    from backend.database.crud import report_crud

    report = report_crud.get(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if report.status != "pending":
        raise HTTPException(status_code=400, detail="Can only update pending reports")

    updated_report = report_crud.update(db, report_id, update_data)
    logger.info(f"Updated report {report_id}")

    return updated_report


@app.delete(
    "/api/reports/{report_id}",
    tags=["Reports"]
)
async def delete_report(
    report_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete a medical report

    Warning: This operation is irreversible!
    """
    from backend.database.crud import report_crud

    success = report_crud.delete(db, report_id)
    if not success:
        raise HTTPException(status_code=404, detail="Report not found")

    logger.info(f"Deleted report {report_id}")
    return {"message": "Report deleted successfully"}


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
