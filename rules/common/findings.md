# Findings

When analysis skills produce findings, follow this convention for presenting and resolving them. This applies to skills that identify fixable issues — audit, challenge (standalone), visual-qa, tool-gaps, and similar. It does not apply to ideation skills like brainstorm, which manage their own output.

## Principle: All Findings Must Be Resolved

Every finding must be resolved — meaning fixed, filed as an issue, or explicitly deferred by the user. Do not guide the user toward shipping code with known unresolved findings. "File as issue" is not skipping — it's proper tracking for work that can't happen now. Explicit user deferral ("Skip") is valid — the principle prevents silent abandonment, not informed decisions.

## Presenting Findings

Every finding must include a **concrete recommendation** — not just what's wrong, but what to do about it. A finding without a recommendation is incomplete.

For findings with multiple valid approaches, present options:
- **Option A** is always the recommended approach, labeled with `(Recommended)`
- Additional options follow
- "File as issue" is always available as an option; recommend it when the fix is out of scope for this session

## Verb Vocabulary

One canonical table. Do not redefine these verbs elsewhere.

| Verb | Meaning | Applies to |
|---|---|---|
| `fix` | Auto-apply the `better-approach` or recommended option | Auto-apply findings; User-directed set by user |
| `file` | Create a GitHub issue via `gh-issue create` (batched at end of execution) | Any finding |
| `defer` | Record in session summary; take no action this session | TENSION findings, explicit user deferral |
| `skip` | Same as `defer` but for "not a real issue" | User override |
| `ask` | Emit one AskUserQuestion at execution time with options | User-directed findings where recommendation is absent or ambiguous |
| `A` / `B` / `C` | Apply the pre-selected option letter | User-directed findings with `options:` lists |

## Default Verb Selection

Pre-populate manifest verbs based on the finding's `recommendation:` field:

| Finding `resolution:` | `recommendation:` field | Default verb |
|---|---|---|
| `Auto-apply` | (n/a) | `fix` |
| `User-directed` | Contains specific option letter (e.g., "Option A") | That letter (`A`) |
| `User-directed` | Absent or says "user must decide" / no clear letter | `ask` |
| `TENSION` | (n/a) | `defer` |

**Format-version 1 fallback**: If a finding lacks a `recommendation:` field entirely, default to `ask`. Write a header comment in the manifest: `<!-- Format-version 1 source — some findings defaulted to 'ask' due to missing recommendation field -->`.

## Resolution Manifest

The F<N> IDs correspond 1:1 to `## Finding N:` headings — Finding 1 → F1, Finding 2 → F2, etc. The "source findings list" is the ordered set of all `## Finding N:` blocks in the findings file.

The manifest is a markdown file at `<tmpdir>/resolutions.md`. The skill reuses the same `<tmpdir>` that holds the findings file — typically obtained via `get-skill-tmpdir` at the start of the skill. Place `resolutions.md` in the same directory as `findings.md`. Each finding gets a block:

```markdown
## F1: Finding title here
**Severity:** HIGH | **Type:** Fragility | **Raised by:** Critic Name (1/5)

**Problem:** What's wrong.

**Why it matters:** Consequence if left unfixed.

**Options:**
- **A** *(recommended)*: First option with full text
- **B**: Second option

**Why A:** One-sentence rationale.

**Verb:** A
```

The above is the **User-directed finding template**. Two additional templates apply for other finding types. The `**Verb:**` line is the only field the user edits in all templates.

**Auto-apply finding template:**
```markdown
## F1: Finding title here
**Severity:** HIGH | **Type:** Fragility | **Raised by:** Critic Name (1/5)

**Problem:** What's wrong.

**Why it matters:** Consequence if left unfixed.

**Better approach:** The specific change to apply.

**Verb:** fix
```

**TENSION finding template:**
```markdown
## F1: Finding title here
**Severity:** TENSION | **Type:** Structural | **Raised by:** Critic Name (1/5)

**Problem:** What's wrong.

**The disagreement:** Side A argues X because Y. Side B argues Z because W.

**Deciding factor:** Question or data point that would resolve the disagreement.

**Verb:** defer
```

The manifest header includes: brief usage instructions, the verb legend, a compaction-recovery pre-hash comment (`<!-- pre-hash: <sha256> -->`), and a mechanism-conditional safety note. For interactive editor sessions with shadow-file autosave support, include a visible blockquote:

> **:q! is safe** — your edits are autosaved to a shadow file every 2 seconds. Save normally or quit — your changes will be recovered.

Omit this safety note for inline display sessions (tertiary fallback).

## Consent Gate

Before the editor opens, ask once. **"Proceed Gate" is an alias for this gate** — it is the successor to the old Proceed Gate.

```
AskUserQuestion:
  question: "Found N findings (breakdown). Ready to review the resolution manifest?"
  header: "Review findings"
  options:
    - label: "Yes — open editor (Recommended)"
      description: "Generate the manifest and open it in your editor"
    - label: "No — stop here"
      description: "I'll review findings and come back later"
```

Do not begin generating or opening the manifest before this prompt.

## Editor Session

Before invoking edit-manifest, emit: "Generating the resolution manifest — your editor will open momentarily. Edit the **Verb:** lines and save. Return here when done."

The skill calls `edit-manifest <path>` (the bin/ script, installed to PATH via install.sh) and waits for it to return. That tool handles all editor mechanics — do not embed editor commands, shell invocations, or pane management here. The rule is mechanism-agnostic.

### Tertiary Fallback — No Editor Available

If `edit-manifest` returns in under 2 seconds (indicating tertiary fallback — no interactive editor environment), do not run Detection Logic immediately. Instead, emit the manifest path with instructions to the user and wait for them to signal completion via chat (e.g., "done", "ready", "finished editing"). When the signal arrives, re-read the manifest and proceed to Detection Logic.

## Detection Logic

The invoking skill runs this logic at notification receipt (or on synchronous return); findings.md defines the cases and actions.

After the editor session ends, determine what happened:

```
pre_hash  = sha256(manifest) captured before edit session
post_hash = sha256(manifest) captured after edit session
shadow_exists = whether <manifest>.shadow exists
shadow_hash = sha256(<manifest>.shadow) if exists else post_hash
```

The pre-hash is recoverable from the `<!-- pre-hash: ... -->` comment embedded in the manifest before the editor launched. Compute post_hash and shadow_hash fresh at execution time via sha256sum — do not rely on values from editor-log.md or context.

| Condition | Meaning | Action |
|---|---|---|
| `post_hash != pre_hash` | User explicitly saved | Proceed to Commit Gate |
| `post_hash == pre_hash` AND `!shadow_exists` | No edits ever typed | "Defaults look good — proceed with current verbs?" |
| `post_hash == pre_hash` AND `shadow_hash != post_hash` | Typed changes, did not save | "You had unsaved changes. Recover, abandon, or re-open?" |
| `post_hash == pre_hash` AND `shadow_hash == post_hash` | Edited then undid all changes | Same as "no edits ever" |

If the user picks "recover": copy the shadow file over the manifest and loop back to the Commit Gate.

## Commit Gate

After detection confirms the manifest is ready:

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
      description: "Defer for now — findings will remain unresolved until you return to this session."
```

## Execution

### Phase 1 — Immediate verbs (in manifest order)

- `fix` on Auto-apply: apply `better-approach` directly, silently
- `fix` on User-directed: apply the recommended option, silently
- `A` / `B` / `C`: apply the specified option, silently
- `ask`: emit ONE AskUserQuestion with header `F{id} ({N}/{M})` where N/M is this `ask` verb's position among all `ask` verbs. Options are the finding's `options:` list PLUS "File as issue" PLUS "Skip". Apply chosen option immediately and continue.
- `defer` / `skip`: record in session summary, take no action

### Phase 2 — Batched `file` verbs

After all Phase 1 verbs, iterate `file` verbs and invoke `gh-issue create` for each. On single failure, continue with rest. Report: `"Filed N issues. M failed: <list>. Retry filing the failed ones?"`

### Phase 3 — Summary

Report: `"Executed: X fix, Y file, Z ask resolutions. Deferred/skipped: W."`

## Manifest Validation Spec

Run before execution. On any failure, route back to the "Revise" path — never abort the session.

1. **Verb value check**: canonical vocabulary only. Case-insensitive, whitespace-trimmed.
2. **Finding ID check**: every `## F<N>:` section must correspond to a finding in the source findings list.
3. **Option letter check**: if verb is `A`/`B`/`C`, that letter must exist in the finding's `options:` list.
4. **Deleted row handling**: if a finding section is missing, treat as `skip` with an explicit warning.
5. **Added content handling**: comments or blank lines added → silently ignored.
6. **Row count anomaly**: if manifest has fewer finding sections than source and delta can't be explained by deleted rows, surface a warning.
7. **Error routing**: on ANY validation failure, show the error inline and route to "Revise."

## Re-edit Loop Cap

5 iterations max. On the 6th revision attempt, switch to inline-display fallback mode:

> "You've revised the manifest 5 times. I'll display it inline here for final review instead of re-opening the editor. If you still need changes after that, tell me in chat."

See `rules/common/findings-anti-patterns.md` for the full Named Anti-Pattern Catalog — eight failure modes with verbatim examples. This file auto-loads alongside `findings.md` — no explicit reference needed in skills.

## Skill-Specific Overrides

Some skills have post-finding interactions beyond fix/file (e.g., visual-qa offers "re-run with different viewport" and "read agent report"). These skills may present their own post-finding gate in place of — not in addition to — the Consent Gate (Proceed Gate). The skill's gate should still include fix and file-as-issue paths. Skills using the legacy Proceed Gate pattern should migrate to the Resolution Manifest flow on next revision.
