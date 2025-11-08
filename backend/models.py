"""
Pydantic Models for Request/Response Validation
Enforces strict schemas to prevent cost exploitation and injection attacks
"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
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
    timestamp: datetime = Field(default_factory=datetime.utcnow)


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
