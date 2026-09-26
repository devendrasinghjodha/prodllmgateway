import pytest
from app.utils.tokens import count_tokens, count_messages_tokens
from app.providers.base import ChatMessage


def test_token_counting():
    text = "Hello world! This is a token calculation test."
    tokens = count_tokens(text)
    assert tokens > 0

    messages = [
        ChatMessage(role="system", content="You are a helpful AI assistant."),
        ChatMessage(role="user", content="Hello, tell me a joke."),
    ]
    msg_tokens = count_messages_tokens(messages)
    assert msg_tokens > len(messages)
