# Python

## Never Use `from __future__ import annotations`

Do not add `from __future__ import annotations` to any file. It changes all annotations to strings at runtime, which breaks Pydantic models, FastAPI dependencies, dataclasses, `typing.get_type_hints()`, and any library that inspects annotations at runtime. Use `X | Y` syntax (Python 3.10+) for type hints instead.

## No `Optional[X]`

Do not use `Optional[X]`. Use `X | None` instead. `Optional[X]` is verbose, misleading (it doesn't mean the argument is optional), and inconsistent with `X | Y` union syntax.

## No Lazy Imports

Do not use lazy imports (importing inside functions or methods). Place all imports at the top of the file where they belong.

Lazy imports obscure dependencies, make grep-based analysis unreliable, break mock patching patterns (`patch("module.lib")` fails when `lib` isn't a module-level attribute), and hide import errors until runtime. They also create inconsistency — half the file uses top-level imports, half uses inline ones.

The only acceptable exception: imports guarded by `TYPE_CHECKING` for avoiding circular imports in type annotations.

## No `datetime.now()` Without Timezone

Do not use `datetime.now()` without a timezone argument. It returns a naive datetime that silently assumes local time, producing incorrect comparisons and serialization when code runs in different timezones or UTC-based infrastructure. Use `datetime.now(tz=timezone.utc)` or pass an explicit `tz=` argument.

## No `os.path.join`

Do not use `os.path.join` or other `os.path.*` functions for path manipulation. Use `pathlib.Path` instead — it is safer, more readable, and composable (e.g., `Path("dir") / "file.txt"`).

## No `pip`

Do not use `pip` to install packages. Always use `uv` (e.g., `uv pip install`, `uv add`). `uv` is the project's package manager and produces reproducible installs.
