---
task_id: "T03"
title: "Add challenge flags, update protocol, and create shared recipe"
status: "planned"
depends_on: []
implements: ["FR#13", "FR#14", "FR#15", "FR#16", "FR#23", "FR#11", "AC#12", "AC#13", "AC#14", "AC#16"]
---

## Summary
Update `mine-challenge` with the `--critics=N` and `--re-challenge` flags, delete the dead file-based re-challenge detection code, update the findings protocol to add the `filed` disposition and bump the format version to 4 (splitting `status` into `visibility` and `disposition`, renaming `Resolution` to `Classification`), create the shared `challenge-gate.md` recipe file, and update the format-version literals in `mine-audit`.

## Target Files

- modify: `skills/mine-challenge/SKILL.md`
- modify: `skills/mine-challenge/findings-protocol.md`
- create: `skills/mine-challenge/challenge-gate.md`
- modify: `skills/mine-audit/SKILL.md`
- read: `skills/mine-comb/comb-gate.md`

## Prompt

### 1. Challenge SKILL.md — flags and detection

In `skills/mine-challenge/SKILL.md`:

**Arguments section** (after line 26): Add two new flags to the optional arguments list:
- `--critics=N` — pin the critic count to exactly N. Overrides triage's default 1–3 range and the re-challenge cap of 2. When `--focus` forces a specialist, that specialist occupies one of the N slots rather than adding to them.
- `--re-challenge` — mark this run as a re-challenge. Replaces the file-based detection.

**Re-challenge detection** (lines 70-73): Delete step 1 entirely — the `challenge-results*.md` / `challenge-findings*.md` directory lookup. It looks for files in the target's directory, but challenge writes to a fresh `mktemp -d`, so the file is never where the check looks. It has never fired. Keep step 2 (the conversation-context fallback) and add: "If `--re-challenge` flag was provided → re-challenge."

**Triage rules** (around line 108-112): Add a rule: "If `--critics=N` is provided: select exactly N critics. `--critics=N` overrides the re-challenge cap of 2."

**Known Callers section** (lines 226-245): Replace the mine-define standalone caller entry (which references the "Challenge first" option being deleted) with three orchestration call sites:
```
Orchestration callers (mandatory, via challenge-gate.md):
- `skills/mine-define/SKILL.md` (Phase 5.5 — design-time challenge)
- `skills/mine-sketch/SKILL.md` (Phase 4.5 — sketch-time challenge with --critics=2)
- `skills/mine-orchestrate/post-execution-pipeline.md` (Step 3.5 — ship-time challenge)
```

**Format-version literal** (line 200): Change `Format-version: 3` to `Format-version: 4`.

### 2. Findings protocol (findings-protocol.md)

In `skills/mine-challenge/findings-protocol.md`:

**Format version** (line 1): Change `<!-- findings-format-version: 3 -->` to `<!-- findings-format-version: 4 -->`.

**Header block** (line 20): Change `**Format-version:** 3` to `**Format-version:** 4`.

**Per-finding fields**: Split the single `status` field into two separate fields:
- Replace `**status:** pending | applied | overflow | skipped` with `**visibility:** presented | overflow | likely-invalid` (synthesis-time, never changes)
- Add `**disposition:** pending | applied | skipped | filed` (resolution-time, tracks outcome) — placed after visibility

Remove the `**overflow:** true | false` field — its information is now encoded in the `visibility` value (`overflow` maps to `visibility: overflow`).

**Resolution field**: Rename `**Resolution:** Auto-apply | User-directed` to `**Classification:** Auto-apply | User-directed` throughout the file, including in the "Resolution Classification" section heading (rename to "Finding Classification") and all references.

**Status and Overflow Fields section** (lines 86-101): Rewrite as "Visibility and Disposition Fields" to document the new split:
- `visibility`: set once at synthesis, never changes. `presented` (in scope for resolution), `overflow` (exceeded cap), `likely-invalid` (flagged by synthesis).
- `disposition`: tracks resolution outcome. `pending` → `applied` | `skipped` | `filed`. NULL for overflow and likely-invalid findings that never enter the resolution flow.

**Add `filed` disposition**: In the status values table (now disposition values), add `filed` with semantics: "User chose to create a tracked issue rather than fix in-place. The issue is the durable record; the finding needs no further in-session attention." This is distinct from `skipped` (user declined to act) — `filed` means the user acted by creating an issue.

**Inline Resolution Flow** (lines 166-229): Update all `status` references to use the new field names:
- Auto-apply: set `disposition: applied` (visibility is already `presented`)
- User-directed: set `disposition: applied` for options, `disposition: skipped` for Skip, `disposition: filed` + create issue for File as issue
- The "Skip — defer to later" option label stays the same; its disposition changes from `status: skipped` to `disposition: skipped`

### 3. Shared recipe (challenge-gate.md)

Create `skills/mine-challenge/challenge-gate.md` modelled on `skills/mine-comb/comb-gate.md`. This file owns the invariant that challenge is not declinable, plus the mechanical sequence.

Structure:

```markdown
# Challenge Gate

The shared gate applied after the challenge runs at a mandatory call site. Callers (`mine-define`, `mine-sketch`, `mine-orchestrate`) read this file and instantiate the parameters below. One source of truth for the gate's central invariant:

> **Challenge runs automatically. There is no option to decline it.**

## Parameters the caller supplies

- **`<header>`** — the `AskUserQuestion` header chip, e.g. `Challenge`. Keep it ≤12 chars.
- **`<gate_type>`** — the cfl gate type: `define-challenge`, `sketch-challenge`, or `ship-challenge`.
- **`<target>`** — what to pass to `/mine-challenge`: a design doc path or a changed-files list file.
- **`<critic_flag>`** — `--critics=N` if pinned, or empty string if using triage default.
- **`<re_challenge_flag>`** — `--re-challenge` if this is a re-challenge, or empty string.
- **`<post_resolution>`** — caller-specific handling after step 6 completes (e.g., sketch's upgrade-to-caliper check, ship-time's unresolved-finding summary).

## The sequence

1. Record the dispatch (skip if cfl tracking is inactive for this run):
   ```bash
   cfl dispatch <gate_type> --agent-type standard-worker --spec <spec_number>
   ```
   Capture `dispatch_id`.

2. Invoke `/mine-challenge <target> <critic_flag> <re_challenge_flag>` and let it resolve findings inline.

3. Record dispatch end (skip if cfl tracking inactive):
   ```bash
   cfl dispatch end <dispatch_id>
   ```

4. Determine verdict from the findings file challenge reported back:
   - No findings → PASS
   - Findings but none CRITICAL or HIGH → WARN
   - Any CRITICAL or HIGH → FAIL

   Record the gate (skip if cfl tracking inactive):
   ```bash
   cfl gate <gate_type> --verdict <v> --data '{"blocking": <N>, "minor": <M>, "critical": <C>, "high": <H>, "medium": <Me>, "tension": <T>, "applied": <A>, "skipped": <S>, "filed": <F>}' --spec <spec_number>
   ```
   `blocking` = CRITICAL + HIGH count. `minor` = MEDIUM + TENSION count. The per-severity and per-disposition counts ride alongside as extra keys. Capture `gate_id` from the JSON output.

5. Read the findings file challenge reported. Emit one batch call that writes all findings (skip if cfl tracking inactive):
   ```bash
   cfl finding record-batch --gate-id <gate_id> --file <findings_json_path>
   ```
   The findings JSON file is constructed from the challenge findings markdown — parse each `## Finding N:` and each `### LI-N:` entry into a JSON object with the column fields. `visibility` is `presented` for main findings, `likely-invalid` for LI entries, `overflow` for overflow entries.

6. For each finding resolved during step 2 (disposition is `applied`, `skipped`, or `filed`), emit (skip if cfl tracking inactive):
   ```bash
   cfl finding resolve --gate-id <gate_id> --finding-num <N> --disposition <d>
   ```

7. Run `<post_resolution>` — the caller's site-specific handling.
```

### 4. Mine-audit format version

In `skills/mine-audit/SKILL.md`, line 137: Change `Format-version: 3` to `Format-version: 4`.

## Focus

- The `challenge-gate.md` structure follows `comb-gate.md` exactly in its Parameters section format — parameter names in backtick-bold, descriptions, and constraints.
- The `--data` payload key names (`blocking`, `minor`) are critical — `bin/agent-stats:170` reads `gate_data.get("minor") or gate_data.get("findings") or 1`, so a payload missing `minor` would silently report `minor=1` from the fallback.
- The format-version bump from 3 to 4 is a documentation change. Nothing validates version agreement at runtime.
- The `filed` disposition is specifically for the "File as issue" inline resolution option. It creates a tracked issue as the durable record, unlike `skipped` which simply declines.

## Verify
- [ ] FR#13: `skills/mine-challenge/SKILL.md` documents `--critics=N` in its Arguments section
- [ ] FR#14: The triage rules state that `--critics=N` overrides the re-challenge cap
- [ ] FR#15: `skills/mine-challenge/SKILL.md` documents `--re-challenge` in its Arguments section
- [ ] FR#16: `grep -n 'challenge-results\*' skills/mine-challenge/SKILL.md` returns nothing
- [ ] FR#23: `skills/mine-challenge/findings-protocol.md` lists `filed` in its disposition table with distinct semantics from `skipped`
- [ ] FR#11: `skills/mine-challenge/challenge-gate.md` names `blocking` and `minor` as required `--data` keys
- [ ] AC#12: The Arguments section documents both `--critics=N` and `--re-challenge`, and triage rules state the override
- [ ] AC#13: `grep -n 'challenge-results\*' skills/mine-challenge/SKILL.md` returns nothing
- [ ] AC#14: `findings-protocol.md` lists `filed` with distinct semantics from `skipped`
- [ ] AC#16: `challenge-gate.md` names `blocking` and `minor` as required `--data` keys
