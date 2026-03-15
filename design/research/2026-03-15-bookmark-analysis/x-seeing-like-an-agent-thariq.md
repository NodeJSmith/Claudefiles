# Seeing like an Agent — Thariq (Claude Code team)

Source: https://x.com/trq212/status/2027463795355095314

## Core Framework

Design tools shaped to the model's abilities. Pay attention to outputs, experiment, learn to "see like an agent."

## Lesson 1: AskUserQuestion Tool Evolution

Three attempts to improve elicitation:

1. **ExitPlanTool with questions parameter** — confused Claude (simultaneous plan + questions, conflicting answers)
2. **Modified markdown output format** — Claude inconsistent at outputting structured format (appended extra sentences, omitted options)
3. **Dedicated AskUserQuestion tool** — structured output, multiple options, modal UI blocks agent loop until user answers. Claude "liked" calling this tool and outputs worked well.

**Key insight:** "Even the best designed tool doesn't work if Claude doesn't understand how to call it."

## Lesson 2: Tasks Replaced Todos (Model Capability Growth)

- **TodoWrite** (original) — keep model on track, system reminders every 5 turns
- Problem: reminders made Claude stick to the list instead of modifying it
- **Task Tool** (replacement) — about agent-to-agent communication, not just tracking
  - Dependencies between tasks
  - Shared updates across subagents
  - Model can alter and delete tasks

**Key insight:** "As model capabilities increase, the tools that your models once needed might now be constraining them. Constantly revisit previous assumptions."

## Lesson 3: Search Interface Evolution

1. **RAG vector database** — required indexing/setup, fragile, context given TO Claude
2. **Grep tool** — Claude searches and builds context ITSELF
3. **Agent Skills with progressive disclosure** — nested search across layers of files

"Over the course of a year Claude went from not really being able to build its own context, to being able to do nested search across several layers of files."

## Lesson 4: Progressive Disclosure over New Tools

~20 tools in Claude Code. Bar to add new tool is high (one more option to think about).

Example: Claude Code Guide subagent
- Problem: Claude didn't know about its own features (MCPs, slash commands)
- Could have put in system prompt → context rot, interferes with main job
- Could have given docs link → Claude loads too many results
- Solution: **Subagent with focused search instructions** — adds to action space without adding a tool

**Key insight:** "We were able to add things to Claude's action space without adding a tool."

## Actionable Takeaways

1. Tools should match model abilities — revisit as models improve
2. Progressive disclosure > stuffing system prompt
3. Subagents as capability extension without tool proliferation
4. Structured tool output (like AskUserQuestion) > hoping model follows format instructions
5. "What works for one model may not be the best for another"
