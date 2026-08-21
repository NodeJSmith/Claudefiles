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
   The findings JSON file is constructed from the challenge findings markdown — parse each `## Finding N:` and each `### LI-N:` entry into a JSON object using this canonical field-name mapping (markdown label → JSON key). Do not improvise other key names — a wrong key silently produces a missing field rather than writing to the intended column. `record_finding_batch` enforces `finding_num`/`title`/`severity`/`visibility`/`raised_by` as required on every entry, plus `finding_type`/`design_level`/`classification`/`why_it_matters` on any entry whose `visibility` is not `likely-invalid`; a missing required field exits 2 with `invalid_findings_file` rather than writing a NULL column.

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
   | `**disposition:**` | `disposition` — **value overridden for `presented` entries, see below; do not copy literally** |
   | `**Why-it-matters:**` | `why_it_matters` |

   `## Likely Invalid` entries (`### LI-N:`) use the same JSON keys with two differences: the `N` in `LI-N` maps to `finding_num` (its own sequence, independent of the main `## Finding N:` numbering — the two sequences can collide on the same integer, which is why `visibility` is part of the table's uniqueness constraint), and `**Original-severity:**` maps to `severity` (there is no separate `Original-severity` column). `Claimed`/`Actually`/`Why-invalid` have no corresponding columns and are not written, the same precedent as the protocol's `Evidence`/`Design-challenge` fields being deliberately excluded from the schema.

   Take `visibility` from each entry's own `**visibility:**` markdown field per the mapping table above — synthesis writes it once and it never changes (`SKILL.md` step 3 for in-cap and overflow findings, step 8 for entries moved to Likely Invalid). Fall back to a section-based default only when the field is genuinely absent: `presented` for a main finding, `likely-invalid` for an LI entry, `overflow` for an overflow entry.

   `disposition` is **not** copied from the markdown for a `presented` entry. By the time this step runs, step 2's inline resolution has already rewritten the markdown's `**disposition:**` field to its terminal value (`applied`/`skipped`/`filed`) — but step 6 below is what applies that terminal value to the database row and stamps `resolved_at`; if this step wrote the terminal value too, step 6's `disposition = 'pending'` guard would match zero rows and `resolved_at` would never get set. So write `disposition: pending` for every `presented` entry unconditionally, regardless of what the markdown currently shows. For `overflow` and `likely-invalid` entries, `disposition` stays absent (NULL), since they never enter the resolution flow. Set every parsed finding object's `target` to the caller-supplied `<target>` value (the same value passed to `/mine-challenge` in step 2) — all findings from one gate examined the same artifact. Construct the JSON array (one object per parsed entry) and write it to a temp path via `get-skill-tmpdir` + Write tool before invoking the command below.

   ```bash
   cfl finding record-batch --gate-id <gate_id> --file <findings_json_path> --source challenge
   ```

6. For each finding resolved during step 2 (disposition is `applied`, `skipped`, or `filed`), emit (skip if cfl tracking inactive):

   ```bash
   cfl finding resolve --gate-id <gate_id> --finding-num <N> --disposition <d>
   ```

7. Run `<post_resolution>` — the caller's site-specific handling.

8. Emit the persistence-complete marker (skip if cfl tracking inactive):

   ```bash
   cfl event challenge.findings-persisted --data '{"gate_type": "<gate_type>"}'
   ```

   The `review.gated` event from step 4 fires before findings are recorded — a resume check that treats it alone as "challenge already ran" can skip re-persisting findings if the run was interrupted between steps 4 and 6. `challenge.findings-persisted` fires only after `<post_resolution>` completes, so it is the marker resume checks must use — a run interrupted anywhere before this point (including mid-`<post_resolution>`, e.g. mid-comb-rerun) re-enters the whole phase from step 1 rather than silently skipping `<post_resolution>`'s own work.
