---
task_id: "T06"
title: "Update documentation and cross-repo references"
status: "planned"
depends_on: ["T01", "T02", "T03", "T04", "T05"]
implements: []
---

## Summary
Update all documentation files that reference ccrecall, its skills, hooks, or plugin registration. This includes REFERENCE.md, ONBOARDING.md, capabilities-core.md, and CLAUDE.md in Claudefiles, plus four cross-repo files in Dotfiles that hard-code `/ccrecall:ccr-resume`. AC#6 is partially covered here (the handoff file's readability by `/cass-resume` is documented in the updated docs).

## Target Files
- modify: `REFERENCE.md`
- modify: `ONBOARDING.md`
- modify: `rules/common/capabilities-core.md`
- modify: `CLAUDE.md`
- modify: `~/Dotfiles/config/claude/rules/personal/capabilities.md`
- modify: `~/Dotfiles/CLAUDE.md`
- modify: `~/Dotfiles/config/claude/orchestrator/CLAUDE.md`
- modify: `~/Dotfiles/home/bin/orchestrator/orchestrator-tick`
- read: `design/specs/1000-ccrecall-to-cass-migration/design.md` (§ Documentation Updates — the authoritative list of changes per file)

## Prompt
Read `design/specs/1000-ccrecall-to-cass-migration/design.md` § Documentation Updates for the complete, per-file list of changes. Apply each one. Below is a summary:

### REFERENCE.md
- Remove ccrecall from the Plugins table (or remove the table if no plugins remain)
- Add cass-recall, cass-context, cass-resume to the Skills table
- Update the Hooks table to list cass-session-start.sh and cass-clear-handoff.sh
- Remove the prose paragraph below the Hooks table about ccrecall plugin hooks not being wired in settings.json
- Remove the note about conversation memory skills being plugin-provided
- Update the `orchestrate-cost` tool description from "Reuses `ccrecall` pricing via PEP 723" to reflect the inlined pricing module
- Update the package installation prose from "`ccrecall` is installed unconditionally from PyPI" to describe cass binary installation

### ONBOARDING.md
- Update the "I want conversation memory" path to reference `/cass-recall`, `/cass-context`, `/cass-resume`
- Update the Plugins glossary entry (currently "Currently: `ccrecall`...")
- Update the Bundles glossary parenthetical (currently "it's now the `ccrecall` plugin")
- Update "Path C: Everything" daily workflow pattern — remove the claim about auto-warning on unanswered questions; note this is now manual via `/cass-resume`
- Note that initial `cass index` is a manual first-run step

### rules/common/capabilities-core.md
- Add `/cass-recall`, `/cass-context`, and `/cass-resume` trigger phrases to the Intent Routing table
- Add `cass-update` to CLI Tools if warranted
- Note: this file contains no ccrecall references to remove

### CLAUDE.md
- Add `cass-*` to the Naming Conventions section alongside `mine-*`, `i-*`, and `cli-*`
- Update the "Making Changes" section's capabilities-file mapping to route `cass-*` trigger phrases to `capabilities-core.md`

### Cross-repo: ~/Dotfiles/config/claude/rules/personal/capabilities.md
- Update the Memory Recall table to reference `/cass-recall` instead of `/cm-recall-conversations`
- Update the Proactive Memory Recall section to reference `/cass-recall`

### Cross-repo: ~/Dotfiles/CLAUDE.md
- Update the orchestrator reset recipe reference from `/ccrecall:ccr-resume` to `/cass-resume`

### Cross-repo: ~/Dotfiles/config/claude/orchestrator/CLAUDE.md
- Update `rc-send` command from `/ccrecall:ccr-resume` to `/cass-resume`

### Cross-repo: ~/Dotfiles/home/bin/orchestrator/orchestrator-tick
- Update heartbeat warning message from `/ccrecall:ccr-resume` to `/cass-resume`

## Focus
- The Dotfiles cross-repo changes are critical — the orchestrator on jessica-desktop runs continuously and hard-codes `/ccrecall:ccr-resume` in three places. These updates must land before or alongside the ccrecall plugin removal, or the orchestrator's reset recipe silently fails.
- REFERENCE.md is the central reference — it needs the most edits. Read it fully before editing to understand the current structure.
- The `/cm-recall-conversations` reference in Dotfiles capabilities.md is already orphaned (predates the ccrecall plugin rename). Updating it to `/cass-recall` cleans up the drift.
- CHANGELOG.md references to ccrecall are historical and should NOT be updated.
- ONBOARDING.md may need structural changes if the Plugins concept no longer has any entries.

## Verify
- [ ] All ccrecall/ccr-*/cm-* references removed from documentation files listed in Target Files
- [ ] Cross-repo Dotfiles files updated with `/cass-resume` replacing `/ccrecall:ccr-resume`
