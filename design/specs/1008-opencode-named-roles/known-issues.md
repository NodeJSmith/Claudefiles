# Known Issues

Durable issues discovered during orchestration that were intentionally not fixed in this run.

## KI-001: standard-worker's WebSearch/WebFetch grant undocumented in Dependencies and Assumptions

Status: open
Run: 93
Source: T04
Reason not fixed now: out-of-scope
Observed in: T04 (pass-2 re-review)
Affected files:
- design/specs/1008-opencode-named-roles/design.md
- agents/standard-worker.md

Issue:
`agents/standard-worker.md:6` was widened during T04's fixer passes to add `WebSearch`
and `WebFetch` to its `tools:` allowlist, because three migrated sites now dispatch it
expecting those tools (`skills/mine-prior-art/SKILL.md:70` — the file's PRIMARY phase,
`skills/mine-brainstorm/SKILL.md:70`, `skills/mine-challenge/SKILL.md:31`). This capability
grant is confirmed correct and working (code-review.md pass 2 verifies the frontmatter and
the empirical justification), but it is not recorded anywhere in `design.md`'s Dependencies
and Assumptions section — unlike every other per-agent tool deviation the doc tracks (the
"Fleet-wide tool widening" bullet covering `planner`/`secrets-auditor`, and the
`mine-prior-art:61` tier-collision bullet for FR#24). A reader relying on Dependencies and
Assumptions as the durable record of accepted deviations would not learn this one happened.

Why deferred:
This is a documentation-completeness gap, not a functional defect — the underlying code
change is correct, tested, and already verified by the pass-2 code review. FR#24 and this
task's own Target Files note for `design.md` scope its "record in Dependencies and
Assumptions" duty specifically to *model-tier* changes from specialist promotion; this is a
*tool* addition to a worker whose tier never changed, so it falls outside FR#24's literal
requirement even though the same "don't discover it after the fact" reasoning applies. This
terminal pass is classify-only (no code changes permitted), so a one-line design.md addition
cannot be made here regardless of how small it is.

Recommended follow-up:
Add a bullet to `design.md`'s Dependencies and Assumptions section, alongside the existing
"Fleet-wide tool widening" bullet, recording that `agents/standard-worker.md` gained
`WebSearch`/`WebFetch` during migration because `mine-prior-art:70`, `mine-brainstorm:70`,
and `mine-challenge:31` require them, following the same format used for the
`secrets-auditor`/`planner` entries.

Acceptance criteria:
- `design.md`'s Dependencies and Assumptions section names `agents/standard-worker.md`'s
  `WebSearch`/`WebFetch` grant and the three consuming sites.
