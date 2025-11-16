"""
Pydantic Models for Request/Response Validation
Enforces strict schemas to prevent cost exploitation and injection attacks
"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime


# ==================== Chat Models ====================

class ChatMessage(BaseModel):
    """Individual chat message"""
    role: str = Field(..., description="Message role: 'user', 'assistant', or 'system'")
    content: str = Field(..., min_length=1, max_length=10000, description="Message content")

    @validator('role')
    def validate_role(cls, v):
        if v not in ['user', 'assistant', 'system']:
            raise ValueError("Role must be 'user', 'assistant', or 'system'")
        return v


class ChatRequest(BaseModel):
    """Chat completion request"""
    messages: List[ChatMessage] = Field(..., min_items=1, max_items=50)
    use_rag: bool = Field(default=True, description="Enable RAG context retrieval")
    rag_filters: Optional[Dict[str, Any]] = Field(default=None, description="RAG metadata filters")
    model: Optional[str] = Field(default=None, description="Override default LLM model")
    max_tokens: Optional[int] = Field(default=2000, ge=1, le=4000)
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    enable_tools: bool = Field(default=True, description="Enable N8N workflow execution")
    user_id: Optional[str] = Field(default=None, description="User identifier for tracking")
    user_name: Optional[str] = Field(default=None, description="User's full name from settings")
    user_latitude: Optional[float] = Field(default=None, ge=-90, le=90, description="User's current latitude")
    user_longitude: Optional[float] = Field(default=None, ge=-180, le=180, description="User's current longitude")


class TokenUsageResponse(BaseModel):
    """Token usage and cost information"""
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    model: str
    rag_context_tokens: int = 0
    conversation_history_tokens: int = 0


class ChatResponse(BaseModel):
    """Chat completion response"""
    message: str
    usage: TokenUsageResponse
    rag_used: bool = False
    rag_sources: Optional[List[Dict]] = None
    tool_calls: Optional[List[Dict]] = None
    model: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# ==================== RAG Models ====================

class DocumentIndexRequest(BaseModel):
    """Request to index a document for RAG"""
    document_id: str = Field(..., min_length=1, max_length=200)
    text: str = Field(..., min_length=1, max_length=100000)
    metadata: Optional[Dict[str, Any]] = Field(default=None)


class DocumentBatchIndexRequest(BaseModel):
    """Batch document indexing request"""
    documents: List[DocumentIndexRequest] = Field(..., min_items=1, max_items=100)


class SearchRequest(BaseModel):
    """RAG search request"""
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: Optional[int] = Field(default=5, ge=1, le=20)
    filters: Optional[Dict[str, Any]] = None


class SearchResult(BaseModel):
    """Single search result"""
    text: str
    score: float
    metadata: Dict[str, Any]
    indexed_at: Optional[str] = None


class SearchResponse(BaseModel):
    """RAG search response"""
    results: List[SearchResult]
    query: str
    total_results: int


# ==================== N8N Workflow Models ====================

class CalendarEventRequest(BaseModel):
    """Request to create calendar event"""
    title: str = Field(..., min_length=1, max_length=200)
    start_time: str = Field(..., description="ISO 8601 datetime")
    end_time: str = Field(..., description="ISO 8601 datetime")
    attendees: Optional[List[str]] = Field(default=None)
    description: Optional[str] = Field(default=None, max_length=5000)

    @validator('attendees')
    def validate_emails(cls, v):
        if v:
            for email in v:
                if '@' not in email:
                    raise ValueError(f"Invalid email: {email}")
        return v


class EmailRequest(BaseModel):
    """Request to send email"""
    to: List[str] = Field(..., min_items=1)
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1, max_length=50000)
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    attachments: Optional[List[str]] = None

    @validator('to', 'cc', 'bcc')
    def validate_emails(cls, v):
        if v:
            for email in v:
                if '@' not in email:
                    raise ValueError(f"Invalid email: {email}")
        return v


class SpreadsheeetUpdateRequest(BaseModel):
    """Request to update Google Sheets"""
    spreadsheet_id: str = Field(..., min_length=1)
    sheet_name: str = Field(..., min_length=1)
    range: str = Field(..., min_length=1)
    values: List[List[Any]] = Field(..., min_items=1)
    append: bool = Field(default=True)


class ContactUpsertRequest(BaseModel):
    """Request to create or update a Google Contact"""
    email: str = Field(..., description="Primary email address")
    given_name: Optional[str] = Field(default=None, max_length=100)
    family_name: Optional[str] = Field(default=None, max_length=100)
    phone_numbers: Optional[List[str]] = Field(default=None)
    organization: Optional[str] = Field(default=None, max_length=200)
    job_title: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=2000)

    @validator('email')
    def validate_email(cls, v):
        if '@' not in v:
            raise ValueError(f"Invalid email: {v}")
        return v


class WorkflowExecutionResponse(BaseModel):
    """N8N workflow execution response"""
    success: bool
    workflow: str
    result: Dict[str, Any]
    execution_time: Optional[float] = None


# ==================== System Models ====================

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: Dict[str, bool]
    version: str


class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ==================== Location-Triggered Question Flow Models ====================

class LocationRequest(BaseModel):
    """Request to create or update a location"""
    name: str = Field(..., min_length=1, max_length=200, description="Location name")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude coordinate")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude coordinate")
    radius_meters: float = Field(default=100.0, ge=10, le=10000, description="Geofence radius in meters")
    description: Optional[str] = Field(default=None, max_length=1000)


class LocationResponse(BaseModel):
    """Location response"""
    id: str
    name: str
    latitude: float
    longitude: float
    radius_meters: float
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class RecurrenceRule(BaseModel):
    """Recurrence rule for scheduling questions"""
    frequency: str = Field(..., description="daily, weekly, monthly, custom")
    interval: int = Field(default=1, ge=1, description="Every N days/weeks/months")
    days_of_week: Optional[List[int]] = Field(default=None, description="0=Monday, 6=Sunday")
    days_of_month: Optional[List[int]] = Field(default=None, ge=1, le=31, description="Specific days of month")
    weekends_only: bool = Field(default=False)
    time_window_start: Optional[str] = Field(default=None, description="HH:MM format")
    time_window_end: Optional[str] = Field(default=None, description="HH:MM format")
    random_time: bool = Field(default=False, description="Random time within window")
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class ThrottleRule(BaseModel):
    """Throttling rule to limit question frequency"""
    max_count: int = Field(..., ge=1, description="Maximum number of times")
    within_hours: Optional[float] = Field(default=None, ge=0.1, description="Within X hours")
    within_days: Optional[int] = Field(default=None, ge=1, description="Within X days")


class QuestionRequest(BaseModel):
    """Request to create a question"""
    location_id: str = Field(..., description="Location ID this question is associated with")
    question_text: str = Field(..., min_length=1, max_length=1000, description="Question to ask")
    question_type: str = Field(default="sequential", description="sequential or conversation")
    order: int = Field(default=0, ge=0, description="Order in sequence (0 = first)")
    recurrence: Optional[RecurrenceRule] = None
    throttle: Optional[ThrottleRule] = None
    enabled: bool = Field(default=True)


# ==================== Recording & Media Models ====================

class SilentRecordingSegment(BaseModel):
    """Individual line inside a silent recording transcript"""
    speaker: Optional[str] = Field(default=None, max_length=200)
    text: str = Field(..., min_length=1, max_length=5000)
    timestamp: Optional[str] = Field(default=None, max_length=100, description="Optional HH:MM:SS timestamp marker")


class SilentRecordingEmailDelivery(BaseModel):
    """Email distribution preferences for a silent recording transcript"""
    enabled: bool = True
    to: List[str] = Field(..., min_items=1)
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    subject: Optional[str] = Field(default=None, max_length=500)
    include_summary: bool = Field(default=True, description="Include AI generated summary before transcript")


class SilentRecordingDriveDelivery(BaseModel):
    """Google Drive delivery preferences"""
    enabled: bool = True
    parent_folder_id: Optional[str] = Field(default=None, description="Drive folder ID to store transcript under")
    file_name: Optional[str] = Field(default=None, max_length=250)
    file_format: Literal["text", "google_doc"] = Field(default="google_doc")
    share_with: Optional[List[str]] = Field(default=None, description="Optional list of email addresses to grant reader access")


class SilentRecordingRequest(BaseModel):
    """Request payload for silent meeting recording transcription"""
    meeting_title: str = Field(..., max_length=300)
    started_at: Optional[str] = Field(default=None, description="ISO 8601 start timestamp")
    ended_at: Optional[str] = Field(default=None, description="ISO 8601 end timestamp")
    location: Optional[str] = Field(default=None, max_length=300)
    participants: Optional[List[str]] = Field(default=None, description="Names or emails of attendees")
    transcript_text: Optional[str] = Field(default=None, description="Plain text transcript (if already available)")
    transcript_segments: Optional[List[SilentRecordingSegment]] = Field(default=None)
    audio_base64: Optional[str] = Field(default=None, description="Base64 encoded audio payload for transcription")
    audio_mime_type: Optional[str] = Field(default="audio/webm")
    summary_instructions: Optional[str] = Field(default=None, max_length=2000)
    email_delivery: Optional[SilentRecordingEmailDelivery] = None
    drive_delivery: Optional[SilentRecordingDriveDelivery] = None

    @validator('audio_base64')
    def validate_audio_base64(cls, value, values):
        if not value and not (values.get('transcript_text') or values.get('transcript_segments')):
            raise ValueError("Provide transcript_text, transcript_segments, or audio_base64")
        return value

    @validator('email_delivery', 'drive_delivery')
    def require_delivery_method(cls, value, values, **kwargs):
        # Validation will happen after both fields processed via root validator
        return value

    @validator('transcript_segments', each_item=True)
    def ensure_segments_have_text(cls, segment):
        if not segment.text.strip():
            raise ValueError("Transcript segment text cannot be empty")
        return segment

    @validator('participants')
    def strip_participants(cls, participants):
        if participants:
            return [p.strip() for p in participants if p and p.strip()]
        return participants

    @validator('meeting_title')
    def title_cannot_be_blank(cls, value):
        if not value.strip():
            raise ValueError("meeting_title cannot be blank")
        return value

    @validator('drive_delivery', always=True)
    def validate_delivery_options(cls, value, values):
        email_delivery = values.get('email_delivery')
        has_email = email_delivery and email_delivery.enabled
        has_drive = value and value.enabled
        if not (has_email or has_drive):
            raise ValueError("At least one delivery option (email or drive) must be enabled")
        return value


class SilentRecordingResponse(BaseModel):
    """Response payload after processing a silent recording"""
    recording_id: str
    transcript_text: str
    summary: Optional[str] = None
    email_delivery: Optional[Dict[str, Any]] = None
    drive_delivery: Optional[Dict[str, Any]] = None


class MediaAnalysisRequest(BaseModel):
    """Request payload for multimodal media analysis"""
    filename: str = Field(..., max_length=255)
    mime_type: str = Field(..., max_length=200)
    base64_content: str = Field(..., description="Base64 encoded binary payload")
    instructions: Optional[str] = Field(default=None, max_length=2000, description="Extra instructions for analysis")
    analysis_focus: List[Literal["summary", "extraction", "actions", "sentiment"]] = Field(
        default_factory=lambda: ["summary"],
        description="Types of insights to generate"
    )
    engines: List[Literal["gemini", "ollama"]] = Field(
        default_factory=lambda: ["gemini", "ollama"],
        description="LLM engines to run analysis against"
    )
    include_text_extraction: bool = Field(default=True, description="Extract text when possible for documents")

    @validator('engines')
    def validate_engines(cls, engines):
        if not engines:
            raise ValueError("At least one engine must be specified")
        return engines


class MediaAnalysisResponse(BaseModel):
    """Response for multimodal analysis requests"""
    filename: str
    mime_type: str
    extracted_text: Optional[str] = None
    gemini_analysis: Optional[str] = None
    ollama_analysis: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QuestionResponse(BaseModel):
    """Question response"""
    id: str
    location_id: str
    question_text: str
    question_type: str
    order: int
    recurrence: Optional[Dict[str, Any]] = None
    throttle: Optional[Dict[str, Any]] = None
    enabled: bool
    created_at: datetime
    updated_at: datetime


class ScheduleRequest(BaseModel):
    """Request to create a schedule for a location"""
    location_id: str = Field(..., description="Location ID")
    questions: List[QuestionRequest] = Field(..., min_items=1, description="Questions to schedule")
    name: Optional[str] = Field(default=None, max_length=200, description="Schedule name")


class ScheduleResponse(BaseModel):
    """Schedule response"""
    id: str
    location_id: str
    name: Optional[str] = None
    questions: List[QuestionResponse]
    created_at: datetime
    updated_at: datetime


class AnswerRequest(BaseModel):
    """Request to submit an answer"""
    question_id: str = Field(..., description="Question ID")
    location_id: str = Field(..., description="Location ID")
    answer_text: str = Field(..., min_length=1, max_length=5000, description="User's answer")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)
    delivery_channel: str = Field(default="app", description="app, notification, or voice")


class AnswerResponse(BaseModel):
    """Answer response"""
    id: str
    question_id: str
    location_id: str
    answer_text: str
    timestamp: datetime
    delivery_channel: str
    logged_to_sheets: bool = False


class LocationTriggerRequest(BaseModel):
    """Request when device enters a location"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)


class QueuedQuestionResponse(BaseModel):
    """Response for queued questions"""
    question_id: str
    question_text: str
    question_type: str
    order: int
    location_id: str
    location_name: str
    schedule_id: str


class ConversationStateRequest(BaseModel):
    """Request to update conversation state"""
    session_id: str = Field(..., description="Conversation session ID")
    message: str = Field(..., min_length=1, max_length=5000, description="User message")
    location_id: Optional[str] = None


class ConversationStateResponse(BaseModel):
    """Conversation state response"""
    session_id: str
    current_question_id: Optional[str] = None
    next_question: Optional[QueuedQuestionResponse] = None
    conversation_active: bool
    message: str
    should_continue: bool = Field(default=True, description="Whether to continue conversation")
