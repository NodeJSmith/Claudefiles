"""Tests for ado_api.cli.limits — shared variadic-argument bound."""

import pytest
from ado_api.cli.limits import MAX_VARIADIC_ITEMS, variadic_limit_validator


class TestVariadicLimitValidator:
    def test_passes_when_within_limit(self) -> None:
        validate = variadic_limit_validator(label="items")
        validate(list, [1, 2, 3])

    def test_allows_exactly_the_limit(self) -> None:
        validate = variadic_limit_validator(label="items")
        validate(list, list(range(MAX_VARIADIC_ITEMS)))

    def test_rejects_one_over_the_limit(self) -> None:
        validate = variadic_limit_validator(label="items")
        with pytest.raises(
            ValueError, match=f"Too many items: {MAX_VARIADIC_ITEMS + 1}"
        ):
            validate(list, list(range(MAX_VARIADIC_ITEMS + 1)))

    def test_label_appears_in_the_message(self) -> None:
        validate = variadic_limit_validator(label="--build items")
        with pytest.raises(ValueError, match="Too many --build items"):
            validate(list, list(range(MAX_VARIADIC_ITEMS + 1)))

    def test_none_value_is_skipped(self) -> None:
        validate = variadic_limit_validator(label="items")
        validate(list, None)

    def test_empty_list_is_fine(self) -> None:
        validate = variadic_limit_validator(label="items")
        validate(list, [])
