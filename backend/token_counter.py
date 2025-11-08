"""
Token Counter Module - Cost Control and Transparency
Implements pre-flight cost mitigation and post-flight reporting
Uses tiktoken for accurate token counting per model
"""
import tiktoken
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from config import settings
import logging

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
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


class TokenCounter:
    """
    Token counting and cost calculation service
    Provides pre-flight budget checking and post-flight cost reporting
    """

    def __init__(self):
        self.encodings_cache: Dict[str, tiktoken.Encoding] = {}

    def _get_encoding(self, model: str) -> tiktoken.Encoding:
        """
        Get or create tiktoken encoding for a specific model
        Caches encodings for performance
        """
        if model in self.encodings_cache:
            return self.encodings_cache[model]

        try:
            # Try to get encoding for specific model
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback to cl100k_base for newer models
            logger.warning(f"Model {model} not found, using cl100k_base encoding")
            encoding = tiktoken.get_encoding("cl100k_base")

        self.encodings_cache[model] = encoding
        return encoding

    def count_tokens(self, text: str, model: str = "gpt-4o-mini") -> int:
        """
        Count tokens in a text string for a specific model

        Args:
            text: The text to count tokens for
            model: The LLM model name (determines encoding)

        Returns:
            Number of tokens
        """
        if not text:
            return 0

        encoding = self._get_encoding(model)
        return len(encoding.encode(text))

    def count_messages_tokens(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4o-mini"
    ) -> int:
        """
        Count tokens for a list of chat messages
        Accounts for message formatting overhead

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: The LLM model name

        Returns:
            Total number of tokens including formatting
        """
        encoding = self._get_encoding(model)

        tokens_per_message = 3  # Every message follows <|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = 1  # If there's a name field

        num_tokens = 0
        for message in messages:
            num_tokens += tokens_per_message
            for key, value in message.items():
                num_tokens += len(encoding.encode(str(value)))
                if key == "name":
                    num_tokens += tokens_per_name

        num_tokens += 3  # Every reply is primed with <|start|>assistant<|message|>
        return num_tokens

    def calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str
    ) -> Tuple[float, float, float]:
        """
        Calculate cost for token usage

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: The LLM model name

        Returns:
            Tuple of (input_cost, output_cost, total_cost) in USD
        """
        # Get cost per 1M tokens from settings
        input_cost_per_1m = settings.cost_per_1m_input_tokens.get(model, 1.0)
        output_cost_per_1m = settings.cost_per_1m_output_tokens.get(model, 5.0)

        # Calculate costs
        input_cost = (input_tokens / 1_000_000) * input_cost_per_1m
        output_cost = (output_tokens / 1_000_000) * output_cost_per_1m
        total_cost = input_cost + output_cost

        return input_cost, output_cost, total_cost

    def pre_flight_check(
        self,
        messages: List[Dict[str, str]],
        rag_context: Optional[str] = None,
        model: str = "gpt-4o-mini",
        max_completion_tokens: int = 2000
    ) -> Dict[str, any]:
        """
        Pre-flight cost mitigation: Check if request is within budget

        Args:
            messages: Conversation history
            rag_context: Additional RAG context to be added
            model: Target LLM model
            max_completion_tokens: Expected max output tokens

        Returns:
            Dict with approval status, token counts, and cost estimates
        """
        # Count conversation tokens
        conversation_tokens = self.count_messages_tokens(messages, model)

        # Count RAG context tokens
        rag_tokens = self.count_tokens(rag_context, model) if rag_context else 0

        # Total input tokens
        total_input_tokens = conversation_tokens + rag_tokens

        # Estimated total tokens (input + expected output)
        estimated_total = total_input_tokens + max_completion_tokens

        # Calculate estimated cost
        input_cost, output_cost, total_cost = self.calculate_cost(
            total_input_tokens,
            max_completion_tokens,
            model
        )

        # Check against budget
        exceeds_budget = estimated_total > settings.max_tokens_per_request
        exceeds_warning = estimated_total > settings.token_budget_warning_threshold

        # Determine if we should suggest truncation
        should_truncate = exceeds_budget

        result = {
            "approved": not exceeds_budget,
            "exceeds_warning_threshold": exceeds_warning,
            "conversation_tokens": conversation_tokens,
            "rag_context_tokens": rag_tokens,
            "total_input_tokens": total_input_tokens,
            "estimated_output_tokens": max_completion_tokens,
            "estimated_total_tokens": estimated_total,
            "estimated_cost_usd": total_cost,
            "should_truncate": should_truncate,
            "model": model,
            "budget_limit": settings.max_tokens_per_request,
        }

        if exceeds_budget:
            logger.warning(
                f"Pre-flight check FAILED: {estimated_total} tokens exceeds budget of {settings.max_tokens_per_request}"
            )
        elif exceeds_warning:
            logger.info(
                f"Pre-flight check WARNING: {estimated_total} tokens exceeds warning threshold"
            )

        return result

    def create_usage_report(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str,
        rag_context_tokens: int = 0,
        conversation_history_tokens: int = 0
    ) -> TokenUsage:
        """
        Create post-flight token usage report

        Args:
            input_tokens: Actual input tokens used
            output_tokens: Actual output tokens generated
            model: Model used
            rag_context_tokens: Tokens from RAG context
            conversation_history_tokens: Tokens from conversation history

        Returns:
            TokenUsage object with detailed breakdown
        """
        input_cost, output_cost, total_cost = self.calculate_cost(
            input_tokens,
            output_tokens,
            model
        )

        return TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            input_cost_usd=input_cost,
            output_cost_usd=output_cost,
            total_cost_usd=total_cost,
            model=model,
            rag_context_tokens=rag_context_tokens,
            conversation_history_tokens=conversation_history_tokens
        )


# Global token counter instance
token_counter = TokenCounter()


def get_token_counter() -> TokenCounter:
    """Dependency injection for FastAPI routes"""
    return token_counter
