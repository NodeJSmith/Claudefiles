# Python

## Never Use `from __future__ import annotations`

Do not add `from __future__ import annotations` to any file. It changes all annotations to strings at runtime, which breaks Pydantic models, FastAPI dependencies, dataclasses, `typing.get_type_hints()`, and any library that inspects annotations at runtime. Use `X | Y` syntax (Python 3.10+) or `Optional[X]` for type hints instead.
