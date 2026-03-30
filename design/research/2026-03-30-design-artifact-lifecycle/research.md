---
proposal: "Manage the accumulation of design/planning documents in a config repo where AI-generated artifacts outnumber code files"
date: 2026-03-30
status: Draft
flexibility: Exploring
motivation: "After a few features, design docs (specs, designs, WPs, research briefs, critiques) outnumber the actual deliverables (skills, scripts, configs). Signal-to-noise ratio degrades."
constraints: "Config repo, not a traditional software project. Code is mostly markdown and shell. Design artifacts are also markdown."
non-goals: "Not redesigning the caliper workflow itself. Not changing what artifacts get produced."
depth: normal
---

# Research Brief: Design Artifact Lifecycle Management

**Initiated by**: Investigation into how to handle accumulation of design documents in a Claude Code config repo.

## Context

### What prompted this

The Claudefiles repo uses an AI-assisted spec-driven development workflow (caliper) that generates multiple artifacts per feature: spec.md, design.md, WP01-WPnn.md, research briefs, critique reports. After 11 features (7 completed, 4 in-progress/stalled), the design directory contains 97 markdown files. The deliverable code (skills, commands, agents, rules, bin scripts) totals 164 files. The design artifacts are approaching a 1:1 ratio with code -- and every new feature adds 5-10 more.

### Current state

**Design artifact inventory (102 files total):**

| Category | Count | Notes |
|----------|-------|-------|
| Work packages (WP*.md) | 54 | Largest category |
| Research briefs | 21 | Includes bookmark analysis (11 files) |
| Design docs (design.md) | 13 | One per spec + 2 in plans/ |
| Other (critiques, plans, misc) | 7 | |
| Specs (spec.md) | 3 | Most features skip formal spec |
| .gitignore files | 4 | In tasks/ dirs |

**Completion status of specs:**

| Status | Specs | WPs |
|--------|-------|-----|
| All WPs done | 7 specs | 39 WPs |
| In-progress (0 WPs done) | 3 specs | 15 WPs |
| Design only (no WPs) | 2 specs | 0 |

Seven completed features account for 39 work packages and 7 design documents that serve no ongoing purpose -- the changes they describe are already merged into the codebase.

**Disk usage:** design/ is 964K vs 1.8MB for all code directories combined. Not a storage problem -- it is a navigation and comprehension problem.

### Key constraints

- This is a config repo, not a traditional software project. The "code" is markdown skill files and shell scripts. The design artifacts are also markdown. There is no compiler or type system to distinguish deliverables from planning docs.
- The caliper workflow (mine.specify -> mine.design -> mine.draft-plan -> mine.orchestrate) produces these artifacts as part of its process. The artifacts are consumed by AI agents during implementation.
- Research briefs and critiques serve as input to design decisions. They capture reasoning that would otherwise be lost.
- The repo has a single default branch (main). No existing branch strategy for archives.

## How Other Projects Handle This

### Pattern 1: Separate Repository (Rust RFCs, React RFCs, Ember RFCs)

Major open-source projects keep RFCs/design docs in a dedicated repo, separate from the implementation:

- **rust-lang/rfcs** has ~2,000 closed PRs and hundreds of accepted RFCs in a `text/` directory. Accepted RFCs stay permanently -- they are never deleted. Inactive RFCs move to an `inactive/` folder. The repo is essentially an append-only log.
- **reactjs/rfcs** and **emberjs/rfcs** follow the same model: separate repo, flat directory of numbered markdown files.
- Ember consolidated from multiple RFC repos (ember-cli/rfcs, emberjs/rfcs) into one, suggesting that proliferation of RFC repos is itself a problem.

**Key insight:** These repos have *thousands* of design docs and it works because the RFC repo is *all* design docs -- there is no code to be diluted. The signal-to-noise problem only arises when design docs live alongside code.

**Applicability:** Low for this repo. A separate "claudefiles-design" repo would add friction to the caliper workflow, which expects design artifacts adjacent to the code. Cross-repo references are fragile.

### Pattern 2: ADR (Architecture Decision Records) with Status Lifecycle

ADRs use an append-only log with status metadata:

- Statuses: proposed -> accepted -> deprecated | superseded
- An ADR is immutable once accepted -- only its status can change
- Superseded ADRs link to their replacement
- Tools like **log4brains** publish ADRs as a static website, making them browsable without cluttering the repo during normal development
- **adr-tools** provides CLI helpers for creating, superseding, and linking ADRs

**Key insight:** ADRs are explicitly designed to accumulate indefinitely. The strategy is not cleanup but *presentation* -- making them browsable/searchable so the flat file list does not matter. Log4brains generates a searchable website from ADR markdown files.

**Applicability:** Medium. The ADR model validates keeping completed artifacts, but the Claudefiles design artifacts are more granular than ADRs (5-7 files per feature vs 1 ADR per decision). The presentation-layer approach (rendering as a browsable site) could work for research briefs and design docs.

### Pattern 3: Subdirectory with Periodic Archival

The most common pattern in practice -- a `docs/` or `design/` directory that grows, with occasional manual cleanup:

- Google's engineering culture uses design docs stored in Google Docs (external tool), not in the code repo. The docs are referenced by link, not by file.
- Many teams move completed design docs to an `archive/` or `done/` subdirectory
- Some projects use date-prefixed directories (like this repo's `design/research/`) to provide implicit chronological ordering

**Key insight:** Manual archival has low setup cost but high ongoing cost. It only works if someone remembers to do it, and "someone" in an AI-assisted workflow is the human operator who may have already moved on.

**Applicability:** Medium-high. This is the simplest option and closest to the current structure.

### Pattern 4: Git Orphan Branch

An orphan branch shares no history with the main branch. Used by GitHub Pages (`gh-pages` branch) to store documentation alongside code without cluttering the working tree:

- Design artifacts would be committed to an `archive` orphan branch
- Main branch only contains active/in-progress design docs
- Git history is preserved but invisible during normal development
- No separate repo, no external tools

**Key insight:** Orphan branches solve the navigation problem (files do not appear in the working tree) while preserving git history. The tradeoff is discoverability -- you have to know to check the orphan branch.

**Applicability:** Medium. Clean separation, but adds workflow complexity. The caliper workflow would need to know about the archival branch, and cross-referencing archived designs from active work becomes harder.

### Pattern 5: Spec-Driven Development Tools (Spec-Kit, Kiro, BMAD)

Emerging SDD tools (2025-2026) take different stances on artifact lifecycle:

- **GitHub spec-kit** has an "archive merged features into main project memory" step but the mechanism is undefined in current docs. It also includes "post-implementation retrospective with spec adherence scoring." The lifecycle question is acknowledged but unresolved.
- **Kiro/Tessl** treats specs as living documents that evolve with the code -- "spec-anchored" development. Specs are never archived; they are updated as the feature evolves. This assumes specs remain useful indefinitely.
- **BMAD Method** stores artifacts in a `bmad/` directory with workflow status tracking. No documented archival process.
- **SDD spectrum**: Spec-first (write once, discard), Spec-anchored (maintain alongside code), Spec-as-source (spec IS the code). Each implies a different archival strategy.

**Key insight:** The entire SDD ecosystem is still working out artifact lifecycle. No one has a mature answer. The "spec-anchored" approach (keep specs as living docs) only works if specs are actually updated when the feature changes -- which rarely happens in practice.

**Applicability:** High relevance for understanding the landscape, but no ready-made solution to adopt.

## The Value Question

Before choosing a strategy, the critical question: **what value do completed design artifacts provide?**

### Arguments for keeping them accessible

1. **Design rationale** -- WHY a decision was made, alternatives considered, constraints that drove the choice. This is genuinely hard to reconstruct from code alone.
2. **Onboarding context** -- new contributors (or a future AI agent with no memory) can read the design doc to understand a feature's intent.
3. **Avoiding re-treading** -- research briefs and critiques capture investigation that should not be repeated.
4. **Debugging aid** -- when a feature behaves unexpectedly, the design doc explains intended behavior.

### Arguments for archival/removal

1. **Navigation cost** -- 97 design files make `find`, `grep`, and tree views noisy. AI agents exploring the codebase spend tokens reading irrelevant completed WPs.
2. **Staleness** -- completed design docs are never updated. They describe the *intended* design, which may have drifted from reality during implementation. Stale docs are worse than no docs.
3. **Proportionality** -- in this repo, a 5-line shell script might have a 500-line design doc + 5 WPs + a research brief. The overhead is disproportionate.
4. **WPs are ephemeral by nature** -- work packages are execution artifacts (task lists). Once done, they have near-zero reference value. The design.md captures the same decisions at a higher level.

### Assessment by artifact type

| Artifact | Post-completion value | Recommendation |
|----------|----------------------|----------------|
| design.md | HIGH -- captures rationale, alternatives, architecture | Keep accessible |
| spec.md | MEDIUM -- captures requirements, but often redundant with design.md | Keep accessible |
| research briefs | HIGH -- captures investigation, prior art, external references | Keep accessible |
| critiques | MEDIUM -- captures review feedback, risks identified | Keep accessible |
| WP*.md | LOW -- task lists with lane status. All information is in git history and design.md | Archive or remove |
| plans/ | LOW -- superseded by specs/ | Archive or remove |

## Options Evaluated

### Option A: Tiered Archival Within the Current Structure

**How it works**: Add an `archive/` subdirectory under `design/specs/`. When a feature's WPs are all `done`, move the entire spec directory to `design/specs/archive/NNN-slug/`. Keep research briefs and critiques in place (they are already date-organized and low-volume). Optionally, extract the design.md from archived specs into a flat `design/decisions/` directory for easy reference (ADR-style).

An automation script (or a caliper post-orchestration step) could detect completed specs and offer to archive them. The `.gitignore` in tasks/ directories is already a precedent for treating some design artifacts as transient.

**Pros**:
- Zero new infrastructure -- just directory moves
- Git history fully preserved (git tracks renames)
- Completed features disappear from the active view but remain one directory deeper
- Research briefs and critiques remain in their current date-organized structure (already manageable)
- Could extract a "decisions log" from design.md files for quick reference

**Cons**:
- Manual process unless automated
- Still in the working tree -- AI agents could still read archived files if they grep broadly
- Does not solve the proportionality problem (archived WPs still exist)

**Effort estimate**: Small -- a script to move directories + update caliper to suggest archival after orchestration completes.

**Dependencies**: None.

### Option B: Delete Completed WPs, Keep Design Docs

**How it works**: After a feature is fully shipped (all WPs done, merged to main), delete the `tasks/` directory entirely. Keep design.md, spec.md, and any critique/research artifacts. The design.md already captures the same decisions at a higher level -- WPs are execution artifacts that are meaningless after execution.

This could be automated as part of `/mine.ship` or as a post-merge hook. A brief summary line could be appended to design.md: "Implemented in [commit range/PR]. N work packages completed."

**Pros**:
- Eliminates the largest category of artifacts (54 WPs = 56% of design files)
- design.md retains the architectural rationale
- Git history preserves the full WP content for anyone who needs it
- Aligns with how WPs are actually used -- they are consumed during orchestration and never referenced again
- Could reduce design file count from ~97 to ~43 immediately

**Cons**:
- Irreversible in the working tree (though recoverable from git)
- Loses the "status board" view of what was done (though design.md frontmatter could capture this)
- Requires trust that git history is a sufficient archive

**Effort estimate**: Small -- `rm -rf design/specs/NNN-*/tasks/` for completed specs, plus a one-line update to caliper workflow.

**Dependencies**: None.

### Option C: Hybrid -- Archive Completed Specs to Orphan Branch

**How it works**: Create a `design-archive` orphan branch. When a feature is fully complete, move the entire spec directory (design.md + tasks/) to the orphan branch and remove it from main. Keep research briefs on main (they have ongoing reference value and are already well-organized by date).

A script would handle the mechanics: commit to orphan branch, remove from main, add a one-line reference in the design.md's former location (or a central `design/archive-index.md`).

**Pros**:
- Cleanest working tree -- completed design artifacts fully invisible during normal development
- Git history preserved on the orphan branch
- No separate repo to manage
- Research briefs and critiques stay on main where they are useful

**Cons**:
- Most complex workflow of the three options
- Cross-referencing requires checking out the orphan branch
- AI agents cannot easily access archived designs (which may be a pro or con)
- Orphan branches are unfamiliar to most developers

**Effort estimate**: Medium -- script to manage orphan branch operations, update caliper workflow.

**Dependencies**: None, but requires understanding orphan branch mechanics.

### Option D: Do Less -- Annotate and Ignore

**How it works**: Do not move or delete anything. Instead:
1. Add a `.gitignore` pattern or editor config to hide `design/specs/*/tasks/` from tree views
2. Add frontmatter `status: completed` to finished design.md files
3. Add a `design/README.md` that explains the structure and links to active vs completed features
4. Optionally exclude `design/specs/*/tasks/` from AI agent context via `.claude/settings.json` file ignore patterns

**Pros**:
- Zero disruption to existing workflow
- No files move, no history changes
- IDE and agent-level filtering solves the navigation problem without touching the filesystem
- Preserves the option to do more later

**Cons**:
- Files still exist and count toward repo size metrics
- Does not address the psychological weight of seeing 97 design files
- Ignoring files from AI context means they cannot be referenced when needed
- Does not solve the problem, just hides it

**Effort estimate**: Small -- configuration changes only.

**Dependencies**: None.

## Concerns

### Technical risks
- **Git rename tracking**: Option A relies on git detecting renames when moving directories. Git handles this well for clean moves but may lose tracking if files are also modified during the move.
- **Orphan branch divergence**: Option C creates a branch that nobody regularly checks. It could silently break (bad commits, missing files) without anyone noticing.

### Complexity risks
- **Caliper workflow coupling**: Any archival step that integrates into the caliper workflow adds a new failure mode to an already multi-step process (specify -> design -> draft-plan -> orchestrate -> ship).
- **Inconsistent application**: If archival is manual, some features get archived and others do not. The inconsistency is worse than no archival at all.

### Maintenance risks
- **Future caliper changes**: If the caliper workflow evolves (e.g., adds new artifact types), the archival process needs to evolve too.
- **Stale research briefs**: Research briefs are date-stamped but never expire. The bookmark-analysis directory alone has 11 files from a single research session. These will accumulate faster than specs.

## Open Questions

- [ ] Are the stalled specs (001, 002, 003, 004, 005) likely to be resumed, or should they be considered abandoned? If abandoned, they are candidates for immediate archival.
- [ ] Should research briefs follow the same lifecycle as specs, or are they permanent reference material?
- [ ] Would excluding `design/specs/*/tasks/` from AI agent context (via settings.json ignore patterns) be sufficient to solve the token-cost problem, making physical archival less urgent?
- [ ] Is there value in extracting a "decisions log" (one-paragraph summaries of each completed feature's design rationale) as a lightweight alternative to keeping full design docs?

## Recommendation

**Option B (Delete Completed WPs, Keep Design Docs)** is the strongest fit for this repo.

The reasoning:
1. Work packages are the largest artifact category (54 files, 56% of design artifacts) and have near-zero post-completion value. They are task lists, not design rationale.
2. Design.md files capture everything worth preserving -- the problem, alternatives considered, architecture decisions, and non-goals.
3. Git history provides a complete audit trail for anyone who needs to see the original WPs.
4. This immediately cuts the design file count roughly in half with zero risk of losing important context.

For the remaining artifacts (design.md, research briefs, critiques), **Option D's annotation approach** works well: add `status: completed` frontmatter to finished design docs, and let the date-organized research directory continue as-is.

The combination (B + D) gives the best ratio of cleanup to effort: delete what is clearly disposable (completed WPs), annotate what is worth keeping (design docs), and leave well-organized content alone (research briefs).

**Consider running `/mine.challenge` on this recommendation** before committing to an approach, particularly to stress-test the claim that completed WPs have near-zero reference value.

### Suggested next steps
1. Audit the 5 stalled specs (001-005) to determine if they should be abandoned or resumed -- this affects what gets archived.
2. Delete `tasks/` directories for the 7 completed specs. Append a completion note to each design.md.
3. Add `status: completed | active | stalled` frontmatter to all design.md files.
4. Consider adding a `design/specs/*/tasks/` exclude pattern to `.claude/settings.json` to reduce AI agent token consumption for any remaining WP directories.
5. Optionally write a `bin/archive-spec` helper that automates steps 2-3 for future completed features.

## Sources

- [ADR GitHub Community](https://adr.github.io/)
- [Martin Fowler: Architecture Decision Record](https://martinfowler.com/bliki/ArchitectureDecisionRecord.html)
- [AWS Prescriptive Guidance: ADR Process](https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/adr-process.html)
- [joelparkerhenderson/architecture-decision-record](https://github.com/joelparkerhenderson/architecture-decision-record)
- [Rust RFC Process](https://rust-lang.github.io/rfcs/0002-rfc-process.html)
- [rust-lang/rfcs Repository](https://github.com/rust-lang/rfcs)
- [reactjs/rfcs Repository](https://github.com/reactjs/rfcs)
- [Ember RFC Stages](https://rfcs.emberjs.com/id/0617-rfc-stages/)
- [emberjs/rfcs Repository](https://github.com/emberjs/rfcs)
- [Log4brains: ADR Management Tool](https://github.com/thomvaill/log4brains)
- [Design Docs at Google](https://www.industrialempathy.com/posts/design-docs-at-google/)
- [Graphite: Understanding Orphan Branches in Git](https://graphite.com/guides/git-orphan-branches)
- [Thoughtworks: Spec-Driven Development](https://www.thoughtworks.com/en-us/insights/blog/agile-engineering-practices/spec-driven-development-unpacking-2025-new-engineering-practices)
- [Martin Fowler: Understanding SDD Tools (Kiro, spec-kit, Tessl)](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html)
- [GitHub spec-kit Repository](https://github.com/github/spec-kit)
- [GitHub Blog: Spec-Driven Development with AI](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/)
- [AWS: AI-Driven Development Lifecycle](https://aws.amazon.com/blogs/devops/ai-driven-development-life-cycle/)
- [BMAD Method](https://github.com/bmad-code-org/BMAD-METHOD)
- [Spec-Driven Development: From Code to Contract (arXiv)](https://arxiv.org/abs/2602.00180)
