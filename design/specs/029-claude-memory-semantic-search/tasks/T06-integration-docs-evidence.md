---
task_id: "T06"
title: "Integration verification, docs, and semantic-recall evidence"
status: "planned"
depends_on: ["T03", "T04", "T05"]
implements: ["FR#3", "AC#1", "AC#7", "AC#8"]
---

## Summary
Tie the feature together: run the full package suite, confirm the keyword-only and recent-chats invariants hold, capture the real before/after semantic-recall evidence on the production DB, and update the user-facing docs (README, CHANGELOG, CLI reference, tool-reference). This is the end-to-end verification + documentation pass.

## Prompt
Work in `packages/claude-memory/` and the repo docs.

1. **Full suite + invariants:**
   - Run `cd packages/claude-memory && uv sync && uv run pytest` — all tests pass (AC#7). Capture the output.
   - Confirm `cm-recent-chats` (time-ordered, no query — uses `get_db_connection` with default `load_vec=False`) produces identical output before and after the change (AC#8). A simple before/after diff on a fixture DB, or a test asserting recent-chats output is unaffected.
   - Confirm the degrade path end-to-end (FR#3): on a connection where vec can't load, `cm-search-conversations -q "..."` returns keyword results and exits 0.

2. **Real semantic-recall evidence (AC#1, manual):** against the live `~/.claude-memory/conversations.db` (~12.8k branches) after `cm-backfill-embeddings` has populated `branch_vec`:
   - Run the known failing query phrased with **different words** than the stored summary (the "windows terminal settings sync" concept). Capture `cm-search-conversations` output **with fusion** (correct session in top results) and **with `--keyword-only`** (misses / wrong rank). Identify the correct session by reading the result.
   - Paste both outputs into the PR description as the before/after evidence. Note which session is "correct" and why.

3. **Docs:**
   - `packages/claude-memory/README.md` — document semantic search, the `--keyword-only` and `--status` flags, the new dependency footprint, and the `cm-backfill-embeddings` command.
   - Package `CHANGELOG` (repo convention) — a feature entry calling out the new runtime deps (`sqlite-vec`, `onnxruntime`, `tokenizers`, `numpy`).
   - `skills-memory/cm-recall-conversations/references/tool-reference.md` — add `--keyword-only` and `--status` to the documented flags.
   - `skills-memory/cm-recall-conversations/SKILL.md` — optional one-line note that semantic recall is now active (no behavior change; fusion is default-on).
   - CLI `--help` text for `--keyword-only` and `--status` (verify the strings read well).

## Focus
- This task runs AFTER T03/T04/T05 land — it verifies their integration, it doesn't re-implement.
- AC#1 is the one manual, non-automatable criterion — it needs the real DB and a completed backfill. The evidence lives in the PR description, not a test file.
- The backfill on the real DB is ~20 min of CPU; run it deliberately (not in CI). `cm-search-conversations --status` should show embedded≈total when it's done.
- Do NOT touch memsearch docs. Do NOT add deps here (T01 owns `pyproject` deps).
- Keep prose human — apply the writing-quality guidance (no AI tells) to README/CHANGELOG entries.

## Verify
- [ ] FR#3: end-to-end, a vec-unavailable environment returns keyword-only search results and exits 0.
- [ ] AC#1: before/after `cm-search-conversations` output for the concept-phrased query (fusion hits, `--keyword-only` misses) is captured in the PR description, with the correct session identified.
- [ ] AC#7: `cd packages/claude-memory && uv sync && uv run pytest` passes (output captured).
- [ ] AC#8: `cm-recent-chats` output is identical before and after the change.
