"""Shared bounds for variadic CLI arguments.

Every command that accepts a repeatable/variadic list caps it at the same value,
so the cap lives here rather than being redeclared per module — three copies had
already drifted apart in their error wording before this was centralized.
"""

from collections.abc import Callable

MAX_VARIADIC_ITEMS = 100


def variadic_limit_validator[T](
    *, label: str = "items"
) -> Callable[[object, list[T] | None], None]:
    """Build a cyclopts ``Parameter(validator=...)`` enforcing :data:`MAX_VARIADIC_ITEMS`."""

    def _validate(_type: object, value: list[T] | None) -> None:
        if value is not None and len(value) > MAX_VARIADIC_ITEMS:
            raise ValueError(
                f"Too many {label}: {len(value)} (max {MAX_VARIADIC_ITEMS})"
            )

    return _validate
