import threading
from typing import Optional
from doclore_api.models import Chunk
from doclore_api.persistence.repository import DocumentRepository, SourceRepository
from doclore_api.retrieval.bm25 import BM25Index
from doclore_api.retrieval.dense import DenseVectorIndex, EmbeddingAdapter
from doclore_api.retrieval.models import Evidence, RetrievalScope
from doclore_api.retrieval.rrf import reciprocal_rank_fusion


class RetrievalService:
    """Orchestrates hybrid sparse + dense retrieval fused via Reciprocal Rank Fusion."""

    def __init__(
        self,
        source_repo: SourceRepository,
        document_repo: DocumentRepository,
        bm25_index: Optional[BM25Index] = None,
        dense_index: Optional[DenseVectorIndex] = None,
        embedding_adapter: Optional[EmbeddingAdapter] = None,
        rrf_k: int = 60,
    ) -> None:
        self.source_repo = source_repo
        self.document_repo = document_repo
        self.bm25_index = bm25_index or BM25Index()
        self.dense_index = dense_index or DenseVectorIndex(embedding_adapter=embedding_adapter)
        self.rrf_k = rrf_k
        self._lock = threading.RLock()

    def _get_project_chunks(self, scope: RetrievalScope) -> list[Chunk]:
        """Fetch all chunks belonging to the scoped project and sources."""
        sources = self.source_repo.list_by_project(scope.project_id)
        if scope.source_ids:
            sources = [s for s in sources if s.id in scope.source_ids]
        if scope.source_types:
            sources = [s for s in sources if s.source_type in scope.source_types]

        all_chunks: list[Chunk] = []
        for src in sources:
            all_chunks.extend(self.document_repo.get_chunks_by_source(src.id))
        return all_chunks

    def search(self, query: str, scope: RetrievalScope, limit: int = 5) -> list[Evidence]:
        """Run hybrid retrieval and return evidence ordered by RRF score."""
        if not query or not query.strip():
            return []
        with self._lock:
            return self._search_locked(query, scope, limit)

    def _search_locked(self, query: str, scope: RetrievalScope, limit: int) -> list[Evidence]:
        chunks = self._get_project_chunks(scope)
        if not chunks:
            return []

        # Index chunks in both BM25 and Dense index
        self.bm25_index.index_chunks(chunks)
        self.dense_index.index_chunks(chunks)

        candidate_ids = {c.id for c in chunks}
        chunk_map = {c.id: c for c in chunks}

        # 1. Sparse BM25 ranking
        sparse_results = self.bm25_index.search(query, candidate_chunk_ids=candidate_ids)
        sparse_ranked_ids = [cid for cid, _ in sparse_results]

        # 2. Dense semantic ranking
        dense_results = self.dense_index.search(query, candidate_chunk_ids=candidate_ids)
        dense_ranked_ids = [cid for cid, _ in dense_results]

        # 3. Reciprocal Rank Fusion
        fused = reciprocal_rank_fusion(
            dense_ranked_ids=dense_ranked_ids,
            sparse_ranked_ids=sparse_ranked_ids,
            k=self.rrf_k,
        )

        top_fused = fused[:limit]
        evidence_list: list[Evidence] = []

        for item in top_fused:
            chunk = chunk_map.get(item.item_id)
            if not chunk:
                continue

            evidence_list.append(
                Evidence(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    text=chunk.text,
                    provenance=chunk.provenance,
                    rrf_score=item.rrf_score,
                    dense_rank=item.dense_rank,
                    sparse_rank=item.sparse_rank,
                    match_type=item.match_type,
                )
            )

        return evidence_list
