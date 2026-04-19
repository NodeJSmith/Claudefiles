# Challenge Findings — Architecture Audit Skill Research Brief
Date: 2026-04-19
Target: /home/jessica/Claudefiles/.claude/worktrees/221-222-227/design/research/2026-04-19-architecture-audit/research.md
Temp dir: /tmp/claude-mine-challenge-E2tsrD
Warnings: none
Format-version: 2

## Finding 1: Recommendation Commits to Haiku Before Capability Is Validated
- severity: HIGH
- confidence: 3/3 (Senior, Architect, Adversarial)
- type: Approach-now
- design-level: Yes
- resolution: User-directed
- raised-by: Senior + Architect + Adversarial
- summary: The brief recommends Option A (Haiku Explore subagents) as the default while explicitly acknowledging that Haiku's adequacy for architectural analysis is an unresolved open question — cost preference is used to answer a capability question the brief itself says is unanswered.
- why-it-matters: If Haiku misses the nuanced findings that motivated the skill, users will trust the audit output while it silently under-reports; correcting this after shipping requires redesigning the subagent briefs, not just swapping a model parameter.
- evidence: research.md §"Concerns / Technical risks" item 1, research.md §"Open Questions" item 1, research.md §"Recommendation" item 1, research.md §"Concerns / Technical risks / Haiku's analytical depth", rules/common/performance.md (Haiku disqualifiers)
- design-challenge: The brief states "The researcher agent on Opus was specifically chosen for deep investigation because Haiku misses nuance" — then recommends Haiku-based exploration for an architecture audit. What evidence from the hassette run justifies confidence that Haiku would have reproduced those findings?
- options: Option A — Change the recommendation to "Prototype before committing to a model tier": write the briefs, run one subagent dimension with Haiku and the same with Sonnet on hassette, compare output to known architect+researcher findings, then choose. / Option B — Accept Option A as written but reframe it as a hypothesis with stated acceptance criteria — define what "Haiku is good enough" means (e.g., 90%+ of findings reproduced) and the trigger for upgrading individual subagents to Sonnet.
- recommendation: Option B — retains implementation momentum while turning an implicit assumption into an explicit testable contract; Option A delays the design doc step without sufficient additional benefit.

## Finding 2: Synthesis Mechanism Is Underspecified for the Hardest Problem
- severity: HIGH
- confidence: 3/3 (Senior, Architect, Adversarial)
- type: Gap
- design-level: Yes
- resolution: User-directed
- raised-by: Senior + Architect + Adversarial
- summary: The brief names synthesis quality as the single hardest implementation challenge, then proposes solving it inline in the orchestrating context with no output contract, deduplication strategy, or conflict-resolution rules.
- why-it-matters: The synthesis mechanism determines the skill's most user-visible output quality; leaving it undefined means the hardest design decision is deferred to implementation with no guidance for when two subagents produce incompatible severity assessments for the same issue.
- evidence: research.md §"Concerns / Complexity risks / Synthesis quality", research.md §"Concerns / Complexity risks / Overlap management", research.md §"Options / Option A" (synthesis = inline, no structure specified), skills/mine.challenge/SKILL.md Phase 3 lines 363–440 (dedicated synthesis subagent with explicit deduplication and conflict rules)
- design-challenge: The research brief identifies synthesis quality as the hardest problem and cites mine.challenge's dedicated synthesis subagent as "proven" — then recommends inline synthesis without explaining why the proven approach is skipped. What are the deduplication and conflict rules for inline synthesis?
- options: Option A — Commit to a dedicated synthesis subagent (like mine.challenge Phase 3) that receives all three subagent reports and applies explicit deduplication, tagging, and conflict-resolution rules — costs more but mirrors proven pattern. / Option B — Commit to inline synthesis but specify the rules explicitly in the research brief: what counts as a duplicate, how severity conflicts are resolved, what the output schema looks like.
- recommendation: Option A — the mine.challenge synthesis subagent pattern exists precisely because inline synthesis at scale produces unreliable deduplication; the extra cost is one agent dispatch and the quality ceiling difference is significant for a correctness-sensitive tool.

## Finding 3: mine.eval-repo Is a Misleading Structural Precedent
- severity: HIGH
- confidence: 3/3 (Senior, Architect, Adversarial)
- type: Approach-now
- design-level: Yes
- resolution: User-directed
- raised-by: Senior + Architect + Adversarial
- summary: The brief cites mine.eval-repo as "the closest structural precedent" for Option A, but eval-repo operates on external repos with orthogonal dimensions, uses a Bash subagent (not Explore) for git commands, and targets a binary adoption verdict — none of which transfer to an owned-codebase health audit; mine.challenge is the closer structural match.
- why-it-matters: Inheriting the wrong structural precedent causes implementation to silently adopt eval-repo assumptions (external clone, binary verdict, Bash subagent, gh API metadata) that don't apply, while missing mine.challenge patterns (structured findings taxonomy, synthesis subagent, severity/type/resolution protocol) that do apply.
- evidence: research.md line 44 and line 127 (eval-repo cited as "closest precedent"), skills/mine.eval-repo/SKILL.md lines 1–10 (adoption verdict), skills/mine.eval-repo/SKILL.md line 28 (Subagent 1 is Bash not Explore), skills/mine.challenge/SKILL.md lines 149–195 (adversarial analysis of owned artifacts with structured findings), skills/mine.eval-repo/SKILL.md line 207 ("Audit your own codebase — use /mine.challenge for that")
- design-challenge: If the architecture audit's goal is "find actionable design problems in an owned codebase," why is the synthesis model taken from a third-party adoption evaluator rather than the mature adversarial review skill that already solves this problem for owned artifacts?
- options: Option A — Reframe the structural precedent to mine.challenge: adopt its findings taxonomy (severity/type/design-level/resolution) for the audit output; treat the three Explore subagents as focused data-collector critics; use the challenge synthesis pattern for Phase 3. Note explicitly where architecture-audit diverges (persistent report, whole-codebase scope, git metrics). / Option B — Keep eval-repo as the structural reference but enumerate every place the audit diverges from eval-repo's pattern so implementation does not accidentally inherit those assumptions.
- recommendation: Option A — mine.challenge is architecturally closer to the use case, and adopting its findings taxonomy creates a composition surface with the existing caliper workflow; Option B produces an isolated audit artifact with a misleading ancestry.

## Finding 4: Output Format Is Undefined — No Contract With Consumers
- severity: HIGH
- confidence: 2/3 (Architect, Adversarial)
- type: Gap
- design-level: Yes
- resolution: User-directed
- raised-by: Architect + Adversarial
- summary: The brief explicitly leaves output format as an open question and treats "start with simple Markdown" as a safe default — but an undefined output format prevents downstream composition, cannot be versioned, and defers a design obligation rather than resolving it.
- why-it-matters: Every consumer of the audit report must reverse-engineer the format from whatever the implementation produces; treating format ambiguity as a "safety feature" forecloses the downstream workflows (mine.define handoff, fix-audit-findings) that are the skill's stated value.
- evidence: research.md §"Open Questions" item 4, research.md §"Recommendation" (no output format specification as prototyping prerequisite), skills/mine.challenge/SKILL.md lines 92–113 (format as a first-class versioned contract), skills/mine.eval-repo/SKILL.md line 207 (current redirect to mine.challenge that mine.architecture-audit would supersede)
- design-challenge: "Starting with a simple Markdown report is safer" prevents output format lock-in but also prevents the skill from being composed with anything. If the user runs this audit and wants to route findings to mine.define, what field does mine.define read?
- options: Option A — Define a minimum output contract now: required header (scope, date, model used, file count) and a per-finding schema with at least severity, area, and description fields; narrative prose fills the body but findings are structured. / Option B — Explicitly scope V1 as a terminal output (human-readable report only) and add a "What this skill does NOT do" section stating it cannot be composed with mine.define — honest about the design decision rather than leaving it open.
- recommendation: Option A — a lightweight schema costs little to define now and avoids a painful retrofit later; Option B forecloses composition unnecessarily for a skill designed to feed planning workflows.

## Finding 5: "Non-Overlapping Briefs" Is the Hardest Assumption and Gets No Design Attention
- severity: HIGH
- confidence: 2/3 (Senior, Architect)
- type: Gap
- design-level: Yes
- resolution: User-directed
- raised-by: Senior + Architect
- summary: Option A's design depends on three subagents producing non-overlapping complementary findings, but the research brief provides no mechanism for detecting or handling overlap — the synthesis step is assigned the problem without any tools to solve it.
- why-it-matters: Architecture analysis dimensions (coupling, structure, patterns) share underlying evidence; a finding about import cycles surfaces in both Structure & Boundaries and Patterns & Practices briefs, and without conflict detection, the audit report will contain redundant or contradictory severity assessments for the same issue.
- evidence: research.md §"Complexity risks" item 3, research.md §"Concerns / Complexity risks / Brief independence", senior.md Finding 4 (eval-repo dimensions are data-type-segregated; audit dimensions are concern-segregated and overlap by nature), skills/mine.challenge/SKILL.md Phase 3 (TENSION identification and conflict escalation rules)
- design-challenge: Can you name a specific finding about a real codebase that Subagent 1 (Structure & Boundaries) would produce that Subagent 2 (Patterns & Practices) would definitely not also produce? If not, the non-overlapping brief assumption is false.
- options: Option A — Commit to a synthesis subagent with explicit overlap rules: when two subagents cite the same file/module with different severity assessments, escalate to the higher severity and tag as cross-agent confirmed (mirrors mine.challenge TENSION mechanism). / Option B — Design subagent output as a structured list with severity and dimension tags (not prose), making synthesis a mechanical merge rather than a quality judgment — independent of synthesis approach, structured output removes ambiguity about what two agents found at the same location.
- recommendation: Option A if Finding 2 resolves to a dedicated synthesis subagent; Option B as a prerequisite for inline synthesis — either way, structured subagent output format is a prerequisite for usable synthesis regardless of which Finding 2 option is chosen.

## Finding 6: Scope Control Is Unresolved With Architectural Consequences
- severity: MEDIUM
- confidence: 3/3 (Senior, Architect, Adversarial)
- type: Gap
- design-level: Yes
- resolution: User-directed
- raised-by: Senior + Architect + Adversarial
- summary: The brief identifies whole-codebase vs. module-scoped as an open question, acknowledges the whole-codebase default doesn't scale past ~300–500 files, and then recommends "start with Option A" without specifying which scope default Option A uses.
- why-it-matters: "Audit entire codebase" vs "audit a specific module" have different subagent brief designs, different output structures, and different user interaction patterns; leaving scope control undefined means the SKILL.md will handle both at implementation time without design guidance.
- evidence: research.md §"Open Questions" item 5, research.md §"Concerns / Technical risks / Codebase size scaling", skills/mine.challenge/SKILL.md lines 168–216 (scope handled via $ARGUMENTS with explicit empty-args interaction design), skills/mine.eval-repo/SKILL.md (always audits full repo — not applicable to user's own codebase)
- design-challenge: If a user runs mine.architecture-audit on a 1000-file monorepo and the three Haiku subagents can each only meaningfully analyze ~100 files, what is the output? This is not a prototyping question — it determines whether the three-subagent structure can work at all for typical enterprise codebases.
- options: Option A — Require explicit scope as a required argument (no whole-codebase default); the skill audits a specified module or directory deeply; cross-cutting concerns are surfaced at import boundaries at the scope edge. / Option B — Default to whole-codebase with a file-count gate: above N files (suggest 300), shift subagent strategy from "read everything" to "sample top-level modules by churn from git log" and explicitly note coverage limitations in the report.
- recommendation: Option B — whole-codebase is the natural user intent for an architecture audit, and automatic degradation with explicit coverage reporting is more useful than forcing users to pre-scope; set N=300 as a concrete threshold rather than leaving it to implementation.

## Finding 7: mine.challenge Overlap Creates a Positioning Gap
- severity: MEDIUM
- confidence: 3/3 (Senior, Architect, Adversarial)
- type: Approach-later
- design-level: Yes
- resolution: User-directed
- raised-by: Senior + Architect + Adversarial
- summary: The brief leaves the mine.challenge overlap as an open question, but this has a concrete consequence: capabilities.md will need trigger phrases that route users correctly between the two skills — without resolved positioning, the table will have two entries for similar phrases with no decision rule.
- why-it-matters: mine.eval-repo currently redirects whole-codebase audits to mine.challenge; adding mine.architecture-audit without updating that redirect and resolving the trigger phrase overlap creates an inconsistency that surfaces at the moment of shipping.
- evidence: research.md §"Open Questions" item 6, skills/mine.challenge/SKILL.md lines 198–214 (empty-args challenge performs codebase recon and architectural review), skills/mine.eval-repo/SKILL.md line 207 ("Audit your own codebase — use /mine.challenge for that"), rules/common/capabilities.md (trigger phrase routing table that will need updating)
- design-challenge: If both skills can produce whole-codebase findings, what is the one-sentence differentiation that tells a user "use mine.architecture-audit not mine.challenge" — and does that differentiation require mine.architecture-audit to exist as a separate skill at all?
- options: Option A — Resolve the positioning in this brief with a one-sentence differentiation: "mine.architecture-audit = structured, dimension-specific, produces a persistent audit report; mine.challenge = adversarial, targets specific design decisions, produces severity-tagged actionable findings for immediate resolution." Update mine.eval-repo and capabilities.md when the skill ships. / Option B — Investigate whether mine.architecture-audit should be a mode or target-type of mine.challenge, sharing synthesis infrastructure and output format while avoiding a separate skill.
- recommendation: Option A — the skills serve different affordances (persistent health report vs. adversarial session-scoped findings), the differentiation is real and explainable, and coupling them would add complexity to mine.challenge's already complex dispatch logic.

## Finding 8: Option C Rejection Rests on a False Factual Claim
- severity: MEDIUM
- confidence: 1/3 (Senior)
- type: Approach-now
- design-level: Yes
- resolution: Auto-apply
- raised-by: Senior
- summary: The brief dismisses Option C (single researcher agent) partly on "single-agent bottleneck" grounds, but researcher.md Phase 1 already dispatches four parallel Explore subagents internally — the bottleneck framing is factually incorrect.
- why-it-matters: The recommendation to reject Option C rests partially on a false claim; correcting it clarifies that the real Option A vs. Option C difference is synthesis ownership and output format, not parallelism — which is a more honest trade-off comparison.
- evidence: research.md §"Option C / Cons" item 2 ("Single-agent bottleneck: All dimensions compete for attention within one agent's context window"), agents/researcher.md Phase 1 lines 69–116 (launches 4 parallel Explore subagents)
- design-challenge: Given that researcher internally launches 4 parallel Explore subagents, the bottleneck concern is factually wrong. Does correcting it change the recommendation?
- better-approach: Revise Option C Con #2 to: "Output format and synthesis ownership: researcher produces a research narrative optimized for decision-making, not a structured audit report; synthesis is internal to researcher and not configurable for architecture-specific deduplication rules." This is accurate and does not change the recommendation.

## Finding 9: Git Commands in Orchestrator Need Validation Against Claude Code Bash Context
- severity: MEDIUM
- confidence: 2/3 (Senior, Adversarial)
- type: Fragility
- design-level: No
- resolution: Auto-apply
- raised-by: Senior + Adversarial
- summary: The brief assigns git log commands with complex format strings to the orchestrating skill context but does not verify these patterns work with the Claude Code Bash tool's eval wrapper — specifically the empty --format= string pattern may produce unexpected output.
- why-it-matters: If git commands fail silently in the orchestrator context (empty format string issue, subdirectory execution, non-git codebase), the Evolution Risk section of the audit report silently disappears with no user indication.
- evidence: research.md §"Option A" orchestrator block (git log patterns listed), CLAUDE.md worktree root ("Never use $(…) command substitution — silently fails"), adversarial.md Finding 4 (empty --format= string concern), research.md §"Feasibility Analysis" table "Evolution risk" row
- design-challenge: Have the proposed git log command patterns (especially --format= with empty format string) been tested in the Claude Code Bash context, or is this assumed to work because mine.challenge mentions git log?
- better-approach: Add to Recommended next steps: "Before writing the SKILL.md, validate the git log command patterns — especially git log --diff-filter=M --name-only --format= — in the Claude Code Bash context against hassette. Add an explicit git availability check as Phase 0 (detect .git directory; if absent, skip git sections with a visible note in the report)."

## Finding 10: File-Count Gate Is a Hard Requirement, Not an Implementation Detail
- severity: MEDIUM
- confidence: 1/3 (Senior)
- type: Fragility
- design-level: No
- resolution: Auto-apply
- raised-by: Senior
- summary: The brief mentions a file-count check for large codebases as a future implementation detail, but without it, Haiku subagents on large codebases will silently produce truncated analysis that users treat as authoritative.
- why-it-matters: Haiku hitting its reasoning limit midway through tracing import cycles across a 400-file codebase will produce a plausible-but-incomplete coupling map with no indication it stopped early — there is no error signal, only missing findings.
- evidence: research.md §"Concerns / Technical risks / Codebase size scaling" ("The skill should include a file-count check and adjust strategy"), research.md §"Recommendation" (file-count gate not listed as a requirement)
- design-challenge: When Haiku hits its reasoning limit midway through a large codebase, will the output say "I could not complete this analysis" or will it produce a plausible-but-incomplete coupling map?
- better-approach: Add to the Recommendation's Caveats section: "The file-count gate is a hard requirement for Option A, not an implementation detail. Specify the threshold (suggest 300 files) and the adjusted strategy (sample top-level modules by churn from git log) in the research brief before the design doc phase begins."

## Finding 11: Subagent Brief Change Surface Creates Maintenance Risk
- severity: MEDIUM
- confidence: 1/3 (Architect)
- type: Structural
- design-level: Yes
- resolution: User-directed
- raised-by: Architect
- summary: With all three subagent briefs embedded inline in the SKILL.md, every change to audit dimensions requires editing the SKILL.md in multiple places simultaneously — there is no structural isolation of the change surface.
- why-it-matters: Inline brief storage mirrors no existing precedent in this repo — mine.challenge uses separate persona files precisely to isolate change surface; when a new audit dimension is added, there is no structure preventing the existing briefs from becoming silently inconsistent with the new one.
- evidence: research.md §"Options / Option A" (subagent mandates as inline natural-language descriptions), skills/mine.challenge/personas/generic/ (each critic's focus in a dedicated persona file), research.md §"Concerns / Complexity risks / Brief engineering" ("will require iteration" — acknowledged but change surface not isolated)
- design-challenge: When the user wants to add a "Security Patterns Explorer" subagent six months from now, how many files change — and what prevents the three existing briefs from becoming silently inconsistent with the new fourth?
- options: Option A — Define each audit dimension as a separate persona/brief file (analogous to mine.challenge's personas/ directory); SKILL.md reads them at runtime; adding a dimension = adding a file with no SKILL.md changes. / Option B — Keep briefs inline but add an explicit "Audit Dimensions" section as the canonical source that the orchestration logic references by name; changing a dimension requires editing one section only.
- recommendation: Option A if Finding 2 resolves to mine.challenge synthesis pattern (persona files are the natural fit); Option B is acceptable if synthesis stays inline, as canonical-section discipline is sufficient isolation for a simpler skill structure.
