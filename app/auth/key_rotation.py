import logging

logger = logging.getLogger("prodllm.key_rotation")


class KeyRotator:
    """
    Manages multiple active API keys per upstream LLM provider with round-robin rotation
    and auto-cooldown when rate limits (429) are encountered.
    """

    def __init__(self):
        self._provider_keys: dict[str, list[str]] = {}
        self._current_index: dict[str, int] = {}

    def register_keys(self, provider: str, keys: list[str]):
        cleaned_keys = [k.strip() for k in keys if k and k.strip()]
        if cleaned_keys:
            self._provider_keys[provider.lower()] = cleaned_keys
            self._current_index[provider.lower()] = 0
            logger.info(f"Registered {len(cleaned_keys)} API keys for provider '{provider}'.")

    def get_key(self, provider: str) -> str | None:
        p = provider.lower()
        keys = self._provider_keys.get(p, [])
        if not keys:
            return None
        idx = self._current_index.get(p, 0)
        selected_key = keys[idx % len(keys)]
        # Advance index for next round
        self._current_index[p] = (idx + 1) % len(keys)
        return selected_key

    def rotate_on_failure(self, provider: str, current_key: str):
        p = provider.lower()
        keys = self._provider_keys.get(p, [])
        if len(keys) > 1 and current_key in keys:
            curr_pos = keys.index(current_key)
            next_pos = (curr_pos + 1) % len(keys)
            self._current_index[p] = next_pos
            logger.warning(
                f"Rate limit or auth error on key for provider '{provider}'. Rotated to next key (pool size: {len(keys)})."
            )


key_rotator = KeyRotator()
