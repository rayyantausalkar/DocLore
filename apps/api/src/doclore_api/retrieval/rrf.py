from dataclasses import dataclass
from typing import Literal, Optional


@dataclass(frozen=True)
class FusedRankItem:
    item_id: str
    rrf_score: float
    dense_rank: Optional[int]
    sparse_rank: Optional[int]
    match_type: Literal["hybrid", "exact_sparse", "dense_semantic"]


def reciprocal_rank_fusion(
    dense_ranked_ids: list[str],
    sparse_ranked_ids: list[str],
    k: int = 60,
) -> list[FusedRankItem]:
    """Combines dense and sparse ranked lists using Reciprocal Rank Fusion.
    
    Formula:
        score(d) = sum_{m in {dense, sparse}} (1 / (k + rank_m(d)))
    
    Ties are broken deterministically by best single rank, then lexicographically by item_id.
    """
    dense_ranks: dict[str, int] = {
        item_id: rank for rank, item_id in enumerate(dense_ranked_ids, start=1)
    }
    sparse_ranks: dict[str, int] = {
        item_id: rank for rank, item_id in enumerate(sparse_ranked_ids, start=1)
    }

    all_ids = set(dense_ranks.keys()).union(set(sparse_ranks.keys()))
    fused_items: list[FusedRankItem] = []

    for item_id in all_ids:
        d_rank = dense_ranks.get(item_id)
        s_rank = sparse_ranks.get(item_id)

        score = 0.0
        if d_rank is not None:
            score += 1.0 / (k + d_rank)
        if s_rank is not None:
            score += 1.0 / (k + s_rank)

        if d_rank is not None and s_rank is not None:
            match_type: Literal["hybrid", "exact_sparse", "dense_semantic"] = "hybrid"
        elif s_rank is not None:
            match_type = "exact_sparse"
        else:
            match_type = "dense_semantic"

        fused_items.append(
            FusedRankItem(
                item_id=item_id,
                rrf_score=score,
                dense_rank=d_rank,
                sparse_rank=s_rank,
                match_type=match_type,
            )
        )

    # Sort descending by score, tie-break by min(rank) if available, then item_id
    def sort_key(item: FusedRankItem):
        best_rank = min(
            item.dense_rank if item.dense_rank is not None else 999999,
            item.sparse_rank if item.sparse_rank is not None else 999999,
        )
        return (-item.rrf_score, best_rank, item.item_id)

    fused_items.sort(key=sort_key)
    return fused_items
