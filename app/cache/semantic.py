import logging
import math
import time

from app.providers.base import ChatResponse

logger = logging.getLogger("prodllm.semantic_cache")


def simple_embedding(text: str, dim: int = 128) -> list[float]:
    """
    Fast, zero-dependency character-trigram bag-of-words embedding vector generator.
    Produces a normalized float vector for semantic similarity matching without heavy dependencies.
    """
    text = text.lower().strip()
    vector = [0.0] * dim
    if not text:
        return vector

    # Character 3-grams
    trigrams = [text[i:i + 3] for i in range(max(1, len(text) - 2))]
    if not trigrams:
        trigrams = [text]

    for tg in trigrams:
        idx = hash(tg) % dim
        vector[idx] += 1.0

    # L2 Normalize
    norm = math.sqrt(sum(x * x for x in vector))
    if norm > 0:
        vector = [x / norm for x in vector]
    return vector


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Compute cosine similarity between two unit vectors."""
    if len(v1) != len(v2):
        return 0.0
    return sum(a * b for a, b in zip(v1, v2))


class SemanticCacheEntry:
    def __init__(self, prompt: str, embedding: list[float], response: ChatResponse, ttl_seconds: int = 3600):
        self.prompt = prompt
        self.embedding = embedding
        self.response = response
        self.expires_at = time.time() + ttl_seconds


class SemanticCache:
    """
    Vector similarity cache for LLM completions.
    Matches semantically similar queries above similarity_threshold (e.g. 0.88),
    drastically reducing upstream LLM invocations and saving token costs.
    """

    def __init__(self, similarity_threshold: float = 0.88, max_entries: int = 1000):
        self.similarity_threshold = similarity_threshold
        self.max_entries = max_entries
        self._entries: dict[str, SemanticCacheEntry] = {}

    def get_query_text(self, messages: list) -> str:
        # Extract last user message
        for m in reversed(messages):
            if getattr(m, "role", "") == "user" or (isinstance(m, dict) and m.get("role") == "user"):
                return getattr(m, "content", "") if hasattr(m, "content") else m.get("content", "")
        return ""

    async def search(self, messages: list, model: str) -> tuple[ChatResponse, float] | None:
        """
        Search for semantically similar cached response.
        Returns: (ChatResponse, similarity_score) if found, else None.
        """
        query_text = self.get_query_text(messages)
        if not query_text or len(query_text) < 5:
            return None

        query_vec = simple_embedding(query_text)
        now = time.time()

        best_match: SemanticCacheEntry | None = None
        best_score = -1.0

        for key, entry in list(self._entries.items()):
            if now > entry.expires_at:
                del self._entries[key]
                continue

            score = cosine_similarity(query_vec, entry.embedding)
            if score > best_score:
                best_score = score
                best_match = entry

        if best_match and best_score >= self.similarity_threshold:
            logger.info(
                f"Semantic cache HIT (similarity: {best_score:.3f} >= {self.similarity_threshold}): "
                f"'{query_text[:40]}' matched '{best_match.prompt[:40]}'"
            )
            resp = best_match.response.model_copy(deep=True)
            resp.cached = True
            return resp, best_score

        return None

    async def store(self, messages: list, model: str, response: ChatResponse, ttl_seconds: int = 3600):
        query_text = self.get_query_text(messages)
        if not query_text:
            return

        if len(self._entries) >= self.max_entries:
            # Evict oldest entry
            oldest_key = min(self._entries.keys(), key=lambda k: self._entries[k].expires_at)
            del self._entries[oldest_key]

        vec = simple_embedding(query_text)
        entry_key = f"{model}:{hash(query_text)}"
        self._entries[entry_key] = SemanticCacheEntry(query_text, vec, response, ttl_seconds)


semantic_cache = SemanticCache()
