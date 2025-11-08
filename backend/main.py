"""
FastAPI AI Agent Gateway - Main Application
Intelligence Layer: LLM orchestration, RAG pipeline, token counting, N8N bridge
Optimized for async I/O-bound operations
"""
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Dict, List
import logging
from datetime import datetime

from config import settings, get_settings
from models import *
from token_counter import TokenCounter, get_token_counter
from rag_service import RAGService, get_rag_service
from n8n_bridge import N8NBridge, get_n8n_bridge, N8NWorkflowError

# Optional imports
try:
    from langfuse import Langfuse
    langfuse_available = True
except ImportError:
    langfuse_available = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI Executive Assistant - Intelligence Layer",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Optional Langfuse observability
langfuse_client = None
if langfuse_available and settings.langfuse_public_key:
    try:
        langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host
        )
        logger.info("Langfuse observability enabled")
    except Exception as e:
        logger.warning(f"Failed to initialize Langfuse: {e}")


# ==================== LLM Integration ====================

async def call_llm(
    messages: List[Dict[str, str]],
    model: str = None,
    max_tokens: int = 2000,
    temperature: float = 0.7
) -> tuple[str, int, int]:
    """
    Call LLM API (OpenAI, Anthropic, or Google)

    Returns:
        Tuple of (response_text, input_tokens, output_tokens)
    """
    from openai import AsyncOpenAI

    model = model or settings.default_llm_model

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )

        response_text = response.choices[0].message.content
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens

        return response_text, input_tokens, output_tokens

    except Exception as e:
        logger.error(f"LLM API call failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM API error: {str(e)}"
        )


# ==================== Health Check Endpoint ====================

@app.get("/health", response_model=HealthResponse)
async def health_check(
    rag_service: RAGService = Depends(get_rag_service),
    n8n_bridge: N8NBridge = Depends(get_n8n_bridge)
):
    """
    System health check endpoint
    Verifies connectivity to all dependent services
    """
    services = {
        "fastapi": True,
        "qdrant": False,
        "n8n": False
    }

    # Check Qdrant
    try:
        stats = rag_service.get_collection_stats()
        services["qdrant"] = bool(stats)
    except Exception as e:
        logger.error(f"Qdrant health check failed: {e}")

    # Check N8N
    try:
        services["n8n"] = await n8n_bridge.health_check()
    except Exception as e:
        logger.error(f"N8N health check failed: {e}")

    overall_status = "healthy" if all(services.values()) else "degraded"

    return HealthResponse(
        status=overall_status,
        services=services,
        version=settings.app_version
    )


# ==================== Chat Endpoint ====================

@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    token_counter: TokenCounter = Depends(get_token_counter),
    rag_service: RAGService = Depends(get_rag_service),
    settings_dep: Settings = Depends(get_settings)
):
    """
    Main chat endpoint with RAG integration and token counting
    Implements pre-flight cost mitigation
    """
    try:
        # Convert Pydantic models to dicts for processing
        messages = [msg.dict() for msg in request.messages]

        # RAG Context Retrieval
        rag_context = None
        rag_sources = None
        rag_tokens = 0

        if request.use_rag:
            user_query = messages[-1]['content']
            rag_context = rag_service.get_rag_context(
                user_query,
                filters=request.rag_filters
            )

            if rag_context:
                rag_tokens = token_counter.count_tokens(
                    rag_context,
                    request.model or settings_dep.default_llm_model
                )

                # Get sources for transparency
                rag_results = rag_service.search(
                    user_query,
                    filters=request.rag_filters
                )
                rag_sources = [
                    {
                        "text": r['text'][:200] + "..." if len(r['text']) > 200 else r['text'],
                        "score": r['score'],
                        "metadata": r['metadata']
                    }
                    for r in rag_results
                ]

        # Pre-flight token budget check
        pre_flight = token_counter.pre_flight_check(
            messages=messages,
            rag_context=rag_context,
            model=request.model or settings_dep.default_llm_model,
            max_completion_tokens=request.max_tokens
        )

        if not pre_flight['approved']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Request exceeds token budget: {pre_flight['estimated_total_tokens']} tokens "
                       f"(limit: {settings_dep.max_tokens_per_request})"
            )

        # Inject RAG context into system message
        if rag_context:
            system_message = {
                "role": "system",
                "content": f"You are an AI Executive Assistant. Use the following context to answer the user's query:\n\n{rag_context}"
            }
            messages.insert(0, system_message)

        # Call LLM
        response_text, input_tokens, output_tokens = await call_llm(
            messages=messages,
            model=request.model or settings_dep.default_llm_model,
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )

        # Create usage report
        usage = token_counter.create_usage_report(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=request.model or settings_dep.default_llm_model,
            rag_context_tokens=rag_tokens,
            conversation_history_tokens=pre_flight['conversation_tokens']
        )

        # Log to Langfuse if available
        if langfuse_client:
            try:
                langfuse_client.trace(
                    name="chat_completion",
                    input=messages,
                    output=response_text,
                    metadata={
                        "model": request.model or settings_dep.default_llm_model,
                        "rag_used": request.use_rag,
                        "total_cost": usage.total_cost_usd
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to log to Langfuse: {e}")

        return ChatResponse(
            message=response_text,
            usage=TokenUsageResponse(**usage.__dict__),
            rag_used=request.use_rag and rag_context is not None,
            rag_sources=rag_sources,
            model=request.model or settings_dep.default_llm_model
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== RAG Endpoints ====================

@app.post("/api/rag/index", status_code=status.HTTP_201_CREATED)
async def index_document(
    request: DocumentIndexRequest,
    rag_service: RAGService = Depends(get_rag_service)
):
    """Index a single document for RAG retrieval"""
    success = rag_service.index_document(
        document_id=request.document_id,
        text=request.text,
        metadata=request.metadata
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to index document"
        )

    return {"success": True, "document_id": request.document_id}


@app.post("/api/rag/index/batch", status_code=status.HTTP_201_CREATED)
async def index_documents_batch(
    request: DocumentBatchIndexRequest,
    rag_service: RAGService = Depends(get_rag_service)
):
    """Index multiple documents in batch"""
    documents = [doc.dict() for doc in request.documents]
    indexed_count = rag_service.index_documents_batch(documents)

    return {
        "success": True,
        "indexed_count": indexed_count,
        "total_requested": len(documents)
    }


@app.post("/api/rag/search", response_model=SearchResponse)
async def search_knowledge(
    request: SearchRequest,
    rag_service: RAGService = Depends(get_rag_service)
):
    """Search the RAG knowledge base"""
    results = rag_service.search(
        query=request.query,
        top_k=request.top_k,
        filters=request.filters
    )

    return SearchResponse(
        results=[SearchResult(**r) for r in results],
        query=request.query,
        total_results=len(results)
    )


@app.get("/api/rag/stats")
async def get_rag_stats(
    rag_service: RAGService = Depends(get_rag_service)
):
    """Get RAG collection statistics"""
    return rag_service.get_collection_stats()


# ==================== N8N Workflow Endpoints ====================

@app.post("/api/workflows/calendar/event", response_model=WorkflowExecutionResponse)
async def create_calendar_event(
    request: CalendarEventRequest,
    n8n_bridge: N8NBridge = Depends(get_n8n_bridge)
):
    """Create Google Calendar event via N8N"""
    try:
        result = await n8n_bridge.create_calendar_event(
            title=request.title,
            start_time=request.start_time,
            end_time=request.end_time,
            attendees=request.attendees,
            description=request.description
        )
        return WorkflowExecutionResponse(**result)
    except N8NWorkflowError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/workflows/email/send", response_model=WorkflowExecutionResponse)
async def send_email(
    request: EmailRequest,
    n8n_bridge: N8NBridge = Depends(get_n8n_bridge)
):
    """Send email via Gmail through N8N"""
    try:
        result = await n8n_bridge.send_email(
            to=request.to,
            subject=request.subject,
            body=request.body,
            cc=request.cc,
            bcc=request.bcc,
            attachments=request.attachments
        )
        return WorkflowExecutionResponse(**result)
    except N8NWorkflowError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/workflows/sheets/update", response_model=WorkflowExecutionResponse)
async def update_spreadsheet(
    request: SpreadsheeetUpdateRequest,
    n8n_bridge: N8NBridge = Depends(get_n8n_bridge)
):
    """Update Google Sheets via N8N"""
    try:
        result = await n8n_bridge.update_spreadsheet(
            spreadsheet_id=request.spreadsheet_id,
            sheet_name=request.sheet_name,
            range=request.range,
            values=request.values,
            append=request.append
        )
        return WorkflowExecutionResponse(**result)
    except N8NWorkflowError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== Error Handlers ====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            detail=str(exc)
        ).dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc)
        ).dict()
    )


# ==================== Startup/Shutdown Events ====================

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Default LLM Model: {settings.default_llm_model}")
    logger.info(f"RAG Enabled: True")
    logger.info(f"N8N Webhook URL: {settings.n8n_webhook_url}")

    # Initialize RAG service
    try:
        rag = get_rag_service()
        stats = rag.get_collection_stats()
        logger.info(f"Qdrant initialized: {stats.get('total_points', 0)} documents indexed")
    except Exception as e:
        logger.error(f"Failed to initialize Qdrant: {e}")

    logger.info("FastAPI AI Agent Gateway ready")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down FastAPI AI Agent Gateway")

    # Flush Langfuse traces
    if langfuse_client:
        try:
            langfuse_client.flush()
        except Exception as e:
            logger.warning(f"Failed to flush Langfuse: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
