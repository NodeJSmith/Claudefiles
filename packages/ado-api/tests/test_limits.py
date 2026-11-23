"""Tests for ado_api.cli.limits — shared variadic-argument bound."""

import pytest
from ado_api.cli.limits import MAX_VARIADIC_ITEMS, validate_item_limit


class TestValidateItemLimit:
    @pytest.mark.parametrize("value", [None, [], [1, 2, 3], list(range(MAX_VARIADIC_ITEMS))])
    def test_accepts_up_to_the_limit(self, value: list[int] | None) -> None:
        validate_item_limit(list, value)

    def test_rejects_one_over_the_limit(self) -> None:
        with pytest.raises(ValueError, match=f"Too many items: {MAX_VARIADIC_ITEMS + 1}"):
            validate_item_limit(list, list(range(MAX_VARIADIC_ITEMS + 1)))
