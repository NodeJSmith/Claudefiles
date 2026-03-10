# Research Brief: /tmp Writing in Claudefiles — Usage Review

**Date**: 2026-03-10
**Status**: Ready for Decision
**Proposal**: Evaluate whether the tmp-writing helpers and patterns in Claudefiles are adding friction vs. solving real problems — and whether Claude Code's native behavior has changed the calculus.
**Initiated by**: "I want to see if we're making things more difficult for ourselves with the direction/helpers we've added"

---

## Context

### What prompted this

Friction in practice. The tmp-writing machinery was introduced to solve a real constraint (Bash tool `$()` breakage) and expanded over time to cover command capture, subagent isolation, PR body avoidance, and error tracking. The question is whether the pattern has accumulated scope beyond its useful core.

### Current state

Two distinct patterns emerged in the codebase, often conflated under the same `get-tmp-filename` surface:

**Pattern A — Command output capture** (the original purpose):
```
get-tmp-filename          # Bash call 1: get unique path
pytest 2>&1 | tee <path> | tail -80   # Bash call 2: capture + tail
```
Exists to preserve verbose output so Claude can `Read` sections instead of re-running expensive commands.

**Pattern B — Unique path for Write tool** (expanded use):
```
get-tmp-filename          # Bash call 1: get unique path
Write <body> → <path>     # Write tool call: write content to that path
gh pr create --body-file <path>  # Bash call 3: use path
```
Used by `mine.create-pr`, `mine.ship`, `mine.orchestrate` (×3), `mine.design`, `mine.plan-review`, `mine.implementation-review`. Here `get-tmp-filename` is called just to get a unique filename — the Write tool does the actual writing, so the `$()` constraint doesn't apply.

**Session-ID naming** (parallel subagent isolation):
```
${CLAUDE_CODE_TMPDIR:-/tmp}/mine-brainstorm-pragmatist-$CLAUDE_SESSION_ID.md
```
Used by `mine.brainstorm` (4 files) and `mine.challenge` (3 files) to give parallel subagents independent write paths. Claude constructs these paths inline and passes them to subagents as literal strings.

**Error tracking** (session-scoped file):
```
${CLAUDE_CODE_TMPDIR:-/tmp}/claude-errors-$CLAUDE_SESSION_ID.md
```
Used by `rules/common/error-tracking.md` and `commands/mine.status.md`.

### Key constraints

- The Bash tool wraps commands in `eval '...' < /dev/null`, which breaks `$(...)` command substitution — CLAUDE.md documents this explicitly
- `CLAUDE_CODE_TMPDIR` is NOT automatically set by Claude Code; it requires explicit user configuration
- Claude Code creates its own internal temp files at `/tmp/claude-{UID}/` (separate from user-managed tmp)

---

## What Claude Code Provides Natively

Claude Code's native tmp support is **minimal and configuration-only**:

- **`CLAUDE_CODE_TMPDIR` (env var)**: Users set this to redirect where Claude Code stores its *own* internal temp files. Claude Code appends `/claude/` to whatever path is given. Not auto-set.
- **No native temp file creation tool** — no built-in equivalent of `get-tmp-filename`
- **No native session-scoped file management**
- **Sandbox `/tmp` path mismatch** (open bug): Claude Code creates files at `/tmp/claude-{UID}/` but the default sandbox allowlist is `/tmp/claude` and `/private/tmp/claude`, causing sandbox permission errors in practice (GitHub issue #23214, unresolved)

Bottom line: everything beyond setting `CLAUDE_CODE_TMPDIR` is user responsibility. Claude Code did not introduce a native feature that supersedes what we built.

---

## Feasibility Analysis

### What the `${CLAUDE_CODE_TMPDIR:-/tmp}` guard actually buys us

| Context | CLAUDE_CODE_TMPDIR set? | Effect of guard |
|---------|------------------------|----------------|
| Normal interactive session | No (default) | Always resolves to `/tmp` |
| User has sandbox mode configured | Sometimes | Routes to sandbox dir |
| Subagent (Task tool) | Inherited from parent | Consistent behavior |

**In practice:** The guard adds ~25 chars of verbosity to every tmp reference (40+ occurrences across the codebase) for a benefit that applies only to users who explicitly opt into sandbox mode with a custom tmp dir. This user is not that user.

### What the `get-tmp-filename` two-call pattern costs

Every use of `get-tmp-filename` requires:
1. A separate Bash call (even pre-approved, still a context step)
2. Claude remembering the printed path from one tool call to use in the next
3. Skill text explaining the pattern and its `$()` constraint

For **Pattern A** (tee capture), this cost is justified — there's no other way to capture piped Bash output to a file without `$()`.

For **Pattern B** (Write tool + unique path), the cost is **unjustified**:
- The Write tool doesn't use Bash at all, so `$()` is irrelevant
- A fixed predictable path (e.g., `/tmp/mine-pr-body.md`) works fine
- Or a session-ID path can be constructed inline without a Bash call
- `mine.orchestrate` calls `get-tmp-filename` *three times* before the main orchestration even begins — three extra steps for something that could be three fixed paths

### Allowedtools redundancy

```json
"Read(/tmp/*)",    // matches top-level /tmp files only
"Read(/tmp/**)",   // matches /tmp recursively (superset of above)
```

Both `/tmp/*` and `/tmp/**` exist for Read, Write, Edit, and Grep — 8 entries where 4 would suffice. `/tmp/**` is a superset of `/tmp/*`.

---

## Options Evaluated

### Option A: Targeted simplification (Recommended)

Fix the two specific places where we've accumulated unnecessary complexity, leave the legitimate pattern alone.

**Changes:**
1. **Pattern B usages** — replace `get-tmp-filename` + Write with a fixed predictable path or inline session-ID path. Affected: `mine.create-pr`, `mine.ship`, `mine.orchestrate`, `mine.design`, `mine.plan-review`, `mine.implementation-review`
2. **`${CLAUDE_CODE_TMPDIR:-/tmp}` guard** — simplify to `/tmp` everywhere except the one place that documents why the guard exists (`command-output.md`). The guard in skill files adds verbosity without practical value.
3. **allowedTools dedup** — remove the `/*` variants, keep only `/**` (4 entries → 4 entries)
4. **Keep Pattern A unchanged** — `get-tmp-filename` + tee for command output capture is the right solution to a real constraint

**Pros:**
- Removes friction from the most common use cases (skills that just need a path for Write)
- Reduces skill text length and complexity (less to explain, less to get wrong)
- Fixed paths for PR bodies, review outputs etc. are predictable and debuggable
- Doesn't change the behavior that actually matters

**Cons:**
- Fixed paths could collide if the same skill runs concurrently (unlikely but possible)
- Requires touching 6 skills

**Effort:** Small — text changes to skill files and settings.json

---

### Option B: Keep everything, document better

Accept that the patterns are correct and add more explanatory text to clarify when to use which pattern.

**Why this won't fix the friction:** The complexity comes from the machinery, not from missing documentation. Adding more docs to explain complex machinery is the wrong direction.

**Effort:** Small, but doesn't help

---

### Option C: Full removal of get-tmp-filename

Remove the `get-tmp-filename` script and pattern entirely, use fixed paths or Write tool everywhere.

**Why this doesn't work:** Pattern A (tee-based command capture) genuinely needs a unique path to avoid collisions between concurrent sessions and between test runs. The `$()` constraint is real. Removing `get-tmp-filename` would mean either hardcoded collision-prone paths or undocumented Bash workarounds.

**Effort:** Medium, and degrades real capability

---

## Concerns

### The `$()` constraint may not be eternal

The CLAUDE.md `$()` warning is based on how the Bash tool currently works (eval wrapper). If Anthropic changes this, the two-call pattern becomes unnecessary even for Pattern A. But we can't count on that.

### Session-ID naming has a hidden assumption

Brainstorm and challenge skills use `$CLAUDE_SESSION_ID` to name temp files. This works because Claude constructs the path as a literal string at runtime — it doesn't need shell expansion. But if `$CLAUDE_SESSION_ID` is not in the system context as a resolvable variable (it's sometimes in the system prompt, sometimes not), this could silently fail and produce files literally named `...-$CLAUDE_SESSION_ID.md`. Worth verifying.

### Fixed paths and concurrent skills

If Option A uses fixed paths (e.g., `/tmp/mine-pr-body.md`), two simultaneous `mine.create-pr` runs would clobber each other. In practice this almost never happens, but session-ID suffix is cleaner if available.

---

## Open Questions

- [ ] Has the Bash tool `eval` wrapper changed recently? If `$()` now works, the two-call pattern can be simplified further
- [ ] Does `$CLAUDE_SESSION_ID` reliably resolve in skill context? Or is it sometimes literal text in the constructed path?
- [ ] Is sandbox mode with custom `CLAUDE_CODE_TMPDIR` actually used by this user? (If no, the guard is pure noise)

---

## Recommendation

**Option A — Targeted simplification.**

The core insight: `get-tmp-filename` exists to solve `$()` being broken in Bash. That problem is real and the two-call pattern is the right fix — *for Bash-piped output*. But it's been copy-pasted into skills that don't use Bash piping at all (they use the Write tool). Those usages add friction without value.

The `${CLAUDE_CODE_TMPDIR:-/tmp}` guard is similarly defensive-for-a-scenario-that-never-happens. Simplifying to `/tmp` in skill text reduces noise significantly.

**What we built is not wrong — it's just been applied too broadly.** The friction comes from Pattern A's necessary complexity leaking into Pattern B where simpler approaches work fine.

### Suggested next steps

1. **Audit Pattern B usages** — read `mine.create-pr`, `mine.ship`, `mine.orchestrate`, `mine.design`, `mine.plan-review`, `mine.implementation-review` and replace `get-tmp-filename` + Write sequences with fixed or session-ID inline paths
2. **Strip `${CLAUDE_CODE_TMPDIR:-/tmp}` from skill text** — leave it only in `command-output.md` (which explains the concept) and `error-tracking.md` (used by a rule, not a skill)
3. **Deduplicate allowedTools** — remove `Read(/tmp/*)`, `Write(/tmp/*)`, `Edit(/tmp/*)`, `Grep(/tmp/*)` (the `/**` variants cover them)
4. **Verify `$CLAUDE_SESSION_ID`** — confirm it resolves at skill runtime for brainstorm/challenge skills, or add a note about what happens when it doesn't

---

## Sources

- [ClaudeLog: What is CLAUDE_CODE_TMPDIR](https://claudelog.com/faqs/what-is-claude-code-tmpdir-in-claude-code/)
- GitHub issue #23214: Sandbox UID suffix path mismatch (open/unresolved)
- GitHub issue #19387: Task tool subagent TMPDIR propagation
