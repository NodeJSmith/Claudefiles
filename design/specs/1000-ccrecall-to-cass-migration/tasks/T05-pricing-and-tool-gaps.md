---
task_id: "T05"
title: "Extract pricing module and update mine-tool-gaps"
status: "planned"
depends_on: []
implements: ["FR#9", "FR#10", "AC#10", "AC#11"]
---

## Summary
Inline the pricing functions from ccrecall's `token_parser.py` into `bin/orchestrate-cost`, removing its ccrecall PyPI dependency. Update `skills/mine-tool-gaps/SKILL.md` to call `cass search --robot` instead of `ccrecall --json search`. Add a pricing parity test to verify the extracted module produces identical results.

## Target Files
- modify: `bin/orchestrate-cost`
- modify: `skills/mine-tool-gaps/SKILL.md`
- modify: `tests/test_hooks.py`
- read: `~/source/claude-code-recall/src/ccrecall/token_parser.py` (lines 63-162 — the pricing block to extract)
- read: `design/specs/1000-ccrecall-to-cass-migration/design.md` (§ Architecture > Pricing extraction)

## Prompt
### bin/orchestrate-cost changes

**Remove the ccrecall dependency:**
1. Update the PEP 723 header — change `dependencies = ["ccrecall>=0.12.0", "whenever>=0.10"]` to `dependencies = ["whenever>=0.10"]`.
2. Remove line 59: `from ccrecall.token_parser import get_pricing, turn_cost`.
3. Update the module docstring: lines 6-8 ("0.12.0 is the floor...") reference a dependency that no longer exists — remove. Lines 16-19 ("Pricing is delegated entirely to ccrecall.token_parser... this tool never hardcodes a rate") become false after inlining — update to describe the inlined pricing table.

**Inline the pricing module:**
Copy the contiguous block from `~/source/claude-code-recall/src/ccrecall/token_parser.py` lines 63-162 into `orchestrate-cost`. This includes:
- `_LEGACY_OPUS_RATES` dict (lines 63-69)
- `MODEL_PRICING` list of tuples (lines 71-118)
- `DEFAULT_PRICING` (line 124)
- `get_pricing()` function (lines 127-139)
- `turn_cost()` function (lines 142-162)

Place this block after the existing imports, before the `START_MARKER` constant (line 68). The `import re` already exists in orchestrate-cost (line 51) — `get_pricing()` uses `re.search()`.

**This is a copy, not a rewrite.** The behavioral invariant requires identical pricing calculations. Do not simplify, rename, or restructure the code.

### skills/mine-tool-gaps/SKILL.md changes

Replace the ccrecall CLI call in the "Targeted mode archaeology" section (lines 59-66):

**Before:**
```bash
ccrecall --json search --query "<tool>" --max-results 10
# Note: max-results caps at 10; --json is a global flag, before the subcommand.
```

**After:**
```bash
cass search "<tool>" --robot --limit 10
```

Update the surrounding prose to reference cass instead of ccrecall. The `--robot` flag replaces `--json` and goes after the subcommand. The `--limit` flag replaces `--max-results`.

### Pricing parity test

Add a test to `tests/test_hooks.py` (or a new test file if cleaner) that verifies the extracted pricing module produces identical results to ccrecall's original:

- For each model tier in `MODEL_PRICING` (opus legacy, opus current, sonnet, haiku), compute `turn_cost()` with a fixed set of token inputs using the inlined pricing, and assert the result matches a hardcoded expected value (computed once from the original ccrecall code).
- Test `get_pricing()` returns the correct rates for representative model IDs: `"claude-opus-4-0"`, `"claude-opus-4-6"`, `"claude-sonnet-4-6"`, `"claude-haiku-4-5"`, and a fallback for an unknown model.

## Focus
- `bin/orchestrate-cost` is a PEP 723 uv-script — it runs via `uv run --script`. The inline dependency metadata is what `uv` reads to create its virtual environment. Removing `ccrecall` from `dependencies` means `uv` no longer installs it.
- The pricing module uses `re.search()` with `re.escape()` — both already available since `import re` is at line 51.
- The `_LEGACY_OPUS_RATES` dict is shared by three `MODEL_PRICING` entries to avoid duplication. Copy the reference pattern exactly.
- `DEFAULT_PRICING` resolves Sonnet rates from `MODEL_PRICING` using a generator expression with `next()`. This pattern must be preserved.
- The mine-tool-gaps SKILL.md change is a two-line edit — replace the command and update the comment.

## Verify
- [ ] FR#9: `orchestrate-cost` runs without ccrecall installed — no import errors, correct pricing
- [ ] FR#10: `mine-tool-gaps` skill calls `cass search --robot` for session discovery
- [ ] AC#10: `orchestrate-cost` produces correct pricing with standalone module
- [ ] AC#11: `/mine-tool-gaps` uses cass, not ccrecall
