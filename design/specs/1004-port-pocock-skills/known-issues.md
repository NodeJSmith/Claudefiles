# Known Issues

Durable issues discovered during orchestration that were intentionally not fixed in this run.

## KI-001: ONBOARDING.md not updated for 6 new skills

Status: resolved — ONBOARDING.md's "Choose Your Path" section now covers mine-wayfinder, mine-teach, mine-domain-model, and the writing pipeline (mine-fragments/mine-shape/mine-beats).
Source: impl-review
Reason not fixed now: out-of-scope
Observed in: T05 (integration-review), impl-review (Phase 3)
Affected files:
- ONBOARDING.md

Issue:
This repo's CLAUDE.md states: "Always update ONBOARDING.md when adding a capability a new adopter should know about (new bundle, significant new skill, workflow change)." This run added 6 new skills (mine-domain-model, mine-wayfinder, mine-teach, mine-fragments, mine-shape, mine-beats) — a substantial capability addition — but ONBOARDING.md was not touched and does not mention any of them.

Why deferred:
`design/specs/1004-port-pocock-skills/design.md`'s Changed Files list only named `rules/common/capabilities-core.md` and `REFERENCE.md` for wiring (T05's scope). ONBOARDING.md was never part of the approved task scope for this run, so updating it now would expand beyond what was planned and reviewed.

Recommended follow-up:
Add a short mention of the 6 new skills to ONBOARDING.md's "Choose Your Path" (or equivalent) section — likely worth a small follow-up task rather than an ad hoc edit, since it should describe when a new adopter would reach for wayfinder vs teach vs the writing pipeline vs domain-model.

Acceptance criteria:
- ONBOARDING.md references at least mine-wayfinder, mine-teach, mine-domain-model, and the writing pipeline (mine-fragments/mine-shape/mine-beats) in a way a new adopter would discover them.

## KI-002: Duplicated procedural boilerplate across the writing pipeline skills

Status: open
Source: clean-code
Reason not fixed now: out-of-scope
Observed in: T04, clean-code (llm-checker, lazy-checker)
Affected files:
- skills/mine-fragments/SKILL.md
- skills/mine-shape/SKILL.md
- skills/mine-beats/SKILL.md

Issue:
Two paragraphs of near-identical procedural instruction are copy-pasted across all three writing-pipeline skills, differing only by skill name and output filename: (1) the "no path given → run `get-skill-tmpdir <skill>`, write to `<dir>/article.md` (or `fragments.md`), tell the user, don't rely on remembering it since the session may not persist" instruction, and (2) the "raw material file is read-only to this skill" line (shared verbatim between mine-shape and mine-beats). `mine-shape` and `mine-beats` additionally duplicate their entire Grounding section verbatim (prerequisite/introduced/term model, `block` vs `beat` substituted) — that duplication is already self-flagged in both files ("duplicated (not shared) by design ... if you change the grounding model here, update the other file too"), so the maintenance-sync risk is at least documented, but the tmpdir/read-only paragraphs are not.

Why deferred:
`design/specs/1004-port-pocock-skills/design.md`'s Approach section explicitly decided: "Others: single SKILL.md, no side files needed" for mine-fragments/mine-shape/mine-beats — i.e., the writing pipeline was deliberately scoped without a shared side file. (Note: mine-domain-model and mine-teach also ended up with no side files — their format templates were delivered as inline SKILL.md sections rather than the side files design.md originally planned — so all 6 ported skills are side-file-free; that's not a distinction that argues for or against consolidating the writing pipeline's duplication.) Extracting the duplicated paragraphs into a shared reference file would reverse the writing pipeline's explicit no-side-file decision, which needs a decision from the user rather than a clean-code pass silently introducing a new side file mid-review.

Recommended follow-up:
If the duplication becomes a real maintenance burden (a rule changes and one of the three copies gets missed), revisit the "no side files" decision for this pipeline — e.g. a small `writing-pipeline-conventions.md` side file referenced by all three skills, covering the tmpdir/output-path rule, the read-only-raw-material rule, and (if desired) the currently-duplicated Grounding section.

Acceptance criteria:
- Either the duplication is consolidated into a shared reference file linked from all three skills, or a deliberate decision to keep them separate is recorded (e.g. in design.md) with rationale.
