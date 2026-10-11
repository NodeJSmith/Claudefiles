# Challenge Gate

The shared gate applied after the challenge runs at a mandatory call site. Its caller, `mine-sketch` (sketch time and build time), reads this file and instantiates the parameters below. One source of truth for the gate's central invariant:

> **Challenge runs automatically. There is no option to decline it.**

## Parameters the caller supplies

- **`<header>`** — the `AskUserQuestion` header chip, e.g. `Challenge`. Keep it ≤12 chars.
- **`<gate_type>`** — the gate's name in the review log: `sketch-challenge` or `ship-challenge`.
- **`<target>`** — what to pass to `/mine-challenge`: a design doc path or a changed-files list file.
- **`<critic_flag>`** — `--critics=N` if pinned, or empty string if using triage default.
- **`<focus_flag>`** — `--focus="<text>"` to steer the critics, or empty string. Callers that don't name it pass empty.
- **`<re_challenge_flag>`** — `--re-challenge` if this is a re-challenge, or empty string.
- **`<post_resolution>`** — caller-specific handling after the findings are resolved (e.g., sketch's ratification of decisions an Auto-apply edit changed, ship-time's known-issues recording).
- **`<review_log>`** — the JSONL file the gate appends its record to. `mine-sketch` passes `<feature_dir>/review-log.jsonl`.
- **`<ledger>`** — the design file whose hash the record carries as `ledger_hash`, so the caller can later tell whether the ledger changed since this gate. `mine-sketch` passes `<feature_dir>/design.md`.

## The sequence

1. Record `git rev-parse --short HEAD` as `<challenged_commit>`: the code the critics are about to see. Capture it now, because `<post_resolution>` may commit fixes before the record is written.

   Invoke `/mine-challenge <critic_flag> <focus_flag> <re_challenge_flag> <target>` and let it resolve findings inline. Flags must come before the target — `SKILL.md:19` parses flags from the beginning of $ARGUMENTS only, stopping at the first non-flag token.

2. Run `<post_resolution>` — the caller's site-specific handling.

3. Append one record to `<review_log>`. The log is the durable history of what challenge found and what the user chose, kept next to the design it critiqued so it lands in git with the change; it exists for later analysis of the skills themselves (which critics earn their place, how often the recommendation is taken). Write it last, after `<post_resolution>`: a record's presence means the whole gate finished, which is what the caller's resume check relies on.

   The record is one JSON object:

   ```json
   {"gate": "<gate_type>", "date": "YYYY-MM-DD", "commit": "<challenged_commit>", "ledger_hash": "<git hash-object <ledger>>", "findings": [ ... ]}
   ```

   `ledger_hash` is `git hash-object <ledger>` run now, after `<post_resolution>`'s edits. `commit` is `<challenged_commit>` from step 1, locating the code the challenge saw; the `<target>` path itself isn't recorded, since a changed-files list lives in a temp directory. A gate with no findings still writes a record, with an empty `findings` array. Other records in the same log (the sketch comb's counts) have a different shape, so a query filters on `gate` first.

   Build each `findings` entry from the findings file `/mine-challenge` reported back — each `## Finding N:` and each `### LI-N:` entry — using exactly these keys. A wrong key name silently loses the field for every later query, so don't improvise:

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
   | `**Recommendation:**` or `*(recommended)*` marker on Options | `recommended` |
   | the option the user picked | `chosen` |
   | the user's note on that pick, if any | `choice_reason` |

   - **`raised_by`** is a list of persona slugs, not the display names the markdown uses, so the same critic always counts as the same critic. A slug is the persona's file name without `.md`, from `skills/mine-challenge/personas/generic/` or `personas/specialist/` (the markdown's "Skeptical Senior Engineer" is `senior-engineer`; "Contract & Caller Critic" is `contract-caller`). A synthesis-raised finding is `["synthesis"]`.
   - **`disposition`** is the terminal value challenge's inline resolution wrote into the findings file during step 1: `applied`, `skipped`, or `filed`.
   - **`recommended`** is the option label marked `*(recommended)*` on a User-directed finding's Options list (`**A** *(recommended)*: add try/except` → `"A: add try/except"`). Omit it for TENSION findings (two competing sides, no recommendation), for Auto-apply findings (no user-facing recommendation), and for likely-invalid entries.
   - **`chosen`** is the label the user selected, as the findings walkthrough worded it (for example `"A: add try/except"` or `"Side B: keep current approach"`), or their "Other" free text. For an Auto-apply finding, use the `better-approach` text, so "what happened" reads the same across finding types. A finding superseded by a convergence finding (see `findings-protocol.md`, Convergence Findings) gets `disposition: "skipped"` and `chosen: "Superseded by Finding <M>"`.
   - **`choice_reason`** is the user's notes from `AskUserQuestion`, or their "Other" free text; omit it when they picked a listed option without comment.

   `## Likely Invalid` entries (`### LI-N:`) use the same keys, with `visibility: "likely-invalid"` and no `disposition`, `recommended`, or `chosen`. Their `N` is its own sequence and can repeat a main finding's number. `**Original-severity:**` maps to `severity`. `Claimed`/`Actually`/`Why-invalid`, `Evidence`, `Design-challenge`, and a convergence finding's `**Converges:**` field are not recorded.

   Write the object to a temp file (in a `get-skill-tmpdir` directory) and append it with `jq -c . <file> >> <review_log>`; `jq` rejects malformed JSON instead of appending it.
