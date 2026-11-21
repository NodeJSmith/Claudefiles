---
name: mine-prior-art
description: "Use when the user says: \"prior art\", \"how do others do this\", \"what patterns exist\", \"industry standards for X\", or wants to survey external approaches."
user-invocable: true
---

# Prior Art

Find out how others solve a problem and bring it back with relevance to this project. Web-first: the point is to look outside the codebase, with the local code used only as comparison context. Typically invoked mid-design, when an architectural question comes up and the user wants to see how others handle it before committing.

A common answer is "they don't bother": peers accept the limitation, document it, or handle it far more simply than the fix on the table. That is as valuable as a pattern, and the research has to look for it on purpose, because search results favor writeups about elaborate solutions.

It answers "how do others solve X?" Use `/mine-research` for what X would take in this codebase, `/mine-sketch` for how to build it, and `/mine-eval-repo` for whether one specific library is worth adopting.

## Arguments

$ARGUMENTS — the topic to survey (a pattern question, a technology survey, a problem-first query). If empty or too vague to search ("caching" versus "how teams handle cache invalidation"), ask what to survey. Ask one disambiguation question if the topic spans domains ("memory management" could be OS, LLM context, or databases); otherwise start. The user already knows what they want, so keep this fast.

## Invoking From a Convergence Gate

The convergence gates in `/mine-challenge` (`findings-protocol.md`) and `/mine-address-pr-issues` (`SKILL.md`) send a mechanism here when several findings keep landing on it. Both follow this section so the two gates stay in step.

**Whether to run it.** Run it when the mechanism deals with a problem other projects also face: reconnection, scheduling, retries, caching, state sync between components. Skip it when the mechanism is internal to the codebase, like its own file format or a skill's state file, because there is nothing outside to compare against. A re-evaluation done only inside the session tends to produce a better custom fix when comparable projects use a simpler one, or none.

**The topic.** Name the mechanism, the failure modes the converging findings describe, and the fixes proposed or applied so far. Ask whether comparable projects guard against those failure modes at all, how much machinery they use, or whether they accept and document the limitation.

**After the brief.** The gate opens its discussion with the brief's recommendation. Accepting the limitation and documenting it is a valid outcome of that discussion.

## Research

Check the project's CLAUDE.md frontmatter for a `peers` field (see `${CLAUDE_CONFIG_DIR:-~/.claude}/rules/common/project-context.md`); those are the comparable projects to search first.

Make a temp directory with `mktemp -d <scratchpad>/mine-prior-art-XXXXXX` (keep the exact path) and launch two `standard-worker` subagents in parallel.

**Local context.** A lightweight look (a few file reads) at how the codebase handles the topic today, which conventions or prior decisions bear on it, and what constraints the architecture imposes. It returns a short summary as its result message, or "No relevant local implementation found." This only fills "How We Do It Today".

**Web research**, the primary track. Substitute the real topic, peers, and tmpdir into the prompt. It should carry the following, with the Depth and Output bullets passed through as written, since they are what keeps the subagent from returning snippets:

- The topic, and the instruction to cite URLs where found and mark unsourced patterns `[no source found]` rather than fabricate one.
- The peers to search first (and to say so if none of them handle the problem), or, with no peers, to first name 2-5 projects solving the same problem for a similar audience.
- Breadth: how popular open-source projects handle it, blog posts and experience reports, official docs, RFCs, talks, documented pitfalls, and where projects deliberately don't handle it (won't-fix issues, documented limitations, FAQ entries). Accepting a limitation is a pattern; record it as one.
- Depth, because the brief informs a design decision and a wrong claim about what a project does is worse than none. A search snippet shows a page exists, not what it says, and docs show intent where code shows behavior, including the edge cases this research exists to compare. So for each project the answer depends on, open the code that does the thing (or, if the topic isn't software behavior, the primary source: the paper, the spec, the maintainer's explanation). A changelog can date a behavior or point to the PR; follow it to the code. Read source with `gh` (tree listing, `gh search code`, raw contents), or a `git clone --depth 1` into `<tmpdir>/src/<repo>` when it needs grepping; page-fetch tools summarize and truncate, so keep those for prose. A project it didn't get to isn't a gap; read it or leave it out. A gap is something it tried and couldn't get, recorded with what it tried.
- Output: write `<tmpdir>/web-research.md` with `## Sources Found` (per source: URL, type, **Opened** yes/no, key takeaway, relevance), `## Patterns Found`, and optional `## Anti-Patterns`, `## Emerging Trends`, `## Gaps` (omit when empty). Each pattern has **Used by**, **How it works**, **Strengths**, **Weaknesses**, **Example** (link or `[no source found]`), and **Read**: for each project in Used by, the file or page opened as a path or permalink, or `secondary:` plus what the claim rests on.

When both return, read `<tmpdir>/web-research.md` and confirm it has `## Patterns Found`. Missing or empty: offer to retry. Thin: proceed and flag the coverage gap when presenting. Then check the **Read** fields: if a claim the recommendation will rest on is `secondary:` and the code is publicly readable, read it yourself or send the subagent back before synthesizing. Opening it takes a minute; a recommendation resting on unopened code can be wrong.

Merge the local summary and web research into `<tmpdir>/brief.md` (the web sections carry through as they are; 3-5 patterns, more if the space is rich):

```markdown
---
topic: "<topic>"
date: YYYY-MM-DD
status: Draft
---

# Prior Art: <Topic>

## The Problem
## How We Do It Today
## Patterns Found
## Anti-Patterns (optional)
## Emerging Trends (optional)
## Gaps (optional)
## Relevance to Us
## Recommendation
## Sources
```

- **The Problem:** what the survey addresses and why teams care.
- **How We Do It Today:** short; comparison context, not the subject. "We don't have this yet" is valid.
- **Patterns and the optional sections:** same schema as `web-research.md`, including each pattern's Used by / How it works / Strengths / Weaknesses / Example / Read.
- **Relevance to Us:** how the patterns map to this project's conventions, and the gap to best practice. If the topic includes fixes being weighed, say plainly where they build more machinery than comparable projects do.
- **Recommendation:** which patterns are worth considering, or "none of these fit, and why". "Accept the limitation and document it" is valid when that's what peers do. Be honest about research gaps.
- **Sources:** all URLs grouped as reference implementations, blog posts and writeups, documentation and standards, each with a one-line description; mark any whose **Opened** is no as `(not opened)`.

## Present

Lead with the recommendation and the one or two most surprising or relevant patterns; the user is mid-task and wants the actionable takeaway, not a recap of the brief. Surface notable anti-patterns and coverage gaps. If coverage was thin, say so ("only N sources found; this may not represent the full landscape"), since a thin area is itself information.

Save the brief to `design/research/YYYY-MM-DD-<topic>/prior-art.md` (topic as a lowercase hyphenated slug, 40 characters max; create the directory) and end by giving the path. The `prior-art.md` name lets it sit beside a `/mine-research` brief on the same topic, and it's worth keeping even when the immediate question is settled.

Then return control. This runs mid-conversation, so don't gate the user with a follow-up menu.

## Principles

It informs decisions and produces no implementation plan; the user decides what to adopt. A survey of snippets is a list of guesses, so read the implementation of each project the answer depends on, and mark what you couldn't source.
