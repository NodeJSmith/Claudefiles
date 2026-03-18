# Research Brief: Optimal Persona Configuration for mine.visual-qa

**Date**: 2026-03-17
**Status**: Ready for Decision
**Proposal**: Determine the optimal set of AI agent personas (2-3) for screenshot-based UI review that maximize non-overlapping issue discovery
**Initiated by**: User exploring whether to add a third persona and whether the current two are differentiated enough

## Key Findings

### What the research says about number of evaluators

Nielsen's foundational research on heuristic evaluation (1992, updated through NN/g) establishes:

- **Single evaluators find ~35% of usability problems** averaged across six case studies
- **3-5 evaluators is the optimal range**, with 4 being optimal in the studied examples
- **Diminishing returns kick in sharply after 5** -- each additional evaluator finds progressively fewer new issues
- **The evaluator effect is real and large**: across 19 evaluators assessing a banking system, there was "substantial nonoverlap" between the sets of problems found. Different people genuinely find different things.
- **The probability of a single evaluator finding a major problem was 42%**; for minor problems, only 32%

The curve shape matters for this decision: going from 1 to 2 evaluators roughly doubles discovery. Going from 2 to 3 adds substantial value. Going from 3 to 4 adds moderate value. Going from 4 to 5 adds marginal value.

**Applied to AI agents**: AI agents are not human evaluators. They don't have the natural variation in background and experience that creates the evaluator effect in humans. The variation must be *engineered* through distinct persona prompts. This means:
- The number of agents matters less than how different their prompts are
- Two agents with highly differentiated prompts may outperform three with overlapping ones
- The research supports 3 as a sweet spot only *if* each persona covers genuinely distinct ground

### What different evaluation methods actually find

Research comparing heuristic evaluation to cognitive walkthrough reveals that different evaluation *approaches* find different *types* of problems:

| Method | Strengths | Issue types |
|--------|-----------|-------------|
| **Heuristic Evaluation** | Holistic view, catches consistency and convention violations | More issues total, especially "satisfaction" problems |
| **Cognitive Walkthrough** | Task-focused, simulates first-time use step by step | Fewer but higher-severity issues, especially "learnability" problems |

In one study, HE found 83 issues vs CW's 58, but CW found more *catastrophic* issues. Only 33% of CW findings overlapped with HE findings. This is a critical insight: **the evaluation frame (holistic scan vs. task walkthrough) determines what gets found more than the evaluator's identity does.**

### What AI can and cannot find from screenshots

A UX Studio study directly tested ChatGPT's ability to evaluate UI from screenshots:

**AI finds well:**
- General design principles and aesthetic issues
- Broad accessibility observations
- Content and layout suggestions
- Visual hierarchy and consistency problems

**AI misses:**
- Specific interactive problems (which buttons are confusing, which gestures users attempt)
- Discoverability issues (e.g., users couldn't find rename/delete options -- ChatGPT never flagged this)
- Real behavioral patterns (users tried "tap and hold to move" -- AI had no model for this)
- Feedback tends to be "general rather than specific" -- identifying categories of problems rather than pinpointing exact elements

**Key insight for mine.visual-qa**: The Playwright integration partially addresses the interaction limitation since agents can click, navigate, and try flows. But they still lack the mental model of "what would a real user try here?" -- they follow prompts, not instincts. This means persona prompts need to compensate by being extremely specific about *what to look for* and *what to try*.

### The 10 distinct lenses for design critique

Designlab's critique checklist identifies these dimensions:

1. Objectives and goals
2. Information architecture and visual hierarchy
3. Navigation structure and controls
4. Visual design and branding
5. Labels and text/copy
6. Accessibility and inclusivity
7. Interactions and animations
8. Mobile responsiveness
9. Usability testing (user research validation)
10. Performance and quality assurance

Not all of these are productive for screenshot-based AI review. Here's a suitability assessment:

| Lens | Screenshot suitability | Notes |
|------|----------------------|-------|
| Visual hierarchy | HIGH | AI excels at this from screenshots |
| Visual design/branding | HIGH | Color, typography, spacing -- highly visible |
| Labels/text/copy | HIGH | Content is fully readable from screenshots |
| Information architecture | HIGH | Layout, grouping, page structure visible |
| Navigation | MEDIUM-HIGH | Visible in screenshots; Playwright can test |
| Mobile responsiveness | MEDIUM-HIGH | Playwright can resize viewport |
| Interactions/animations | MEDIUM | Playwright can click/interact but can't "feel" timing |
| Accessibility | LOW-MEDIUM | Surface-level only (contrast, text size); code audit is better |
| Performance | LOW | Not visible in screenshots |
| User research validation | N/A | Requires real users |

## Persona Analysis

### The overlap problem with the current two personas

The current setup has:
1. **Visual Design Critic** (design-visual-storyteller) -- "design-savvy user, honest opinionated visual critique"
2. **Fresh-Eyes UX Reviewer** (design-ux-researcher) -- "new user, what looks weird/confusing/unclear/ugly"

**Honest assessment: these two overlap significantly.** Here's why:

Both prompts instruct the agent to:
- Take screenshots and react to what they see
- Describe their first impression / gut reaction
- Identify what looks "off" (alignment, spacing, sizing, color, typography)
- Note what's confusing or unclear
- Try mobile viewport, dark/light mode, sort/filter controls

The *intended* difference is perspective (design-savvy vs. naive user), but when both are AI agents looking at the same screenshots, this distinction collapses. An AI doesn't have a "naive user" mental model that's meaningfully different from a "design-savvy" mental model -- both are just the same LLM reacting to visual input. The differentiation must come from *what they're instructed to look for*, not *who they're pretending to be*.

**What's actually different between them:**
- Agent 1 focuses on visual hierarchy, polish, visual weight ("does the visual hierarchy make sense?")
- Agent 2 focuses on user confusion and task completion ("what would make you hesitate?")
- Agent 2 includes "try the main creation/add flow end to end" -- a task walkthrough component
- Agent 1 includes "does the purpose of the page immediately clear?" -- an information architecture component

These are genuine differences but they're buried under a lot of shared surface area. The prompts need sharper differentiation to avoid redundant findings.

### Candidate review lenses ranked by distinctness and screenshot suitability

Here are the genuinely distinct lenses available for screenshot-based AI review, ordered by how different they are from each other:

**Tier 1: Highly distinct, high screenshot suitability**

| Lens | What it catches | Overlap with others |
|------|----------------|-------------------|
| **Visual polish and craft** | Alignment, spacing, color harmony, typography, visual weight, whitespace balance, border/shadow consistency | Low overlap with task-based or content review |
| **Task walkthrough (cognitive walkthrough)** | Can I complete the core tasks? Where do I get stuck? What's the logical next step at each point? | Low overlap with visual review; catches different issue types |
| **Content and labeling** | Are labels clear? Is copy helpful or confusing? Are empty states explained? Are error messages useful? Do headings tell you what's below them? | Surprisingly distinct from visual and task review -- often missed entirely |

**Tier 2: Distinct but partially overlapping**

| Lens | What it catches | Overlap concern |
|------|----------------|----------------|
| **Information density and cognitive load** | Too much on screen? Can I scan this? Is there progressive disclosure? Are related things grouped? | Partially overlaps with visual hierarchy analysis |
| **Consistency and pattern recognition** | Does the same element look/behave the same everywhere? Are button styles consistent? Do tables follow the same pattern across pages? | Partially overlaps with visual polish |
| **Mobile and responsive** | Does the layout survive at 375px? Do touch targets work? Does the nav collapse sensibly? | Could be a sub-task of any other lens |

**Tier 3: Not distinct enough for a separate agent**

| Lens | Why not separate |
|------|-----------------|
| **New user vs. power user** | Without real user behavior data, AI can't meaningfully distinguish these perspectives |
| **Emotional design** | Collapses into visual design when evaluated from screenshots |
| **Brand consistency** | Subset of visual design unless the agent has brand guidelines to compare against |

### Why the cognitive walkthrough / task lens is the strongest third perspective

The research is clear: **heuristic evaluation and cognitive walkthrough find different types of issues with only ~33% overlap**. This directly maps to mine.visual-qa's situation:

- The current Visual Design Critic is doing heuristic evaluation (scan the screen, flag problems against design principles)
- The current UX Reviewer *intends* to do cognitive walkthrough ("try the main creation/add flow") but its prompt buries this under a lot of heuristic-evaluation-style instructions

A dedicated task-focused agent would:
1. Navigate through specific user flows end-to-end (create an item, edit it, delete it, search for something)
2. At each step, ask: "Is the next action obvious? Can I tell what happened? Do I know where I am?"
3. Focus on *sequences*, not *screens* -- the transition between states, not just what each screen looks like
4. Catch problems the visual review misses: dead ends, confusing flows, missing confirmation, ambiguous navigation

This agent can use Playwright effectively because it's *doing things*, not just *looking at things*.

## Recommendations

### For 2 agents: Sharpen the existing split

If keeping 2 agents, differentiate them more aggressively:

**Agent 1: Visual Craft Critic** -- pure visual review
- Remove all task/flow instructions
- Focus exclusively on: visual hierarchy, spacing, alignment, color, typography, consistency between pages, mobile layout, dark mode
- Instruct it to compare pages against each other ("does the dashboard use the same card style as the settings page?")
- This is a *scanner* -- it looks at every pixel and reacts

**Agent 2: Flow Walker** -- pure task walkthrough
- Remove all "does this look pretty" instructions
- Focus exclusively on: can I complete the main tasks? What happens when I click things? Are transitions logical? Do I know where I am? Is there feedback after actions?
- Give it specific tasks to attempt ("create an item", "find and edit an existing item", "delete something")
- Instruct it to narrate moment-by-moment: "I see a button labeled X. I click it. Now I see Y. I expected Z."
- This is a *navigator* -- it walks paths and narrates the experience

This split maps directly to heuristic evaluation vs. cognitive walkthrough, which research shows produces the lowest overlap (~33%).

### For 3 agents: Add a Content and Density reviewer

The third perspective that covers the most new ground is **content, labeling, and information density**:

**Agent 3: Content and Clarity Reviewer**
- Focus on: Are labels clear and consistent? Is the copy helpful? Do headings describe what's below? Are empty states useful? Are error messages actionable?
- For dashboards/admin panels: Is there too much on screen? Is data grouped logically? Can you scan this page in 3 seconds and know what matters?
- For consumer apps: Does the copy feel human? Is there jargon? Would a non-technical person understand this?
- This agent looks at the *words and information organization*, not the visual styling or task flow

**Why content/density rather than the other candidates:**
1. It's the most reliably distinct from both visual and task review -- content issues are almost never surfaced by design critics or flow walkers
2. AI is actually excellent at evaluating copy and labeling from screenshots (high text comprehension)
3. It's particularly valuable for the admin panel use case where information density is the primary design challenge
4. Content/copy problems are the category that users notice but designers often skip

### Recommended agent type assignments

| Agent | Recommended subagent_type | Rationale |
|-------|--------------------------|-----------|
| Visual Craft Critic | `design-visual-storyteller` | Retains the visual/aesthetic orientation of the current agent |
| Flow Walker | `design-ux-researcher` | The UX researcher persona naturally focuses on user behavior and task completion |
| Content and Clarity Reviewer | `design-ui-designer` | The UI designer agent has the strongest content structure and information architecture orientation. Alternatively, no specific agent type needed -- the prompt itself drives behavior more than the persona. |

### On the agent type question

Looking at the existing agent definitions, there's an important subtlety: the `design-visual-storyteller` agent is actually about brand narrative and multimedia content creation -- it has almost nothing to do with visual UI critique. Similarly, `design-ux-researcher` is about user research methodology and study design, not about reacting to screenshots.

**The persona prompts in mine.visual-qa completely override the agent definitions.** The detailed prompt given to each agent is what drives behavior; the agent type provides ambient context that's mostly irrelevant. This means:
- The choice of agent type is less important than the quality of the prompt
- Any of the design-oriented agents would work for any of these roles
- The prompts should be self-contained and not rely on the agent persona to fill gaps

## Concerns

### Technical risks
- **AI convergence**: Even with distinct prompts, LLMs tend to converge toward similar observations. The sharper and more specific the prompts are about what to focus on (and what to *ignore*), the less overlap there will be.
- **Screenshot-only limitations**: The UX Studio research found AI gives "general rather than specific" feedback from screenshots. Prompt engineering must aggressively push for specificity ("reference exact elements, not categories").

### Complexity risks
- **3 agents = 3x Playwright sessions**: Each agent independently navigates the app, takes screenshots, and writes a report. Three agents triple the API calls, time, and token usage.
- **Synthesis burden**: More agents means more findings to cross-reference. The Phase 4 synthesis in the current skill already handles deduplication, but with three independent reports the merge becomes harder.

### Maintenance risks
- **Prompt drift**: The effectiveness of differentiated personas depends entirely on prompt quality. If the prompts gradually accumulate shared instructions (like "also try mobile viewport" appearing in all three), they'll converge back toward redundancy.
- **False precision**: Three agents may create a false sense of thoroughness. The research is clear that AI screenshot review misses entire categories of problems that only real user testing reveals.

## Open Questions

- [ ] **Does the current overlap actually matter in practice?** Before optimizing for non-overlap, it's worth checking: do the current two agents produce largely duplicate findings, or does the "two perspectives on the same thing" approach actually produce useful cross-referencing signal? Run both agents on an app you know well and compare the raw reports.
- [ ] **Should the third agent be conditional?** For consumer apps, a content/copy reviewer adds the most. For admin panels, an information density reviewer adds the most. These could be the same agent with a different prompt fragment, or the skill could ask the user what kind of app they're reviewing.
- [ ] **Is the agent type assignment consequential?** Run the same prompt with different agent types (design-visual-storyteller vs. design-ui-designer) and compare outputs. If they're identical, simplify by using a single agent type for all three.
- [ ] **Token budget**: Three parallel agents each taking screenshots of multiple pages will consume significant tokens. Is there a budget constraint that favors 2 over 3?
- [ ] **Prompt specificity experiment**: The biggest lever isn't the number of agents -- it's the specificity of the prompts. Before adding a third agent, try rewriting the two existing prompts with the sharper differentiation described above and see if that alone resolves the overlap problem.

## Recommendation

**Start with sharpening the existing 2-agent split before adding a third.** The current two personas have meaningful overlap that reducing from "general reaction to screenshots" to "specific, distinct evaluation frames" would address. The visual-vs-task split (heuristic evaluation vs. cognitive walkthrough) is the most research-supported way to differentiate two evaluators.

If the sharpened 2-agent configuration still leaves gaps -- particularly around content/copy quality and information density -- then add the third agent. But the third agent should be a specific, tested addition, not a speculative one.

### Suggested next steps
1. **Rewrite the two existing prompts** using the sharpened split (Visual Craft Critic + Flow Walker) with explicit instructions about what to focus on and what to *ignore*
2. **Test the rewritten prompts** on a known app and compare the raw reports for overlap -- target <30% finding overlap
3. **If gaps remain**, prototype the Content and Clarity Reviewer prompt and test it as the third agent
4. **Review whether agent type matters** by running the same prompt through different agent types and comparing output quality

## Sources

- [How to Conduct a Heuristic Evaluation (NN/g)](https://www.nngroup.com/articles/how-to-conduct-a-heuristic-evaluation/)
- [The Theory Behind Heuristic Evaluations (NN/g)](https://www.nngroup.com/articles/how-to-conduct-a-heuristic-evaluation/theory-heuristic-evaluations/)
- [Finding Usability Problems Through Heuristic Evaluation (Nielsen 1992, CHI proceedings)](https://course.ccs.neu.edu/is4300sp13/ssl/articles/p373-nielsen.pdf)
- [10 Usability Heuristics for User Interface Design (NN/g)](https://www.nngroup.com/articles/ten-usability-heuristics/)
- [What's the difference between HE and CW? (MeasuringU)](https://measuringu.com/he-cw/)
- [Comparison of HE and CW usability evaluation methods (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC7651936/)
- [Comparison of usability evaluation methods: HE vs CW (BMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9206256/)
- [Can AI take over usability testing? (UX Studio)](https://www.uxstudioteam.com/ux-blog/ai-usability-test)
- [A 10-point Design Critique Checklist (Designlab)](https://designlab.com/blog/design-critique-checklist-for-ux-designers)
- [Personas in Heuristic Evaluation (IEEE Xplore)](https://ieeexplore.ieee.org/document/7108068/)
- [AI in Automated and Remote UX Evaluation: Systematic Review 2014-2024 (Wiley)](https://onlinelibrary.wiley.com/doi/10.1155/ahci/7442179)
- [Human-Centered Design Through AI-Assisted Usability Testing (Smashing Magazine)](https://www.smashingmagazine.com/2025/02/human-centered-design-ai-assisted-usability-testing/)
- [How to Run a UX Design Critique (Nielsen PhD Substack)](https://jakobnielsenphd.substack.com/p/design-crit)
- [Dashboard Design: Information Architecture That Prevents Cognitive Overload](https://www.sanjaydey.com/saas-dashboard-design-information-architecture-cognitive-overload/)
- [Evaluate Interface Learnability with Cognitive Walkthroughs (NN/g)](https://www.nngroup.com/articles/cognitive-walkthroughs/)
