# Research Brief: Design Direction Skill for Claude Code

**Date**: 2026-03-19
**Status**: Ready for Decision
**Proposal**: Research best practices for UI/design planning before writing frontend code, to inform building a Claude Code "design direction" skill
**Initiated by**: User wants to replace/improve AI-assisted design skills with something grounded in real design practice

## Context

### What prompted this

The user is replacing some AI-assisted design skills in their Claude Code configuration and wants to understand professional design practices before building new ones. The goal is a skill that helps plan UI design direction -- palette, typography, spacing, component patterns, feel -- before writing any frontend code. The output feeds into actual app development (React, Svelte, etc.), not standalone mockups.

### Current state

The existing skill (`skills/mine.interface-design/SKILL.md`) is a 289-line prompt that combines design direction and implementation guidance into a single workflow. It has strong philosophical grounding -- "Intent First," domain exploration, self-review checks, the "swap test" -- but bundles planning and building into one skill.

Key strengths of the current skill:
- **Domain exploration is excellent.** The four-part exploration (domain concepts, color world, signature element, defaults to reject) is a strong framework that aligns with professional practice.
- **Anti-default philosophy is well-articulated.** The "swap test" and requirement to explain WHY for every decision directly address the AI slop problem.
- **Token architecture is present.** Primitives, semantic, and component tokens are referenced, with evocative naming encouraged (`--ink` and `--parchment` vs `--gray-700`).

Key gaps:
- **No separation between direction-setting and building.** The skill jumps from exploration to code. A dedicated planning phase would let the user evaluate direction before committing.
- **No structured output format.** The "Component Checkpoint" is a per-component checklist, not a reusable design direction document.
- **No reference collection mechanism.** No way to gather visual references or mood board material before establishing direction.
- **The `system.md` persistence is implementation-focused.** It captures patterns after building, not direction decisions before building.

### Key constraints

- This is a Claude Code skill (prompt template), not a traditional design tool
- Must work for a solo developer without a designer on the team
- Output must feed into actual code (React, Svelte, Tailwind, etc.), not Figma mockups
- Must prevent AI-generated "slop" -- the generic Inter/purple-gradient/rounded-corners aesthetic
- Should be lightweight enough to use on small projects without feeling like overhead

## What the Research Found

### 1. What Works in Professional Design Handoff

Professional designers produce a hierarchy of artifacts, but developers report using only a subset:

**What developers actually use:**
- Design tokens (CSS variables or JSON) -- the single most actionable artifact
- Component specs with states (default, hover, active, focus, disabled, loading, empty, error)
- Typography scale with clear hierarchy (not just "use Inter")
- Spacing system with a base unit and named increments
- Color palette with semantic mappings (not just raw hex values)

**What developers ignore:**
- High-fidelity mockups (they diverge from implementation too quickly)
- Brand guidelines documents (too abstract, not actionable)
- Style guides without code examples

**The minimum viable handoff** is: tokens file + component examples + states documentation. Everything else is nice-to-have.

**Key insight from the Martin Fowler article on token architecture:** The three-tier hierarchy (option/primitive, decision/semantic, component) documents intent through its structure. Option tokens define *what* is available, decision tokens define *how* options are applied, component tokens define *where* they appear. Starting with two tiers is fine; add component tokens only when design evolution requires it.

### 2. Design Token Architecture in Practice

Mature design systems (Shadcn, Radix, Material) converge on a common structure:

**Shadcn/Radix approach:**
- CSS variables in `:root` with HSL values
- Semantic naming with background/foreground pairs
- Modifier prefixes: `muted`, `accent`, `destructive`
- Dark mode through `.dark` class overrides on the same variables
- Spacing on Tailwind's 0.25rem increment scale
- Five-tier shadow hierarchy from subtle to pronounced

**The "closed token layer" pattern** (from Hardik Pandya's "Expose Your Design System to LLMs"):
- Every value in the codebase references a `var(--token)`, never raw values
- The LLM picks from a closed set of named variables instead of inventing plausible values
- This is the single most effective technique for preventing AI drift across sessions

**Documentation structure that works:**
- `foundations/` -- color.md, typography.md, spacing.md, radius.md, elevation.md, motion.md
- `tokens/` -- token-reference.md (master map of every CSS variable)
- Component specs following a consistent template: metadata, overview, anatomy, tokens used, props/API, states, code examples

### 3. AI-Specific Insights

**What produces generic output:**
- Vague prompts ("make it clean and modern") -- NN/g research confirms AI fills ambiguity with defaults
- No component registry constraints -- when AI can invent any markup, it invents familiar markup
- No token constraints -- without a closed set of variables, AI invents plausible values that drift
- No domain context -- without knowing what the product *is*, AI produces what templates look like

**What produces distinctive output:**
- **Reference established styles by name.** "Neobrutalism" or "editorial serif with monospace accents" outperforms "professional and clean" (NN/g finding).
- **Provide mock data.** Realistic sample content forces design to follow data shape, not generic placeholder shapes.
- **Constrain the palette of available components.** Treat AI like a contractor who can only use materials from your warehouse, not Home Depot.
- **Externalize taste into a structured brief.** The BrainGrid article recommends: user job + success state, screen inventory, token constraints, required interaction states, one reference screen.

**The core anti-slop mechanism:** AI slop happens when there is no system-level owner. The fix is not better prompts -- it is a persistent design system document that every session reads before generating UI code. As Pandya puts it: "Your 10th session produces the same visual quality as your 1st."

**Common AI aesthetic tropes to explicitly avoid:**
- Inter/system font as default
- Purple/blue gradients
- Uniform rounded corners (same radius everywhere)
- Three-column card grid with icons
- Soft pastel backgrounds
- Generic hero sections

### 4. Lightweight Methods for Solo Developers

**Style Tiles** (Samantha Warren, styletil.es) are the most relevant format:
- A middle ground between mood board (too vague) and full comp (too detailed)
- Contains: fonts, colors, interface elements, textures, adjectives
- Quick to create, flexible to change
- Directly maps to design tokens
- Establishes direction without committing to layout

**The solo developer workflow that works:**
1. **Collect references** (15 min) -- 3-5 screenshots of apps/sites whose *feel* matches intent. Not for copying; for articulating what you want.
2. **Name the aesthetic** (5 min) -- Use specific language. "Dense data terminal with warm accents" not "clean and professional."
3. **Make token decisions** (20 min) -- Color palette, type scale, spacing base, depth strategy, border radius scale. These are THE decisions.
4. **Write it down** (10 min) -- One document with the decisions and the reasoning. This is the design direction.
5. **Build one screen** (implementation) -- Apply tokens to a single representative screen. Validate direction before scaling.

**Total: ~50 minutes of design planning before any code.** This is the minimum viable design exploration.

### 5. What Actually Prevents Generic-Looking UIs

From the research, five factors separate "designed" from "template":

**1. Constraint commitment.** Pick one depth strategy (borders-only, subtle shadows, layered shadows, surface tints) and commit. Mixing approaches is the clearest signal of no system. Same for border radius -- one scale, used consistently.

**2. Typography with personality.** The single highest-impact decision. Inter/system-ui reads as "no designer touched this." A single distinctive font (Bricolage Grotesque, Fraunces, Space Grotesk) used decisively changes everything. The current skill's typography cheat sheet is strong here.

**3. Domain-derived color.** Colors should come from the product's world, not a random palette generator. A cooking app and a code editor are both "tools" but their color worlds are completely different. The current skill's "Color Lives Somewhere" section nails this.

**4. Asymmetry and proportion.** Templates are symmetrical. Designed interfaces break symmetry intentionally -- a wider left column, a heavier header, an oversized metric. The "signature element" concept in the current skill addresses this.

**5. State completeness.** Every interactive element with all states (default, hover, active, focus, disabled). Data views with loading, empty, and error states. Missing states feel broken and unfinished -- this is the most common gap in AI-generated UI.

## Recommended Approach

### What a "Design Direction" Skill Should Look Like

Based on the research, the skill should produce a **Design Direction Document** -- a structured artifact that sits between "I have an idea" and "I'm writing components." This document becomes the persistent reference for all subsequent UI work.

**Separation of concerns:**
- `mine.interface-design` (or a renamed version) stays as the *building* skill that reads the direction document and produces code
- The new skill is purely *planning* -- it produces the direction document but writes zero UI code

### Recommended Document Structure

The output should be a markdown file (`.interface-design/direction.md` or similar) with:

```markdown
# Design Direction: [Product Name]

## Intent
- **Who**: [specific person, specific context]
- **What they do**: [the verb, not "use the app"]
- **Feel**: [specific aesthetic language, not "clean and modern"]

## References
- [Named reference 1]: [what to take from it]
- [Named reference 2]: [what to take from it]

## Domain Exploration
- **Domain concepts**: [5+ concepts from this product's world]
- **Color world**: [colors that exist naturally in this domain]
- **Signature element**: [one thing unique to THIS product]
- **Defaults rejected**: [obvious choices and why they're wrong]

## Token Decisions

### Color
- **Palette**: [specific hex/HSL values with semantic names]
- **Why**: [how these connect to domain and intent]
- **Background/foreground pairs**: [light and dark mode]

### Typography
- **Primary font**: [name] -- [why this font for this product]
- **Scale**: [specific sizes in rem/px]
- **Weights**: [which weights, for what purpose]

### Spacing
- **Base unit**: [value]
- **Scale**: [list of values]

### Depth
- **Strategy**: [borders-only | subtle shadows | layered | surface tints]
- **Why**: [connection to intent]

### Border Radius
- **Scale**: [small, medium, large values]
- **Character**: [sharp=technical, round=friendly]

### Motion
- **Micro-interactions**: [duration, easing]
- **Transitions**: [duration, easing]

## Anti-patterns
- [Specific things to avoid for THIS product]

## Component Notes
- [Any component-specific decisions that emerged during exploration]
```

### Skill Workflow

1. **Gather context** -- Ask about the product, the person using it, what they need to accomplish, what it should feel like. Use specific probing questions, not open-ended "describe your vision."
2. **Collect references** -- Ask the user for 2-3 apps/sites whose *feel* (not features) matches their intent. If they can't name any, suggest options based on the domain.
3. **Domain exploration** -- Run the four-part exploration from the current skill (this is already strong). Present domain concepts, color world, signature, and defaults to reject.
4. **Propose direction** -- Present a concrete direction with specific token values, not abstract concepts. Include visual language the user can evaluate ("dense like a terminal" vs "open like a notebook").
5. **Confirm and save** -- Write the direction document. This becomes the source of truth for all subsequent UI work.

### What This Means for the Current Skill

The current `mine.interface-design` skill should be split:

| Concern | Skill | Output |
|---------|-------|--------|
| Design direction (planning) | New skill (e.g., `mine.design-direction`) | `.interface-design/direction.md` |
| Design system implementation | Revised `mine.interface-design` | CSS tokens + components |
| Design review/QA | Existing `mine.visual-qa` | Screenshot-based review |

The revised `mine.interface-design` would start by reading `direction.md` (like it currently reads `system.md`) and apply those decisions to code. The key difference: direction decisions are made *before* building, not discovered *during* building.

### What to Carry Forward from the Current Skill

These sections are strong and should transfer to the new skill in some form:
- **"Intent First"** -- the who/what/feel framework
- **"Product Domain Exploration"** -- the four-part exploration (domain, color world, signature, defaults)
- **"Where Defaults Hide"** -- the philosophy that everything is a design decision
- **Self-review checks** -- swap test, squint test, signature test, token test
- **Typography cheat sheet** from `references/principles.md`
- **Precision vs. Warmth examples** from `references/principles.md`

### What to Add That's Missing

- **Reference collection step** -- explicitly ask for visual references before exploring
- **Structured output format** -- the direction document template above
- **Specific anti-slop language** -- name the AI aesthetic tropes explicitly so they can be rejected consciously
- **Mock data requirement** -- require realistic sample content before making layout decisions
- **The "closed token layer" principle** -- every value must reference a named token, never raw values
- **State inventory** -- list required states for every interactive element and data view as part of direction

## Concerns

### Technical risks
- **Token format portability.** A direction document written for Tailwind CSS variables may not translate cleanly to other frameworks. Keep the document framework-agnostic at the decision level, framework-specific only in the token values section.

### Complexity risks
- **Two skills where one existed.** Splitting direction from implementation means the user invokes two skills instead of one. For small projects, this could feel like overhead. Consider a "quick mode" that combines both for projects that don't warrant a separate planning phase.
- **Document maintenance.** If the direction document drifts from actual implementation, it becomes stale. The implementation skill should validate against it, not just read it.

### Maintenance risks
- **AI aesthetic trends shift.** Today's anti-slop advice (avoid Inter, avoid purple gradients) will age. The skill should teach *how* to identify defaults, not maintain a list of specific defaults to avoid.

## Open Questions

- [ ] Should the direction document live at `.interface-design/direction.md` (per-project) or somewhere in the skill's output? The current skill uses `.interface-design/system.md` for persistence.
- [ ] Should the skill support multiple directions for the same project (e.g., exploring 2-3 options before committing)? Style tiles traditionally present 2-3 options.
- [ ] How should the direction skill interact with existing design systems? If the user is already using Shadcn, the direction is partly pre-decided. Should the skill detect and adapt?
- [ ] Should there be a "design audit" mode that evaluates existing UI against the direction document and flags drift?

## Recommendation

**Split the current skill into two: a planning skill and a building skill.** The planning skill produces a structured design direction document; the building skill consumes it.

The current skill's philosophical content is strong -- the domain exploration, anti-default philosophy, and self-review checks are well-grounded in what the research shows works. What's missing is the *structured output* and *reference collection* that make direction decisions persist and translate into code.

The "closed token layer" insight from the LLM-specific research is the single most actionable finding: every value must reference a named token. This should be a hard constraint in both the direction document and the implementation skill.

### Suggested next steps

1. **Design the direction document format.** Use the template above as a starting point, but refine based on what feels right for the user's workflow.
2. **Write the planning skill.** Keep the domain exploration and anti-default philosophy from the current skill, add reference collection and structured output.
3. **Revise the implementation skill.** Make it read `direction.md` as its source of truth. Add validation that all values reference defined tokens.
4. **Test on a real project.** Run the planning skill on an upcoming UI project to validate the workflow before committing to the split.

## Sources

- [Martin Fowler: Design Token-Based UI Architecture](https://martinfowler.com/articles/design-token-based-ui-architecture.html) -- Three-tier token hierarchy (option/decision/component), scope management, when not to over-engineer
- [Hardik Pandya: Expose Your Design System to LLMs](https://hvpandya.com/llm-design-systems) -- The "closed token layer" pattern, spec directory structure, audit scripts for token compliance
- [BrainGrid: Design System Optimized for AI Coding](https://www.braingrid.ai/blog/design-system-optimized-for-ai-coding) -- Three-tier token architecture in practice, AI-facing documentation format, prompt pattern templates
- [NN/g: Prompt to Design Interfaces -- Why Vague Prompts Fail](https://www.nngroup.com/articles/vague-prototyping/) -- Five prompting techniques, reference established styles by name, mock data requirement
- [AI Slop vs Constrained UI: Why Most Generative Interfaces Fail](https://dev.to/puckeditor/ai-slop-vs-constrained-ui-why-most-generative-interfaces-fail-pm9) -- Component registry constraints, schema validation, business context injection
- [Killing AI Slop: Frontend Design Skill Creates Boutique UI](https://dailyaiworld.com/post/killing-ai-slop-how-front-end-design-skill-creates-boutique-ui) -- Define philosophy first, guide with constraints, use AI for exploration only
- [Style Tiles (styletil.es)](https://styletil.es/) -- Middle ground between mood board and comp, directly maps to design tokens
- [Shadcn Design Principles Breakdown](https://gist.github.com/eonist/c1103bab5245b418fe008643c08fa272) -- CSS variable structure, semantic naming conventions, shadow hierarchy
- [Figma: Designer's Handbook for Developer Handoff](https://www.figma.com/blog/the-designers-handbook-for-developer-handoff/) -- What developers actually use from design artifacts
- [Contentful: Design Tokens Explained](https://www.contentful.com/blog/design-token-system/) -- Primitives, semantic, component token layers
- [Claude Code for Designers (Builder.io)](https://www.builder.io/blog/claude-code-for-designers) -- AI-assisted design workflows with Claude Code
- [How to Use AI (Claude) to Build UI Powered by the Design System](https://levelup.gitconnected.com/how-to-use-ai-claude-to-build-ui-powered-by-the-design-system-4a3bb1112f3d) -- Design system as source of truth for AI code generation
- [CareerFoundry: Style Tiles -- Everything You Need to Know](https://careerfoundry.com/en/blog/ui-design/style-tiles/) -- Style tile methodology and components
