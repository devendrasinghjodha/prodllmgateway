import logging

from app.providers.base import ChatMessage
from app.utils.tokens import count_messages_tokens, count_tokens

logger = logging.getLogger("prodllm.compression")


def prune_chat_context(
    messages: list[ChatMessage],
    max_context_tokens: int = 4000,
    keep_system_messages: bool = True,
    recent_messages_to_keep: int = 4,
) -> list[ChatMessage]:
    """
    Intelligently prune chat conversation context to fit within token limits and reduce API cost:
    1. Always preserves system prompt instructions.
    2. Always preserves the N most recent user and assistant interactions.
    3. Prunes older intermediate conversation turns if total tokens exceed max_context_tokens.
    """
    current_tokens = count_messages_tokens(messages)
    if current_tokens <= max_context_tokens or len(messages) <= recent_messages_to_keep + 1:
        return messages

    system_msgs = [m for m in messages if m.role == "system"] if keep_system_messages else []
    non_system_msgs = [m for m in messages if m.role != "system"]

    # Keep recent messages
    recent_msgs = non_system_msgs[-recent_messages_to_keep:]
    older_msgs = non_system_msgs[:-recent_messages_to_keep]

    # Calculate remaining budget
    fixed_tokens = count_messages_tokens(system_msgs + recent_msgs)
    available_budget = max(0, max_context_tokens - fixed_tokens)

    pruned_older = []
    accumulated_tokens = 0

    # Add older messages starting from most recent of older messages
    for msg in reversed(older_msgs):
        msg_tok = count_tokens(msg.content) + 4
        if accumulated_tokens + msg_tok <= available_budget:
            pruned_older.insert(0, msg)
            accumulated_tokens += msg_tok
        else:
            break

    total_pruned = system_msgs + pruned_older + recent_msgs
    saved_tokens = current_tokens - count_messages_tokens(total_pruned)
    if saved_tokens > 0:
        logger.info(f"Context pruning saved {saved_tokens} tokens ({current_tokens} -> {count_messages_tokens(total_pruned)})")

    return total_pruned
