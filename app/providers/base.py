from abc import ABC, abstractmethod
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
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
    content: Optional[str] = None
    name: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None


class ChatRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    max_completion_tokens: Optional[int] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    user: Optional[str] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    # Gateway specific metadata
    priority: Optional[str] = "normal"  # high, normal, low

    def get_effective_max_tokens(self) -> Optional[int]:
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
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None


class ChatChoice(BaseModel):
    index: int = 0
    message: ChatChoiceMessage
    finish_reason: Optional[str] = "stop"


class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChatChoice]
    usage: Usage
    provider: Optional[str] = None
    latency_ms: Optional[float] = None
    cached: Optional[bool] = False


class DeltaMessage(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None


class StreamChoice(BaseModel):
    index: int = 0
    delta: DeltaMessage
    finish_reason: Optional[str] = None


class ChatStreamChunk(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[StreamChoice]
    provider: Optional[str] = None


class ProviderHealth(BaseModel):
    provider: str
    status: str  # "healthy", "degraded", "unhealthy"
    latency_ms: float = 0.0
    last_checked: float = Field(default_factory=time.time)
    error: Optional[str] = None


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Execute non-streaming chat completion."""
        pass

    @abstractmethod
    async def stream(self, request: ChatRequest) -> AsyncGenerator[ChatStreamChunk, None]:
        """Execute streaming chat completion."""
        pass

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        """Check provider status and response time."""
        pass

    def estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Estimate USD cost based on token counts.
        """
        cost_rates: Dict[str, Dict[str, float]] = {
            "gemini": {"input": 0.075, "output": 0.30},
            "openrouter": {"input": 0.0, "output": 0.0},  # Free models
            "agnes": {"input": 0.05, "output": 0.15},     # Agnes AI
            "mock": {"input": 0.0, "output": 0.0},
        }

        rates = cost_rates.get(self.name.lower(), {"input": 0.10, "output": 0.40})
        cost = (prompt_tokens / 1_000_000 * rates["input"]) + (completion_tokens / 1_000_000 * rates["output"])
        return round(cost, 8)
