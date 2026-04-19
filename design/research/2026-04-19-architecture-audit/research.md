---
proposal: "Build a mine.architecture-audit skill that dispatches parallel agents to perform systematic design pattern, coupling, and structural analysis on any Python or TypeScript codebase."
date: 2026-04-19
status: Draft
flexibility: Exploring
motivation: "The user manually ran architect + researcher in parallel on a project and got convergent-but-complementary results. They want to codify this as a repeatable skill but want to validate the agent decomposition before committing."
constraints: "Claude Code skill (SKILL.md); dispatches subagents via Agent tool; available agents are architect, researcher, code-reviewer, integration-reviewer, qa-specialist, Explore; read-only analysis only; must work on Python and TypeScript codebases"
non-goals: "Code changes, implementation, runtime profiling, benchmarking"
depth: deep
---

# Research Brief: Architecture Audit Skill Design

**Initiated by**: User wants to codify a manual two-agent architecture audit workflow (architect + researcher) into a repeatable `mine.architecture-audit` skill, but wants to validate whether this decomposition is complete.

## Context

### What prompted this

The user ran a manual architecture audit on a project (hassette) by dispatching both the `architect` agent (structural mapping, Mermaid diagrams, gap analysis) and the `researcher` agent (deep pattern analysis, web research, coupling investigation) in parallel, then synthesizing their reports manually. Both agents converged on core findings but surfaced unique insights the other missed. The user now wants to make this repeatable, but before committing to the two-agent split, wants to explore whether there are coverage gaps, whether additional agents would help, or whether a fundamentally different structure would be better.

### Current state

The Claudefiles repo has a rich agent ecosystem with clear role boundaries:

| Agent | Model | Tools | Primary Role |
|-------|-------|-------|-------------|
| `architect` | Sonnet | Read/Grep/Glob/Write/Edit | Structural mapping, Mermaid diagrams, interface documentation, gap analysis. Writes to `docs/`. Read-only for source code. |
| `researcher` | Opus | Read/Grep/Glob/Bash/Write/WebSearch/WebFetch/Task | Deep codebase investigation, web research, structured research briefs. Can run git commands, package managers. |
| `integration-reviewer` | Sonnet | Read/Grep/Glob/Bash | Duplication, misplacement, naming drift, coupling, orphaned code. Diff-focused (reviews changes). |
| `code-reviewer` | Sonnet | Read/Grep/Glob/Bash | Correctness, security, code quality, performance. Diff-focused. |
| `qa-specialist` | Sonnet | Read/Grep/Glob/Bash | Adversarial testing, edge cases, test coverage. Writes and runs tests. |
| `Explore` | Haiku | Read/Grep/Glob | Fast read-only codebase navigation. Cheapest option. |

**Key agent capability gaps relevant to architecture audit:**
- **No agent has AST parsing tools** -- all analysis is done by reading source code directly via Read/Grep/Glob
- **architect** cannot run commands (no Bash), so it cannot run `git log` for churn analysis, `pip list` for dependency inventory, or any static analysis tools
- **researcher** has the richest toolset (Bash, WebSearch) but is Opus-model (most expensive) and designed for single-topic investigation, not multi-dimensional auditing
- **integration-reviewer** and **code-reviewer** are diff-focused -- they review changes against existing patterns, not the overall system health

**Existing skills with overlapping concerns:**
- `mine.challenge` -- adversarial review of artifacts via 3-5 parallel critics. Mature synthesis pipeline with findings taxonomy, severity system, and resolution protocol. Operates on a specific target, not whole-codebase health.
- `mine.eval-repo` -- third-party repo evaluation with 4 parallel subagents (history, tests, quality, API). Closest structural precedent for a multi-agent audit, but designed for external repos.
- `mine.research` -- deep investigation dispatching the researcher agent. Single-agent, single-topic.
- `i-audit` -- frontend-specific quality audit (a11y, performance, theming, responsive). Read-only diagnostic. Good output format precedent.

### Key constraints

1. **Read-only** -- the skill produces a report, never modifies code
2. **Agent tool dispatch only** -- no custom scripts, no AST tooling
3. **LLM-approximated metrics** -- coupling, cohesion, dependency depth, fan-in/fan-out must all be estimated by reading code, not computed precisely
4. **Cross-language** -- must work on Python and TypeScript without language-specific tooling
5. **Cost awareness** -- researcher runs on Opus ($$$); architect on Sonnet; Explore on Haiku. The decomposition should use expensive models only where they add clear value.

## Feasibility Analysis

### What an architecture audit needs to cover

Based on established tools (ArchUnit, jQAssistant, Sonargraph, dependency-cruiser, NDepend) and architecture review frameworks (ARDURA six-dimension model, ATAM, GitHub Well-Architected checklist), a comprehensive architecture audit covers these categories:

| Category | Sub-concerns | Can LLM approximate? |
|----------|-------------|---------------------|
| **Structural integrity** | Module boundaries, layering, separation of concerns, package organization | Yes -- reading directory structure, imports, and file contents |
| **Coupling analysis** | Afferent/efferent coupling, dependency depth, fan-in/fan-out, circular dependencies | Partially -- can trace imports and identify obvious cycles, but precise metrics require tooling |
| **Cohesion analysis** | LCOM, relational cohesion, single responsibility adherence | Yes qualitatively -- reading classes and assessing whether methods/attributes relate |
| **Dependency management** | External dependency health, version currency, unused deps, transitive risk | Partially -- can read manifests; researcher can web-search for dep health |
| **Design pattern usage** | Pattern identification, anti-pattern detection, consistency of pattern application | Yes -- core LLM strength |
| **Error handling** | Consistency, coverage, fail-safe vs fail-fast, error propagation patterns | Yes -- grep for exception handling, read patterns |
| **Configuration management** | Secrets handling, env var usage, config file organization | Yes -- grep-based analysis |
| **Convention enforcement** | Naming, file organization, import ordering, module boundaries | Yes -- compare against established patterns |
| **Data flow** | State management, data transformation chains, persistence patterns | Yes -- trace through code |
| **API surface** | Interface design, contract clarity, versioning, backward compatibility | Yes -- read public interfaces |
| **Technical debt signals** | God files/classes, dead code, TODO density, complexity hotspots | Yes -- file size, grep for TODOs, read complex areas |
| **Evolution risk** | Change frequency hotspots, contributor concentration, age of components | Needs git commands (Bash access) |

### What the architect agent covers vs. misses

The architect agent excels at categories 1, 9, and 10 (structural integrity, data flow, API surface). It produces Mermaid diagrams, maps interfaces, and identifies architectural gaps. However, it **cannot**:
- Run `git log` for churn/hotspot analysis (no Bash)
- Run `pip list`/`npm list` for dependency inventory (no Bash)
- Run linters or static analysis (no Bash)
- Search the web for dependency health or pattern best practices (no WebSearch)
- Quantify coupling metrics even approximately without systematic import tracing across many files

### What the researcher agent covers vs. misses

The researcher agent has the richest toolset and can do everything the architect can plus run commands and search the web. It excels at categories 2, 5, 6, 11, and 12 (coupling, patterns, error handling, tech debt, evolution risk). However:
- It is designed for single-topic deep investigation, not multi-dimensional sweeps
- It runs on Opus (most expensive model)
- Its output format (research brief) is designed for proposals, not audit reports
- It dispatches its own Explore subagents internally, adding another layer of agent nesting

### What integration-reviewer and code-reviewer could add

Both are **diff-focused** by design -- they review changes, not system health. Repurposing them for whole-codebase audit would require:
- Overriding their "find changed files" workflow
- Ignoring their severity/verdict framework designed for commit gating
- Losing their core value proposition (they are excellent at what they do precisely because they are narrowly scoped)

**Verdict**: Neither should be repurposed. Their dimensional concerns (duplication, naming drift, coupling detection for integration-reviewer; security, correctness for code-reviewer) should instead be absorbed into the audit agents' briefs.

## Options Evaluated

### Option A: Three Explore subagents + synthesis (recommended for investigation)

**How it works**: Instead of dispatching heavyweight architect/researcher agents, dispatch three purpose-briefed `Explore` subagents (Haiku, read-only, fast) in parallel, each covering a distinct audit dimension. The orchestrating skill context handles synthesis, formatting, and any git/dependency commands itself.

The three subagents, each with a focused brief:

1. **Structure & Boundaries Explorer** -- Module organization, layering, import patterns, circular dependencies, fan-in/fan-out estimation, API surface quality. Covers categories: structural integrity, coupling (import-level), cohesion, API surface.

2. **Patterns & Practices Explorer** -- Design pattern identification, error handling consistency, configuration management, naming conventions, data flow patterns, state management. Covers categories: design patterns, error handling, config management, conventions, data flow.

3. **Health & Risk Explorer** -- Technical debt signals (god files, dead code, TODO density, complexity hotspots), dependency manifest analysis (read pyproject.toml/package.json), test coverage structure, documentation gaps. Covers categories: tech debt, dependency management (manifest-level), convention enforcement.

The orchestrating context (main skill) then:
- Runs `git log --format='%H %an %ae' --since='6 months ago'` for contributor/churn data
- Runs `git log --diff-filter=M --name-only --format=` for change hotspots
- Reads `pyproject.toml`/`package.json` for dependency inventory
- Synthesizes all findings into a structured report with severity, effort/impact matrix, and actionable recommendations

**Pros**:
- **Cost-efficient**: Three Haiku subagents are ~9x cheaper than one Opus researcher agent
- **Parallel with no nesting**: Explore subagents don't spawn their own subagents (unlike researcher which internally dispatches Explore subagents)
- **Clear, non-overlapping briefs**: Each subagent has a focused mandate reducing redundancy
- **Git/dependency analysis stays in the orchestrator**: The skill itself can run Bash commands, so no need to pay for researcher's Bash access
- **Matches existing patterns**: `mine.eval-repo` uses a similar 4-subagent parallel exploration pattern
- **Composable**: Can add a 4th subagent for specific concerns (security, frontend patterns) without changing the core structure

**Cons**:
- **Haiku's analytical ceiling**: Explore subagents use Haiku, which is less capable than Sonnet/Opus for nuanced architectural reasoning. Complex coupling analysis or subtle anti-pattern detection may suffer.
- **No web research**: Explore subagents cannot search the web. Dependency health checks, best-practice comparison, and pattern validation against industry standards are unavailable.
- **No diagram generation**: Explore subagents can only read; they cannot write Mermaid diagrams (no Write tool). The orchestrator would need to generate diagrams itself or skip them.
- **Synthesis burden on orchestrator**: The main context must synthesize three reports plus git data, which consumes context window.

**Effort estimate**: Medium -- the SKILL.md structure is well-understood from existing skills; the main work is crafting effective subagent briefs and the synthesis/output format.

**Dependencies**: None -- uses only existing infrastructure.

### Option B: Architect + Explore subagents (hybrid approach)

**How it works**: Keep the architect agent for what it does best (structural mapping, Mermaid diagrams, interface documentation), but replace the researcher with two Explore subagents for the analytical dimensions. The orchestrating skill handles git commands and synthesis.

1. **Architect agent** (Sonnet, Write access) -- Full structural analysis, produces Mermaid diagrams in `docs/`, maps module boundaries and data flow, identifies architectural gaps. This is the artifact-producing agent.

2. **Patterns & Practices Explorer** (Haiku, read-only) -- Design pattern usage, error handling consistency, convention adherence, anti-pattern detection.

3. **Health & Debt Explorer** (Haiku, read-only) -- Tech debt signals, dependency manifest analysis, test coverage gaps, dead code detection.

The orchestrator runs git commands for churn/hotspot data and synthesizes everything into the final report.

**Pros**:
- **Diagram output**: Architect produces Mermaid diagrams as a tangible artifact, which is one of the most valuable outputs of an architecture audit
- **Sonnet-level structural analysis**: The architect agent runs on Sonnet, giving better structural reasoning than Haiku
- **Artifact separation**: Diagrams go to `docs/`, the audit report goes to a temp file -- clean separation
- **Proven agent**: The architect agent is already mature and well-tested

**Cons**:
- **Architect's narrow brief**: The architect agent has a strong existing identity ("high-level big picture", "interfaces in, interfaces out") that may resist a detailed coupling/cohesion analysis brief
- **Write side-effects**: The architect writes to `docs/diagrams/` -- the audit skill claims to be read-only but would create documentation artifacts. This is arguably a feature, not a bug, but it needs to be explicit.
- **Mixed cost profile**: One Sonnet agent + two Haiku agents is cheaper than Opus but more expensive than all-Haiku
- **Architect's iteration loop**: The architect agent has an "iterate until no TBD remain" workflow that conflicts with a single-pass audit

**Effort estimate**: Medium -- similar to Option A but with the added complexity of managing architect's existing behavioral patterns within the audit context.

**Dependencies**: None new.

### Option C: Single researcher agent with structured brief (do less)

**How it works**: Skip multi-agent orchestration entirely. Dispatch a single researcher agent with a comprehensive architecture audit brief that covers all dimensions. The researcher already knows how to dispatch its own Explore subagents internally, run git commands, and search the web. The SKILL.md is minimal -- it frames the audit questions, dispatches the researcher, and presents the results.

**Pros**:
- **Simplest implementation**: One agent dispatch, one output file, minimal synthesis
- **Full capability access**: Researcher has Bash, WebSearch, and spawns its own Explore subagents -- no capability gaps
- **Proven workflow**: The researcher agent's internal Phase 1/2/3 structure handles multi-dimensional investigation
- **Deep analysis**: Opus model gives the highest quality reasoning for complex architectural concerns

**Cons**:
- **Most expensive per invocation**: Opus pricing for every audit run
- **Single-agent bottleneck**: All dimensions compete for attention within one agent's context window. The researcher is designed for deep single-topic investigation, not broad multi-dimensional sweeps.
- **Nested subagent overhead**: Researcher dispatches its own Explore subagents, which adds latency and complexity vs. the orchestrating skill dispatching them directly
- **Output format mismatch**: Researcher produces a "research brief" format designed for proposals, not audit findings. Would need a custom output template.
- **No diagrams**: Researcher doesn't produce Mermaid diagrams

**Effort estimate**: Small -- the SKILL.md is essentially a thin wrapper around a researcher dispatch with a custom brief.

**Dependencies**: None new.

## Concerns

### Technical risks

1. **Haiku's analytical depth** (Options A, B): The core risk is whether Haiku-powered Explore subagents can reliably detect subtle architectural issues like implicit coupling through shared data formats, inconsistent error handling patterns, or design pattern misapplication. Testing on real codebases is needed to validate. The researcher agent on Opus was specifically chosen for deep investigation because Haiku misses nuance.

2. **LLM-approximated metrics accuracy**: Fan-in/fan-out, coupling depth, and cohesion metrics approximated by reading imports are inherently imprecise. An LLM reading `from foo import bar` can count import relationships, but it cannot easily trace runtime dependencies, dynamic imports, or framework-injected dependencies. The audit should clearly label these as "approximate" and not present them as precise measurements.

3. **Codebase size scaling**: For large codebases (500+ files), Explore subagents may not be able to read enough files to form accurate assessments. The skill should include a file-count check and adjust strategy (e.g., sampling top-level modules, focusing on high-churn areas from git history).

### Complexity risks

1. **Synthesis quality**: Combining 3+ subagent reports plus git data into a coherent, non-redundant audit report is non-trivial. The `mine.challenge` skill's synthesis approach (dedicated synthesis subagent) is proven but adds another agent dispatch. The `mine.eval-repo` approach (inline synthesis) is simpler but may produce lower quality output.

2. **Brief engineering**: The quality of subagent output is dominated by brief quality. Three different briefs, each covering different dimensions, each needing to produce structured, comparable output -- this is the hardest part to get right and will require iteration.

3. **Overlap management**: Even with focused briefs, subagents will notice things outside their mandate. Structural issues surface when looking at patterns; pattern issues surface when looking at structure. The synthesis step must handle this gracefully.

### Maintenance risks

1. **Agent prompt drift**: If the architect or researcher agent prompts evolve (they are actively maintained), the audit skill's briefs may fall out of sync. Option A (all Explore subagents) avoids this because Explore is a generic type with no persona to drift.

2. **Output format evolution**: If the audit produces a specific findings format, consuming skills (like a future `mine.define` handoff) would depend on that format. Starting with a simple Markdown report (no machine-parseable contract) is safer.

3. **Scope creep**: Architecture audits are infinitely expandable. The skill needs a clear "done when" definition to prevent it from becoming a kitchen-sink analysis tool.

## Open Questions

- [ ] **Haiku vs Sonnet for analytical subagents**: Should the audit use `Explore` (Haiku) or `general-purpose` (Sonnet) subagents? The cost difference is 3x per subagent. Testing on a real codebase (hassette or this repo) would reveal whether Haiku misses findings that Sonnet catches.

- [ ] **Diagram generation**: Should the audit produce Mermaid diagrams as artifacts, or is the textual report sufficient? If diagrams are desired, the architect agent (Option B) is the natural choice. If not, Option A is simpler and cheaper.

- [ ] **Web research inclusion**: Should the audit include web research for dependency health, pattern best practices, or security advisories? If yes, a researcher dispatch or a separate WebSearch step in the orchestrator is needed.

- [ ] **Output format**: Should the audit produce a structured findings format (like mine.challenge) for downstream consumption, or a narrative Markdown report (like mine.research)? The answer depends on whether there will be a "fix the audit findings" workflow downstream.

- [ ] **Scope control**: Should the skill audit the entire codebase by default, or require the user to specify a module/directory? Whole-codebase audits risk being too broad; module-scoped audits risk missing cross-cutting concerns.

- [ ] **Overlap with mine.challenge**: When the user runs `/mine.challenge` on a whole codebase (empty args, no target), it already does a form of architectural review via its three generic critics. Should `mine.architecture-audit` be positioned as a deeper, more structured alternative, or should it be integrated into challenge's workflow?

## Recommendation

**Start with Option A (three Explore subagents + orchestrator synthesis) but prototype on a real codebase before committing.**

The reasoning:

1. **Cost discipline**: Opus researcher costs ~9x more than Haiku Explore subagents. For a skill that will be invoked frequently across projects, cost matters. If Haiku proves insufficient, upgrading individual subagents to Sonnet (`general-purpose`) is a targeted fix.

2. **Architectural clarity**: The orchestrating skill owns synthesis, git commands, and output formatting. Subagents are pure data collectors with focused briefs. This matches the pattern in `mine.eval-repo` and avoids the nesting complexity of researcher-spawning-Explore-subagents.

3. **No agent persona coupling**: Using Explore subagents means the audit skill fully controls the brief, output format, and analysis dimensions. No dependency on architect or researcher agent evolution.

4. **Diagrams can be added later**: If the user wants diagrams, a follow-up can add an architect dispatch as a fourth subagent (Option B hybrid). This is additive, not architectural -- it doesn't change the core structure.

5. **The manual run proved the concept**: Both architect and researcher converged on core findings. This suggests the findings are discoverable by reading code -- the question is whether cheaper models can discover them too. That is a prototyping question, not a design question.

**Caveat**: If prototyping reveals that Haiku subagents miss critical findings that Sonnet/Opus catches, the fallback is Option B (architect for structure, Sonnet subagents for analysis). The SKILL.md structure is the same either way -- only the `subagent_type` and brief contents change.

### Suggested next steps

1. **Prototype the subagent briefs**: Write draft briefs for the three Explore subagents and test them manually against hassette or this repo. Compare output quality against the manual architect+researcher run.
2. **Write a design doc via `/mine.define`**: Formalize the skill structure, output format, Phase 1-2-3 workflow, and user interaction (scope selection, output destination).
3. **Consider running `/mine.challenge` on the design doc**: The two-agent vs three-subagent decomposition and the Haiku-vs-Sonnet tradeoff are exactly the kind of design decisions that benefit from adversarial review.

## Sources

- [AI-powered Code Review with LLMs: Early Results (arxiv)](https://arxiv.org/html/2404.18496v2)
- [Exploring the best open-source AI code review tools in 2025 (Graphite)](https://graphite.com/guides/best-open-source-ai-code-review-tools-2025)
- [9 Software Architecture Metrics for Sniffing Out Issues (Beningo)](https://www.beningo.com/9-software-architecture-metrics-for-sniffing-out-issues/)
- [Architect's Guide to Cohesion and Coupling Metrics (Medium)](https://medium.com/@kachmarani/an-architects-guide-to-cohesion-and-coupling-metrics-for-bussiness-stakeholders-f15ff595d0d5)
- [Software Architecture Review: Evaluation Criteria (ARDURA Consulting)](https://ardura.consulting/blog/software-architecture-review-checklist/)
- [ArchUnit: Architectural Testing for Java Applications (Medium)](https://medium.com/@emedinam/archunit-architectural-testing-for-java-applications-46a515d1b421)
- [ArchUnit official site](https://www.archunit.org/)
- [jQAssistant architecture exploration (Hascode)](https://www.hascode.com/software-architecture-exploration-and-validation-with-jqassistant-neo4j-and-cypher/)
- [dependency-cruiser GitHub](https://github.com/sverweij/dependency-cruiser)
- [Automated Software Architecture Design Recovery from Source Code Using LLMs (ECSA 2025)](https://conf.researchr.org/details/ecsa-2025/ecsa-2025-call-for-research-papers/7/Automated-Software-Architecture-Design-Recovery-from-Source-Code-Using-LLMs)
- [Software Architecture Meets LLMs: A Systematic Literature Review (arxiv)](https://arxiv.org/pdf/2505.16697)
- [VoltAgent awesome-claude-code-subagents architect-reviewer](https://github.com/VoltAgent/awesome-claude-code-subagents/blob/main/categories/04-quality-security/architect-reviewer.md)
- [GitHub Well-Architected Checklist for Architecture](https://wellarchitected.github.com/library/architecture/checklist/)
