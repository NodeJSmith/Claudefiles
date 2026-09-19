## Sources Found

### AGENTS.md (official site)
- **URL**: https://agents.md/
- **Type**: standard / specification
- **Key takeaway**: AGENTS.md is an open, tool-agnostic convention (led by OpenAI, with Google/Cursor/Factory) for giving AI coding agents instructions. As of late 2025 over 60,000 OSS repos had adopted it and 20+ tools support it. It explicitly supports nested files — closer to the target file wins.
- **Relevance**: Direct precedent for the nesting convention described in the research question; the canonical source for "nearest file wins" resolution semantics.

### AI Coding Tip 014 — Use Nested AGENTS.md Files (Maximiliano Contieri, Medium)
- **URL**: https://mcsee.medium.com/ai-coding-tip-014-use-nested-agents-md-files-23031bb0786a
- **Type**: blog post / experience report
- **Key takeaway**: Advocates starting with one root AGENTS.md and adding nested files only when a package/service/directory has genuinely different commands or local rules — not by default.
- **Relevance**: Practical guidance on when nesting is warranted vs. unnecessary duplication.

### A Complete Guide To AGENTS.md (aihero.dev)
- **URL**: https://www.aihero.dev/a-complete-guide-to-agents-md
- **Type**: blog post / guide
- **Key takeaway**: Documents that OpenAI's own primary repo uses ~88 nested AGENTS.md files across its tree, each adding only instructions specific to that subdirectory, and that conflicting nested vs. root guidance resolves in favor of the file nearest the edited path.
- **Relevance**: Concrete large-scale reference implementation of the nested pattern at real scale.

### AGENTS.md in a monorepo: nested files and precedence (DEV Community)
- **URL**: https://dev.to/promptmaster/agentsmd-in-a-monorepo-nested-files-and-precedence-1b7d
- **Type**: blog post
- **Key takeaway**: Recommends a root AGENTS.md for workspace-wide tooling/conventions plus one per top-level package containing only what's specific to that package (commands, conventions, boundaries) — "state shared rules once at the root, override only what differs." Two levels (root + one per package) covers almost every real monorepo.
- **Relevance**: Gives a concrete rule of thumb for how much to nest and what content belongs at which level.

### 6 AGENTS.md Examples From Real Production Repos (ssojet.com)
- **URL**: https://ssojet.com/blog/agents-md-examples
- **Type**: blog post / survey of real repos
- **Key takeaway**: Apache Airflow's AGENTS.md enforces documentation-naming conventions the agent would otherwise get wrong every time; Cloudflare's workers-sdk leads its file with package-manager/tooling guardrails specific to that repo's build quirks.
- **Relevance**: Shows what actually goes in these files in practice — narrow, repo-specific gotchas rather than generic advice.

### AGENTS.md Spec (2026): Recommended Sections + AGENTS.md vs CLAUDE.md vs .cursorrules (morphllm.com)
- **URL**: https://www.morphllm.com/agents-md-guide
- **Type**: reference/guide
- **Relevance**: Comparative treatment of the competing file-name conventions and their relationship to nesting; background for tool-support differences.

### Claude Code docs — Extend Claude Code
- **URL**: https://code.claude.com/docs/en/features-overview
- **Type**: official documentation
- **Key takeaway**: Claude reads CLAUDE.md files from the working directory up to root at launch, and discovers nested CLAUDE.md files in subdirectories as it accesses those files during a session (lazy, on-demand loading) rather than eagerly loading the whole tree.
- **Relevance**: Documents the actual mechanics of nested CLAUDE.md loading for the tool named in the question.

### Claude Code's CLAUDE.md inheritance: how nested configs actually work (DEV Community)
- **URL**: https://dev.to/subprime2010/claude-codes-claudemd-inheritance-how-nested-configs-actually-work-4en0
- **Type**: blog post / experience report
- **Key takeaway**: CLAUDE.md files are additive across levels (global → project root → subdirectory → deeper subdirectory), not overriding — all applicable levels contribute simultaneously to context, and Claude uses judgment to reconcile conflicts, generally favoring the more specific (deeper) file.
- **Relevance**: Important behavioral contrast with AGENTS.md's explicit "nearest wins" rule — CLAUDE.md nesting is described as additive/merging rather than override-by-proximity, which changes how conflicting module-level guidance should be written.

### Layered CLAUDE.md: Subdirectory Context That Scales (claudefa.st)
- **URL**: https://claudefa.st/blog/guide/mechanics/subdirectory-claude-md
- **Type**: blog post / guide
- **Key takeaway**: Recommends keeping the root CLAUDE.md under ~200 lines and pushing subdirectory-specific detail (build/test commands local to that part of the codebase, local conventions) into nested files instead of bloating the root; recommends moving reference material that isn't always needed into skills that load on demand rather than always-loaded CLAUDE.md content.
- **Relevance**: Direct advice on root-vs-nested content split, matching the research question's "what goes in them vs. root."

### [FEATURE REQUEST] Nested CLAUDE.md context · Issue #705 (anthropics/claude-code)
- **URL**: https://github.com/anthropics/claude-code/issues/705
- **Type**: GitHub issue (feature request / user reports)
- **Relevance**: User-reported pain points and requests around nested CLAUDE.md discovery — useful for understanding gaps and desired behavior from actual users, not just docs.

### Support nested CLAUDE.local.md discovery in subdirectories · Issue #22652 (anthropics/claude-code)
- **URL**: https://github.com/anthropics/claude-code/issues/22652
- **Type**: GitHub issue
- **Relevance**: Confirms an active gap area (nested `CLAUDE.local.md`, the gitignored personal-override variant, is not yet discovered the same way nested `CLAUDE.md` is), showing the ecosystem is still maturing around nesting semantics.

### Subdirectory-Specific .cursorrules Support (Cursor Community Forum)
- **URL**: https://forum.cursor.com/t/subdirectory-specific-cursorrules-support/40566
- **Type**: forum thread / feature request
- **Key takeaway**: `.cursorrules` (single root file) was deprecated by Cursor in late 2024 in favor of a `.cursor/rules/` directory; genuine per-subdirectory nesting is not what a `.cursor/rules/` folder's own internal subfolders do — for real per-package granularity Cursor's current documented mechanism is nested AGENTS.md files, not nested `.cursor/rules` directories.
- **Relevance**: Clarifies a common point of confusion — Cursor converged on AGENTS.md for directory-scoped instructions rather than maintaining its own competing nested-rules mechanism.

### Rules | Cursor Docs
- **URL**: https://cursor.com/help/customization/rules
- **Type**: official documentation
- **Relevance**: Authoritative current-state description of Cursor's rules system and its relationship to AGENTS.md.

### Adding repository custom instructions for GitHub Copilot (GitHub Docs)
- **URL**: https://docs.github.com/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot
- **Type**: official documentation
- **Key takeaway**: `.github/copilot-instructions.md` is a single global file always included in every Copilot request — it is not itself split or selectively loaded. Separately, `.github/instructions/NAME.instructions.md` files (optionally organized in subdirectories) use `applyTo:` frontmatter with glob patterns to scope instructions to matching files/paths, giving path-specific rather than directory-nested behavior.
- **Relevance**: Copilot's mechanism for "module-level" context is glob-based path targeting (`applyTo`), a materially different design from AGENTS.md/CLAUDE.md's directory-tree nesting — worth distinguishing in any comparison across tools.

### .copilot-instructions.md per folder · Issue #3303 (microsoft/vscode-copilot-release)
- **URL**: https://github.com/microsoft/vscode-copilot-release/issues/3303
- **Type**: GitHub issue
- **Relevance**: User request confirming per-folder `copilot-instructions.md` (directory nesting, as opposed to glob-based `applyTo` scoping) is a requested-but-not-native capability as of research date.

### Windsurf Rules Directory / Windsurf Rules and Memories guide
- **URL**: https://windsurf.com/editor/directory ; https://qaskills.sh/blog/windsurf-rules-and-memories-guide
- **Type**: official + blog
- **Key takeaway**: Windsurf evolved from a single root `.windsurfrules` file to a `.windsurf/rules/` directory of individual rule files (each capped at 6,000 characters, 12,000 total), with rules markable as Always On, Manual (@mention), or Model Decision (auto-attached by relevance) — a tagging/activation model rather than filesystem-path nesting. Global rules live in `~/.windsurf/rules/` (every project) and project rules in `.windsurf/rules/` (git-committed, team-shared), with project rules taking precedence on conflict.
- **Relevance**: A third distinct architecture for scoping instructions — activation-mode-based rather than directory-tree-based — useful contrast for the comparison table.

### [Windsurf] Rules loaded 2x-9x per response with nested git repos (token waste) · Issue #305 (Exafunction/codeium)
- **URL**: https://github.com/Exafunction/codeium/issues/305
- **Type**: GitHub issue / documented pitfall
- **Key takeaway**: When a workspace contains multiple nested git repos, Windsurf's rules loader can load the same `.windsurf/rules/` content redundantly (2x-9x) per response, wasting context tokens — a concrete documented pitfall of directory-based rule discovery interacting poorly with nested repo structures.
- **Relevance**: Anti-pattern / pitfall example directly relevant to the "common pitfalls" ask.

### AGENTS.md Best Practices 2026: What 60,000+ Repos Teach Us (The Prompt Shelf)
- **URL**: https://thepromptshelf.dev/blog/agents-md-best-practices-2026/
- **Type**: blog post / aggregated analysis
- **Key takeaway**: Analysis across ~2,500 repos found diminishing returns once an AGENTS.md file exceeds roughly 150 lines — inference cost rises 20-23% with no measurable behavior improvement past that point ("the novel problem" — the agent starts skimming and losing load-bearing lines). Also reports six recurring defect types found in 91 of 100 popular AGENTS.md files: Lint Leakage, Context Bloat, Skill Leakage, Conflicting Instructions, Init Fossilization, and Blind References.
- **Relevance**: Directly answers "common pitfalls and anti-patterns others have documented," with a specific quantified size threshold.

### AGENTS.md Patterns: What Actually Changes Agent Behavior (blakecrosley.com)
- **URL**: https://blakecrosley.com/blog/agents-md-patterns
- **Type**: blog post / experience report
- **Key takeaway**: Argues the real failure mode isn't a too-thin file but one that grows chronologically into a changelog/log of decisions rather than staying a living, current reference — "short, current, specific" is load-bearing, not a style preference. An outdated command or path is worse than no file, since the agent will follow it with full confidence.
- **Relevance**: Strong anti-pattern citation — staleness risk, and the mechanism by which nested files rot (nobody revisits them once written).

### Structural Quality Gaps in Practitioner AI Governance Prompts (arXiv)
- **URL**: https://arxiv.org/pdf/2604.21090
- **Type**: research paper
- **Relevance**: Empirical study of practitioner-authored AI governance/instruction prompts (of which AGENTS.md-style files are an instance) — background on the maturity/quality of these artifacts as actually written in the wild.

### ETH Zurich study on AGENTS.md files (via search-engine synthesis, no direct URL captured)
- **URL**: [no source found — surfaced only as an aggregated web-search summary, no direct paper/article link resolved]
- **Type**: unverified claim
- **Key takeaway**: Reported to show structured, project-specific context files dramatically improve AI coding output accuracy holding the model constant, with the improvement attributable to context content rather than model choice.
- **Relevance**: If a primary source can be located, this would be the strongest direct evidence for "does module-level context improve AI accuracy" — flagged here as unverified pending a real citation. Do not cite this claim without independently locating the paper.

## Patterns Found

### Pattern 1: Root + Nested AGENTS.md/CLAUDE.md, filesystem-tree scoped

**Used by**: OpenAI's primary repo (~88 nested AGENTS.md files), Apache Airflow, Cloudflare workers-sdk, and the broader AGENTS.md ecosystem (60,000+ repos per agents.md); Claude Code natively supports the same shape for CLAUDE.md.

**How it works**: A root-level file (`AGENTS.md` or `CLAUDE.md`) carries project-wide conventions — package manager, overall architecture, org-wide style rules, how to run the full test suite. Individual packages, services, or deeply nested directories that have genuinely different build commands, local conventions, or domain-specific gotchas get their own file in that directory. When an agent works on a file, it discovers and loads the instruction file(s) along the path from root down to that file's directory. AGENTS.md's documented resolution model treats the nearest file to the edited path as authoritative when there's a direct conflict; Claude Code's documented model instead treats levels as additive, with deeper/more-specific guidance generally taking precedence in the agent's judgment rather than through hard override semantics (https://dev.to/subprime2010/claude-codes-claudemd-inheritance-how-nested-configs-actually-work-4en0).

**Strengths**: Scales naturally with monorepo structure; keeps root files short and generic; lets a subproject with an unusual build system or an unusual architectural invariant document that fact exactly where an agent will encounter it, without forcing every contributor to read subproject-specific detail up front. Because files load lazily as the agent navigates into a directory (per Claude Code docs), it doesn't bloat every session's starting context.

**Weaknesses**: Governance is per-repo and manual — nothing forces a nested file to stay in sync with the code around it, and staleness ("wrong package manager," "wrong path") is reported as actively worse than having no file, because the agent follows it confidently (https://blakecrosley.com/blog/agents-md-patterns). Files also drift into changelogs/logs of past decisions rather than staying a current spec if nobody prunes them. Analysis across thousands of repos found no behavioral benefit — and rising inference cost — once a single file passes roughly 150 lines (https://thepromptshelf.dev/blog/agents-md-best-practices-2026/). Precedence/merge semantics differ meaningfully between tools (AGENTS.md's "nearest wins" vs. Claude Code's "additive, judgment-based"), so a nested file written to *override* a root rule may behave differently depending on which tool reads it.

**Example**: https://www.aihero.dev/a-complete-guide-to-agents-md (OpenAI's ~88-file example); https://code.claude.com/docs/en/features-overview (Claude Code's discovery mechanics)

### Pattern 2: Glob/path-scoped instruction files (applyTo frontmatter), not directory-tree nesting

**Used by**: GitHub Copilot (`.github/instructions/*.instructions.md` with `applyTo:` glob frontmatter), layered on top of a single always-included `.github/copilot-instructions.md`.

**How it works**: One global file (`copilot-instructions.md`) is always sent with every request regardless of what's being edited — it is not selectively loaded and cannot itself be split into auto-loaded pieces. For scoped guidance, authors instead create separate `NAME.instructions.md` files (optionally grouped into subdirectories purely for author organization, not for loading semantics) and declare an `applyTo:` glob pattern in frontmatter (e.g. `applyTo: "src/api/**/*.ts"`). Copilot matches the current file against these globs and layers in the matching instructions, independent of where the instructions file physically lives on disk.

**Strengths**: Decouples "where the instructions file lives" from "what it applies to" — a single instructions file can cover a cross-cutting glob (all `*.test.ts` files anywhere) that a pure directory-nesting model can't express without duplicating the file into every matching folder.

**Weaknesses**: The always-on global file has no selective-loading equivalent to AGENTS.md's nested/lazy discovery, so it can't be kept small the way root CLAUDE.md/AGENTS.md files are recommended to be — everything in it costs context on every request. Per-folder physical nesting (the direct analogue to AGENTS.md nesting) is a requested-but-unsupported feature (https://github.com/microsoft/vscode-copilot-release/issues/3303).

**Example**: https://docs.github.com/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot

### Pattern 3: Activation-mode-scoped rules directory (not path-based)

**Used by**: Windsurf (`.windsurf/rules/`, formerly a single root `.windsurfrules`).

**How it works**: Individual rule files live in a flat or lightly-nested `.windsurf/rules/` directory, each tagged with an activation mode: Always On (loaded every session), Manual (only pulled in via explicit `@mention`), or Model Decision (the model decides whether a rule is relevant and auto-attaches it). Global (`~/.windsurf/rules/`, applies to every project) and project-level (`.windsurf/rules/`, git-shared) tiers exist, with project rules winning conflicts. Scoping to a "module" is achieved by writing a rule whose content or Model-Decision relevance ties it to a particular area, not by which directory the rule file sits in.

**Strengths**: Explicit control over whether context always loads vs. loads only on demand, independent of file location — arguably a cleaner mechanism for balancing "always relevant" project rules against "sometimes relevant" module detail than pure directory-tree nesting, since it doesn't require the agent to have already navigated into a directory to discover the rule.

**Weaknesses**: Hard per-file (6,000 char) and total (12,000 char) size caps force aggressive splitting and pruning. Directory nesting inside `.windsurf/rules/` is not the same mechanism as per-package AGENTS.md nesting and can misbehave: in workspaces containing multiple nested git repos, the same rules content has been reported loading redundantly (2x-9x) per response (https://github.com/Exafunction/codeium/issues/305), wasting tokens rather than saving them.

**Example**: https://windsurf.com/editor/directory ; https://github.com/Exafunction/codeium/issues/305 (pitfall)

## Anti-Patterns

- **Stale/fossilized nested instructions.** A nested file that says the wrong package manager or wrong file path is reported as actively worse than no file at all — the agent follows it with full confidence rather than discovering the correct behavior on its own. Named "Init Fossilization" in one survey of 100 popular AGENTS.md files. Source: https://thepromptshelf.dev/blog/agents-md-best-practices-2026/, https://blakecrosley.com/blog/agents-md-patterns

- **Letting the file become a changelog instead of a current spec.** Nested/root instruction files that accumulate historical rationale and one-off notes over time (rather than being pruned to reflect only current, load-bearing rules) degrade into logs nobody trusts or maintains. Source: https://blakecrosley.com/blog/agents-md-patterns

- **Context bloat past ~150 lines per file.** Cross-repo analysis found diminishing-to-negative returns (rising inference cost, no measurable behavior gain) once a single AGENTS.md file grows past roughly 150 lines — the fix is nesting/splitting content into directory-scoped files rather than growing one file indefinitely. Source: https://thepromptshelf.dev/blog/agents-md-best-practices-2026/

- **Conflicting instructions across nesting levels with no clear precedence model in the author's head.** Because tools differ on how they resolve nested-vs-root conflicts (AGENTS.md: nearest file wins; Claude Code: additive/judgment-based merge — https://dev.to/subprime2010/claude-codes-claudemd-inheritance-how-nested-configs-actually-work-4en0), authors who assume one tool's semantics while writing for a multi-tool audience can produce instructions that behave inconsistently across agents. Named "Conflicting Instructions" as a recurring defect. Source: https://thepromptshelf.dev/blog/agents-md-best-practices-2026/

- **Rules directory duplication in multi-repo workspaces.** Directory-based rule discovery (Windsurf's `.windsurf/rules/`) can redundantly re-load the same content once per detected git root in a nested-repo workspace, wasting context rather than scoping it precisely. Source: https://github.com/Exafunction/codeium/issues/305

## Emerging Trends

- **Convergence toward AGENTS.md as the cross-tool nesting standard.** Cursor's own docs now point to AGENTS.md (root + subdirectories) as the documented mechanism for directory-scoped rules rather than maintaining a separate nested-rules-folder concept of its own (https://forum.cursor.com/t/subdirectory-specific-cursorrules-support/40566), suggesting tool vendors are consolidating around one nesting convention rather than each maintaining bespoke nested formats.
- **A widely-repeated numeric size guideline (~150-200 lines per file) is emerging as informal best practice** for both root and nested files, independently reported by Claudefa.st (root CLAUDE.md under ~200 lines, push detail into nested files/skills) and The Prompt Shelf's cross-repo AGENTS.md analysis (~150 lines diminishing-returns threshold) — worth treating as a soft convention rather than a hard spec, since neither source is an official standard.
