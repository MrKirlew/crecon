"""
Location-Triggered Question Flow API Endpoints
"""
import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from uuid import uuid4

from models import (
    LocationRequest, LocationResponse,
    QuestionRequest, QuestionResponse,
    ScheduleRequest, ScheduleResponse,
    AnswerRequest, AnswerResponse,
    LocationTriggerRequest,
    QueuedQuestionResponse,
    ConversationStateRequest, ConversationStateResponse
)
from location_service import LocationService
from question_service import QuestionService
from recurrence_service import RecurrenceService
from sheets_logger import SheetsLogger
from n8n_bridge import N8NBridge, get_n8n_bridge
from config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/location", tags=["location-triggered-questions"])


# Global service instances (singleton pattern)
_location_service: Optional[LocationService] = None
_question_service: Optional[QuestionService] = None
_recurrence_service: Optional[RecurrenceService] = None
_missing_sheet_warning_logged = False
settings = get_settings()


def get_location_service() -> LocationService:
    """Get or create location service"""
    global _location_service
    if _location_service is None:
        _location_service = LocationService()
    return _location_service


def get_recurrence_service() -> RecurrenceService:
    """Get or create recurrence service"""
    global _recurrence_service
    if _recurrence_service is None:
        _recurrence_service = RecurrenceService()
    return _recurrence_service


def get_question_service() -> QuestionService:
    """Get or create question service"""
    global _question_service
    if _question_service is None:
        location_service = get_location_service()
        recurrence_service = get_recurrence_service()
        _question_service = QuestionService(location_service, recurrence_service)
    return _question_service


def get_sheets_logger(n8n_bridge: N8NBridge = Depends(get_n8n_bridge)) -> SheetsLogger:
    """Get or create sheets logger"""
    global _missing_sheet_warning_logged
    spreadsheet_id = settings.location_questions_spreadsheet_id

    if not spreadsheet_id and not _missing_sheet_warning_logged:
        logger.warning(
            "location_questions_spreadsheet_id is not configured; Q&A logging will be skipped"
        )
        _missing_sheet_warning_logged = True

    return SheetsLogger(n8n_bridge, spreadsheet_id=spreadsheet_id)


# ==================== Location Endpoints ====================

@router.post("/locations", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
async def create_location(
    request: LocationRequest,
    location_service: LocationService = Depends(get_location_service)
):
    """Create a new location"""
    location = location_service.create_location(
        name=request.name,
        latitude=request.latitude,
        longitude=request.longitude,
        radius_meters=request.radius_meters,
        description=request.description
    )
    return LocationResponse(**location.to_dict())


@router.get("/locations", response_model=List[LocationResponse])
async def list_locations(
    location_service: LocationService = Depends(get_location_service)
):
    """List all locations"""
    locations = location_service.list_locations()
    return [LocationResponse(**loc.to_dict()) for loc in locations]


@router.get("/locations/{location_id}", response_model=LocationResponse)
async def get_location(
    location_id: str,
    location_service: LocationService = Depends(get_location_service)
):
    """Get a location by ID"""
    location = location_service.get_location(location_id)
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return LocationResponse(**location.to_dict())


@router.put("/locations/{location_id}", response_model=LocationResponse)
async def update_location(
    location_id: str,
    request: LocationRequest,
    location_service: LocationService = Depends(get_location_service)
):
    """Update a location"""
    location = location_service.update_location(
        location_id=location_id,
        name=request.name,
        latitude=request.latitude,
        longitude=request.longitude,
        radius_meters=request.radius_meters,
        description=request.description
    )
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return LocationResponse(**location.to_dict())


@router.delete("/locations/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(
    location_id: str,
    location_service: LocationService = Depends(get_location_service)
):
    """Delete a location"""
    success = location_service.delete_location(location_id)
    if not success:
        raise HTTPException(status_code=404, detail="Location not found")


# ==================== Question Endpoints ====================

@router.post("/questions", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED)
async def create_question(
    request: QuestionRequest,
    question_service: QuestionService = Depends(get_question_service)
):
    """Create a new question"""
    question = question_service.create_question(
        location_id=request.location_id,
        question_text=request.question_text,
        question_type=request.question_type,
        order=request.order,
        recurrence=request.recurrence.dict() if request.recurrence else None,
        throttle=request.throttle.dict() if request.throttle else None,
        enabled=request.enabled
    )
    return QuestionResponse(**question.to_dict())


@router.get("/locations/{location_id}/questions", response_model=List[QuestionResponse])
async def get_questions_for_location(
    location_id: str,
    question_service: QuestionService = Depends(get_question_service)
):
    """Get all questions for a location"""
    questions = question_service.get_questions_for_location(location_id)
    return [QuestionResponse(**q.to_dict()) for q in questions]


# ==================== Schedule Endpoints ====================

@router.post("/schedules", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    request: ScheduleRequest,
    question_service: QuestionService = Depends(get_question_service)
):
    """Create a new schedule with questions"""
    # Create questions first
    questions = []
    for q_req in request.questions:
        question = question_service.create_question(
            location_id=q_req.location_id,
            question_text=q_req.question_text,
            question_type=q_req.question_type,
            order=q_req.order,
            recurrence=q_req.recurrence.dict() if q_req.recurrence else None,
            throttle=q_req.throttle.dict() if q_req.throttle else None,
            enabled=q_req.enabled
        )
        questions.append(question)
    
    # Create schedule
    schedule = question_service.create_schedule(
        location_id=request.location_id,
        questions=questions,
        name=request.name
    )
    return ScheduleResponse(**schedule.to_dict())


@router.get("/locations/{location_id}/schedules", response_model=List[ScheduleResponse])
async def get_schedules_for_location(
    location_id: str,
    question_service: QuestionService = Depends(get_question_service)
):
    """Get all schedules for a location"""
    schedules = question_service.get_schedules_for_location(location_id)
    return [ScheduleResponse(**s.to_dict()) for s in schedules]


# ==================== Location Trigger Endpoints ====================

@router.post("/trigger", response_model=List[QueuedQuestionResponse])
async def trigger_location(
    request: LocationTriggerRequest,
    location_service: LocationService = Depends(get_location_service),
    question_service: QuestionService = Depends(get_question_service)
):
    """
    Trigger when device enters a location
    Returns queued questions that should be asked
    """
    # Find location
    nearby_locations = location_service.find_nearby_locations(
        request.latitude,
        request.longitude
    )
    
    if not nearby_locations:
        return []
    
    # Get queued questions for all nearby locations
    all_queued = []
    for location in nearby_locations:
        questions = question_service.queue_questions_for_location(
            location.id,
            current_time=request.timestamp
        )
        
        # Get schedule for location (assuming one schedule per location for now)
        schedules = question_service.get_schedules_for_location(location.id)
        schedule_id = schedules[0].id if schedules else str(uuid4())
        
        for question in questions:
            all_queued.append(QueuedQuestionResponse(
                question_id=question.id,
                question_text=question.question_text,
                question_type=question.question_type,
                order=question.order,
                location_id=location.id,
                location_name=location.name,
                schedule_id=schedule_id
            ))
    
    return all_queued


@router.post("/conversation/start", response_model=ConversationStateResponse)
async def start_conversation(
    location_id: str,
    schedule_id: Optional[str] = None,
    question_service: QuestionService = Depends(get_question_service),
    location_service: LocationService = Depends(get_location_service)
):
    """Start a conversation session for a location"""
    # Get questions
    if schedule_id:
        schedule = question_service.schedules.get(schedule_id)
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        questions = schedule.questions
    else:
        questions = question_service.get_questions_for_location(location_id)
    
    if not questions:
        raise HTTPException(status_code=404, detail="No questions found for location")
    
    # Get schedule ID
    if not schedule_id:
        schedules = question_service.get_schedules_for_location(location_id)
        schedule_id = schedules[0].id if schedules else str(uuid4())
    
    # Create session
    session = question_service.create_conversation_session(
        location_id=location_id,
        schedule_id=schedule_id,
        questions=questions
    )
    
    # Get first question
    first_question = session.get_current_question()
    location = location_service.get_location(location_id)
    
    return ConversationStateResponse(
        session_id=session.session_id,
        current_question_id=first_question.id if first_question else None,
        next_question=QueuedQuestionResponse(
            question_id=first_question.id,
            question_text=first_question.question_text,
            question_type=first_question.question_type,
            order=first_question.order,
            location_id=location_id,
            location_name=location.name if location else "Unknown",
            schedule_id=schedule_id
        ) if first_question else None,
        conversation_active=True,
        message=first_question.question_text if first_question else "No questions available",
        should_continue=first_question is not None
    )


@router.post("/conversation/state", response_model=ConversationStateResponse)
async def update_conversation_state(
    request: ConversationStateRequest,
    background_tasks: BackgroundTasks,
    question_service: QuestionService = Depends(get_question_service),
    sheets_logger: SheetsLogger = Depends(get_sheets_logger),
    location_service: LocationService = Depends(get_location_service)
):
    """Update conversation state with user message"""
    result = question_service.process_conversation_message(
        request.session_id,
        request.message
    )
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    session = question_service.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get location info
    location = location_service.get_location(session.location_id)
    
    # Log answer if we just answered a question
    if result.get("current_question_id") and request.message:
        # Check if this was an answer (not a "next topic" command)
        message_lower = request.message.lower().strip()
        next_phrases = ["next topic", "next question", "move on", "skip", "next"]
        is_next_command = any(phrase in message_lower for phrase in next_phrases)
        
        if not is_next_command:
            # Record answer
            current_q = session.get_current_question()
            if current_q:
                answer_record = question_service.record_answer(
                    question_id=current_q.id,
                    location_id=session.location_id,
                    answer_text=request.message,
                    delivery_channel="app"
                )
                
                # Log to sheets in background
                background_tasks.add_task(
                    sheets_logger.log_qa_pair,
                    question_id=current_q.id,
                    question_text=current_q.question_text,
                    answer_text=request.message,
                    location_id=session.location_id,
                    location_name=location.name if location else "Unknown",
                    schedule_id=session.schedule_id,
                    delivery_channel="app",
                    timestamp=answer_record["timestamp"]
                )
    
    # Build response
    next_q_data = result.get("next_question")
    next_question = None
    if next_q_data:
        next_question = QueuedQuestionResponse(**next_q_data)
    
    return ConversationStateResponse(
        session_id=result["session_id"],
        current_question_id=result.get("current_question_id"),
        next_question=next_question,
        conversation_active=result["conversation_active"],
        message=result["message"],
        should_continue=result.get("should_continue", True)
    )


# ==================== Answer Endpoints ====================

@router.post("/answers", response_model=AnswerResponse, status_code=status.HTTP_201_CREATED)
async def submit_answer(
    request: AnswerRequest,
    background_tasks: BackgroundTasks,
    question_service: QuestionService = Depends(get_question_service),
    sheets_logger: SheetsLogger = Depends(get_sheets_logger),
    location_service: LocationService = Depends(get_location_service)
):
    """Submit an answer to a question"""
    # Get question
    question = question_service.questions.get(request.question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    # Get location
    location = location_service.get_location(request.location_id)
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    
    # Record answer
    answer_record = question_service.record_answer(
        question_id=request.question_id,
        location_id=request.location_id,
        answer_text=request.answer_text,
        delivery_channel=request.delivery_channel,
        timestamp=request.timestamp
    )
    
    # Log to sheets in background
    background_tasks.add_task(
        sheets_logger.log_qa_pair,
        question_id=request.question_id,
        question_text=question.question_text,
        answer_text=request.answer_text,
        location_id=request.location_id,
        location_name=location.name,
        schedule_id="",  # TODO: Get from context
        delivery_channel=request.delivery_channel,
        timestamp=request.timestamp
    )
    
    return AnswerResponse(
        id=answer_record["id"],
        question_id=answer_record["question_id"],
        location_id=answer_record["location_id"],
        answer_text=answer_record["answer_text"],
        timestamp=answer_record["timestamp"],
        delivery_channel=answer_record["delivery_channel"],
        logged_to_sheets=True
    )
