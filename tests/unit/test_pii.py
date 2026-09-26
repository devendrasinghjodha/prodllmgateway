import pytest
from app.guardrails.pii import PIIMasker
from app.providers.base import ChatMessage


def test_pii_masking_and_unmasking():
    masker = PIIMasker()
    original_text = "Please contact me at john.doe@company.org or call 415-555-0199 with card 4532-1234-5678-9012."
    messages = [ChatMessage(role="user", content=original_text)]

    masked_msgs, mapping = masker.mask_messages(messages)
    masked_content = masked_msgs[0].content

    # Assert PII is redacted
    assert "john.doe@company.org" not in masked_content
    assert "415-555-0199" not in masked_content
    assert "4532-1234-5678-9012" not in masked_content
    assert "[EMAIL_1]" in masked_content or "[PHONE_" in masked_content

    # Simulate LLM echoing the placeholders in response
    llm_reply = f"I have received your inquiry for [EMAIL_1] and verified phone [PHONE_2]."
    restored_reply = masker.unmask_text(llm_reply, mapping)

    assert "john.doe@company.org" in restored_reply
    assert "[EMAIL_1]" not in restored_reply
