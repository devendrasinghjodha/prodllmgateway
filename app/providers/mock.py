import asyncio
import time
import uuid
from collections.abc import AsyncGenerator

from app.providers.base import (
    ChatChoice,
    ChatChoiceMessage,
    ChatRequest,
    ChatResponse,
    ChatStreamChunk,
    DeltaMessage,
    LLMProvider,
    ProviderHealth,
    StreamChoice,
    Usage,
)


class MockProvider(LLMProvider):
    name = "mock"

    def __init__(self, simulated_latency_ms: float = 10.0, fail_rate: float = 0.0):
        self.simulated_latency_ms = simulated_latency_ms
        self.fail_rate = fail_rate

    async def chat(self, request: ChatRequest) -> ChatResponse:
        start_time = time.time()
        if self.simulated_latency_ms > 0:
            await asyncio.sleep(self.simulated_latency_ms / 1000.0)

        latency_ms = (time.time() - start_time) * 1000

        prompt_text = "".join([m.content for m in request.messages])
        prompt_tokens = max(1, len(prompt_text.split()))
        completion_tokens = 25
        total_tokens = prompt_tokens + completion_tokens

        return ChatResponse(
            id=f"chatcmpl-mock-{uuid.uuid4().hex[:12]}",
            model=request.model or "mock-model",
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatChoiceMessage(
                        role="assistant",
                        content=f"Mock response to: {request.messages[-1].content if request.messages else 'hello'}",
                    ),
                    finish_reason="stop",
                )
            ],
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost=0.0,
            ),
            provider=self.name,
            latency_ms=latency_ms,
        )

    async def stream(self, request: ChatRequest) -> AsyncGenerator[ChatStreamChunk, None]:
        req_id = f"chatcmpl-mock-{uuid.uuid4().hex[:12]}"
        model = request.model or "mock-model"
        tokens = ["This", " is", " a", " fast", " mock", " stream", " response", "."]

        for token in tokens:
            if self.simulated_latency_ms > 0:
                await asyncio.sleep((self.simulated_latency_ms / len(tokens)) / 1000.0)
            yield ChatStreamChunk(
                id=req_id,
                model=model,
                choices=[
                    StreamChoice(
                        index=0,
                        delta=DeltaMessage(role="assistant", content=token),
                        finish_reason=None,
                    )
                ],
                provider=self.name,
            )

        yield ChatStreamChunk(
            id=req_id,
            model=model,
            choices=[
                StreamChoice(
                    index=0,
                    delta=DeltaMessage(),
                    finish_reason="stop",
                )
            ],
            provider=self.name,
        )

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            status="healthy",
            latency_ms=self.simulated_latency_ms,
        )
