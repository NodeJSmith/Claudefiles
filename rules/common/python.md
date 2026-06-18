---
tool: claude, codex, antigravity
---

# Python

## Never Use `from __future__ import annotations`

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

Do not add `from __future__ import annotations` to any file. It changes all annotations to strings at runtime, which breaks Pydantic models, FastAPI dependencies, dataclasses, `typing.get_type_hints()`, and any library that inspects annotations at runtime. Use `X | Y` syntax (Python 3.10+) for type hints instead.

## No `Optional[X]`

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

Do not use `Optional[X]`. Use `X | None` instead. `Optional[X]` is verbose, misleading (it doesn't mean the argument is optional), and inconsistent with `X | Y` union syntax.

## No Lazy Imports

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

Do not use lazy imports (importing inside functions or methods). Place all imports at the top of the file where they belong.

Lazy imports obscure dependencies, make grep-based analysis unreliable, break mock patching patterns (`patch("module.lib")` fails when `lib` isn't a module-level attribute), and hide import errors until runtime. They also create inconsistency — half the file uses top-level imports, half uses inline ones.

The only acceptable exception: imports guarded by `TYPE_CHECKING` for avoiding circular imports in type annotations.

## Use `whenever` Instead of stdlib `datetime`

Use the [`whenever`](https://github.com/ariebovenberg/whenever) library for all date/time operations. Do not use `datetime`, `date`, `time`, or `timedelta` from the standard library.

stdlib `datetime` is error-prone — naive datetimes silently lose timezone info, arithmetic ignores DST transitions, and comparisons between aware and naive objects raise at runtime. `whenever` makes these errors impossible at the type level.

```python
from whenever import Instant, ZonedDateTime, TimeDelta

now = Instant.now()
deadline = now.add(hours=24)
meeting = ZonedDateTime(2026, 3, 15, 14, 0, tz="America/New_York")
duration = TimeDelta(hours=2, minutes=30)
```

**Boundary exception:** When a library requires stdlib types (SQLAlchemy columns, Pydantic serialization, third-party APIs), convert at the boundary. Keep `whenever` types in all application logic.

```python
record.created_at = meeting.to_stdlib()
loaded = Instant(record.created_at)
```
