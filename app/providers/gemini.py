import json
import time
import uuid
from collections.abc import AsyncGenerator

from app.config import settings
from app.providers.base import (
    ChatChoice,
    ChatChoiceMessage,
    ChatMessage,
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


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str | None = None,
        timeout: float = 30.0,
    ):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.base_url = (base_url or settings.GEMINI_BASE_URL).rstrip("/")
        self.default_model = default_model or settings.GEMINI_DEFAULT_MODEL
        self.timeout = timeout

    def _resolve_model(self, request_model: str) -> str:
        if request_model in ["gemini", "auto", "default", "fast"]:
            return self.default_model
        if request_model.startswith("gemini-"):
            return request_model
        return self.default_model

    def _convert_messages(self, messages: list[ChatMessage]) -> tuple[str | None, list[dict]]:
        system_instruction = None
        contents = []

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            else:
                role = "user" if msg.role == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg.content}]
                })

        return system_instruction, contents

    def _build_payload(self, request: ChatRequest) -> dict:
        system_instruction, contents = self._convert_messages(request.messages)
        payload: dict = {
            "contents": contents,
            "generationConfig": {}
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        gen_config = payload["generationConfig"]
        if request.temperature is not None:
            gen_config["temperature"] = request.temperature
        if request.top_p is not None:
            gen_config["topP"] = request.top_p
        
        max_tokens = request.get_effective_max_tokens()
        if max_tokens is not None:
            gen_config["maxOutputTokens"] = max_tokens

        if request.stop:
            stops = [request.stop] if isinstance(request.stop, str) else request.stop
            gen_config["stopSequences"] = stops

        # Universal Function Calling / Tools Translation
        from app.providers.tools import tool_adapter
        if request.tools:
            gemini_tools = tool_adapter.openai_to_gemini_tools(request.tools)
            if gemini_tools:
                payload["tools"] = gemini_tools

        return payload

    async def chat(self, request: ChatRequest) -> ChatResponse:
        start_time = time.time()
        model = self._resolve_model(request.model)
        url = f"{self.base_url}/models/{model}:generateContent"
        params = {"key": self.api_key} if self.api_key else {}
        payload = self._build_payload(request)
        client = get_http_client()

        resp = await client.post(url, params=params, json=payload, timeout=self.timeout)
        latency_ms = (time.time() - start_time) * 1000

        if resp.status_code != 200:
            resp.raise_for_status()

        data = resp.json()

        # Parse Gemini Response
        from app.providers.tools import tool_adapter
        content_text = ""
        tool_calls = None
        finish_reason = "stop"

        candidates = data.get("candidates", [])
        if candidates:
            cand = candidates[0]
            finish_reason = cand.get("finishReason", "stop").lower()
            if "content" in cand:
                parts = cand["content"].get("parts", [])
                for p in parts:
                    if "text" in p:
                        content_text += p["text"]
            # Check for function call
            tool_calls = tool_adapter.gemini_response_to_openai_tool_calls(cand)
            if tool_calls:
                finish_reason = "tool_calls"

        usage_meta = data.get("usageMetadata", {})
        prompt_tokens = usage_meta.get("promptTokenCount", 0)
        completion_tokens = usage_meta.get("candidatesTokenCount", 0)
        total_tokens = usage_meta.get("totalTokenCount", prompt_tokens + completion_tokens)

        cost = self.estimate_cost(model, prompt_tokens, completion_tokens)

        return ChatResponse(
            id=f"chatcmpl-gemini-{uuid.uuid4().hex[:12]}",
            model=model,
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatChoiceMessage(
                        role="assistant",
                        content=content_text if content_text else None,
                        tool_calls=tool_calls,
                    ),
                    finish_reason=finish_reason,
                )
            ],
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
        model = self._resolve_model(request.model)
        url = f"{self.base_url}/models/{model}:streamGenerateContent"
        params = {"key": self.api_key, "alt": "sse"} if self.api_key else {"alt": "sse"}
        payload = self._build_payload(request)
        req_id = f"chatcmpl-gemini-{uuid.uuid4().hex[:12]}"
        client = get_http_client()

        async with client.stream("POST", url, params=params, json=payload, timeout=self.timeout) as response:
            if response.status_code != 200:
                await response.aread()
                response.raise_for_status()

            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if not data_str:
                    continue
                try:
                    data = json.loads(data_str)
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        for part in parts:
                            if "text" in part:
                                yield ChatStreamChunk(
                                    id=req_id,
                                    model=model,
                                    choices=[
                                        StreamChoice(
                                            index=0,
                                            delta=DeltaMessage(content=part["text"]),
                                            finish_reason=None,
                                        )
                                    ],
                                    provider=self.name,
                                )
                except json.JSONDecodeError:
                    continue

        # Send final stop chunk
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
        start_time = time.time()
        try:
            if not self.api_key:
                return ProviderHealth(
                    provider=self.name,
                    status="unhealthy",
                    latency_ms=0.0,
                    error="API key not configured",
                )
            url = f"{self.base_url}/models/{self.default_model}"
            client = get_http_client()
            resp = await client.get(url, params={"key": self.api_key}, timeout=5.0)
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
