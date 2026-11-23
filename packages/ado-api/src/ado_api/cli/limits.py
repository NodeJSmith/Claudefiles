"""The cap every repeatable/variadic CLI argument shares."""

from collections.abc import Sized

MAX_VARIADIC_ITEMS = 100


def validate_item_limit(_type: object, value: Sized | None) -> None:
    """A cyclopts ``Parameter(validator=...)`` enforcing :data:`MAX_VARIADIC_ITEMS`."""
    if value is not None and len(value) > MAX_VARIADIC_ITEMS:
        raise ValueError(f"Too many items: {len(value)} (max {MAX_VARIADIC_ITEMS})")
