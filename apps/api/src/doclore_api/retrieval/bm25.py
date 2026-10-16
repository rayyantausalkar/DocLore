import math
import re
from typing import Optional
from doclore_api.models import Chunk


class BM25Index:
    """In-memory Okapi BM25 implementation optimized for developer documentation and code tokens."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.corpus_size: int = 0
        self.avgdl: float = 0.0
        self.doc_lengths: dict[str, int] = {}
        # token -> doc_id -> frequency
        self.inverted_index: dict[str, dict[str, int]] = {}
        # token -> document count
        self.doc_frequencies: dict[str, int] = {}
        self.chunks_by_id: dict[str, Chunk] = {}

    @staticmethod
    def tokenize(text: str) -> list[str]:
        """Tokenize preserving technical tokens, error codes, HTTP statuses, and identifiers."""
        # Find continuous sequences of alphanumeric characters, underscores, and hyphens
        raw_tokens = re.findall(r"[A-Za-z0-9_\-\.\/]+", text.lower())
        tokens: list[str] = []
        for t in raw_tokens:
            cleaned = t.strip(".-/")
            if cleaned:
                tokens.append(cleaned)
                # If token has subparts (snake_case, kebab-case, or dot-notation), also add components
                subparts = re.split(r"[_\-\.]+", cleaned)
                if len(subparts) > 1:
                    for sp in subparts:
                        if sp:
                            tokens.append(sp)
        return tokens

    def index_chunks(self, chunks: list[Chunk]) -> None:
        """Indexes or re-indexes a collection of chunks."""
        self.corpus_size = len(chunks)
        self.chunks_by_id = {c.id: c for c in chunks}
        self.inverted_index.clear()
        self.doc_frequencies.clear()
        self.doc_lengths.clear()

        total_length = 0
        for chunk in chunks:
            tokens = self.tokenize(chunk.text)
            length = len(tokens)
            self.doc_lengths[chunk.id] = length
            total_length += length

            tf_map: dict[str, int] = {}
            for token in tokens:
                tf_map[token] = tf_map.get(token, 0) + 1

            for token, freq in tf_map.items():
                if token not in self.inverted_index:
                    self.inverted_index[token] = {}
                self.inverted_index[token][chunk.id] = freq
                self.doc_frequencies[token] = self.doc_frequencies.get(token, 0) + 1

        self.avgdl = (total_length / self.corpus_size) if self.corpus_size > 0 else 0.0

    def search(self, query: str, candidate_chunk_ids: Optional[set[str]] = None) -> list[tuple[str, float]]:
        """Score candidate chunks using Okapi BM25 formula.
        
        Returns a sorted list of (chunk_id, bm25_score) descending.
        """
        if self.corpus_size == 0:
            return []

        query_tokens = self.tokenize(query)
        if not query_tokens:
            return []

        scores: dict[str, float] = {}

        for token in query_tokens:
            if token not in self.inverted_index:
                continue

            doc_dict = self.inverted_index[token]
            df = self.doc_frequencies[token]

            # Standard Okapi IDF
            idf = math.log(1.0 + (self.corpus_size - df + 0.5) / (df + 0.5))

            for chunk_id, tf in doc_dict.items():
                if candidate_chunk_ids is not None and chunk_id not in candidate_chunk_ids:
                    continue

                doc_len = self.doc_lengths.get(chunk_id, 0)
                norm = 1.0 - self.b + self.b * (doc_len / self.avgdl if self.avgdl > 0 else 1.0)
                term_score = idf * (tf * (self.k1 + 1.0)) / (tf + self.k1 * norm)
                scores[chunk_id] = scores.get(chunk_id, 0.0) + term_score

        # Sort descending by score, tie-break by chunk_id
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        return [(cid, score) for cid, score in ranked if score > 0.0]
