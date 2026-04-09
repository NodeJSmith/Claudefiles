# Design: Per-Finding Resolution Manifest for mine.challenge

**Date:** 2026-04-09
**Status:** approved
**Research:** design/research/2026-04-09-per-item-resolution-loops/research.md (prior art), design/research/2026-04-09-per-item-resolution-loops/codebase-research.md (feasibility)
**Challenge:** Findings at /tmp/claude-mine-design-challenge-4FEDDV/findings.md; 22 original + 4 dogfood-discovered. All resolved via the dogfood manifest flow that is the topic of this design (meta-testing).

## Problem

`mine.challenge` routinely bundles 7–11 unrelated findings into a single "Accept all?" AskUserQuestion prompt during Phase 4 resolution, despite `rules/common/findings.md` explicitly stating "present each judgment call, collect the user's choice, then move to the next question." Real-world examples collected from session logs show the same anti-pattern repeating across 10+ sessions: double gates after "Yes," 9 findings bundled as `Yes — accept all recommendations` / `No — I want to discuss some` binaries, multi-select checkboxes with ambiguous fix-vs-file semantics, "MEDIUM batch 1 / 2 / 3" prompts that legitimize grouping, and "Skip revisions" / "Enough challenges — approve as-is" bail-out options that silently violate the "all findings must be resolved" principle.

Prior-art research established with peer-reviewed evidence that this cannot be fixed with prose rules alone. Three 2025–2026 papers (IFScale, "When Instructions Multiply," "LLMs Get Lost in Multi-Turn Conversation") show that instruction-following degrades predictably as density grows, and that the LLM's tendency to collapse per-item loops is partly a *coping strategy* for poor multi-turn state handling. The abstract "each" language in the current rule has no chance of winning against this prior. **The fix must be structural.**

## Non-Goals

- **No changes to critic phases or synthesis logic.** The finding content itself is unchanged.
- **No changes to the findings file schema or `Format-version`.** The manifest renderer consumes existing contract fields.
- **No migration of `mine.visual-qa` or `mine.tool-gaps` in this design.** Both continue using their existing Skill-Specific Override gates. However, `bin/edit-manifest` and the resolution manifest format are designed to be **reusable** — a follow-up design will migrate visual-qa to use them. This design ships the enabling infrastructure; visual-qa migration is explicit scope for the next design iteration. Structured callers (mine.design, mine.specify) also implement their own per-finding loops with the same vulnerability; fixing those is out of scope — they are unaffected by *this design's changes*, not by the underlying problem.
- **No changes to structured callers** (`mine.design`, `mine.specify`, `mine.orchestrate`). They consume the findings file directly and generate their own revision plans — never touching the standalone resolve flow.
- **No new durable artifact type.** Resolution manifests are session-scoped and live in the existing challenge tmpdir.
- **No bulk triage primitives.** Grouping findings by severity or type is explicitly rejected — it's the failure mode we're fixing, not a feature.

## Architecture

### The core insight

The current flow places per-finding decisions inside an interactive prompt loop, which the LLM collapses into a single bundled prompt. The fix is to move per-finding decisions into a **review surface the user edits directly** — a manifest file opened in their `$EDITOR` via a shared helper script. Because the manifest exists on disk as N discrete sections (one per finding), there is no interactive loop for the LLM to collapse. The manifest IS the per-finding discipline.

This is the `git rebase -i` pattern, proven over 15+ years of developer workflow, adapted to Claude Code's execution environment.

### The resolution manifest format

The manifest is a markdown file at `<tmpdir>/resolutions.md` containing per-finding blocks with full context (problem, consequence, options with reasoning, and an editable Verb line). Dogfood testing revealed that compact table formats lose too much context — the user cannot make informed decisions from a row that just shows "F1 fix CRITICAL Set timeout" without seeing what's broken and why the fix is right.

The format uses one markdown section per finding:

```markdown
## F1: Bash tool timeout silently kills edit sessions
**Severity:** CRITICAL | **Type:** Fragility | **Raised by:** Operational Resilience (1/5)

**Problem:** <finding summary — what's wrong>

**Why it matters:** <one sentence — consequence if left unfixed>

**Options:**
- **A** *(recommended)*: <first option with full text>
- **B**: <second option>

**Why A:** <one-sentence rationale for the recommendation>

**Verb:** A
```

**TENSION findings** substitute `**The disagreement:**` + `**Deciding factor:**` for the Options/Why block. **Auto-apply findings** use `**Better approach:**` instead of Options. The `**Verb:**` line is the only field the user edits.

The manifest header includes:
- Brief usage instructions (how to edit, save, exit)
- A legend of valid verbs and their meanings
- A compaction-recovery pre-hash comment: `<!-- pre-hash: <sha256> -->`
- A prominent safety note: `<!-- Your edits are captured via autosave shadow file — :q! is safe -->`

**In nvim**, users can use `/Verb:` to jump between verb lines for quick scanning.

### Verb vocabulary

Six verbs, exhaustive:

| Verb | Meaning | Applies to |
|---|---|---|
| `fix` | Auto-apply the `better-approach` or recommended option | Auto-apply findings; User-directed set by user |
| `file` | Create a GitHub issue via `gh-issue create` (batched at end of execution) | Any finding |
| `defer` | Record in session summary; take no action this session | TENSION findings, explicit user deferral |
| `skip` | Same as `defer` but for "not a real issue" | User override |
| `ask` | Emit one AskUserQuestion at execution time with options | User-directed findings where recommendation is absent or ambiguous |
| `A` / `B` / `C` | Apply the pre-selected option letter | User-directed findings with `options:` lists |

**The canonical definition of the verb vocabulary lives in `rules/common/findings.md`.** Other files (mine.challenge SKILL.md Phase 4, anti-pattern catalog entries) reference the rule by name rather than re-stating verbs inline. This is the single source of truth, avoiding the change-amplification risk of vocabulary defined in multiple places.

### Default verb selection

The skill pre-populates the manifest with default verbs before opening it for edit. Defaults are chosen from **contract fields only** — never from presentation-only fields — to avoid format-drift fragility:

| Finding `resolution:` | `recommendation:` field | Default verb |
|---|---|---|
| `Auto-apply` | (n/a) | `fix` |
| `User-directed` | Contains specific option letter (e.g., "Option A") | That letter (`A`) |
| `User-directed` | Absent or says "user must decide" / no clear letter | `ask` |
| `TENSION` | (n/a) | `defer` |

This uses `recommendation:` — a contract field always present for User-directed findings — rather than the presentation-only `confidence:` field. Parsing `"3/5 (Senior + Architect)"` strings is fragile; parsing "pick the option letter from the recommendation" is deterministic and stable.

**Format-version 1 fallback**: If a finding lacks `recommendation:` (pre-enrichment format), default to `ask`. Write a header comment on the manifest: `<!-- Format-version 1 source — some findings defaulted to 'ask' due to missing recommendation field -->`. This is normative spec, not an open question.

### The edit mechanism: `bin/edit-manifest` helper script

Editor launching is delegated to a shared helper script in `bin/`, NOT embedded in any SKILL.md or rule file. This is the load-bearing architectural decision that separates mechanism from policy:

- `rules/common/findings.md` describes the manifest format, verb vocabulary, and execution semantics — **mechanism-agnostic**
- `skills/mine.challenge/SKILL.md` Phase 4 invokes `bin/edit-manifest <path>` and handles hash comparison — **no tmux knowledge**
- `bin/edit-manifest` encapsulates all editor-launching mechanics — **the only place tmux specifics live**

**Why a helper script rather than rule-embedded or skill-embedded logic:**

1. **Shared reuse**: Future skills (visual-qa migration, tool-gaps migration, custom finding-producing skills) call the same script. Tmux logic lives in one file, not N.
2. **Mechanism-agnostic rules**: `rules/common/findings.md` is auto-loaded into every analysis skill's context. Keeping tmux specifics out of it prevents coupling every skill to an infrastructure detail. The rule describes *what* the manifest is and *how* verbs execute; the *how to launch the editor* lives in a separate artifact.
3. **Testable in isolation**: `edit-manifest /tmp/foo.md` can be tested without invoking any skill.
4. **Aligns with repo conventions**: `bin/` already contains shared CLI tools (`gh-issue`, `claude-tmux`, `git-default-branch`, `get-skill-tmpdir`). A new one fits the pattern.
5. **Installable via `install.sh`**: symlinked into `~/.local/bin/` alongside other helpers.

**Script responsibilities**:

```
bin/edit-manifest <manifest-path>
```

1. Detect tmux availability (`[ -n "$TMUX" ]` and tmux version probe)
2. Check `$EDITOR` against a known-non-blocking list (`code`, `subl`, `atom`, `gedit`, `open`, `xdg-open`); warn if matched, suggest `EDITOR='code --wait'` or similar
3. Delete any stale shadow file at `<manifest-path>.shadow`
4. If tmux present: run `tmux new-window + wait-for` pattern with shadow-autosave
5. If tmux absent: fall back per tiered strategy below
6. Signal the parent's `wait-for` channel on exit (any exit kind, via `trap`)
7. Write diagnostic events to `<tmpdir>/editor-log.md`

**The tmux new-window + wait-for invocation** (inside the script):

```bash
# Acquire lock FIRST to eliminate wait-for signal race
tmux wait-for -L edit-done &

tmux new-window -n manifest "zsh -l -c '
  trap \"tmux wait-for -S edit-done\" EXIT HUP TERM
  rm -f ${MANIFEST}.shadow
  nvim \
    -c \"set updatetime=2000\" \
    -c \"autocmd CursorHold,CursorHoldI <buffer> silent write! ${MANIFEST}.shadow\" \
    -c \"autocmd VimLeave * silent write! ${MANIFEST}.shadow\" \
    \"${MANIFEST}\"
'"

# Wait for the signal (parent already locked)
wait
tmux wait-for -U edit-done  # release lock
```

Key mechanisms:
- **`tmux wait-for -L`** (lock mode) acquired by parent *before* `new-window` — eliminates the race where the child's `-S` signal could fire before the parent was listening. See N2 below.
- **`trap ... EXIT HUP TERM`** in the child shell — signals `edit-done` even if the tmux window is forcibly closed, the shell is HUPed, or the editor crashes. Without this, closing the tmux window directly would leave the parent hanging. See N3 below.
- **`zsh -l -c`** wraps the editor invocation to get the user's login PATH (handles mise, asdf, direnv, nix tool managers that only export from login shells).
- **Shadow file via autocmd** captures in-memory buffer state to `<manifest>.shadow` on inactivity (`CursorHold`) and on any exit (`VimLeave`). See N4 below. This means `:q!` is safe — the shadow file has the user's work regardless of save intent.

### Fallback tiers when tmux is absent

For users without tmux (native terminal sessions, VS Code's terminal without tmux, Cursor, etc.), `bin/edit-manifest` chooses from a tiered fallback:

1. **Primary (tmux 2.4+ present):** `tmux new-window + wait-for` as specified above. Wide coverage — tmux `wait-for` is old (2.4+, released 2015).

2. **Secondary (Claude Code with `/ide` integration present):** If the session has IDE integration (detectable via environment or file markers — TBD, time-boxed investigation, ~4 hours max), invoke the IDE's "open file" primitive. The user edits in their IDE window. Detection of "done editing" is TBD — probably "signal via chat message" or "watch the file for a save marker." **Investigation deferred to implementation — do not block on solving this perfectly.**

3. **Tertiary (no tmux, no IDE integration):** Write the manifest file. Display its path to the user via a message: *"I've written the resolution manifest to `<path>`. Open it in your preferred editor, edit the `**Verb:**` lines, save, and say 'done' (or 'abandon') when you're ready."* The user manually opens the file, edits, and returns via chat. Claude parses the user's "done" message as the signal to re-read the manifest. Free-text edits in chat ("change F4 to file, F7 to skip") are also accepted as an alternative to file editing.

The tertiary tier is the minimal viable path for any environment. It loses some ergonomics (manual open, manual signal) but preserves the structural anti-bundling property — the manifest is still the review surface, the user still makes per-finding decisions, there is still no bundled prompt.

### `$EDITOR` blocking detection

Common `$EDITOR` values exit immediately without blocking (`code`, `subl`, `atom`, `gedit`, `open`, `xdg-open`). If invoked naively, the editor returns in milliseconds, the shadow file is empty, and the detection logic sees "user didn't edit" — silently defeating the anti-bundling guarantee.

`bin/edit-manifest` defends with two checks:

1. **Proactive check before launch**: Match `$EDITOR` against a known-non-blocking list. If matched, emit a warning and suggest the `--wait` variant (`code --wait`, `subl -w`, etc.) before the window opens. User can Ctrl+C to abort and fix their environment, or proceed and accept the risk.

2. **Reactive check after exit**: Measure elapsed time of the editor session. If exit code is 0, hash is unchanged, AND elapsed < 1 second (strong signal of non-blocking editor rather than "looked but didn't change"), emit: "Your editor returned in {N}ms without saving. Either it's non-blocking (try `EDITOR='code --wait'`) or you quit without changes. Re-open, type changes in chat, or abandon." Loop back unconditionally — do NOT silently offer "proceed with defaults."

Combined, these catch the most common misconfiguration before it causes silent data loss.

### Detection logic: hash + shadow comparison

After the editor session exits (via task-notification receipt — see next section), the skill performs a **four-way decision tree** based on hash comparisons:

```
pre_hash = sha256(manifest_path)       // captured before edit session
post_hash = sha256(manifest_path)      // original file after edit
shadow_exists = [ -f manifest_path.shadow ]
shadow_hash = sha256(manifest_path.shadow) if shadow_exists else post_hash
```

| Condition | Meaning | Action |
|---|---|---|
| `post_hash != pre_hash` | User explicitly saved (`:wq` or `:w` + `:q`) | Execute manifest |
| `post_hash == pre_hash` AND `!shadow_exists` | No edits ever typed | "Defaults are good — proceed with current verbs?" |
| `post_hash == pre_hash` AND `shadow_hash != post_hash` | User typed changes but did not explicitly save (`:q`, `:q!`, `:cq`, or closed window externally) | "You had unsaved changes in the manifest. Recover them, abandon, or re-open?" |
| `post_hash == pre_hash` AND `shadow_hash == post_hash` | Edited, autosaved, but ended up matching (user edited then undid) | Same as "no edits ever" |

The shadow file is the recovery side-channel for the `:q!` muscle-memory case. Without it, vim users reflexively `:q!` and lose all work silently. The shadow captures the in-memory buffer via nvim autocmds on `CursorHold` (after 2s inactivity) and `VimLeave` (any exit).

**If the user picks "recover" after `:q!`**, the skill copies the shadow file over the manifest (`cp <shadow> <manifest>`) and loops back to the commit gate using the recovered content.

### Task-notification handling (Bash auto-backgrounding)

The Bash tool auto-backgrounds long-running blocking calls after an internal threshold. `bin/edit-manifest` blocks until the editor exits, but the bash tool will likely return a task ID and send a task-notification when complete, not block synchronously in the LLM's turn. The skill must handle BOTH sync-return and async-via-task-notification.

**Operational rules for Phase 4**:

1. **Set `timeout: 600000`** on the edit-manifest Bash call as a defense-in-depth safety belt, even though auto-backgrounding usually fires first.
2. **Acknowledge async completion**: Phase 4 prose says "when the editor session completes" rather than "when the bash call returns." This signals to the LLM that the completion may arrive via task-notification, not synchronous return.
3. **Pre-hash persistence in the manifest**: Before launching the editor, embed `<!-- pre-hash: <sha256> -->` as a comment in the manifest file. This makes the pre-hash recoverable from disk if the LLM's context is compacted between task-start and task-notification receipt.
4. **Re-read state on notification receipt**: When a task-notification arrives for an editor command, re-read `<tmpdir>/manifest.md` (session state), `<tmpdir>/findings.md` (source findings), `<tmpdir>/resolutions.md` (manifest with user's edits), and `<tmpdir>/resolutions.md.shadow` (safety-net state). Do not assume any of these are in LLM context.
5. **Compute hashes at notification time**: The pre-hash comes from the in-manifest comment; the post-hash and shadow hash are computed fresh at notification receipt.

### The consent gate (restored Proceed Gate)

Before generating and opening the manifest, the skill asks for explicit user consent:

```
AskUserQuestion:
  question: "Challenge found N findings (breakdown). Ready to review the resolution manifest?"
  header: "Review findings"
  options:
    - label: "Yes — open editor (Recommended)"
      description: "Generate the manifest and open it in your editor"
    - label: "No — stop here"
      description: "I'll review findings and come back later"
```

This is NOT the old "Proceed to fix all findings?" binary gate. This gate's only purpose is to get explicit consent before the editor window opens — respecting the existing `findings.md` contract that says "Do not begin fixing anything before this prompt." The manifest is still written either way (generating the manifest is cheap and side-effect-free), but the editor only launches after user consent.

**The term "Proceed Gate" is preserved as an alias** in the new `findings.md` for the consent gate, so existing references in `mine.challenge/SKILL.md` lines 32, 123, 126 and `mine.tool-gaps/SKILL.md` line 178 remain semantically valid without requiring updates to those files.

### The commit gate

After the editor session exits and the detection logic runs, the skill re-reads and validates the manifest, then presents a single commit gate:

```
AskUserQuestion:
  question: "Execute resolution manifest?"
  header: "Execute"
  options:
    - label: "Yes (Recommended)"
      description: "Run fix/file/A/B/etc. verbs. One prompt per 'ask' row during execution."
    - label: "Revise"
      description: "Re-open the editor for more changes"
    - label: "No"
      description: "Abandon resolution — findings will not be resolved this session"
```

This is the **only** decision gate in the execution flow after manifest generation. The per-finding decisions already happened in the editor; the commit gate is a single binary commit checkpoint, not a bundled judgment call.

### Manifest validation spec

After the editor session, before the commit gate, the skill re-reads the manifest and validates each row. The design specifies what happens in every error case — this is load-bearing for the editor pattern because errors during manifest editing are inevitable:

1. **Verb value check**: canonical vocabulary only (`fix`, `file`, `defer`, `skip`, `ask`, `A`, `B`, `C`). Case-insensitive (`Fix` → `fix`), trimmed of whitespace. On failure: show error inline with the offending row and the valid verb list, ask user to re-open via "Revise" path.
2. **Finding ID check**: every `## F<N>:` section must correspond to a finding in the source `findings.md`. On modified ID (e.g., user changed `F3` to `F33`): error inline, ask to re-open.
3. **Option letter check**: if verb is `A`/`B`/`C`, that letter must exist in the finding's `options:` list. On mismatch (e.g., verb `C` on a finding with only A/B options): error inline.
4. **Deleted row handling**: if a finding section is missing from the manifest (user deleted it): treat as `skip` with an explicit warning: *"Finding F3 was removed from the manifest. Treating as skip. Did you mean to defer?"*
5. **Added content handling**: comments or blank lines added by the user → silently ignored.
6. **Row count anomaly**: if the manifest has fewer finding sections than the source `findings.md` and the delta can't be explained by deleted rows: surface *"Manifest appears incomplete (expected N findings, found M). This may indicate an editor crash or accidental deletion. Re-open to verify?"*
7. **Error routing**: on ANY validation failure, route back to the "Revise" path — never abort the session. The editor re-opens with the partial manifest, the user fixes the error, re-saves.

### Execution phase

On "Yes" from the commit gate, the skill iterates the manifest finding-by-finding in two phases:

**Phase 1 — Immediate verbs** (in manifest order):
- `fix` on Auto-apply: apply `better-approach` directly
- `fix` on User-directed: apply the recommended option (from `recommendation:`)
- `A`/`B`/`C`: apply the specified option
- `ask`: emit ONE AskUserQuestion with header `F{id} ({N}/{M})`. Options are the finding's `options:` list PLUS "File as issue" PLUS "Skip". The `(N/M)` position counter is Pattern 1 from prior art — grounds the user in "which finding, of how many." Apply the user's chosen option immediately and continue.
- `defer` / `skip`: record in session summary, no action.

**Phase 2 — Batched `file` verbs** (at the end):
- After all Phase 1 verbs have executed, iterate `file` verbs and invoke `gh-issue create` for each.
- Batch here (not inline) so GitHub API failures are isolated from code changes: if `gh-issue create` fails on F3 after F1 and F2 were successfully fixed, the code changes are already safe. The user sees a batch-level summary of which issues succeeded and which failed, and can retry the batch filing without re-applying code changes.
- On failure of a single `file` verb, continue with the rest (do not halt the batch). At the end, report: `"Filed N issues. M failed: <list with finding IDs and error messages>. Retry filing the failed ones?"`

**Phase 3 — Summary**:
- Report: `"Executed: X fix, Y file, Z ask resolutions. Deferred/skipped: W."`
- If any errors occurred, list them.
- Return control to the caller (standalone mode) or wrap up and exit.

**Execution-phase bundling prevention**: `ask` verbs MUST emit exactly one AskUserQuestion per row. The position counter `(N/M)` in the header is Pattern 1 fallback from the prior-art brief. The Named Anti-Pattern Catalog (below) explicitly forbids bundling ask prompts.

**Acknowledged residual risk**: The `ask` verb path still relies on LLM compliance with prose rules (the anti-pattern catalog) to prevent bundling at execution time. The manifest eliminates bundling for the pre-decided rows (`fix`, `file`, `A`/`B`/`C`, `defer`, `skip`) — which is most of them — but for genuinely ambiguous findings where the user chose `ask`, the per-finding prompt loop is restored and therefore prone to the same failure mode. The design accepts this as residual risk because: (1) the `ask` subset is small, (2) the position counter is a concrete anchor for each prompt, and (3) eliminating `ask` entirely (option B from finding F12) would aggressively change the handling of low-confidence findings. Test strategy validates this with a targeted check: *"with 5 `ask` rows in the manifest, confirm execution emits exactly 5 separate AskUserQuestion calls."*

### Re-edit loop cap

The commit gate's "Revise" option re-opens the editor and loops back. Without a cap, a confused user could cycle indefinitely. The design specifies a cap of **5 iterations**. On the 6th attempt to revise, the skill switches to inline-display fallback mode automatically:

> "You've revised the manifest 5 times. I'll display it inline here for final review instead of re-opening the editor. If you still need changes after that, tell me in chat."

This serves as both a hard limit and a diagnostic signal — repeated revisions usually mean the user is confused about what the verbs do, and the inline display gives claude a chance to explain.

### Observability: `editor-log.md`

`bin/edit-manifest` writes diagnostic events to `<tmpdir>/editor-log.md` during each invocation. Entries include:
- Invocation: timestamp, manifest path, tmux availability detected, `$EDITOR` value, shell command constructed
- Blocking editor check: elapsed time if non-blocking detected, suggested fix
- Exit: exit code, elapsed ms, pre-hash, post-hash, shadow hash, change detected (yes/no)
- Each verb executed: finding ID, verb, result (applied/filed/ask-issued/deferred/skipped/error) with error text
- Any validation errors with full context

The log is written as structured markdown (append-only) so the user can read it when debugging. It lives in the tmpdir (cleaned up on the 7-day schedule) and costs nothing to write. When a user reports "the editor didn't open" or "my changes didn't apply," this is the first file to check.

### Named Anti-Pattern Catalog

Added to `rules/common/findings.md`, modeled verbatim on `rules/common/interaction.md`'s "AskUserQuestion Blocks in Skills (CRITICAL)" section. Eight enumerated failure modes, each with a concrete example drawn from the session logs:

1. **Bundling N findings into one `Accept all?` AskUserQuestion** — "Do not bundle N findings into a single AskUserQuestion. Emit one AskUserQuestion per `ask` row during manifest execution, with `(N/M)` position in the header."
2. **Multi-select as verb selector** — "Do not use `multiSelect: true` to mean 'fix some, file others.' Multi-select is for 'which items match this single decision,' not 'which verb applies to which item.' Verbs belong to the manifest's Verb column."
3. **Double-gate after 'Yes'** — "Do not re-prompt 'Which findings?' after the commit gate. The commit gate's contract is 'execute the manifest as written' — no further triage questions before execution."
4. **Meta-gates with relabeled Proceed Gate** — "Do not rename the consent/commit gates with new labels ('Review findings,' 'Triage findings,' 'Apply revisions') and re-implement their logic. There is exactly one consent gate and one commit gate per resolve flow."
5. **Option labels showing actions instead of problems** — "Option labels in execution-phase `ask` prompts describe the finding's alternative fixes, not generic verbs. A label is 'Move cleanup to session start (Option A)', not 'Fix it.' The verb is encoded by which option is chosen."
6. **Auto-apply mixed with judgment calls in one prompt** — "Auto-apply findings MUST execute silently during manifest iteration. They do not appear as options in `ask` prompts. Interleaving Auto-apply execution with User-directed questions defeats the manifest's discipline."
7. **Permissive defaults that collapse to 'accept all'** — "Default verbs in the manifest must reflect the finding's actual classification and recommendation. User-directed findings without a clear recommendation default to `ask`, not `fix`. Defaulting everything to `fix` recreates the `Accept all?` failure mode in manifest form."
8. **Bail-out options violating 'all findings must be resolved'** — "Do not offer `Skip revisions` / `Enough — approve as-is` options at any gate. Explicit deferral is valid (via `defer` or `skip` verbs), but it must be recorded per finding in the manifest, not smuggled in as a catch-all escape."

Each entry includes a verbatim example from the session logs compiled at the start of this design cycle. The prior-art research was explicit that named failure modes are *necessary but not sufficient* — the structural fix (manifest + editor script) is what actually prevents bundling; the catalog is defense-in-depth.

### File layout changes

**NEW: `bin/edit-manifest`** (~80 lines of zsh)
- Helper script implementing the editor-launching mechanism
- Detects tmux availability, blocking editor, fallback tier
- Invokes `tmux new-window + wait-for` with shadow-autosave autocmds
- Writes to `<tmpdir>/editor-log.md`
- Installed via `install.sh` as a symlink in `~/.local/bin/`

**MAJOR REWRITE: `rules/common/findings.md`** (grows from ~54 lines to ~150 lines)
- Principle: "All Findings Must Be Resolved" (kept, unchanged)
- Presenting Findings (kept, unchanged)
- **NEW**: Resolution Manifest section — describes the manifest format, default verb selection (recommendation-based), execution flow, and validation spec. **Mechanism-agnostic** — says "the invoking skill calls `edit-manifest` to launch the editor session" without naming tmux.
- **NEW**: Verb vocabulary — the canonical definition (see table above)
- **NEW**: Named Anti-Pattern Catalog — 8 failure modes with verbatim examples
- **NEW**: Consent Gate and Commit Gate sections
- Resolving Findings (rewritten) — now describes manifest iteration, execution-phase `(N/M)` prompts, batched `file` verbs, and the specific contract for each verb. "Proceed Gate" retained as an alias.
- Skill-Specific Overrides (kept, unchanged) — visual-qa and tool-gaps continue to use this escape hatch, follow-up design will migrate them to the manifest path

**MINOR EDIT: `skills/mine.challenge/SKILL.md`** (Phase 4, lines 508–512)
- Insert after the summary paragraph: *"If mode is `standalone`, write `<tmpdir>/resolutions.md` per the Resolution Manifest format in `rules/common/findings.md` (defaults from findings' `recommendation:` fields). Present the Consent Gate. On Yes, invoke `edit-manifest <tmpdir>/resolutions.md` and wait for the editor session to complete (via task-notification). Run the detection and validation logic from `rules/common/findings.md`. Present the Commit Gate. Execute the manifest."*
- Update line 510's delegation prose to reference the new flow.
- No changes to Phase 1, 2, 3 or critic/synthesis logic.

**COSMETIC EDIT: `skills/mine.visual-qa/SKILL.md`** (lines 301 and 305)
- Both prose references to "collect all user-directed answers first, then execute fixes" → updated to "follow the Resolution Manifest flow in `rules/common/findings.md`" (which still routes through the legacy path via Skill-Specific Overrides for this design).
- Add explicit language to the follow-up note: "Visual-QA currently uses the Skill-Specific Override path. A follow-up design will migrate visual-qa to produce manifest-compatible findings and use the Resolution Manifest flow directly."

**MINOR EDIT: `rules/common/interaction.md`**
- Document the AskUserQuestion `preview` field in the "AskUserQuestion Blocks in Skills (CRITICAL)" section. The field DOES exist in the tool schema but is currently undocumented in the rule, making it invisible to future maintainers who might want to use it for side-by-side display of manifest-like content.

**NO CHANGE**: `skills/mine.design/SKILL.md`, `skills/mine.specify/SKILL.md`, `skills/mine.orchestrate/SKILL.md` (structured callers, bypass the resolve flow). `skills/mine.tool-gaps/SKILL.md` (has its own skill-specific override gate). `skills/mine.grill/SKILL.md` (inherits improved standalone behavior). All other callers unchanged.

## Alternatives Considered

### tmux display-popup (original proposal — rejected)

The original design used `tmux display-popup -E -w 90% -h 90%` to open a floating modal editor. Dogfood testing revealed a fatal UX issue: tmux popups do not dynamically resize with the terminal. When the user resizes their terminal window (a routine action when moving from a side-docked layout to a centered one), the popup stays at its original dimensions and the content gets clipped. Tmux 3.4 (and later as of design time) has no option to make popups resize with the client.

Tmux `new-window + wait-for` has the same semantic (blocking call until editor exits) with none of the resize issues — the editor runs in a regular tmux window that the terminal emulator manages natively. We adopted it during the session and updated the design accordingly.

### Option A: Manifest as display-only (rejected by research + dogfood)

Skill writes the manifest, displays it inline, then asks one AskUserQuestion per User-directed finding. The manifest is decorative; every finding still triggers its own interactive prompt.

**Rejected because**: no structural benefit over the status quo. The bundling failure mode occurs *in the AskUserQuestion call itself*, and this option still uses N AskUserQuestion calls. The LLM would collapse them identically to today.

### Option B: Pure "edit file, then say go" (originally rejected, rescued by bin/edit-manifest)

The prior-art brief rejected this because it assumed the user would have to issue Edit tool calls themselves. With `bin/edit-manifest` + tmux new-window, the user's experience is identical to `git rebase -i` opening `$EDITOR`: they type `:wq` to save, exit, everything continues. **The final design is effectively Option B made viable by the helper script.**

### Option C: Free-text edits in chat (partial — used as tertiary fallback)

User responds in chat with natural-language verb changes ("change F4 to file, F7 to skip"). Anti-bundling is strong because the manifest is still the shared reference, but parsing is brittler than file editing. Kept as the **tertiary fallback** for environments without tmux or IDE integration.

### Option D: Hybrid with inline display (superseded)

Research originally recommended Option D: inline display via AskUserQuestion `preview` field + free-text edits + commit gate. During Phase 3 interrogation we discovered `tmux display-popup` made pure Option B viable. Then dogfood testing showed display-popup had a resize issue, so we moved to `tmux new-window`. Option D remains as the **secondary/tertiary fallback** logic (inline display via `preview` field when available, plus free-text parsing).

### Group-by-kind / severity-tiered batches (explicitly rejected)

The LLM is *already* doing this wrong, grouping findings into "MEDIUM batch 1 / 2 / 3" prompts. Formalizing grouping legitimizes the exact failure mode we're fixing. The manifest treats each finding as its own section regardless of severity or type.

### Durable manifest at `design/challenge/NNN-name/resolutions.md` (rejected)

Resolutions are session-scoped. Adding a new durable artifact type creates lifecycle-management burden with no downstream consumer. Tmpdir is the correct home.

### nvim persistent undo (`undofile`) as `:q!` safety (rejected)

Investigated as a recovery mechanism for the `:q!` muscle-memory hazard. Does NOT help: nvim's undo files only persist changes that have been *saved*. If the user `:q!`s without ever `:w`ing, the undo file is empty. Shadow file via autocmd is the correct approach (finding N4).

### Aggressive autosave to the original file (rejected — breaks detection)

Initially considered: pass `autocmd TextChanged <buffer> silent write` to save the buffer to the original file on every change. This would make `:q!` harmless. Rejected because it collapses every exit to "saved" and destroys the hash-comparison mechanism that distinguishes `:wq` from `:q` from "opened but didn't change." Writing to a **shadow file** (not the original) preserves both properties: the original file's hash still tells you what the user explicitly committed; the shadow file's hash tells you what they typed.

## Test Strategy

This is a prompt/rules/bin repo with no unit test infrastructure. "Tests" here mean manual validation in real sessions.

### Already completed (design-time dogfood validation)

- **Popup mechanism round-trip**: Created a throwaway manifest, opened via `tmux display-popup -E`, user edited in nvim, saved with `:wq`, claude re-read the file and saw the edit. ✓
- **Exit code propagation**: Verified `:cq` returns exit 1 through the popup layer. ✓
- **`$EDITOR` respect**: Verified `EDITOR=nano` invokes nano instead of nvim. ✓
- **`:q` vs `:wq` indistinguishable by exit code**: Verified both return exit 0, confirming hash-based detection is required. ✓
- **PATH resolution**: Verified naive invocation without `$SHELL -lc` wrapper fails with exit 127 due to mise-managed editor not in popup PATH. Wrapper fixes it. ✓
- **Popup resize failure mode**: Verified that tmux `display-popup` does not resize when the terminal is resized — this is why we switched to `new-window + wait-for`. ✓
- **`new-window + wait-for` round-trip**: Verified this replaces the popup with no loss of semantics and resizes naturally. ✓
- **Bash tool auto-backgrounding**: Verified the bash tool auto-backgrounds the blocking `new-window + wait-for` call and delivers completion via task-notification. The design now explicitly handles async completion. ✓
- **Vim muscle memory (`:q!`) loss**: Verified in real-time during dogfood that `:q!` silently destroys edits. This drove the shadow-file autocmd mechanism (N4). ✓
- **Shadow file recovery**: Verified that `autocmd VimLeave` writes the shadow file on any exit, preserving user edits across `:q!`. ✓
- **This entire design doc was resolved via the dogfood manifest flow** — 22 original findings + 4 new ones were reviewed in a manifest file opened in the new-window + wait-for pattern, with shadow-file autosave protecting against the `:q!` discovered during the review. The flow successfully handled explicit save, per-finding pushback, scope expansion requests, and `:q!` recovery in a single real-world session.

### Validation after implementation

- **Trigger mine.challenge on a real target** with 5+ mixed-resolution findings. Confirm:
  - Manifest file is written to `<tmpdir>/resolutions.md`
  - Default verbs match the recommendation-based policy
  - `bin/edit-manifest` launches the editor via `new-window + wait-for`
  - Shadow file is created and captures in-flight edits
  - Consent gate fires before the editor launches
  - Commit gate appears after the edit session with Yes/Revise/No options
  - Execution phase emits exactly one AskUserQuestion per `ask` row with `(N/M)` position counter
  - Auto-apply findings execute silently
  - `file` verbs are batched at the end, not inline
  - Validation errors route back to Revise, not abort

- **Verify no bundling regression** by re-challenging one of the target PRs that previously triggered the bug (session `99e9716a` had 31 findings producing "MEDIUM batch 1/2/3" bundling). The execution phase should produce N individual AskUserQuestion calls where the user chose `ask`, not N bundled into 1.

- **Verify structured callers unaffected** — run `/mine.design` with `--findings-out` and confirm it never touches `bin/edit-manifest` or the manifest path.

- **Verify fallback tiers**:
  - **Primary (tmux)**: Default path on the development machine.
  - **Tertiary (no tmux)**: Run the skill with `unset TMUX` in the bash environment (or from a plain terminal session), verify the tertiary fallback engages and the user can complete resolution via chat.
  - **Secondary (IDE)**: Time-boxed investigation during implementation — may defer if IDE hook doesn't expose a suitable primitive.

- **Non-blocking editor detection**: Set `EDITOR=code` (without `--wait`) and run the skill. Verify the proactive check fires a warning before the window opens, AND the reactive check catches it if the user proceeds anyway.

- **Shadow-file recovery**: Open the editor, type changes, `:q!`. Verify the detection logic offers recovery options (recover, abandon, re-open).

- **Anti-pattern catalog regression test**: Produce a synthetic findings file that previously triggered bundling. Confirm the LLM, reading the new `findings.md`, emits the manifest flow rather than a bundled prompt.

- **`(N/M)` counter test**: With 5 `ask` rows, confirm execution emits exactly 5 separate AskUserQuestion calls — each with `(N/5)` in the header.

No unit tests possible. Validation is session-level and observational — we compare behavior before and after against the compiled examples of bad AskUserQuestion prompts.

## Open Questions

- **Claude Code `/ide` integration for the secondary fallback**: Time-boxed investigation during implementation. May produce a working primitive, may not — don't block on perfection. Falls through to tertiary if not available.
- **wait-for lock mode correctness**: The design specifies `tmux wait-for -L` acquired by the parent before `new-window` to eliminate the race where `-S` could fire before the listener is ready. This needs validation during implementation — tmux's `wait-for` documentation is sparse on the lock-vs-signal interaction.
- **`bin/edit-manifest` script installation**: Confirm `install.sh` picks up the new script automatically (it globs `bin/*`) or requires an update. Verify during implementation.
- **TENSION (F21) — non-vim user validation**: The popup-vs-mental-model tension was partially resolved by this dogfood session for the CLI-user profile (the user engaged substantively with the manifest). A non-vim user test remains outstanding but is lower priority given the new-window mechanism works with any `$EDITOR`. Tracked as a follow-up validation.
- **Follow-up design: visual-qa migration**. This design ships the enabling infrastructure (`bin/edit-manifest`, manifest format, rule structure). A follow-up design doc will cover migrating visual-qa to produce manifest-compatible findings and use the Resolution Manifest flow via the same script. Expected scope: extending visual-qa synthesis to emit `severity:`, `resolution:`, `recommendation:` fields; updating visual-qa Phase 4 to call `edit-manifest`; possibly extending tool-gaps similarly.

## Impact

### Files modified or created

| File | Change type | Lines | Description |
|---|---|---|---|
| `bin/edit-manifest` | **NEW** | ~80 | Helper script — all editor-launching mechanics (tmux detection, shell wrapping, shadow autocmds, fallback tiers) |
| `rules/common/findings.md` | **MAJOR REWRITE** | ~54 → ~150 | Add Resolution Manifest section, Verb vocabulary, Consent/Commit Gates, Anti-Pattern Catalog, validation spec. Remove any mechanism-specific language. Preserve Proceed Gate as alias. |
| `skills/mine.challenge/SKILL.md` | Minor edit | ~5 lines | Lines 508–512: insert manifest-generation and `edit-manifest` invocation step. No other changes. |
| `skills/mine.visual-qa/SKILL.md` | Cosmetic | 2 lines | Lines 301 and 305: prose updates referencing the new flow name. Follow-up note about planned migration. |
| `rules/common/interaction.md` | Minor addition | ~5 lines | Document the AskUserQuestion `preview` field in the existing section. |

### Files NOT modified (explicitly verified)

- `skills/mine.challenge/SKILL.md` Phases 1, 2, 3 (all critic phases and synthesis) — unchanged
- `skills/mine.challenge/SKILL.md` findings file format (lines 402–423) — unchanged
- `skills/mine.design/SKILL.md`, `skills/mine.specify/SKILL.md`, `skills/mine.orchestrate/SKILL.md` — structured callers, bypass the resolve flow
- `skills/mine.tool-gaps/SKILL.md` — has its own skill-specific override gate
- `skills/mine.grill/SKILL.md`, `skills/mine.research/SKILL.md`, `skills/mine.brainstorm/SKILL.md`, `skills/mine.build/SKILL.md` — various non-impactful caller types (passthrough, detection, or inheritance of improved behavior)

### Dependencies

- **tmux 2.4+** for the primary path (wait-for is old, much wider coverage than the 3.2+ originally required by popup). Installed version at design time is 3.4.
- **A usable `$EDITOR` configured for blocking invocation** — nvim, vim, nano, emacs, etc. GUI editors require explicit `--wait` flags (`code --wait`, `subl -w`). `bin/edit-manifest` warns on known-non-blocking values.
- **A login shell with the editor in PATH** — `zsh -l` wrapper resolves PATH via the user's profile, picking up mise, asdf, direnv, nix-managed editors.
- **Existing runtime deps** (`spec-helper`, `gh-issue`, `get-skill-tmpdir`) — unchanged.
- **Fallback path** requires no tmux and no editor (chat-only) — always available.

### Migration risk

Low. The change is scoped to the standalone resolve flow of a single skill plus a new shared helper script. Structured callers are unaffected. No findings-file schema changes, no contract version bumps, no caller contract changes. The worst-case failure mode is the tertiary fallback path (write file + free-text edits in chat), which is strictly better than the current bundled behavior.

### Session log evidence (for post-implementation validation)

The following sessions produced bad AskUserQuestion prompts during Phase 4 resolution. After implementing this design, re-challenging the same targets should produce manifest-based flows instead:

- Session `99e9716a` (2026-04-08, hassette source-tier) — produced 3 "MEDIUM batch N" bundled prompts
- Session `0421be8c` (2026-04-07) — produced "Quick decisions for the user-directed findings" with 9 findings bundled
- Session `cb1c59ad` (2026-04-07) — produced two "Remaining user-directed findings" prompts with 11 and 12 findings bundled
- Session `5cfebd80` (2026-04-08) — the one known-good per-finding prompt (Finding 19), should continue to work cleanly
- **Session `a175a1a7` (2026-04-09, this session)** — dogfood design of the manifest flow. Successfully resolved 26 findings (22 from challenge + 4 from dogfood discovery) via the manifest pattern with shadow-file recovery after a real `:q!` incident. This session is itself the first validation of the design.
