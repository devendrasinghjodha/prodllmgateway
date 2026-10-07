import time
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

from pydantic import BaseModel, Field


class FunctionCall(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    id: str
    type: str = "function"
    function: FunctionCall


class ChatMessage(BaseModel):
    role: str
    content: str | None = None
    name: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


class ChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    temperature: float | None = 1.0
    top_p: float | None = 1.0
    n: int | None = 1
    stream: bool | None = False
    stop: str | list[str] | None = None
    max_tokens: int | None = None
    max_completion_tokens: int | None = None
    presence_penalty: float | None = 0.0
    frequency_penalty: float | None = 0.0
    user: str | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None
    # Gateway specific metadata
    priority: str | None = "normal"  # high, normal, low

    def get_effective_max_tokens(self) -> int | None:
        if self.max_completion_tokens is not None:
            return self.max_completion_tokens
        return self.max_tokens


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0


class ChatChoiceMessage(BaseModel):
    role: str = "assistant"
    content: str | None = None
    tool_calls: list[ToolCall] | None = None


class ChatChoice(BaseModel):
    index: int = 0
    message: ChatChoiceMessage
    finish_reason: str | None = "stop"


class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[ChatChoice]
    usage: Usage
    provider: str | None = None
    latency_ms: float | None = None
    cached: bool | None = False


class DeltaMessage(BaseModel):
    role: str | None = None
    content: str | None = None
    tool_calls: list[ToolCall] | None = None


class StreamChoice(BaseModel):
    index: int = 0
    delta: DeltaMessage
    finish_reason: str | None = None


class ChatStreamChunk(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[StreamChoice]
    provider: str | None = None


class ProviderHealth(BaseModel):
    provider: str
    status: str  # "healthy", "degraded", "unhealthy"
    latency_ms: float = 0.0
    last_checked: float = Field(default_factory=time.time)
    error: str | None = None


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Execute non-streaming chat completion."""

    @abstractmethod
    async def stream(self, request: ChatRequest) -> AsyncGenerator[ChatStreamChunk, None]:
        """Execute streaming chat completion."""

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        """Check provider status and response time."""

    def estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Estimate USD cost based on token counts.
        """
        cost_rates: dict[str, dict[str, float]] = {
            "gemini": {"input": 0.075, "output": 0.30},
            "openrouter": {"input": 0.0, "output": 0.0},  # Free models
            "agnes": {"input": 0.05, "output": 0.15},     # Agnes AI
            "mock": {"input": 0.0, "output": 0.0},
        }

        rates = cost_rates.get(self.name.lower(), {"input": 0.10, "output": 0.40})
        cost = (prompt_tokens / 1_000_000 * rates["input"]) + (completion_tokens / 1_000_000 * rates["output"])
        return round(cost, 8)
