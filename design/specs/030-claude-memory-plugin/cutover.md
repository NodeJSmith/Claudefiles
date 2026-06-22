# Cutover: De-vendor claude-memory, consume ccrecall as a plugin

**Date:** 2026-06-21 (updated 2026-06-22)
**Status:** documented — **do not execute yet** (gated on external prerequisites)
**Companion:** [`brief.md`](./brief.md) (the platform decision); this doc is the Claudefiles-side change set.

## What this is

The Claudefiles-side cutover: remove the vendored `packages/claude-memory` + the
`cm-*` skill bundle + the hand-wired memory hooks, and instead consume the extracted
[`ccrecall`](https://github.com/NodeJSmith/claude-code-recall) plugin. This document is
an execution-ready inventory. The destructive removals are **staged behind three external
prerequisites** (below) because executing early takes live memory dark on all 5 machines
— the brief's explicit "no data-loss window" constraint.

## Decisions locked in (session 2026-06-21)

- **Plugin source (RESOLVED 2026-06-22):** the ccr repo doubles as a single-plugin
  marketplace. Marketplace name **`claude-code-recall`**, source **`NodeJSmith/claude-code-recall`**
  (the GitHub repo); `enabledPlugins` key is **`ccrecall@claude-code-recall`**. We do **not**
  touch the ccr repo from Claudefiles.
- **Package install (RESOLVED 2026-06-22):** `ccrecall` is published — PyPI **v0.10.0**.
  Install with `uv tool install ccrecall` (separate from `install.py` bundles; provides both
  the `ccrecall` CLI and the five `cm-*` hook binaries).
- **`mine-resume`:** delete it. The plugin ships `ccr-resume` (identical workflow, uses
  `ccrecall tail` instead of the removed `cm-session-tail`) as the replacement.
- **Data dir + embedding model CHANGED (discovered 2026-06-22 — earlier "zero migration"
  assumption was wrong):** `ccrecall` stores at **`~/.ccrecall/`**, not `~/.claude-memory/`,
  and swaps the embedding model **bge-m3 (1024-dim, `EMBEDDING_VERSION` 1) → jina-v2-small-en
  (512-dim, version 2)**. Existing machines therefore need a data migration — but as of
  ccrecall **v0.11.0 this is automatic** (the SessionStart hook detects the legacy dir and
  background-copies it forward). See [Per-machine data migration](#per-machine-data-migration-new)
  below.

## External prerequisites (gating — must be true before executing the removals)

1. **✅ DONE — ccrecall marketplace exists and is reachable** from all 5 machines.
   `.claude-plugin/marketplace.json` is on `origin/main`; name `claude-code-recall`,
   plugin `ccrecall` (source `./`). `enabledPlugins` references `ccrecall@claude-code-recall`.
2. **✅ DONE — `ccrecall` is installable as a package** providing the hook binaries
   (`cm-memory-setup`, `cm-memory-sync`, `cm-memory-context`, `cm-onboarding`,
   `cm-clear-handoff`) and the `ccrecall` CLI. Published to PyPI v0.11.0
   (`uv tool install ccrecall`).
3. **✅ DONE — automatic legacy migration shipped** (ccrecall v0.11.0, not Claudefiles). The
   data dir renamed (`~/.claude-memory/` → `~/.ccrecall/`) and the model swapped, but it's now
   handled automatically: the bundled `cm-memory-setup` SessionStart hook detects a legacy
   `~/.claude-memory/conversations.db` and background-spawns `ccrecall migrate`, which
   **copies** the DB + portable config into `~/.ccrecall/` (atomic, WAL-checkpointed; original
   left as backup), triggers the dim self-heal, and is idempotent. No manual step. Re-seeding
   historical semantic search stays opt-in (`ccrecall backfill embeddings`).

All three prerequisites now hold — the cutover is unblocked. (It is still staged here, not
executed, pending the dev-machine verify in §F.)

## Per-machine data migration (NEW) {#per-machine-data-migration-new}

The earlier draft assumed the data path was unchanged. It is **not** — verified against
ccrecall `origin/main` source on 2026-06-22:

| | Old vendored `claude-memory` (all 5 machines today) | New `ccrecall` v0.10.0 |
|---|---|---|
| Data dir | `~/.claude-memory/` | `~/.ccrecall/` |
| Model | `gpahal/bge-m3-onnx-int8` | `jinaai/jina-embeddings-v2-small-en` |
| Dim | 1024 | 512 |
| `EMBEDDING_VERSION` | 1 | 2 |

What this means per machine:

- **Dir rename (AUTOMATIC as of ccrecall v0.11.0):** `cm-memory-setup` detects the legacy
  `~/.claude-memory/conversations.db` and background-spawns `ccrecall migrate`, which copies
  the DB + portable config into `~/.ccrecall/` (atomic, WAL-checkpointed) and leaves the
  original as a backup. Idempotent; no manual `mv`. The old dir can be deleted once the copy
  is confirmed. (v0.10.0 had no shim — that's what prerequisite 3 fixed.)
- **Re-embed (automatic, then opt-in seed):** on first open, ccrecall's `_ensure_vec_schema`
  sees `branch_vec` is `float[1024]` ≠ `float[512]` and drops+recreates it empty at 512-dim
  (lossless — vectors are derived). The backfill eligibility predicate re-embeds any branch
  with `embedding_version < 2` **or** missing from `branch_vec` — i.e. all of them. Forward
  coverage rebuilds automatically via embed-on-write; historical re-seed is the opt-in
  `ccrecall backfill embeddings` (CPU-heavy, never auto-spawned; first run downloads the
  ~120 MB jina model). Until it finishes, search degrades to keyword-only for un-re-embedded
  branches — still functional.

All of the above is delegated to `ccrecall migrate` (prerequisite 3); Claudefiles does not
implement it.

## Reference: ccrecall plugin shape (source of truth = the ccr repo)

- Plugin name: **`ccrecall`** (`.claude-plugin/plugin.json`, v0.9.0).
- Skills: **`ccr-recall`** (was `cm-recall-conversations`), **`ccr-tokens`** (was
  `cm-get-token-insights`), **`ccr-resume`** (replaces local `mine-resume`).
- Bundled hooks (`hooks/hooks.json`, ship **with** the plugin): SessionStart →
  `cm-memory-setup`, `cm-onboarding`, `cm-memory-context`; SessionEnd → `cm-clear-handoff`;
  Stop → `cm-memory-sync`. **These are why Claudefiles must drop its hand-wired copies** —
  otherwise both fire.
- The bundled hooks still invoke the bare `cm-*` binary names for now (collapse to
  `ccrecall hook ...` is a later ccr phase). The binaries come from the `ccrecall` package.

---

## A. Files / directories to DELETE

| Target | Notes |
|---|---|
| `skills-memory/` (whole dir) | `cm-get-token-insights/`, `cm-recall-conversations/`, `capabilities-memory.md`. Replaced by plugin skills `ccr-tokens` / `ccr-recall`. |
| `packages/claude-memory/` (whole dir) | The vendored package. Source moves to the standalone ccr repo. Note: the live `uv tool install -e` editable install points *here*, so deletion must coincide with installing `ccrecall` from PyPI. |
| `skills/mine-resume/` (whole dir) | Replaced by plugin skill `ccr-resume`. Depends on the removed `cm-session-tail` binary, so it cannot survive de-vendoring anyway. |

## B. `settings.json` edits

Line numbers indicative (2026-06-21); match on content.

**B1 — Remove 12 `cm-*` permission entries** (currently lines 26–37 in `permissions.allow`):
`cm-backfill-summaries`, `cm-clear-handoff`, `cm-import-conversations`,
`cm-ingest-token-data`, `cm-memory-context`, `cm-memory-setup`, `cm-memory-sync`,
`cm-onboarding`, `cm-recent-chats`, `cm-search-conversations`, `cm-sync-current`,
`cm-write-config`.
*(If skills/CLI invoke `ccrecall ...` directly via Bash later, add `Bash(ccrecall:*)` —
deferred, part of plugin enablement.)*

**B2 — Remove the 5 hand-wired memory hooks** (the plugin provides these):
- `SessionStart` (lines 108–133): remove the 3 memory hook objects (`cm-memory-setup`,
  `cm-onboarding`, `cm-memory-context`). **Keep** the first hook (`tmux-remind.sh`) — the
  array survives with just that one entry.
- `SessionEnd` (lines 134–143): remove the sole `cm-clear-handoff` hook → `SessionEnd: []`.
- `Stop` (lines 145–155): remove the sole `cm-memory-sync` hook → `Stop: []`.

**B3 — Plugin wiring (values RESOLVED 2026-06-22):**
- `extraKnownMarketplaces`: add the `claude-code-recall` marketplace, source
  `NodeJSmith/claude-code-recall` (GitHub repo doubles as a single-plugin marketplace).
- `enabledPlugins`: add `"ccrecall@claude-code-recall": true`.
- Plugin skills are namespaced: `/ccrecall:ccr-recall`, `/ccrecall:ccr-resume`,
  `/ccrecall:ccr-tokens` — the cross-repo Dotfiles capabilities routing (§H) must use the
  namespaced form, not bare `/ccr-recall`.
- Per `CLAUDE.md`, run `claude-merge-settings` after editing (never hand-edit
  `~/.claude/settings.json`).

## C. `install.py` edits

| Line (approx) | Change |
|---|---|
| 30 | `SKILL_DIRS` — drop `"skills-memory"`. |
| 132–142 | Delete the entire `"memory"` `Bundle(...)` definition (label "Memory (cm-*)", skills `cm-get-token-insights`/`cm-recall-conversations`, `packages=("claude-memory",)`, `capabilities_files=("capabilities-memory.md",)`). |
| 408 | Remove `"memory": bool(skills.get("memory", False)),` from the v1→v2 config migration. |
| 1236 | Remove the `skills.memory → bundles.memory` diff-output line. |
| 394, 398 | Historical v1→v2 migration comments mentioning `skills.memory` / `packages.claude-memory` — leave for history or trim; non-functional. |

**RESOLVED (2026-06-22) + IMPLEMENTED:** `install.py` installs `ccrecall` from PyPI
**unconditionally** (not via a bundle) — the plugin is enabled globally, so the package
is a hard dependency, not an opt-in. `ensure_ccrecall()` installs it when absent and
removes the legacy `claude-memory` install **only once `ccrecall` is present** (never
leaving a machine with neither). `do_uninstall` removes `ccrecall` too. The `SKILL_DIRS`,
`get_bundles`, and v1→v2 migration edits in the table above are done. The destructive
file removals (§A), `settings.json` (§B), and remaining doc edits (§D, except the
CLAUDE.md consistency edits which shipped with this `install.py` change) are still staged.

## D. Doc edits

**`REFERENCE.md`:**
- L37 — `mine-resume` row: delete the row (skill is being removed). If a resume pointer is
  still wanted, note that `ccr-resume` ships with the ccrecall plugin.
- L80–85 — delete the `### Memory Skills (cm-*) — Memory bundle` section + table.
- L155 — capabilities-files line: drop `capabilities-memory.md (Memory)`.
- L184–191 — delete the 5 `cm-*` (package) hook rows from the Hooks table.
- L232 — drop "`claude-memory` installs with the Memory bundle."
- L237 — delete the `claude-memory` Packages-table row.
- Add: a Plugins-table entry for `ccrecall` (per `CLAUDE.md` "When bundling a new plugin").

**`ONBOARDING.md`:**
- L35 — bundle list mentions "conversation memory" as a bundle — reframe (memory is now a
  plugin, not a bundle).
- L58–59 — "I want conversation memory" → install the `ccrecall` plugin; `/ccr-recall`
  searches past sessions (was `/cm-recall-conversations`).
- L143 — `/mine-resume` → `/ccr-resume`; drop "With the Memory bundle, the SessionStart
  hook also auto-warns…" (or reattribute to the plugin).

**`CLAUDE.md`:**
- L21 — remove the `cm-*` naming-convention line (no longer a Claudefiles namespace).
- L62 — drop `skills-memory/` from the "re-run install.py" directory list.
- L65 — drop `skills-memory/capabilities-memory.md for cm-*` from the capabilities-file list.

**`CHANGELOG.md`:** historical entries (cm-*, claude-memory) — leave as-is (history).

**`design/specs/*`:** historical specs referencing claude-memory (018, 019, 025, 026, 029,
030) — leave as-is. Add a final note to `030` when the cutover executes.

## E. Tests

`tests/test_install.py` — remove/adjust memory-bundle coverage: `test_memory_bundle_has_claude_memory`,
`test_memory_capabilities_file`, `test_finds_in_skills_memory`, the `skills-memory` fixture
setup, the memory deselection/install assertions, and the `claude-memory` package
install/uninstall + config-migration tests. Run `timeout 300 pytest tests/test_install.py`
after editing.

`packages/merge-settings/tests/test_merge.py` — a mock references `claude-memory`; update
or drop. (Moot if the merge-settings tests use it only as illustrative mock data.)

## F. Sequencing (cutover order — preserve the no-data-loss window)

1. **[ccr side — DONE]** Marketplace + PyPI package published; automatic legacy migration
   shipped (v0.11.0). No remaining ccrecall blockers.
2. **Dev machine first.** Install the package (`uv tool install ccrecall`) + enable the
   plugin. On the next session start the bundled `cm-memory-setup` auto-migrates
   `~/.claude-memory` → `~/.ccrecall` in the background. Confirm memory (recall, context
   injection, sync, resume) works **from the plugin** before removing the vendored copy.
   Overlap is fine *except* the hooks: do not enable the plugin's hooks while Claudefiles
   still wires its own, or they double-fire. Sequence: strip Claudefiles hooks (B2) in the
   same change that enables the plugin. Optionally `ccrecall backfill embeddings` to re-seed
   historical semantic search (CPU-heavy, ~120 MB jina download — run when idle; keyword
   search works meanwhile).
3. Land the Claudefiles removals (A–E) once the plugin is verified.
4. `claude-merge-settings` + `uv run install.py` (clears stale `cm-*` symlinks via
   `find_stale_symlinks`) + `uv tool uninstall claude-memory`.
5. Roll out to the other 4 machines: git sync + `uv run install.py` + `uv tool install
   ccrecall` + `uv tool uninstall claude-memory`. The **package swap is per-machine** (does
   not propagate via git); the auto-migration then fires on first session start. Optional
   per-machine `ccrecall backfill embeddings` when each box is idle.

## G. Deferred / open items (decide at execution time)

- ~~Exact marketplace name + source string~~ — RESOLVED: `claude-code-recall` /
  `NodeJSmith/claude-code-recall`.
- ~~`enabledPlugins` key format~~ — RESOLVED: `ccrecall@claude-code-recall`.
- ~~Package install path: `uv tool install ccrecall` (PyPI) — and whether `install.py`
  automates it or it's manual/plugin-managed.~~ — RESOLVED + IMPLEMENTED (2026-06-22):
  `install.py` automates it unconditionally via `ensure_ccrecall()`. See §C.
- Whether to add `Bash(ccrecall:*)` permission (if skills shell out to the CLI directly).
  **Open.**
- `uv tool uninstall claude-memory` on each machine post-cutover.
- **Blocked on ccrecall:** prerequisite 3 (`ccrecall migrate` + `cm-memory-setup`
  detect-and-nudge) must ship before the per-machine cutover (§F) can run cleanly.

## H. Cross-repo follow-ups (NOT in this repo — track separately)

The global **Dotfiles** rules reference the old skill names and must be updated when the
plugin lands (they are not part of Claudefiles):
- `Dotfiles/config/claude/rules/personal/capabilities.md` — "Memory Recall" and "Proactive
  Memory Recall" sections route to `/cm-recall-conversations` → update to `/ccr-recall`.
- `Dotfiles/config/claude/rules/personal/mcp-tools.md` — verify no stale memory refs.
- Auto-memory `MEMORY.md` index + `ccrecall-extraction.md` note — refresh once cutover done.
