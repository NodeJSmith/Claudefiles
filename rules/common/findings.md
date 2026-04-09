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

The manifest is a markdown file at `<tmpdir>/resolutions.md`. Each finding gets a block:

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

TENSION findings substitute `**The disagreement:**` + `**Deciding factor:**` for the Options/Why block. Auto-apply findings use `**Better approach:**` instead of Options. The `**Verb:**` line is the only field the user edits.

The manifest header includes: brief usage instructions, the verb legend, a compaction-recovery pre-hash comment (`<!-- pre-hash: <sha256> -->`), and a safety note (`<!-- Your edits are captured via autosave shadow file — abandoning the editor is safe -->`).

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

The skill calls `bin/edit-manifest <path>` and waits for it to return. That tool handles all editor mechanics — do not embed editor commands, shell invocations, or pane management here. The rule is mechanism-agnostic.

## Detection Logic

After the editor session ends, determine what happened:

```
pre_hash  = sha256(manifest) captured before edit session
post_hash = sha256(manifest) captured after edit session
shadow_exists = whether <manifest>.shadow exists
shadow_hash = sha256(<manifest>.shadow) if exists else post_hash
```

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
      description: "Abandon resolution — findings will not be resolved this session"
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

## Named Anti-Pattern Catalog (CRITICAL)

These are failure modes that recur across skill implementations. Each is named so it can be cited. Do not repeat any of them.

1. **Bundling N findings into one `Accept all?` AskUserQuestion** — Do not bundle multiple findings into a single AskUserQuestion. Emit one AskUserQuestion per `ask` row during manifest execution, with `(N/M)` position in the header.

   **Looks like this:**
   ```
   AskUserQuestion:
     question: "I found 9 findings. How would you like to handle them?"
     options:
       - label: "Yes — accept all recommendations"
       - label: "No — I want to discuss some"
   ```
   **Instead:** Write the manifest, present the Consent Gate, open the editor. The user sets verbs in the editor, not in one bundled AskUserQuestion.

2. **Multi-select as verb selector** — Do not use `multiSelect: true` to mean "fix some, file others." Multi-select is for "which items match this single decision," not "which verb applies to which item." Verbs belong to the manifest's Verb column.

   **Looks like this:**
   ```
   AskUserQuestion:
     question: "Which findings should be filed as issues?"
     multiSelect: true
     options:
       - label: "F1: Missing timeout"
       - label: "F3: No retry logic"
   ```
   **Instead:** The user sets `file` in the Verb column of each finding's manifest section. No AskUserQuestion needed for this decision.

3. **Double-gate after 'Yes'** — Do not re-prompt "Which findings?" after the commit gate. The commit gate's contract is "execute the manifest as written."

   **Looks like this:**
   ```
   # User clicks "Yes" at commit gate
   AskUserQuestion:
     question: "Which issues should I address first?"
     options:
       - label: "CRITICAL findings first"
       - label: "Quick wins first"
   ```
   **Instead:** After "Yes" at the commit gate, iterate the manifest in order. No additional triage gates.

4. **Meta-gates with relabeled Proceed Gate** — Do not rename the consent/commit gates and re-implement their logic under new labels.

   **Looks like this:**
   ```
   AskUserQuestion:
     question: "How would you like to handle these findings?"
     options:
       - label: "Full review — go through each finding"
       - label: "Auto-accept — apply all recommendations"
       - label: "Skip revisions — continue without changes"
   ```
   **Instead:** Use the Consent Gate (before editor) and Commit Gate (after editor) exactly as defined. No additional meta-gates.

5. **Option labels showing actions instead of findings** — In execution-phase `ask` prompts, labels describe the finding's alternative fixes, not generic verbs.

   **Looks like this:**
   ```
   AskUserQuestion:
     question: "How should I handle F3?"
     options:
       - label: "Fix it"
       - label: "File it"
       - label: "Skip it"
   ```
   **Instead:** Labels are the finding's actual option text: "Add exponential backoff (Option A)", "Use circuit breaker pattern (Option B)", "File as issue", "Skip".

6. **Auto-apply mixed with judgment calls in one prompt** — Auto-apply findings MUST execute silently during manifest iteration. They do not appear as options in `ask` prompts.

   **Looks like this:**
   ```
   AskUserQuestion:
     question: "Ready to fix these findings?"
     options:
       - label: "Fix F1 (auto) and decide on F2, F3"
       - label: "Review each one manually"
   ```
   **Instead:** `fix` verbs execute silently. `ask` verbs emit their own individual AskUserQuestion. They do not share a prompt.

7. **Permissive defaults that collapse to 'accept all'** — Default verbs must reflect the finding's actual classification. User-directed findings without a clear recommendation default to `ask`, not `fix`.

   **Looks like this:**
   ```
   # Manifest generated with all verbs defaulted to "fix" regardless of finding type
   **Verb:** fix  ← (applied to a finding with no recommendation field and two valid options)
   ```
   **Instead:** Follow the Default Verb Selection table. `User-directed` + no recommendation → `ask`. `Auto-apply` only → `fix`.

8. **Bail-out options violating 'all findings must be resolved'** — Do not offer `Skip revisions` / `Enough — approve as-is` options at any gate. Explicit deferral is valid, but it must be recorded per finding via `defer` or `skip` verbs in the manifest.

   **Looks like this:**
   ```
   AskUserQuestion:
     question: "What would you like to do with these findings?"
     options:
       - label: "Fix issues now"
       - label: "Skip revisions"
       - label: "Enough challenges — approve as-is"
   ```
   **Instead:** Every finding must be resolved. Use `defer` or `skip` verbs in the manifest for findings the user wants to punt. Do not offer session-level bail-outs.

## Skill-Specific Overrides

Some skills have post-finding interactions beyond fix/file (e.g., visual-qa offers "re-run with different viewport" and "read agent report"). These skills may present their own post-finding gate in place of — not in addition to — the Consent Gate (Proceed Gate). The skill's gate should still include fix and file-as-issue paths. Skills using the legacy Proceed Gate pattern should migrate to the Resolution Manifest flow on next revision.
