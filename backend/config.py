"""
Configuration Management for AI Executive Assistant
Loads and validates environment variables using Pydantic Settings
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    All sensitive values should be provided via .env file
    """

    # ==================== Ollama Configuration (Open Source AI) ====================
    ollama_host: str = "http://ollama:11434"
    ollama_base_url: str = "http://ollama:11434"
    ollama_vision_model: str = "llava:13b"

    # ==================== LLM API Configuration ====================
    # Model routing is automatic based on model name prefix:
    # - llama*, mistral*, etc. → Ollama (free, local)
    # - gemini* → Google Gemini API
    # - gpt* → OpenAI API
    # - claude* → Anthropic API
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None

    # Model Selection and Routing
    default_llm_model: str = "llama3.2:3b"  # Free Ollama model
    premium_llm_model: str = "gemini-2.0-flash"  # Fast Gemini model

    # Token Budget and Cost Control
    max_tokens_per_request: int = 8000
    token_budget_warning_threshold: int = 6000

    # ==================== Qdrant Vector Database Configuration ====================
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    qdrant_collection_name: str = "executive_knowledge"

    # Embedding Model Configuration
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # ==================== N8N Webhook Integration ====================
    n8n_webhook_url: str = "http://n8n:5678/webhook"
    n8n_webhook_secret: str

    # ==================== Redis Cache Configuration (Optional) ====================
    redis_host: str = "redis"
    redis_port: int = 6379
    enable_cache: bool = False
    cache_ttl_seconds: int = 3600

    # ==================== Langfuse Observability (Optional) ====================
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_host: Optional[str] = None

    # ==================== Application Configuration ====================
    app_name: str = "AI Executive Assistant"
    app_version: str = "1.0.0"
    debug: bool = False

    # Location-triggered questions configuration
    location_questions_spreadsheet_id: Optional[str] = None
    conversation_logging_spreadsheet_id: Optional[str] = None

    # CORS Configuration
    cors_origins: list[str] = ["*"]

    # ==================== RAG Configuration ====================
    rag_top_k: int = 5
    rag_score_threshold: float = 0.7

    # Maximum context length for RAG (in tokens)
    max_rag_context_tokens: int = 4000

    # ==================== Cost Tracking ====================
    # Cost per 1M tokens (update based on current pricing)
    cost_per_1m_input_tokens: dict[str, float] = {
        # Open Source Models (Ollama) - FREE
        "llama3.2:3b": 0.0,
        "llama3.2:7b": 0.0,
        "llama3.2": 0.0,
        "mistral": 0.0,
        "mistral:7b": 0.0,
        "phi3": 0.0,
        "gemma2": 0.0,
        "qwen2.5": 0.0,
        "mixtral:8x7b": 0.0,
        # Commercial Models
        "gpt-4o-mini": 0.60,
        "gpt-4": 1.25,
        "gpt-4-turbo": 10.00,
        "claude-3-haiku": 0.25,
        "claude-3-sonnet": 3.00,
        "gemini-2.5-flash": 0.15,
    }

    cost_per_1m_output_tokens: dict[str, float] = {
        # Open Source Models (Ollama) - FREE
        "llama3.2:3b": 0.0,
        "llama3.2:7b": 0.0,
        "llama3.2": 0.0,
        "mistral": 0.0,
        "mistral:7b": 0.0,
        "phi3": 0.0,
        "gemma2": 0.0,
        "qwen2.5": 0.0,
        "mixtral:8x7b": 0.0,
        # Commercial Models
        "gpt-4o-mini": 2.40,
        "gpt-4": 10.00,
        "gpt-4-turbo": 30.00,
        "claude-3-haiku": 1.25,
        "claude-3-sonnet": 15.00,
        "gemini-2.5-flash": 0.60,
    }

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Dependency injection for FastAPI routes"""
    return settings
