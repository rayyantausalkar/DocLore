from doclore_api.retrieval.rrf import reciprocal_rank_fusion


def test_rrf_boosts_items_in_both_lists() -> None:
    # item-A appears in both (rank 1 in dense, rank 2 in sparse)
    # item-B appears only in dense (rank 2)
    # item-C appears only in sparse (rank 1)
    dense_ranked = ["item-A", "item-B"]
    sparse_ranked = ["item-C", "item-A"]

    fused = reciprocal_rank_fusion(dense_ranked, sparse_ranked, k=60)

    # item-A: 1/(60+1) + 1/(60+2) = 1/61 + 1/62 = 0.01639 + 0.01613 = 0.03252
    # item-C: 1/(60+1) = 0.01639
    # item-B: 1/(60+2) = 0.01613
    assert len(fused) == 3
    assert fused[0].item_id == "item-A"
    assert fused[0].match_type == "hybrid"
    assert fused[0].dense_rank == 1
    assert fused[0].sparse_rank == 2

    assert fused[1].item_id == "item-C"
    assert fused[1].match_type == "exact_sparse"
    assert fused[1].dense_rank is None
    assert fused[1].sparse_rank == 1

    assert fused[2].item_id == "item-B"
    assert fused[2].match_type == "dense_semantic"
    assert fused[2].dense_rank == 2
    assert fused[2].sparse_rank is None


def test_rrf_deterministic_tie_breaking() -> None:
    # Both items have identical single-rank scores
    dense_ranked = ["item-beta", "item-alpha"]
    sparse_ranked = ["item-alpha", "item-beta"]

    fused = reciprocal_rank_fusion(dense_ranked, sparse_ranked, k=60)
    # Both have rank 1 in one and rank 2 in the other!
    # They should have the exact same score, and tie break deterministically by item_id
    assert fused[0].rrf_score == fused[1].rrf_score
    assert fused[0].item_id == "item-alpha"
    assert fused[1].item_id == "item-beta"
