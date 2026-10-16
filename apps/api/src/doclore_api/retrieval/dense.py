import hashlib
import math
import os
import re
from typing import Optional, Protocol
import httpx
from doclore_api.models import Chunk


class EmbeddingAdapter(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...


class DeterministicEmbeddingAdapter:
    """In-process deterministic embedding adapter for tests and local fallback.
    
    Generates consistent unit-normalized semantic feature vectors using term hashing,
    n-grams, and character bigrams, allowing semantic similarity without external models.
    """

    def __init__(self, dimensions: int = 128) -> None:
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dimensions
            tokens = re.findall(r"\w+", text.lower())
            
            # Words
            for token in tokens:
                h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
                idx = h % self.dimensions
                sign = 1.0 if (h // self.dimensions) % 2 == 0 else -1.0
                vec[idx] += sign

            # Character trigrams for morphological and root similarity
            for token in tokens:
                for i in range(len(token) - 2):
                    trigram = token[i:i + 3]
                    h = int(hashlib.md5(trigram.encode("utf-8")).hexdigest(), 16)
                    idx = h % self.dimensions
                    sign = 1.0 if (h // self.dimensions) % 2 == 0 else -1.0
                    vec[idx] += 0.5 * sign

            # Normalize to unit vector
            norm = math.sqrt(sum(v * v for v in vec))
            if norm > 0.0:
                vec = [v / norm for v in vec]
            embeddings.append(vec)
        return embeddings


class LMStudioEmbeddingAdapter:
    """Connects to LM Studio's OpenAI-compatible /v1/embeddings endpoint."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        fallback: Optional[EmbeddingAdapter] = None,
    ) -> None:
        self.base_url = base_url or os.getenv("DOCLORE_LLM_BASE_URL", "http://127.0.0.1:1234/v1").rstrip("/")
        self.model = model or os.getenv("DOCLORE_EMBEDDING_MODEL", "text-embedding-nomic-embed-text-v1.5")
        self.api_key = api_key or os.getenv("DOCLORE_LLM_API_KEY", "lm-studio")
        self.fallback = fallback or DeterministicEmbeddingAdapter()

    BATCH_SIZE = 32

    last_used_fallback: bool = False

    def _embed_remote(self, texts: list[str]) -> Optional[list[list[float]]]:
        results: list[list[float]] = []
        try:
            with httpx.Client(timeout=httpx.Timeout(60.0, connect=2.0)) as client:
                for start in range(0, len(texts), self.BATCH_SIZE):
                    batch = texts[start:start + self.BATCH_SIZE]
                    res = client.post(
                        f"{self.base_url}/embeddings",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json={"input": batch, "model": self.model},
                    )
                    if res.status_code != 200:
                        return None
                    items = sorted(res.json()["data"], key=lambda x: x["index"])
                    vectors = [item["embedding"] for item in items]
                    if len(vectors) != len(batch) or any(not v for v in vectors):
                        return None
                    results.extend(vectors)
        except Exception:
            return None
        return results

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # Empty strings are rejected by some embedding servers.
        safe_texts = [t if t.strip() else " " for t in texts]
        remote = self._embed_remote(safe_texts)
        if remote is not None:
            self.last_used_fallback = False
            return remote
        # Fall back for the WHOLE call so a single response never mixes dimensions.
        self.last_used_fallback = True
        return self.fallback.embed(safe_texts)


class DenseVectorIndex:
    """In-memory vector store computing cosine similarity over normalized embeddings.

    Embeddings are cached by chunk id + text hash, so repeated searches only embed
    new or changed chunks (not the whole project every query).
    """

    def __init__(self, embedding_adapter: Optional[EmbeddingAdapter] = None) -> None:
        self.embedding_adapter = embedding_adapter or DeterministicEmbeddingAdapter()
        # chunk_id -> vector
        self.vectors: dict[str, list[float]] = {}
        self._text_hash: dict[str, str] = {}
        self._texts: dict[str, str] = {}

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()

    def _embed_and_store(self, items: list[tuple[str, str]]) -> None:
        if not items:
            return
        embeddings = self.embedding_adapter.embed([text for _, text in items])
        if len(embeddings) != len(items):
            return
        for (chunk_id, text), emb in zip(items, embeddings):
            self.vectors[chunk_id] = emb
            self._text_hash[chunk_id] = self._hash(text)
            self._texts[chunk_id] = text

    def index_chunks(self, chunks: list[Chunk]) -> None:
        if not chunks:
            self.vectors.clear()
            self._text_hash.clear()
            self._texts.clear()
            return
        pending = [
            (c.id, c.text)
            for c in chunks
            if c.id not in self.vectors or self._text_hash.get(c.id) != self._hash(c.text)
        ]
        self._embed_and_store(pending)

    def search(
        self,
        query: str,
        candidate_chunk_ids: Optional[set[str]] = None,
    ) -> list[tuple[str, float]]:
        if not self.vectors or not query.strip():
            return []

        query_embs = self.embedding_adapter.embed([query])
        if not query_embs:
            return []
        query_emb = query_embs[0]
        q_norm = math.sqrt(sum(x * x for x in query_emb))
        if q_norm == 0.0:
            return []

        # If the embedding model changed (e.g. LM Studio came online after a fallback
        # run), re-embed chunks whose dimension no longer matches the query.
        stale = [
            (cid, self._texts[cid])
            for cid, vec in self.vectors.items()
            if len(vec) != len(query_emb)
            and cid in self._texts
            and (candidate_chunk_ids is None or cid in candidate_chunk_ids)
        ]
        self._embed_and_store(stale)

        scores: dict[str, float] = {}
        for chunk_id, vec in self.vectors.items():
            if candidate_chunk_ids is not None and chunk_id not in candidate_chunk_ids:
                continue
            if len(vec) != len(query_emb):
                continue  # incompatible dimensions; never compare truncated vectors

            dot = sum(q * v for q, v in zip(query_emb, vec))
            v_norm = math.sqrt(sum(v * v for v in vec))
            sim = dot / (q_norm * v_norm) if (q_norm * v_norm) > 0.0 else 0.0
            if sim > 0.0:
                scores[chunk_id] = sim

        # Sort descending by score, tie-break by chunk_id
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        return ranked
