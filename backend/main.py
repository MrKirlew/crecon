"""
FastAPI AI Agent Gateway - Main Application
Intelligence Layer: LLM orchestration, RAG pipeline, token counting, N8N bridge
Optimized for async I/O-bound operations
"""
from fastapi import FastAPI, HTTPException, Depends, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import Response
from fastapi.encoders import jsonable_encoder
import json
from typing import Dict, List
import logging
from datetime import datetime
from uuid import uuid4
import pytz

from config import settings, get_settings, Settings
from models import *
from token_counter import TokenCounter, get_token_counter
from rag_service import RAGService, get_rag_service
from n8n_bridge import N8NBridge, get_n8n_bridge, N8NWorkflowError
from google_tools import GOOGLE_WORKSPACE_TOOLS
from google_functions import execute_google_function
from voice_service import VoiceService

# Import AI-augmented endpoints
try:
    from ai_endpoints import router as ai_router
    ai_endpoints_available = True
except ImportError:
    ai_endpoints_available = False
    logger.warning("AI endpoints not available - ai_endpoints.py not found")

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

# Include AI-augmented endpoints router
if ai_endpoints_available:
    app.include_router(ai_router)
    logger.info("AI-augmented endpoints registered (3,000+ command variations)")

# Include location-triggered question flow endpoints
try:
    from location_endpoints import router as location_router
    app.include_router(location_router)
    logger.info("Location-triggered question flow endpoints registered")
except ImportError as e:
    logger.warning(f"Location endpoints not available: {e}")

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
    temperature: float = 0.7,
    n8n_bridge: N8NBridge = None
) -> tuple[str, int, int]:
    """
    Call LLM API - Routes to appropriate provider based on model name:
    - Ollama: llama*, mistral*, qwen*, etc. (open source models)
    - Google Gemini: gemini* models
    - OpenAI: gpt* models
    - Anthropic: claude* models

    Returns:
        Tuple of (response_text, input_tokens, output_tokens)
    """
    model = model or settings.default_llm_model

    try:
        # Route to Ollama for open-source models (llama, mistral, etc.)
        if any(model.startswith(prefix) for prefix in ['llama', 'mistral', 'qwen', 'phi', 'codellama', 'vicuna']):
            import ollama

            logger.info(f"Calling Ollama with model: {model}")

            # Configure Ollama client to use the Docker service
            client = ollama.Client(host=settings.ollama_host)

            # Call Ollama
            response = client.chat(
                model=model,
                messages=messages,
                options={
                    'temperature': temperature,
                    'num_predict': max_tokens,
                }
            )

            response_text = response['message']['content']

            # Ollama returns token counts in the response
            input_tokens = response.get('prompt_eval_count', 0)
            output_tokens = response.get('eval_count', 0)

            logger.info(f"Ollama response: {len(response_text)} chars, {input_tokens} input tokens, {output_tokens} output tokens")

            return response_text, input_tokens, output_tokens

        # Route to Google Gemini for gemini* models
        elif model.startswith('gemini'):
            from google import genai

            logger.info(f"Calling Google Gemini with model: {model}")

            if not settings.google_api_key:
                raise ValueError("Google API key not configured")

            # Initialize Gemini client with new SDK
            client = genai.Client(api_key=settings.google_api_key)

            # Convert messages to Gemini format
            gemini_messages = []
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                gemini_messages.append({"role": role, "parts": [{"text": msg["content"]}]})

            # Generate content with chat history
            # Function calling loop (max 5 iterations)
            max_iterations = 5
            iteration = 0
            final_response_text = ""
            total_input_tokens = 0
            total_output_tokens = 0

            while iteration < max_iterations:
                iteration += 1
                logger.info(f"Gemini iteration {iteration}/{max_iterations}")

                # Generate content with tools
                response = client.models.generate_content(
                    model=model,
                    contents=gemini_messages,
                    config={
                        "temperature": temperature,
                        "max_output_tokens": max_tokens,
                        "tools": [GOOGLE_WORKSPACE_TOOLS],
                    }
                )

                # Track tokens
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    usage_meta = response.usage_metadata
                    total_input_tokens += getattr(usage_meta, "prompt_token_count", 0) or 0
                    total_output_tokens += getattr(usage_meta, "candidates_token_count", 0) or 0

                # Check for function calls
                has_function_call = False
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'content') and candidate.content:
                        for part in candidate.content.parts:
                            if hasattr(part, 'function_call') and part.function_call:
                                has_function_call = True
                                fc = part.function_call
                                logger.info(f"Function call: {fc.name} with args: {dict(fc.args)}")

                                # Execute function
                                if n8n_bridge:
                                    function_result = await execute_google_function(
                                        fc.name,
                                        dict(fc.args),
                                        n8n_bridge
                                    )
                                else:
                                    function_result = {"status": "error", "error": "n8n_bridge not available"}

                                # Add to conversation
                                gemini_messages.append({
                                    "role": "model",
                                    "parts": [{"function_call": {"name": fc.name, "args": dict(fc.args)}}]
                                })
                                gemini_messages.append({
                                    "role": "user",
                                    "parts": [{"function_response": {
                                        "name": fc.name,
                                        "response": function_result
                                    }}]
                                })
                                break

                if not has_function_call:
                    # Final response
                    final_response_text = response.text
                    logger.info(f"Gemini final response: {len(final_response_text)} chars")
                    break

            response_text = final_response_text
            input_tokens = total_input_tokens
            output_tokens = total_output_tokens
            logger.info(f"Gemini response: {len(response_text)} chars, {input_tokens} input tokens, {output_tokens} output tokens")

            return response_text, input_tokens, output_tokens

        # Route to OpenAI for gpt* models
        elif model.startswith('gpt'):
            from openai import AsyncOpenAI

            logger.info(f"Calling OpenAI with model: {model}")

            if not settings.openai_api_key:
                raise ValueError("OpenAI API key not configured")

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

        # Default: try OpenAI (for claude or other models via OpenAI-compatible endpoints)
        else:
            from openai import AsyncOpenAI

            logger.info(f"Calling default provider (OpenAI-compatible) with model: {model}")

            if not settings.openai_api_key:
                raise ValueError(f"No provider configured for model: {model}. Configure API keys or use Ollama models (llama, mistral, etc.)")

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
    settings_dep: Settings = Depends(get_settings),
    n8n_bridge: N8NBridge = Depends(get_n8n_bridge)
):
    """
    Main chat endpoint with RAG integration and token counting
    Implements pre-flight cost mitigation
    """
    try:
        request_start = datetime.utcnow()

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

        # Get current date/time for context
        local_tz = pytz.timezone('America/Chicago')
        current_local = datetime.now(local_tz)
        current_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
        date_context = (
            "Current clock references:\n"
            f"- Local (America/Chicago): {current_local.strftime('%A, %B %d, %Y at %I:%M %p %Z')}\n"
            f"- UTC: {current_utc.strftime('%A, %B %d, %Y at %H:%M %Z')}\n"
            "Always include accurate dates/times when scheduling or summarizing events."
        )

        # Inject system message with date/time and optional RAG context
        system_content = f"You are an AI Executive Assistant with access to Google Workspace.\n\n{date_context}"

        if rag_context:
            system_content += f"\n\nUse the following context to answer the user's query:\n\n{rag_context}"

        system_content += "\n\nWhen creating calendar events, always use ISO 8601 format for dates (YYYY-MM-DDTHH:MM:SS). When attendees are mentioned by name, search contacts first to get their email addresses.\n\nWhen creating tasks, always convert due dates to RFC 3339 format with timezone offset (e.g., '2025-11-15T19:00:00-06:00' for 7pm Central Time on November 15, 2025). The current timezone is America/Chicago (UTC-6). If only a date is given without time, use 11:59 PM of that date in the local timezone. Always include the timezone offset in the format: YYYY-MM-DDTHH:MM:SS±HH:MM.\n\nWhen searching for contacts, if multiple matches are found, automatically return the information for the first/best match (usually the one with the exact name match). Only ask for clarification if the name is ambiguous and there are multiple people with the same exact name."

        system_message = {
            "role": "system",
            "content": system_content
        }
        messages.insert(0, system_message)

        selected_model = request.model or settings_dep.default_llm_model

        # Start Langfuse trace (SDK v2)
        trace_id = None
        if langfuse_client:
            try:
                # Extract user_id from request
                user_id = request.user_id if hasattr(request, 'user_id') and request.user_id else None
                
                trace = langfuse_client.trace(
                    id=f"chat-{uuid4()}",
                    name="chat_completion",
                    user_id=user_id,  # User tracking
                    input=messages,
                    start_time=request_start,
                    metadata={
                        "model": selected_model,
                        "rag_used": request.use_rag,
                        "rag_filters": request.rag_filters,
                        "rag_context_tokens": rag_tokens
                    }
                )
                trace_id = getattr(trace, "id", None)
                if trace_id is None and isinstance(trace, dict):
                    trace_id = trace.get("id")
            except Exception as e:
                logger.warning(f"Failed to start Langfuse trace: {e}")

        # Call LLM
        response_text, input_tokens, output_tokens = await call_llm(
            messages=messages,
            model=selected_model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            n8n_bridge=n8n_bridge
        )

        # Create usage report
        usage = token_counter.create_usage_report(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=selected_model,
            rag_context_tokens=rag_tokens,
            conversation_history_tokens=pre_flight['conversation_tokens']
        )

        # Log to Langfuse if available (trace + generation for SDK v2)
        if langfuse_client and trace_id:
            try:
                langfuse_client.generation(
                    trace_id=trace_id,
                    name="assistant_response",
                    model=selected_model,
                    input=messages,
                    output=response_text,
                    start_time=request_start,
                    end_time=datetime.utcnow(),
                    usage={
                        "input": usage.input_tokens,
                        "output": usage.output_tokens,
                        "total": usage.total_tokens,
                        "unit": "TOKENS"
                    },
                    metadata={
                        "rag_used": request.use_rag and rag_context is not None,
                        "rag_context_tokens": rag_tokens,
                        "total_cost": usage.total_cost_usd,
                        "input_cost": usage.input_cost_usd,
                        "output_cost": usage.output_cost_usd,
                        "processing_time_ms": (datetime.utcnow() - request_start).total_seconds() * 1000,
                        "rag_sources": rag_sources
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to log Langfuse generation: {e}")

        return ChatResponse(
            message=response_text,
            usage=TokenUsageResponse(**usage.__dict__),
            rag_used=request.use_rag and rag_context is not None,
            rag_sources=rag_sources,
            model=selected_model
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        if langfuse_client:
            try:
                event_payload = {
                    "name": "chat_completion_error",
                    "level": "ERROR",
                    "metadata": {
                        "model": request.model or settings.default_llm_model,
                        "rag_used": request.use_rag,
                        "error": str(e)
                    }
                }
                if trace_id:
                    event_payload["trace_id"] = trace_id
                langfuse_client.event(**event_payload)
            except Exception as lf_error:
                logger.warning(f"Failed to log error to Langfuse: {lf_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== Voice Conversation WebSocket ====================

# Initialize voice service
voice_service = VoiceService()

@app.websocket("/api/voice/ws")
async def voice_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time voice conversations
    Handles bidirectional communication for voice input/output
    """
    await websocket.accept()
    session_id = str(uuid4())
    logger.info(f"Voice WebSocket connection established: {session_id}")
    
    try:
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "message": "Voice connection established. Ready to listen."
        })
        
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            if message_type == "voice_text":
                # Client sent transcribed text
                text = data.get("text", "").strip()
                if not text:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Empty text received"
                    })
                    continue
                
                logger.info(f"Voice input received: {text[:50]}...")
                
                # Process through voice service
                voice_result = await voice_service.process_voice_message(
                    text=text,
                    session_id=session_id,
                    conversation_history=voice_service.get_session_history(session_id)
                )
                
                if voice_result["status"] != "success":
                    await websocket.send_json({
                        "type": "error",
                        "message": voice_result.get("error", "Processing failed")
                    })
                    continue
                
                # Get conversation history
                messages = voice_result["messages"]
                
                # Send processing status
                await websocket.send_json({
                    "type": "processing",
                    "message": "Processing your request..."
                })
                
                # Call LLM with conversation history
                try:
                    # Get current date/time for context
                    local_tz = pytz.timezone('America/Chicago')
                    current_local = datetime.now(local_tz)
                    current_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
                    date_context = (
                        "Current clock references:\n"
                        f"- Local (America/Chicago): {current_local.strftime('%A, %B %d, %Y at %I:%M %p %Z')}\n"
                        f"- UTC: {current_utc.strftime('%A, %B %d, %Y at %H:%M %Z')}\n"
                        "Always include accurate dates/times when scheduling or summarizing events."
                    )
                    
                    # Build system message
                    system_content = f"You are an AI Executive Assistant with access to Google Workspace.\n\n{date_context}"
                    system_content += "\n\nWhen creating calendar events, always use ISO 8601 format for dates (YYYY-MM-DDTHH:MM:SS). When attendees are mentioned by name, search contacts first to get their email addresses.\n\nWhen searching for contacts, if multiple matches are found, automatically return the information for the first/best match (usually the one with the exact name match). Only ask for clarification if the name is ambiguous and there are multiple people with the same exact name."
                    
                    # Convert to format expected by call_llm
                    llm_messages = [{"role": "system", "content": system_content}]
                    for msg in messages:
                        llm_messages.append({
                            "role": msg["role"],
                            "content": msg["content"]
                        })
                    
                    # Get dependencies
                    settings_dep = get_settings()
                    n8n_bridge = get_n8n_bridge()
                    
                    # Call LLM (this handles function calling automatically)
                    response_text, input_tokens, output_tokens = await call_llm(
                        messages=llm_messages,
                        model=settings_dep.default_llm_model,
                        max_tokens=2000,
                        temperature=0.7,
                        n8n_bridge=n8n_bridge
                    )
                    
                    # Format response for voice
                    voice_response = await voice_service.format_response_for_voice(
                        chat_response=response_text,
                        session_id=session_id
                    )
                    
                    # Send response back to client
                    await websocket.send_json({
                        "type": "response",
                        "text": response_text,
                        "session_id": session_id,
                        "tokens": {
                            "input": input_tokens,
                            "output": output_tokens
                        }
                    })
                    
                except Exception as e:
                    logger.error(f"Error in voice LLM call: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Failed to process request: {str(e)}"
                    })
            
            elif message_type == "ping":
                # Keep-alive ping
                await websocket.send_json({"type": "pong"})
            
            elif message_type == "clear_history":
                # Clear conversation history
                voice_service.clear_session(session_id)
                await websocket.send_json({
                    "type": "history_cleared",
                    "message": "Conversation history cleared"
                })
            
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                })
                
    except WebSocketDisconnect:
        logger.info(f"Voice WebSocket disconnected: {session_id}")
        voice_service.clear_session(session_id)
    except Exception as e:
        logger.error(f"Voice WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Connection error: {str(e)}"
            })
        except:
            pass
        voice_service.clear_session(session_id)


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


@app.post("/api/workflows/contacts/upsert", response_model=WorkflowExecutionResponse)
async def upsert_contact(
    request: ContactUpsertRequest,
    n8n_bridge: N8NBridge = Depends(get_n8n_bridge)
):
    """Create or update a Google Contact via N8N"""
    try:
        result = await n8n_bridge.upsert_contact(
            email=request.email,
            given_name=request.given_name,
            family_name=request.family_name,
            phone_numbers=request.phone_numbers,
            organization=request.organization,
            job_title=request.job_title,
            notes=request.notes
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
    return Response(
        status_code=exc.status_code,
        media_type="application/json",
        content=ErrorResponse(
            error=exc.detail,
            detail=str(exc)
        ).model_dump_json()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return Response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        media_type="application/json",
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc)
        ).model_dump_json()
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
