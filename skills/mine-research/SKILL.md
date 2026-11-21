---
name: mine-research
description: "Use when the user says: \"research adding X\", \"feasibility study\", \"evaluate approach\", or wants a focused investigation before committing. Dispatches the researcher agent for codebase investigation and presents a structured brief."
user-invocable: true
---

# Research

Answer "what would it take to do X in this codebase?" before anyone designs it. The result is a research brief grounded in the actual code, good enough that a design can start from it without redoing the investigation. It informs a decision; it doesn't make one. Use `/mine-sketch` to settle how to build it.

## Arguments

$ARGUMENTS — the proposal to investigate (a change, a technology question, a pattern evaluation, a migration, a broad direction). If empty, ask what the user is considering.

## Understand the ask first

The user's first description is rarely the whole picture, so don't explore the codebase until you know what they want and why. The distinctions that change the research: whether they've decided on an approach or are choosing; whether the named technology is the need or one candidate for it; hard constraints; urgency; what's new territory for them.

Ask what you can't tell from the request, in at most two rounds of `AskUserQuestion`, with options written for this proposal's domain. A specific proposal needs fewer questions than a vague one. The answers must settle the researcher's **Flexibility** value (`Exploring`, `Leaning`, `Decided`). `Decided` makes it drop alternatives, so record it only when the user said they've decided, never inferred from a confidently worded request. Anything else still unclear becomes an open question for the brief.

## Investigate

Dispatch a `researcher` agent so the exploration and synthesis stay out of your context. Make a temp directory with `mktemp -d <scratchpad>/mine-research-XXXXXX` and launch `Agent(subagent_type: "researcher")` with the caller prompt checklist from `${CLAUDE_CONFIG_DIR:-~/.claude}/agents/researcher.md` filled in from the user's answers, plus the output path `<tmpdir>/brief.md`.

Set `Depth` from what you learned. Quick suits a decided user with a narrow scope, deep suits an exploring user with a broad one, and normal is the default and the right choice when scope is unclear.

When the agent finishes, read `<tmpdir>/brief.md` and confirm it exists and opens with a `# Research Brief:` header. If it's missing or incomplete, tell the user and offer a retry or a manual investigation in this context.

## Save and present

Copy (never move) the brief to the repo's existing research location when it has one (`design/research/YYYY-MM-DD-<topic>/research.md`, or `docs/research/YYYY-MM-DD-<topic>.md` where the repo uses `docs/research/`); otherwise to `design/research/YYYY-MM-DD-<topic>/research.md`. Create the directory, tell the user the path, and leave the tmpdir copy intact, since challenge and design handoffs reference it. If the user would rather just see it, show it inline.

Set `<research_brief_path>` to the saved file, or to `<tmpdir>/brief.md` if it wasn't saved. Present the key findings conversationally, then ask what to do next.

## Closing menu

Build the menu from this brief, not from a stock list. The failure to avoid is a menu where every option assumes the research is finished: a brief with unresolved open questions isn't ready for challenge, design, or build, because those would stall on the same questions or bake a guess into the design. Read the brief's Open Questions and Recommendation, decide what the natural next move is, put that first as the recommended option, and write each description around the brief's actual content (name the open questions rather than saying "resolve open questions"). Order by fit.

Outcomes that may fit, depending on the findings: resolving the open questions now; challenging the findings with `/mine-challenge`; sketching a design with `/mine-sketch`; building directly when the brief leaves nothing to decide; investigating a specific gap further; stopping here with the brief saved (always available). Offer the others only when the findings make them meaningful, and add an outcome the brief calls for that isn't listed.

Resolving open questions: sort each by what answers it. Questions that need the user (preference, priority, intent) go to them in one `AskUserQuestion` call with options grounded in the findings. Questions that need more reading or a read-only command are investigated directly, or by a `researcher` or `standard-worker` if broad; a throwaway probe in the tmpdir that only observes behavior is fine. Questions that need a real prototype stay open, since a prototype is build work. As answers land, update the brief at `<research_brief_path>`: check off the question with its answer and revise any feasibility, options, concerns, or recommendation text it changes. Then summarize what changed and rebuild the menu from the updated brief.

Handoffs:
- Challenge: `/mine-challenge --mode=passthrough --target-type=research <research_brief_path>`, then return to the menu.
- Sketch: `/mine-sketch` with a one-line description of the change and "Prior research brief at `<research_brief_path>`", so sketch reads the brief as prior work.
- Build: implement using the brief as the guide, through the normal pre-commit reviewers.

## Principles

- A scoped question ("can X be done?") is answered by completing the brief and offering the menu. Don't silently start filing issues, design, or shipping from it.
- Prior analysis covers the problem space; research covers the solution space (competing approaches, existing codebase patterns, API constraints). Skipping it moves that investigation into the design phase, where it's more expensive.
- No code during investigation. Code is written only after the menu, if the user picks build.
- It evaluates one proposal against this codebase. It doesn't audit health (`/mine-challenge`) or run benchmarks.
