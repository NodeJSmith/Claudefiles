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
   cfl dispatch <gate_type> --agent-type standard-worker
   ```
   Capture `dispatch_id`. Note: `--spec` is not included here — callers thread it per their own convention (mine-define and mine-plan pass `--spec <spec_number>`; mine-orchestrate uses CWD-based resolution, matching the rest of `post-execution-pipeline.md`).

2. Invoke `/mine-challenge <critic_flag> <re_challenge_flag> <target>` and let it resolve findings inline. Flags must come before the target — `SKILL.md:19` parses flags from the beginning of $ARGUMENTS only, stopping at the first non-flag token.

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
   cfl gate <gate_type> --verdict <v> --data '{"blocking": <N>, "minor": <M>, "critical": <C>, "high": <H>, "medium": <Me>, "tension": <T>, "applied": <A>, "skipped": <S>, "filed": <F>}'
   ```
   `blocking` = CRITICAL + HIGH count. `minor` = MEDIUM + TENSION count. The per-severity and per-disposition counts ride alongside as extra keys. Capture `gate_id` from the JSON output.

5. Read the findings file challenge reported. Emit one batch call that writes all findings (skip if cfl tracking inactive):
   The findings JSON file is constructed from the challenge findings markdown — parse each `## Finding N:` and each `### LI-N:` entry into a JSON object using this canonical field-name mapping (markdown label → JSON key). Do not improvise other key names — a wrong key writes a silently-empty column, since only `finding_num`/`title`/`severity`/`visibility` are enforced as required.

   | Markdown label (main `## Finding N:` entries) | JSON key |
   |---|---|
   | `N` (from the heading) | `finding_num` |
   | `<title>` (from the heading) | `title` |
   | `**Severity:**` | `severity` |
   | `**Type:**` | `finding_type` |
   | `**Design-level:**` | `design_level` |
   | `**Classification:**` | `classification` |
   | `**Raised-by:**` | `raised_by` |
   | `**visibility:**` | `visibility` |
   | `**disposition:**` | `disposition` |
   | `**Why-it-matters:**` | `why_it_matters` |

   `## Likely Invalid` entries (`### LI-N:`) use the same JSON keys with two differences: the `N` in `LI-N` maps to `finding_num` (its own sequence, independent of the main `## Finding N:` numbering — the two sequences can collide on the same integer, which is why `visibility` is part of the table's uniqueness constraint), and `**Original-severity:**` maps to `severity` (there is no separate `Original-severity` column). `Claimed`/`Actually`/`Why-invalid` have no corresponding columns and are not written, the same precedent as the protocol's `Evidence`/`Design-challenge` fields being deliberately excluded from the schema.

   `visibility` is `presented` for main findings, `likely-invalid` for LI entries, `overflow` for overflow entries. Set every parsed finding object's `target` to the caller-supplied `<target>` value (the same value passed to `/mine-challenge` in step 2) — all findings from one gate examined the same artifact. Construct the JSON array (one object per parsed entry) and write it to a temp path via `get-skill-tmpdir` + Write tool before invoking the command below.
   ```bash
   cfl finding record-batch --gate-id <gate_id> --file <findings_json_path> --source challenge
   ```

6. For each finding resolved during step 2 (disposition is `applied`, `skipped`, or `filed`), emit (skip if cfl tracking inactive):
   ```bash
   cfl finding resolve --gate-id <gate_id> --finding-num <N> --disposition <d>
   ```

7. Run `<post_resolution>` — the caller's site-specific handling.
