# Plan: mine.build — Single Entry Point Skill

**Date:** 2026-03-09
**Design doc:** design/plans/2026-03-09-mine-build/design.md
**Status:** implemented

## Overview

Create `skills/mine.build/SKILL.md` — the caliper workflow entry point that routes between simple direct implementation and the full design→plan→review→orchestrate→ship chain, with optional sophia CR tracking. Then update README.md and capabilities.md to register the new skill.

## Task sequence

1. Write `skills/mine.build/SKILL.md`
2. Update `README.md` — skill count and table row
3. Update `rules/common/capabilities.md` — routing entry and Workflow section

---

## Task 1: Write `skills/mine.build/SKILL.md`

**files:** `skills/mine.build/SKILL.md` (new)

**steps:**
1. Create `skills/mine.build/` directory.
2. Write `SKILL.md` with frontmatter (`name: mine.build`, `description`, `user-invokable: true`) and three phases. Use `skills/mine.orchestrate/SKILL.md` as a structural template for phase layout and formatting conventions.
   - **Phase 1 — Understand the request:** accept `$ARGUMENTS` as the change description; if empty, present an AskUserQuestion asking what to build. Paraphrase the request back briefly.
   - **Phase 2 — Check sophia + route:** make two separate Bash calls — `command -v sophia && echo "installed" || echo "missing"` and `Glob: SOPHIA.yaml`. Record `sophia_installed` and `sophia_yaml_exists`. Provide a brief complexity signal (simple = 1–3 files, clear approach; complex = multiple modules, design uncertainty, cross-system). Present three routing options via AskUserQuestion: "Simple — implement directly", "Complex — full caliper workflow", "Complex + Sophia — full workflow with CR tracking". Always show all three options; add "(sophia setup required)" to the Sophia option description if either check was negative.
   - **Phase 3 — Execute.** Three sub-paths:
     - **Path A (Simple):** explore with Glob/Grep/Read → implement the change → launch `code-reviewer` subagent → present findings → AskUserQuestion gate (Ship via `/mine.ship` / Fix issues and re-review / Stop here).
     - **Path B (Complex):** tell user "Starting the full caliper workflow — each step has its own sign-off gate." Then chain: follow `/mine.design` phases for this request → when design is approved, follow `/mine.draft-plan` phases using the design doc path → when plan is drafted, follow `/mine.plan-review` phases → on APPROVE, follow `/mine.orchestrate` phases → mine.orchestrate's post-execution handoff offers `/mine.implementation-review` inline → after implementation review APPROVE, offer mine.ship via AskUserQuestion (Yes / No — I'll ship manually). If mine.plan-review returns REQUEST_REVISIONS, return to mine.draft-plan. If ABANDON, stop.
     - **Path C (Complex + Sophia):** First, resolve sophia readiness: if sophia not installed, offer AskUserQuestion (Yes — install sophia / Switch to Complex / Stop). If "Yes": run `sophia-install`; on success continue, on failure offer Switch or Stop. If sophia installed but SOPHIA.yaml missing, offer AskUserQuestion (Yes — run `/mine.sophia` to init / Switch to Complex / Stop). If "Yes": follow `/mine.sophia` init flow, then continue. Then run Path B with these sophia additions: (a) after plan is approved by mine.plan-review, create a CR with `sophia cr add --description "<request>"`, then offer AskUserQuestion (Yes — set the contract via `/mine.sophia contract` / Skip — add later); (b) mine.orchestrate already detects the active CR and handles per-task updates; (c) after implementation review APPROVE, run `sophia cr status --json`, surface CR state, offer AskUserQuestion (Yes — sophia cr merge / No — I'll handle it manually), then proceed to mine.ship gate as in Path B.

**verification:** `cat skills/mine.build/SKILL.md` — file exists; frontmatter is valid with `name: mine.build`, `description`, `user-invokable: true`; all three paths are present.

**done-when:** `skills/mine.build/SKILL.md` exists and contains Phases 1, 2, and 3 with all three routing paths (A, B, C) fully described.

**avoid:**
- `$(...)` command substitution in Bash code blocks — why: the Bash tool wraps commands in `eval '...' < /dev/null`, which mangles `$()` causing silent failures. Use separate sequential Bash calls instead.
- Duplicating the phase logic of mine.design, mine.draft-plan, mine.orchestrate, etc. inline — why: those skills are already complete; mine.build chains them by instructing Claude to follow each skill's phases in sequence, not by re-specifying them.

---

## Task 2: Update `README.md` — skill count and table row

**files:** `README.md`

**steps:**
1. Change `### Skills (28)` to `### Skills (29)`.
2. Insert a new row for `mine.build` in alphabetical order in the skills table — after `mine.brainstorm` and before `mine.challenge`:
   ```
   | `mine.build` | Single entry point — routes between direct implementation and the full caliper workflow (design → plan → orchestrate → ship), with optional sophia CR tracking |
   ```

**verification:** `grep -n "mine.build" README.md` — returns the new table row; `grep "Skills (" README.md` — shows `(29)`.

**done-when:** README shows `Skills (29)` and contains a `mine.build` table row between `mine.brainstorm` and `mine.challenge`.

**avoid:**
- Editing the skills count anywhere other than the `### Skills (N)` heading — why: only that heading tracks the count.

---

## Task 3: Update `rules/common/capabilities.md` — routing entry and Workflow section

**files:** `rules/common/capabilities.md`

**steps:**
1. Add a new row to the intent routing table immediately before the `mine.design` row (grouping it with the caliper workflow skills):
   ```
   | "build this", "implement this", "make this change", "start a feature", "what workflow should I use" | `/mine.build` |
   ```
2. Add a `### /mine.build` description in the **Workflow** section immediately before the `### /mine.design` entry, following the same format as other workflow entries:
   ```markdown
   ### /mine.build

   Single entry point for implementing changes. Assesses complexity, checks for sophia, and routes to: direct implementation + code review + ship (simple), or the full caliper chain design → draft-plan → plan-review → orchestrate → implementation-review → ship (complex). Optionally integrates sophia CR tracking throughout.
   ```

**verification:** `grep -n "mine.build" rules/common/capabilities.md` — returns both the intent routing row and the section header.

**done-when:** `rules/common/capabilities.md` has a routing table entry for mine.build and a description paragraph in the Workflow section.

**avoid:**
- Adding mine.build to the Analysis & Refactoring section — why: mine.build is a workflow orchestrator, not an analysis tool. It belongs in the Workflow section.
