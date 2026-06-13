"""Reciprocal Rank Fusion — pure function, no model dependency."""

# At small top-K its exact value barely matters; 60 is the standard default.
RRF_K = 60


def rrf(ranked_lists: list[list[int]], k: int = RRF_K) -> list[int]:
    """Standard Reciprocal Rank Fusion over any number of ranked id-lists.

    Returns fused ids in descending score order. Handles empty lists and
    fully disjoint lists without error.
    """
    scores: dict[int, float] = {}
    for ranked in ranked_lists:
        for rank, id_ in enumerate(ranked):
            scores[id_] = scores.get(id_, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda id_: scores[id_], reverse=True)
