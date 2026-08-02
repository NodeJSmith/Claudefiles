# Known Issues

Durable issues discovered during orchestration that were intentionally not fixed in this run.

## KI-001: ONBOARDING.md not updated for 6 new skills

Status: open
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
