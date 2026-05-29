---
task_id: "T04"
title: "Write ONBOARDING and REFERENCE docs, trim README"
status: "done"
depends_on: ["T01"]
implements: ["FR#11", "FR#12", "AC#6", "AC#7", "AC#8", "AC#9"]
---

## Summary

Create `ONBOARDING.md` (the primary deliverable — a journey-oriented adoption guide structured around user personas), move the README's reference tables into a new `REFERENCE.md`, and trim `README.md` to a minimal first-impressions document. Update `CLAUDE.md`'s "Making Changes" instructions to point at the new docs, and add a `CHANGELOG.md` entry. Depends on T01 so the bundle structure described in the docs matches what the installer actually ships.

## Prompt

Implement design `## Architecture` → "Onboarding doc structure" and "README simplification", plus `## Documentation Updates`.

**1. `ONBOARDING.md`** (repo root) — follow the six-section structure in the design's "Onboarding doc structure" exactly:
   1. **What This Is** (2 paragraphs) — plain-language description + who it's for (assumes basic Claude Code familiarity).
   2. **Install** (short) — `git clone` + `uv run install.py`; one sentence on `--reconfigure`/`--uninstall`; note that the base always installs and the wizard asks about optional add-ons.
   3. **Key Concepts** — Skills, Commands, Agents, Rules, Hooks, Bundles (the descriptions in the design).
   4. **Choose Your Path** — Path A (Pick and Choose, organized by problem → which bundle, with the base-is-enough cases), Path B (The Full Pipeline: grill/define → plan → orchestrate → ship, end-to-end walkthrough with a concrete small-feature example showing what each step produces), Path C (Everything).
   5. **Customizing** (short) — own rules, `/mine.write-skill`, settings + `claude-merge-settings`, removing things.
   6. **Reference** — one line linking to `REFERENCE.md`.
   Write the prose to the repo's `writing-quality.md` standard: no AI-vocabulary tells, no em dashes, have a voice. Bundle counts and skill names must match T01's `BUNDLES` (e.g. Frontend = 19 `i-*` skills).

**2. `REFERENCE.md`** (repo root) — move the full component tables (skills, agents, commands, hooks, bin scripts) currently in `README.md` here (AC#8). This is the lookup document. Per the repo's "no counts in documentation" convention, do not introduce hardcoded totals that will drift; tables of named items are fine.

**3. Trim `README.md`** (FR#12, AC#9) — keep only: 3-sentence project description, install section, link to `ONBOARDING.md`, requirements, local dev section, license. Reference tables are removed (now in `REFERENCE.md`). Target under 50 lines.

**4. `CLAUDE.md`** — update the "Making Changes" section: change the "Always update `README.md`" instruction so the maintenance targets for skill/agent/command changes are `ONBOARDING.md` and `REFERENCE.md` (whichever the change affects), not `README.md`.

**5. `CHANGELOG.md`** — add one concise entry for the installer redesign + onboarding docs (1-2 bullets per the repo's changelog-conciseness convention; do not itemize every file).

## Focus

- The current `README.md` is 267 lines and is the source of the reference tables to relocate — read it fully before splitting so no table is lost in the move to `REFERENCE.md`.
- AC#6 and AC#7 are reader-comprehension outcomes: a reader of Path A can name which bundle to install for a need (e.g. "I want code review" → base is enough); a reader of Path B can describe define → plan → orchestrate → ship and which skill runs each step. Write Paths A and B so those outcomes are achievable — concrete invocations, explicit "included in base" labels, a worked pipeline example.
- The bundle names/contents and the "all `mine.*` in base" framing must match T01. If T01's `BUNDLES` differs from the design in any detail, the docs follow the code, not the design draft.
- Docs-only task — no test infrastructure applies. Verification is by reading the artifacts against the criteria below (the design's Test Strategy has no doc tests).
- This task depends only on T01 (the bundle structure). It does not need T02/T03, so it can run in parallel with them once T01 lands.

## Verify
- [ ] FR#11: `ONBOARDING.md` exists at repo root with all six sections (What This Is, Install, Key Concepts, Choose Your Path with Paths A/B/C, Customizing, Reference); the persona-driven reference tables no longer live in `README.md`.
- [ ] FR#12: `README.md` contains only project description, install, link to `ONBOARDING.md`, requirements, local dev, and license.
- [ ] AC#6: after reading Path A, a reader can name which bundle to install for a specific need (e.g. "I want code review" → base is enough) — Path A maps needs to bundles with explicit "included in base" labels.
- [ ] AC#7: after reading Path B, a reader can describe the define → plan → orchestrate → ship sequence and which skill to invoke for each step — Path B is an end-to-end walkthrough with a concrete example.
- [ ] AC#8: `REFERENCE.md` contains the full component tables (skills, agents, commands, hooks, bin scripts) previously in `README.md`.
- [ ] AC#9: `README.md` is under 50 lines.
