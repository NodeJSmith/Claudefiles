---
proposal: "Extract hardcoded personas from skills (challenge critics, brainstorm thinkers) into a selectable library with runtime matching based on the artifact being reviewed"
date: 2026-03-29
status: Draft
flexibility: Exploring
motivation: "Skills like mine.challenge and mine.brainstorm hardcode their personas. Different targets (Python backend vs Svelte frontend vs SKILL.md) would benefit from different specialist perspectives."
constraints: "Must work within Claude Code's Agent tool and SKILL.md conventions. No external runtime, no Python scripts for selection logic. All selection happens in-prompt."
non-goals: "Not building a general-purpose agent framework. Not replacing the Agent tool's subagent_type system."
depth: deep
---

# Research Brief: Runtime Persona Selection for Parallel Subagents

**Initiated by**: Investigating prior art and best practices for extracting hardcoded personas from skills into a selectable library with runtime matching.

## Context

### What prompted this

Skills like `mine.challenge` and `mine.brainstorm` launch parallel subagents with hardcoded personas. `mine.challenge` always uses the same three critics (Skeptical Senior Engineer, Systems Architect, Adversarial Reviewer) regardless of whether the target is Python backend code, a Svelte component, a SKILL.md file, or a research brief. `mine.brainstorm` always uses the same four thinkers (Pragmatist, User Advocate, Moonshot, Wildly Imaginative). The hypothesis is that different targets would benefit from different specialist perspectives -- a security-focused critic for auth code, a prompt engineering critic for SKILL.md files, a data modeling critic for schema changes.

### Current state

**How personas are defined today**: Each persona is inline in its SKILL.md file as a named section with a persona description, characteristic question, focus areas, and (for brainstorm) full prompt template text. There is no shared format, no tagging, no metadata beyond the prose.

Key files:
- `skills/mine.challenge/SKILL.md` (lines 213-252): Three critic personas -- Skeptical Senior Engineer, Systems Architect, Adversarial Reviewer
- `skills/mine.brainstorm/SKILL.md` (lines 72-188): Four thinker personas -- Pragmatist, User Advocate, Moonshot, Wildly Imaginative
- `skills/mine.grill/SKILL.md` (lines 43-68): Five interrogation lenses (Product, Design, Engineering, Scope, Adversarial) -- not subagents but thematic focus areas
- `skills/mine.visual-qa/SKILL.md`: Two or three reviewer personas (Visual Craft Critic, Flow Walker, Content/Clarity)

**How selection works today**: It doesn't. Every invocation uses every persona. The `--target-type` flag in `mine.challenge` adjusts what critics *focus on* (e.g., "This is a `spec` target -- focus on requirement completeness") but does not change *which* critics run.

**Prior internal research**: `design/research/2026-03-17-visual-qa-personas.md` investigated optimal persona configuration for `mine.visual-qa`. Key finding: "The persona prompts in mine.visual-qa completely override the agent definitions. The detailed prompt given to each agent is what drives behavior; the agent type provides ambient context that's mostly irrelevant." This confirms that personas are prompt-driven, not framework-driven.

### Key constraints

- All orchestration happens in-prompt within SKILL.md files. There is no Python runtime, no external selection service, no database.
- The Agent tool accepts a prompt string and a `subagent_type`. Persona selection must resolve to a prompt string before the Agent call.
- Claude Code context window is the binding constraint -- loading a persona library means consuming tokens.
- Skills must remain self-contained and debuggable. A skill author reading the SKILL.md should understand what personas will run without chasing references across multiple files.

## Prior Art Summary

### Multi-agent frameworks: How they handle persona/role selection

**CrewAI** defines agents with `role`, `goal`, and `backstory` fields. Roles are typically hardcoded per crew. Dynamic selection is a known pain point -- a [community discussion](https://community.crewai.com/t/dynamic-agent-selection-in-crewai-enhancing-efficiency-without-hardcoding/2734) shows developers wanting to "dynamically select and run only agents relevant to the user's query." Proposed solutions: (1) hierarchical process with a manager agent that delegates (unreliable -- hallucination issues), (2) Flows with intent classification (more deterministic, preferred by community). CrewAI does not have a persona library or tagging system; roles are defined per-crew.

**AutoGen (Microsoft)** uses `ConversableAgent` and `AssistantAgent` with system prompts. Agent selection happens through conversation patterns and group chat managers. No persona library concept -- agents are instantiated in code with hardcoded system prompts. The v0.4 rewrite added event-driven architecture but still has no runtime role selection mechanism.

**LangGraph** implements routing via conditional edges -- a function examines the current state and routes to the appropriate agent node. This is the closest to what we need: a classifier (LLM-based or rule-based) examines the input and selects which agents to activate. The pattern is well-documented with [routing tutorials](https://dev.to/jamesli/advanced-langgraph-implementing-conditional-edges-and-tool-calling-agents-3pdn) showing input classification followed by agent dispatch.

**Semantic Kernel (Microsoft)** describes "Intelligent Routing Graphs" where the kernel's LLM acts as router, using "function descriptions and conversation history to select the most relevant agent(s) for each turn." Agent selection uses vector similarity matching. Rich function descriptions are "paramount for accurate dynamic routing."

**Amazon Bedrock Inline Agents** allow runtime reconfiguration of agent instructions, tools, and models without redeployment. This is the industrial-grade version of what we're considering -- dynamic persona composition at call time. But it requires an API service layer.

### Adversarial review: Specialization by artifact type

The adversarial code review pattern is well-established. [ASDLC.io](https://asdlc.io/patterns/adversarial-code-review/) documents "council mode" that "spawns task-scoped perspectives selected based on what could break." A [Hacker News discussion](https://news.ycombinator.com/item?id=47360961) on paired adversarial review agents validates the pattern of specialized reviewers (Security Agent, Performance Agent, Architecture Agent, Testing Agent) running in parallel.

The [LobeHub Skills Marketplace](https://lobehub.com/skills/jw409-kinderpowers-adversarial-review) and [MCP Market](https://mcpmarket.com/tools/skills/adversarial-code-reviewer) both list adversarial code review skills for Claude Code, confirming community interest in this pattern. However, none implement dynamic persona selection -- they all hardcode their reviewer set.

### Persona file format standards

Three emerging standards for agent definition files:

1. **Open Agent Format (OAF) v0.8.0**: `AGENTS.md` with YAML frontmatter (`name`, `vendorKey`, `agentKey`, `version`, `slug`, `description`, `author`, `license`, `tags`) + Markdown body. Tags enable discovery. Designed for distribution (`.zip` archives).

2. **Agent Format (agentformat.org)**: Pure YAML with `schema_version`, `metadata` (id, name, version, description), `interface` (input/output types), `action_space` (tools), `execution_policy` (instructions, model, max_steps). JSON Schema validated.

3. **Synkra AIOX**: Markdown with YAML frontmatter containing `persona_profile`, `persona`, `commands`, `dependencies`. Explicit persona section.

All three use YAML frontmatter for metadata + Markdown body for instructions. Tags/labels for discovery are universal. None implement automatic selection -- they're definition formats, not selection systems.

### Research on persona effectiveness

**Critical finding -- personas hurt accuracy, help alignment**: The [PRISM paper](https://arxiv.org/abs/2603.18507) (Hu et al., March 2026) demonstrates that expert personas consistently damage factual accuracy (MMLU: 68.0% vs 71.6% baseline) while improving alignment-dependent tasks (writing, roleplay, structured output). This is directly relevant: our personas are used for *alignment tasks* (structured critique, creative ideation) not factual retrieval, so the pattern is in the helpful zone.

**Persona selection is harder than it looks**: The [same research](https://arxiv.org/html/2311.10054v3) found that "the effect of each persona on model performance varies across questions, making it difficult to reliably identify which persona consistently yields better performance, suggesting that the effect might largely be random." Automatic persona selection via RoBERTa classifiers performed "no better than random selection."

**PRISM's solution -- intent-based routing**: PRISM routes at the query level: a lightweight binary gate (trained on early-layer representations) decides whether to activate the persona adapter for each input. The gate learns which query types benefit from persona activation without explicit supervision. This is too heavy for our use case (requires LoRA fine-tuning) but the principle -- route based on intent classification, not persona matching -- is instructive.

**Solo Performance Prompting (SPP)**: [Wang et al., 2024](https://arxiv.org/abs/2307.05300) showed that a single LLM can dynamically identify and simulate multiple personas per task, with the key finding that "cognitive synergy only emerges in GPT-4 and does not appear in less capable models." The personas are determined dynamically by the task, not from a pre-defined library. This suggests the LLM itself could be the selector.

**The Wharton "Playing Pretend" study**: Found that "telling a model it's an expert in a particular field hinders the model's ability to fetch facts from pretraining data." Again, our use case (structured critique, not factual Q&A) sidesteps this concern.

### Design guidance for effective personas

The [Agentic Thinking blog](https://agenticthinking.ai/blog/agent-personas/) identifies five essential elements: Role, Expertise, Process, Output format, and Constraints. Key anti-patterns: overly broad scope, missing process definition, no output templates, absent constraints, generic roles. The guidance aligns with what `mine.challenge` already does well -- each critic has a named role, specific focus areas, a characteristic question, and shared output format requirements.

## Feasibility Analysis

### What would need to change

| Area | Files affected | Effort | Risk |
|------|---------------|--------|------|
| Persona definitions | New `personas/` directory (5-10 files) | Low | Format design is the hard part |
| mine.challenge | 1 file (SKILL.md) | Medium | Selection logic adds complexity to an already complex skill |
| mine.brainstorm | 1 file (SKILL.md) | Medium | Same complexity concern |
| mine.visual-qa | 1 file (SKILL.md) | Medium | Already has persona overlap issues |
| mine.grill | 1 file (SKILL.md) | Low | Lenses are simpler than full personas |

### What already supports this

- **Target-type classification exists**: `mine.challenge` already classifies targets as `code`, `spec`, `design-doc`, `brief`, `skill-file`, `research`, `other`. This is a natural selection key.
- **Persona structure is consistent**: All existing personas follow the same pattern (name, persona description, characteristic question, focus areas). Extraction to a shared format is straightforward.
- **YAML frontmatter is the codebase convention**: SKILL.md files already use YAML frontmatter. Persona definition files would follow the same pattern.
- **The Agent tool accepts arbitrary prompts**: There's no framework constraint on what gets passed to a subagent. Selection logic just needs to produce the right prompt string.

### What works against this

- **Context window cost**: Loading a persona library to select from means reading all persona files (or at least their metadata) before making a selection. With 10-15 personas, this could add 2-5K tokens of overhead per skill invocation.
- **Selection reliability**: Research consistently shows that automatic persona selection is hard. The PRISM paper needed trained classifiers; simpler approaches (keyword matching, LLM-based selection) may not reliably pick the best personas.
- **Debugging complexity**: Currently, a skill author reads the SKILL.md and knows exactly which personas run. With runtime selection, the personas that ran depend on the input, making debugging harder.
- **Diminishing returns from persona diversity**: The visual-qa-personas research found that "the persona prompts completely override the agent definitions" and that "the differentiation must come from what they're instructed to look for, not who they're pretending to be." Adding more personas doesn't help if the *focus instructions* don't change.
- **No evidence that current personas underperform**: The hypothesis that "different targets need different critics" is untested. The Skeptical Senior Engineer, Systems Architect, and Adversarial Reviewer are domain-agnostic by design. There's no data showing they produce worse results on frontend code vs backend code.

## Options Evaluated

### Option A: Persona Library with Tag-Based Selection

**How it works**: Extract personas into individual files in a `personas/` directory. Each file has YAML frontmatter with tags (`domain: [backend, frontend, infra]`, `skill: [challenge, brainstorm]`, `strength: [security, architecture, ux, performance]`). Skills read persona metadata at invocation time, match tags against the target type and any user-provided `--focus`, and select the top N personas. Selection logic lives in the SKILL.md prompt instructions.

```yaml
# personas/security-critic.md
---
name: Security Critic
type: critic  # critic | thinker | lens
tags: [security, auth, backend, api]
strength: "Runtime risks, auth bypass, injection, privilege escalation"
for-skills: [mine.challenge]
---

**Persona**: Has broken into systems professionally...
**Characteristic question**: "What can an attacker do with this?"
**Focus**: [security-specific focus areas]
```

The SKILL.md would include instructions like: "Read all files in `personas/` with `type: critic`. Match tags against the target type. Select 3 personas with the best tag overlap. If fewer than 3 match, fall back to the default set."

**Pros**:
- Clean separation of persona definitions from skill orchestration logic
- New personas can be added without modifying any SKILL.md
- Tags enable discovery and filtering
- Follows established patterns (OAF, SKILL.md frontmatter conventions)
- Personas become independently testable and challengeable artifacts

**Cons**:
- Selection logic in prose (SKILL.md instructions) is fuzzy -- the LLM interprets "best tag overlap" differently each time
- Reading all persona files adds latency and token overhead on every invocation
- Tag taxonomy must be designed upfront and maintained consistently
- No evidence that tag-based selection produces better results than the current hardcoded set
- Adds a new directory and file convention to learn and maintain

**Effort estimate**: Medium -- persona extraction is mechanical, but selection logic design and testing is non-trivial.

**Dependencies**: None (pure markdown/YAML files).

### Option B: LLM-Selected Personas (Ask the Model to Pick)

**How it works**: Keep persona definitions in a library (same file format as Option A), but instead of tag matching, the orchestrating skill reads the target artifact and asks the LLM to select the best 3 personas from the library. The selection prompt includes persona summaries (name + one-line description) and the target's type/content.

The SKILL.md would include: "Before launching critics, read the persona index (`personas/index.md`). Given the target type and content, select the 3 personas that would provide the most diverse and valuable critique. Explain your selection briefly, then launch the selected personas."

**Pros**:
- The model can make nuanced selections that tag matching cannot (e.g., "this code has complex state management, pick the concurrency specialist")
- No tag taxonomy to maintain -- the model reads persona descriptions and decides
- Aligns with the SPP research finding that capable models can dynamically identify relevant personas

**Cons**:
- Non-deterministic -- the same target may get different persona sets on different runs
- Adds a selection step before the parallel launch, increasing latency
- The model might always pick the same "safe" personas (the PRISM research shows selection is harder than it looks)
- Selection reasoning consumes context tokens
- Harder to debug: "why did it pick these three?"

**Effort estimate**: Medium -- similar file extraction work, but selection prompt design requires iteration and testing.

**Dependencies**: None.

### Option C: Target-Type Persona Presets (Do Less)

**How it works**: Don't build a persona library. Instead, define 2-3 persona *presets* per target type directly in the SKILL.md. The existing `--target-type` classification already runs; extend it to swap persona definitions, not just focus instructions.

```
### If target-type is `code`:
  Critic 1: Skeptical Senior Engineer (current)
  Critic 2: Systems Architect (current)
  Critic 3: Security & Reliability Reviewer (new, replaces Adversarial Reviewer)

### If target-type is `skill-file`:
  Critic 1: Prompt Engineering Critic (new)
  Critic 2: Contract & Integration Critic (new)
  Critic 3: Adversarial Reviewer (current)

### If target-type is `spec` or `design-doc`:
  Critic 1: Skeptical Senior Engineer (current)
  Critic 2: Systems Architect (current)
  Critic 3: Adversarial Reviewer (current) -- default set works well for documents
```

**Pros**:
- Simplest implementation -- no new files, no selection logic, no library
- Deterministic -- same target type always gets the same critics
- Self-contained and debuggable -- everything is visible in the SKILL.md
- Directly addresses the original motivation (different critics for different artifact types)
- Can be extended incrementally (add presets for new target types as needed)

**Cons**:
- Personas are still hardcoded, just with branching
- SKILL.md grows larger with each target-type preset
- No reuse across skills (mine.challenge and mine.brainstorm would maintain separate persona sets)
- Adding a new persona means editing the SKILL.md, not dropping a file
- Doesn't scale beyond 5-7 target types before the SKILL.md becomes unwieldy

**Effort estimate**: Small -- adding conditional persona blocks to existing skills.

**Dependencies**: None.

## Concerns

### Technical risks

- **Selection accuracy is the core risk**: The PRISM research demonstrates that even trained classifiers struggle to reliably select the right persona for a given input. Tag-based matching (Option A) and LLM-based selection (Option B) are both weaker approaches than PRISM's trained gate. The risk is building selection infrastructure that performs no better than the current hardcoded set.
- **The "persona override" finding**: The visual-qa-personas research found that detailed prompt instructions override agent type entirely. This means the *focus instructions* within each persona matter far more than *which* persona is selected. Optimizing selection without optimizing focus instructions is solving the wrong problem.

### Complexity risks

- **New abstraction layer**: A persona library adds a new concept (persona files, selection logic, tag taxonomy) to a system that currently has skills, commands, agents, and rules. Each new concept increases the learning curve and maintenance burden.
- **Testing burden**: Persona selection is inherently hard to test. How do you verify that the "right" personas were selected for a given target? The evaluation criteria are subjective.
- **Prompt engineering at two levels**: Currently, persona prompt quality is optimized in one place (the SKILL.md). With a library, you're optimizing both the persona prompt AND the selection logic -- two interacting prompt engineering surfaces.

### Maintenance risks

- **Tag taxonomy drift**: If using tags, the taxonomy will drift as new personas are added unless actively maintained. Tags like "backend" and "api" overlap; "security" applies to both code and infrastructure. Taxonomy design is a known hard problem.
- **Persona staleness**: Personas in a library are easier to forget about than personas inline in a skill. A persona that's rarely selected may go years without being updated.
- **Output contract fragility**: `mine.challenge` has a specific output contract (finding tags, severity levels, etc.) consumed by calling skills. If different persona sets produce different output shapes, the contract breaks.

## Open Questions

- [ ] **Is there actually a problem?** Has anyone run `mine.challenge` on a SKILL.md file and felt the critics were wrong for the job? Or on frontend code and wished for a CSS specialist? Without concrete failure cases, this may be a solution looking for a problem.
- [ ] **Would focus-instruction tuning solve it cheaper?** The `--target-type` flag already adjusts focus. Would expanding those focus instructions (e.g., "for skill-file targets, also check prompt ambiguity, caller contract compatibility, and LLM behavior assumptions") achieve 80% of the benefit at 10% of the cost?
- [ ] **What's the token budget for persona selection overhead?** Reading a persona index (even just names + one-line descriptions for 15 personas) costs tokens. Is this acceptable given the skill's existing context budget?
- [ ] **Should brainstorm personas change at all?** The brainstorm thinkers (Pragmatist, User Advocate, Moonshot, Wildly Imaginative) are designed to be domain-agnostic thinking modes, not domain-specific experts. Runtime selection may not even make sense for this skill.

## Recommendation

**Start with Option C (target-type presets), and only if that's insufficient, graduate to Option A (persona library).**

The research is clear on two points:

1. **Personas help for structured critique and creative tasks** (our use case) -- the PRISM finding that personas hurt accuracy doesn't apply here because we're using personas for alignment-dependent work (structured output, adversarial reasoning), not factual retrieval.

2. **Automatic persona selection is unreliable** -- every approach from RoBERTa classifiers to LLM-based routing struggles to beat manual selection. Tag matching has the same problem. The selection mechanism is the hard part, not the persona library.

Option C avoids the selection problem entirely by manually mapping target types to persona sets. This is the pattern that `mine.challenge` already uses for focus instructions -- extending it to persona swapping is a natural next step. It's deterministic, debuggable, and testable.

Before building anything, I'd suggest verifying the premise: run `mine.challenge` on three different target types (Python code, a SKILL.md, a design doc) and compare the critic reports. If the current generic personas produce good critiques across all three, the ROI of persona specialization is low regardless of implementation approach.

If Option C proves valuable and the number of target types grows beyond what fits cleanly in a SKILL.md, *then* extract to a persona library (Option A) with the tag taxonomy informed by real usage data rather than speculative categorization.

### Suggested next steps

1. **Test the premise** -- run `mine.challenge` on a SKILL.md file and on frontend code. Evaluate whether the current critics miss domain-specific issues that a specialized persona would catch.
2. **If yes, prototype Option C** -- add 1-2 target-type-specific persona presets to `mine.challenge` (e.g., a `skill-file` preset with a Prompt Engineering Critic). Test whether it produces better findings.
3. **Expand focus instructions first** -- before swapping personas, try expanding the `--target-type` focus instructions to include domain-specific concerns. This is the cheapest possible intervention.
4. **Consider running `/mine.challenge` on this research brief** to stress-test the recommendation before acting on it.

## Sources

### Academic research
- [Expert Personas Improve LLM Alignment but Damage Accuracy: PRISM (Hu et al., 2026)](https://arxiv.org/abs/2603.18507)
- [When "A Helpful Assistant" Is Not Really Helpful: Personas in System Prompts Do Not Improve Performances of LLMs (Zheng et al., 2024)](https://arxiv.org/html/2311.10054v3)
- [Solo Performance Prompting: Multi-Persona Self-Collaboration (Wang et al., 2024)](https://arxiv.org/abs/2307.05300)
- [Playing Pretend: Expert Personas Don't Improve Factual Accuracy (Wharton/GAIL, 2026)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5879722)

### Framework documentation
- [CrewAI Agents Documentation](https://docs.crewai.com/en/concepts/agents)
- [CrewAI Dynamic Agent Selection Discussion](https://community.crewai.com/t/dynamic-agent-selection-in-crewai-enhancing-efficiency-without-hardcoding/2734)
- [AutoGen Multi-agent Conversation Framework](https://microsoft.github.io/autogen/0.2/docs/Use-Cases/agent_chat/)
- [LangGraph Conditional Edges and Tool-Calling Agents](https://dev.to/jamesli/advanced-langgraph-implementing-conditional-edges-and-tool-calling-agents-3pdn)
- [AI Agent Routing: Tutorial & Best Practices (Patronus AI)](https://www.patronus.ai/ai-agent-development/ai-agent-routing)
- [Semantic Kernel Agent Orchestration](https://devblogs.microsoft.com/semantic-kernel/guest-blog-orchestrating-ai-agents-with-semantic-kernel-plugins-a-technical-deep-dive/)
- [Amazon Bedrock Inline Agents](https://aws.amazon.com/blogs/machine-learning/build-a-dynamic-role-based-ai-agent-using-amazon-bedrock-inline-agents/)

### Agent definition formats
- [Open Agent Format (OAF)](https://openagentformat.com/)
- [Agent Format Specification](https://agentformat.org/)

### Persona design guidance
- [Designing Agent Personas That Actually Work (Agentic Thinking)](https://agenticthinking.ai/blog/agent-personas/)
- [Multi-Persona Prompting for Better Outputs (PromptHub)](https://www.prompthub.us/blog/exploring-multi-persona-prompting-for-better-outputs)
- [Role Prompting: Does Adding Personas Really Make a Difference?](https://medium.com/@dan_43009/role-prompting-does-adding-personas-to-your-prompts-really-make-a-difference-ad223b5f1998)

### Adversarial review
- [Adversarial Code Review Pattern (ASDLC.io)](https://asdlc.io/patterns/adversarial-code-review/)
- [Adversarial Code Review: Paired Agents, Zero Noise (Hacker News)](https://news.ycombinator.com/item?id=47360961)

### Claude Code community
- [Awesome Claude Skills (GitHub)](https://github.com/travisvn/awesome-claude-skills)
- [Awesome Claude Code Subagents (GitHub)](https://github.com/VoltAgent/awesome-claude-code-subagents)
- [Claude Code Customization Guide](https://alexop.dev/posts/claude-code-customization-guide-claudemd-skills-subagents/)

### Internal prior work
- `design/research/2026-03-17-visual-qa-personas.md` -- persona differentiation research for mine.visual-qa
