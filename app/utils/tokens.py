from app.providers.base import ChatMessage

try:
    import tiktoken
    _encoder = tiktoken.get_encoding("cl100k_base")
except Exception:
    _encoder = None


def count_tokens(text: str) -> int:
    """
    Count tokens using tiktoken (cl100k_base) with fast heuristic fallback.
    """
    if not text:
        return 0
    if _encoder:
        try:
            return len(_encoder.encode(text))
        except Exception:
            pass
    # Fast fallback heuristic: ~4 chars per token in English
    return max(1, len(text) // 4)


def count_messages_tokens(messages: list[ChatMessage]) -> int:
    """
    Calculate prompt token count from a list of ChatMessage objects according to OpenAI formatting rules.
    """
    num_tokens = 0
    for msg in messages:
        num_tokens += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
        num_tokens += count_tokens(msg.role)
        num_tokens += count_tokens(msg.content)
        if msg.name:
            num_tokens += count_tokens(msg.name)
    num_tokens += 2  # every reply is primed with <im_start>assistant
    return num_tokens
