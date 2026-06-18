# Repo Boundary Inventory: claude-memory Extraction

**Date:** 2026-06-18
**Status:** investigated (filesystem-verified against the `split-claude-memory` worktree)
**Resolves:** Open Question #2 of `brief.md` ("Repo boundary / what moves")

Every item below was confirmed by reading the actual files, not the brief. Corrections to
the brief are called out in section F.

---

## A. Moves wholesale — the package

`packages/claude-memory/` transplants into the new repo root essentially unchanged. It is
already self-contained packaging-wise:

- **28 source modules** under `src/claude_memory/` (incl. `hooks/` subpackage: 11 hook/helper modules).
- **22 test files + 7 JSONL fixtures** under `tests/` — strong enough to serve as a refactor pin.
- **`pyproject.toml`** — setuptools backend, pinned native deps (sqlite-vec, tokenizers, onnxruntime, numpy), and all 14 console-script entrypoints.
- **`README.md`, `CHANGELOG.md`, `uv.lock`** already exist — more publish-ready than the brief implied.

**The 14 entrypoints (exactly as brief counted):**
| Group | Scripts |
|---|---|
| Hook entrypoints (wired in settings.json) | `cm-memory-setup`, `cm-memory-sync`, `cm-memory-context`, `cm-onboarding`, `cm-clear-handoff` |
| Internal helpers (subprocess-spawned) | `cm-sync-current`, `cm-backfill-summaries`, `cm-backfill-embeddings`, `cm-import-conversations`, `cm-write-config` |
| Skill CLIs (called from SKILL.md) | `cm-recent-chats`, `cm-search-conversations`, `cm-ingest-token-data`, `cm-session-tail` |

## B. Moves — the bundle surface (skills + capabilities)

- `skills-memory/cm-recall-conversations/` — `SKILL.md` + `references/lenses.md` + `references/tool-reference.md`
- `skills-memory/cm-get-token-insights/SKILL.md`
- `skills-memory/capabilities-memory.md` (the intent-routing table loaded into context)

After extraction `skills-memory/` is **empty** and the dir itself leaves Claudefiles.

## C. Becomes the plugin manifest — currently hand-wired in `settings.json`

These are the lines a Claude Code plugin manifest must reproduce so an external user gets
them without editing `settings.json`:

- **5 hook declarations:**
  - SessionStart → `cm-memory-setup`, `cm-onboarding`, `cm-memory-context` (3 entries)
  - SessionEnd → `cm-clear-handoff`
  - Stop → `cm-memory-sync`
  - (each guarded by `command -v … >/dev/null 2>&1 && … || true`)
- **12 Bash permission allow-entries** (`Bash(cm-*:*)`, settings.json lines 26–37).

## D. Stays in Claudefiles but must be edited (de-vendoring glue)

| File | What changes |
|---|---|
| `install.py` | Memory `Bundle` (lines 131–141), `SKILL_DIRS` includes `"skills-memory"` (line 30), bundle-wiring (lines 388–402, 1230). The bundle either disappears or is reframed as "install the external plugin." |
| `settings.json` | Remove the 5 cm-* hook entries + 12 cm-* permission entries (now provided by the plugin). |
| `tests/test_install.py` | Memory-bundle assertions (lines 367, 396–441, 544–545). |
| `REFERENCE.md` | Memory Skills section (78–83), hooks table rows (181–189), packages rows (238, 243), capabilities row (152), and the `mine-resume`→`cm-session-tail` row (36). |
| `ONBOARDING.md` | Memory bundle mentions (35, 58–59). |
| `CLAUDE.md` | memory references. |

## E. Cross-package couplings that do NOT move — decisions required

1. **`skills/mine-resume` → memory plugin (DECIDED: travels + renames to `ccm-resume`).**
   `mine-resume` calls `cm-session-tail` as its primary lever **and `/cm-recall-conversations`
   as its fallback** — both memory-plugin-owned, so it cannot function without the plugin.
   It moves into the plugin's skill bundle and is renamed `ccm-resume`.

   **Move is clean:** single `SKILL.md`, in no explicit bundle, `user-invocable` +
   `disable-model-invocation` (no `capabilities-core.md` routing entry, no hook/permission
   wiring). Rename touches:
   - `skills/mine-resume/SKILL.md` → `skills-memory/ccm-resume/SKILL.md`; `name:` field; `$ARGUMENTS` usage unchanged.
   - `packages/claude_memory/src/claude_memory/session_tail.py` lines 5, 275 — docstring/comment "the mine-resume skill" → "ccm-resume".
   - `REFERENCE.md:36`, `ONBOARDING.md:143` — name + "ships with the Memory plugin" note.
   - **Doc-only wrinkle:** the SKILL's "How this differs from neighbors" section cites
     `mine-good-morning` and `mine-status`, which **stay in Claudefiles**. In the extracted
     repo those skills don't exist — generalize the prose or drop the cross-refs.

2. **`Dotfiles/config/claude/rules/personal/capabilities.md` → `/cm-recall-conversations`**
   (personal cross-repo consumer; lines 49–53). This is exactly the brief's "phase 2, I'll
   handle phase 2 after since it's in Dotfiles." Stays a Dotfiles edit, out of this repo's scope.

## E-bis. Naming — DECIDED (decoupled by layer)

The "Claude Code memory/recall" namespace is **saturated** — three published npm tools already
squat the obvious names: `ccmem` ("Claude Code Memory"), `ccrecall` ("sync Claude Code
transcripts… recall past sessions"), `cchist` ("aggregate Claude Code conversation history
across machines"). Each does nearly this. Full name consistency across layers isn't achievable
in this space, so names are **decoupled by layer** instead of forced to match. Reframe accepted:
it's **conversation history + search**, not "memory" — naming reflects that.

| Layer | Name | Collision check |
|---|---|---|
| GitHub repo | `claude-code-recall` | Unique within owner; descriptive `claude-code-*` is the common community pattern; low trademark risk since the binary itself doesn't say "claude". |
| PyPI package + import + binary | `ccrecall` | **PyPI free (404 verified).** npm `ccrecall` exists but is a *different channel* — CC plugins ship via git marketplace + PyPI, not npm — so it can't install through our path; the only clash is a PATH binary, which needs both tools installed, and no one running memory tooling does. |
| Skills | `ccr-*` | Plugin-local, zero collision. |

**Skill rebrand (tightened — `ccr` already means "cc recall", so drop the redundant suffix):**
| Now | After |
|---|---|
| `mine-resume` | `ccr-resume` |
| `cm-recall-conversations` | `ccr-recall` |
| `cm-get-token-insights` | `ccr-tokens` |

**Accepted caveat (not technical):** `ccrecall` isn't uniquely ours in search — the npm tool
shares it. Fine under the dogfood-first framing; findability is secondary.

### Sequencing — DECIDED: identity at extraction, entrypoint collapse at cyclopts

- **Extraction phase** renames the externally-visible identity only: repo → `claude-code-recall`,
  PyPI/import package → `ccrecall` (`src/claude_memory/` → `src/ccrecall/` + fix internal
  imports), the 3 skills → `ccr-*`. The **14 console-script binaries keep their `cm-*` names**
  for now — they're Claude/hook-invoked internals, invisible to humans; the renamed `ccr-*`
  skills transitionally call the still-`cm-*` binaries (a planned, scoped, harmless interim
  state per `outcome-oriented-execution.md`).
- **Cyclopts phase (deferred, per brief)** collapses the 14 `cm-*` scripts into
  `ccrecall <subcommand>`, updating skill call sites, plugin manifest, and `Bash(...)`
  permissions in the same wave. Target map:
  - Hooks (5): `cm-memory-setup/-sync/-context`, `cm-onboarding`, `cm-clear-handoff` → `ccrecall hook session-start | stop | …`
  - Helpers (5): `cm-sync-current`, `cm-backfill-summaries`, `cm-backfill-embeddings`, `cm-import-conversations`, `cm-write-config` → `ccrecall sync-current`, `ccrecall backfill {summaries,embeddings}`, `ccrecall import`, `ccrecall write-config`
  - Skill CLIs (4): `cm-recent-chats`, `cm-search-conversations`, `cm-ingest-token-data`, `cm-session-tail` → `ccrecall recent-chats`, `ccrecall search`, `ccrecall ingest-token-data`, `ccrecall session-tail`

  **Rationale:** binary names are invisible to the user, so a transitional `cm-*` costs
  nothing — whereas flat-renaming them at extraction (`cm-search` → `ccrecall-search`) only to
  collapse them again at cyclopts (`→ ccrecall search`) is two renames for one outcome.
  Identity is what the new repo exposes on day one, so it's renamed first.

**Reference sites the renames must catch (filesystem-verified):**
- *Extraction:* `pyproject.toml` (`name`, package dir), `src/claude_memory/` tree + all internal
  `claude_memory` imports, the 3 skill dirs + their `name:` fields, `mine-resume`→`ccr-resume`
  refs in `REFERENCE.md`/`ONBOARDING.md` and `session_tail.py` docstrings (lines 5, 275).
- *Cyclopts:* `pyproject.toml [project.scripts]` (all 14), package subprocess spawns
  (`cm-backfill-embeddings` ×14, `cm-session-tail` ×8, `cm-write-config`/`cm-sync-current`/`cm-import-conversations` ×3 each, `cm-recall-conversations`/`cm-backfill-summaries` ×2 each),
  skill-file CLI calls (`capabilities-memory.md`, `cm-get-token-insights/SKILL.md`,
  `cm-recall-conversations/SKILL.md` + `references/tool-reference.md`, `mine-resume/SKILL.md`),
  `settings.json` (5 hook commands + 12 `Bash(cm-*)` perms → `Bash(ccrecall:*)`).
- *Cross-repo, phase 2:* `Dotfiles/.../capabilities.md` (`/cm-recall-conversations` → `/ccr-recall`).

**Build the lever:** both renames are wide mechanical sweeps — write each as a codemod /
scripted pass with grep-zero verification (`rg 'claude_memory|cm-' → 0 hits outside history`),
not hand edits.

## F. Corrections to the brief

- **No "recall agent" exists.** Brief Open Q #2 lists "the recall agent" as part of the move.
  `agents/` contains none, and the memory `Bundle` declares `agents=()`. Recall is
  **skill-only**. Drop it from the inventory.
- **Package is more publish-ready than stated.** Brief says "no plugin manifest exists" (true),
  but `README.md`, `CHANGELOG.md`, and a committed `uv.lock` are already present.
- **Entrypoint count confirmed:** exactly 14 (5 hooks + 5 helpers + 4 skill CLIs).
