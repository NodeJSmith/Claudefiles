"""Tests for the pure RRF fusion function."""

from claude_memory.fusion import rrf, RRF_K


class TestRrf:
    def test_basic_merge(self):
        """A shared id ranks above singletons from a single list."""
        # id 1 appears in both lists (rank 0+0), should outrank ids only in one
        result = rrf([[1, 2, 3], [1, 4, 5]])
        assert result[0] == 1  # id 1 is top because it appears in both

    def test_disjoint_lists(self):
        """Fully disjoint lists return all ids with no error."""
        result = rrf([[1, 2], [3, 4]])
        assert set(result) == {1, 2, 3, 4}
        assert len(result) == 4

    def test_empty_list(self):
        """An empty ranked_lists returns an empty result."""
        assert rrf([]) == []

    def test_single_empty_ranked_list(self):
        """A list containing one empty list returns an empty result."""
        assert rrf([[]]) == []

    def test_mixed_empty(self):
        """Empty list mixed with non-empty list is handled gracefully."""
        assert rrf([[], [1, 2, 3]]) == [1, 2, 3]

    def test_deterministic(self):
        """Same input always produces same output."""
        lists = [[1, 2, 3], [2, 3, 4], [3, 4, 5]]
        assert rrf(lists) == rrf(lists)

    def test_shared_id_outranks_singletons(self):
        """Id shared across more lists should rank above ids in fewer lists."""
        # id 10 appears in 3 lists at rank 0 each; id 20 appears only once
        result = rrf([[10, 20], [10, 30], [10, 40]])
        assert result[0] == 10

    def test_additive_score_multi_list_id_ranks_first(self):
        """An id in two lists (additive score 2/(k+1)) outranks an id in one (1/(k+1))."""
        # id 2 appears in both lists at rank 0; id 1 and id 3 each in one list.
        result = rrf([[2, 1], [2, 3]], k=RRF_K)
        assert result[0] == 2

    def test_custom_k(self):
        """Custom k parameter is respected."""
        result = rrf([[1, 2], [2, 3]], k=10)
        # id 2 appears in both lists → should be first
        assert result[0] == 2

    def test_single_list(self):
        """Single ranked list preserves original order."""
        assert rrf([[5, 3, 1]]) == [5, 3, 1]

    def test_returns_all_ids(self):
        """Result contains every id that appeared in any list."""
        lists = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        result = rrf(lists)
        assert set(result) == {1, 2, 3, 4, 5, 6, 7, 8, 9}
