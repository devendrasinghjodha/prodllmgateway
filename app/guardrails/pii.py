import logging
import re

from app.providers.base import ChatMessage

logger = logging.getLogger("prodllm.pii")


class PIIMasker:
    """
    Real-time Personally Identifiable Information (PII) Masker & Anonymizer.
    Masks sensitive data before sending to upstream LLMs, and restores it in responses.
    """

    PATTERNS = {
        "EMAIL": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
        "PHONE": r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
        "CREDIT_CARD": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
        "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
        "IPV4": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    }

    def __init__(self):
        self._compiled = {k: re.compile(v) for k, v in self.PATTERNS.items()}

    def mask_text(self, text: str, mapping: dict[str, str]) -> str:
        masked_text = text
        for pii_type, regex in self._compiled.items():
            matches = list(regex.finditer(masked_text))
            for match in reversed(matches):
                val = match.group(0)
                # Check if already mapped
                placeholder = None
                for pl, orig in mapping.items():
                    if orig == val:
                        placeholder = pl
                        break
                if not placeholder:
                    placeholder = f"[{pii_type}_{len(mapping) + 1}]"
                    mapping[placeholder] = val

                start, end = match.span()
                masked_text = masked_text[:start] + placeholder + masked_text[end:]
        return masked_text

    def mask_messages(self, messages: list[ChatMessage]) -> tuple[list[ChatMessage], dict[str, str]]:
        mapping: dict[str, str] = {}
        masked_messages = []

        for msg in messages:
            masked_content = self.mask_text(msg.content or "", mapping)
            masked_messages.append(
                ChatMessage(
                    role=msg.role,
                    content=masked_content,
                    name=msg.name,
                )
            )

        if mapping:
            logger.info(f"PII Masker redacted {len(mapping)} sensitive entities: {list(mapping.keys())}")

        return masked_messages, mapping

    def unmask_text(self, text: str, mapping: dict[str, str]) -> str:
        if not mapping or not text:
            return text
        unmasked = text
        for placeholder, original in mapping.items():
            unmasked = unmasked.replace(placeholder, original)
        return unmasked


pii_masker = PIIMasker()
