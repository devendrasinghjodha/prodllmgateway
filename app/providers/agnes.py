import json
import time
import uuid
from collections.abc import AsyncGenerator

from app.config import settings
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
from app.utils.http_client import get_http_client


class AgnesProvider(LLMProvider):
    name = "agnes"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str | None = None,
        timeout: float = 30.0,
    ):
        self.api_key = api_key or settings.AGNES_API_KEY
        self.base_url = (base_url or settings.AGNES_BASE_URL).rstrip("/")
        self.default_model = default_model or settings.AGNES_DEFAULT_MODEL
        self.timeout = timeout

    def _resolve_model(self, request_model: str) -> str:
        if request_model in ["agnes", "auto", "default", "standard"]:
            return self.default_model
        if request_model.startswith("agnes-"):
            return request_model
        return self.default_model

    def _build_payload(self, request: ChatRequest, stream: bool = False) -> dict:
        model = self._resolve_model(request.model)
        payload = {
            "model": model,
            "messages": [msg.model_dump(exclude_none=True) for msg in request.messages],
            "temperature": request.temperature,
            "top_p": request.top_p,
            "stream": stream,
        }

        max_tokens = request.get_effective_max_tokens()
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        if request.stop:
            payload["stop"] = request.stop

        return payload

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "ProdLLM-Gateway/1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def chat(self, request: ChatRequest) -> ChatResponse:
        start_time = time.time()
        url = f"{self.base_url}/chat/completions"
        payload = self._build_payload(request, stream=False)
        headers = self._get_headers()
        client = get_http_client()

        resp = await client.post(url, headers=headers, json=payload, timeout=self.timeout)
        latency_ms = (time.time() - start_time) * 1000

        if resp.status_code != 200:
            resp.raise_for_status()

        data = resp.json()

        choices = []
        for c in data.get("choices", []):
            msg = c.get("message", {})
            choices.append(
                ChatChoice(
                    index=c.get("index", 0),
                    message=ChatChoiceMessage(
                        role=msg.get("role", "assistant"),
                        content=msg.get("content", ""),
                    ),
                    finish_reason=c.get("finish_reason", "stop"),
                )
            )

        usage_dict = data.get("usage", {})
        prompt_tokens = usage_dict.get("prompt_tokens", 0)
        completion_tokens = usage_dict.get("completion_tokens", 0)
        total_tokens = usage_dict.get("total_tokens", prompt_tokens + completion_tokens)

        cost = self.estimate_cost(payload["model"], prompt_tokens, completion_tokens)

        return ChatResponse(
            id=data.get("id", f"chatcmpl-agnes-{uuid.uuid4().hex[:12]}"),
            created=data.get("created", int(time.time())),
            model=data.get("model", payload["model"]),
            choices=choices,
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost=cost,
            ),
            provider=self.name,
            latency_ms=latency_ms,
        )

    async def stream(self, request: ChatRequest) -> AsyncGenerator[ChatStreamChunk, None]:
        url = f"{self.base_url}/chat/completions"
        payload = self._build_payload(request, stream=True)
        headers = self._get_headers()
        req_id = f"chatcmpl-agnes-{uuid.uuid4().hex[:12]}"
        client = get_http_client()

        async with client.stream("POST", url, headers=headers, json=payload, timeout=self.timeout) as response:
            if response.status_code != 200:
                await response.aread()
                response.raise_for_status()

            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    choices = []
                    for c in data.get("choices", []):
                        delta_dict = c.get("delta", {})
                        choices.append(
                            StreamChoice(
                                index=c.get("index", 0),
                                delta=DeltaMessage(
                                    role=delta_dict.get("role"),
                                    content=delta_dict.get("content"),
                                ),
                                finish_reason=c.get("finish_reason"),
                            )
                        )
                    yield ChatStreamChunk(
                        id=data.get("id", req_id),
                        created=data.get("created", int(time.time())),
                        model=data.get("model", payload["model"]),
                        choices=choices,
                        provider=self.name,
                    )
                except json.JSONDecodeError:
                    continue

    async def health_check(self) -> ProviderHealth:
        start_time = time.time()
        try:
            if not self.api_key:
                return ProviderHealth(
                    provider=self.name,
                    status="unhealthy",
                    latency_ms=0.0,
                    error="API key not configured",
                )
            url = f"{self.base_url}/models"
            headers = self._get_headers()
            client = get_http_client()
            resp = await client.get(url, headers=headers, timeout=5.0)
            latency_ms = (time.time() - start_time) * 1000
            if resp.status_code == 200:
                return ProviderHealth(
                    provider=self.name,
                    status="healthy",
                    latency_ms=round(latency_ms, 2),
                )
            return ProviderHealth(
                provider=self.name,
                status="unhealthy",
                latency_ms=round(latency_ms, 2),
                error=f"Status {resp.status_code}: {resp.text[:100]}",
            )
        except Exception as e:
            return ProviderHealth(
                provider=self.name,
                status="unhealthy",
                latency_ms=(time.time() - start_time) * 1000,
                error=str(e),
            )
