import logging
import re

from app.providers.base import ChatMessage

logger = logging.getLogger("prodllm.guardrails")

# Common blocked words and injection patterns
DEFAULT_BLOCKED_PATTERNS = [
    r"ignore previous instructions",
    r"bypass system prompt",
    r"you are now in developer mode",
    r"reveal your system prompt",
]


class ContentGuardrail:
    """
    Guardrail checking prompt safety, blocked words, and injection attempts.
    """

    def __init__(self, blocked_patterns: list[str] | None = None):
        patterns = blocked_patterns or DEFAULT_BLOCKED_PATTERNS
        self._regexes = [re.compile(p, re.IGNORECASE) for p in patterns]

    def validate_messages(self, messages: list[ChatMessage]) -> tuple[bool, str | None]:
        """
        Scan messages for violations.
        Returns: (is_safe, error_message)
        """
        for msg in messages:
            for regex in self._regexes:
                if regex.search(msg.content):
                    logger.warning(f"Guardrail triggered by pattern: {regex.pattern}")
                    return False, f"Request violated content safety policy (matched rule: {regex.pattern})"
        return True, None


guardrails = ContentGuardrail()
