import pytest
from app.auth.api_keys import generate_api_key, hash_api_key


def test_api_key_generation():
    raw_key, key_hash, prefix = generate_api_key("pllm_")
    assert raw_key.startswith("pllm_")
    assert prefix.startswith("pllm_")
    assert len(key_hash) == 64  # SHA-256 output length
    assert hash_api_key(raw_key) == key_hash


def test_api_key_deterministic_hashing():
    key1 = "pllm_test_key_123456"
    hash1 = hash_api_key(key1)
    hash2 = hash_api_key(key1)
    assert hash1 == hash2
    assert hash1 != hash_api_key("pllm_different_key")
