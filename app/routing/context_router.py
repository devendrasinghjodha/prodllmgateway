import logging
from typing import List, Optional
from app.providers.base import LLMProvider, ChatRequest
from app.routing.policies import RoutingPolicy
from app.utils.tokens import count_messages_tokens

logger = logging.getLogger("prodllm.context_router")


class ContextLengthPolicy(RoutingPolicy):
    """
    Dynamic context-length routing:
    - Long prompts (> 8,000 tokens): Routes to large context models (e.g. Gemini 1.5 Pro / Flash 1M context)
    - Medium prompts (2,000 - 8,000 tokens): Routes to balanced standard models (Agnes / OpenRouter)
    - Short prompts (< 2,000 tokens): Routes to ultra-low-latency models
    """

    def select_providers(
        self,
        request: ChatRequest,
        available_providers: List[LLMProvider],
        user_id: Optional[str] = None,
    ) -> List[LLMProvider]:
        token_count = count_messages_tokens(request.messages)
        provider_map = {p.name.lower(): p for p in available_providers}

        if token_count > 8000:
            logger.info(f"Long context detected ({token_count} tokens) -> prioritizing Gemini large context.")
            preferred = ["gemini", "openrouter", "agnes"]
        elif token_count < 2000:
            preferred = ["agnes", "gemini", "openrouter"]
        else:
            preferred = ["openrouter", "gemini", "agnes"]

        ordered = []
        for name in preferred:
            if name in provider_map:
                ordered.append(provider_map[name])
        for p in available_providers:
            if p not in ordered:
                ordered.append(p)
        return ordered
