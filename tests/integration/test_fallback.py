import pytest
from httpx import AsyncClient
from app.providers.base import LLMProvider, ChatRequest, ChatResponse, ChatChoice, ChatChoiceMessage, Usage, ProviderHealth
from app.reliability.fallback import FallbackOrchestrator


class FailingProvider(LLMProvider):
    name = "failing-provider"

    async def chat(self, request: ChatRequest) -> ChatResponse:
        raise ConnectionError("Simulated upstream provider outage")

    async def stream(self, request: ChatRequest):
        raise ConnectionError("Simulated stream outage")

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(provider=self.name, status="unhealthy", error="outage")


class BackupProvider(LLMProvider):
    name = "backup-provider"

    async def chat(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(
            id="chatcmpl-backup-123",
            model="backup-model",
            choices=[ChatChoice(index=0, message=ChatChoiceMessage(role="assistant", content="Rescued by backup provider!"))],
            usage=Usage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
            provider=self.name,
        )

    async def stream(self, request: ChatRequest):
        pass

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(provider=self.name, status="healthy")


@pytest.mark.asyncio
async def test_automatic_fallback_on_provider_failure():
    orchestrator = FallbackOrchestrator()
    providers = [FailingProvider(), BackupProvider()]
    req = ChatRequest(model="auto", messages=[{"role": "user", "content": "hello"}])

    resp = await orchestrator.execute_chat(providers, req)
    assert resp.provider == "backup-provider"
    assert resp.choices[0].message.content == "Rescued by backup provider!"
