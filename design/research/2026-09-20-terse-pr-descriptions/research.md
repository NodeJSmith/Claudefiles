---
topic: "terse, outcome-focused PR descriptions that exclude mid-development narration"
date: 2026-09-20
status: Draft
---

# Prior Art: Terse, Outcome-Focused PR Descriptions

## The Problem

PR descriptions are meant to be read by someone with zero session context — a reviewer today, a teammate in a year, the author themselves after forgetting the details. Two failure modes compete for that reader's attention: exhaustive detail (narrating every file touched, every intermediate attempt) and vagueness (a one-line non-answer). The specific failure motivating this survey is the first kind, and a subtype of it: prose that narrates the *development process* ("tried X, ended up doing Y because Z") rather than the *shipped state and its durable rationale*. This has become a more visible problem with AI-authored PR text specifically, since an LLM has no incentive to skip retelling its own reasoning process the way a human author — who finds writing tedious — naturally would.

## How We Do It Today

`skills/mine-create-pr/worker.md` (Step 5, "Draft PR Body") is the only place PR description generation actually happens, and it currently pushes in the opposite direction: it asks for a "comprehensive" PR and instructs bullets to include "motivation, tradeoffs, or decisions worth preserving" with no length ceiling and no exclusion for mid-development narration. `rules/common/git-workflow.md`'s Changelog Timing section covers changelog entries specifically, not PR description prose. `rules/common/writing-discipline.md` has the right general rules (cut before polish, one idea per paragraph) but is never cross-referenced from the PR-generation path, so nothing forces it to apply there.

## Patterns Found

### Pattern 1: What/Why Structure (durable rationale only, no process log)

**Used by**: Google (CL descriptions), Kubernetes, HackerOne, freeCodeCamp, Cloud City, Graphite, most major OSS CONTRIBUTING.md guides.

**How it works**: The description answers exactly two questions — "what changed" (enough to understand the diff's intent without reading it) and "why" (the problem, the reasoning for the chosen approach, tradeoffs, known shortcomings, links to design docs/tickets for depth). Google frames this explicitly as a *permanent historical record* for readers with no session memory — which is the structural reason exploration narration doesn't belong: it answers "how did the session go," a question nobody with zero context is asking.

**Strengths**: Scales to a reader with zero context, years later. Forces distillation: if a detail doesn't answer "what" or "why," cut it.

**Weaknesses**: Requires discipline — nothing mechanically stops an author from smuggling narration into the "why" section by treating "why Y" as "here's everything I considered."

**Example**: https://google.github.io/eng-practices/review/developer/cl-descriptions.html

### Pattern 2: Structural Enforcement via History Rewriting (squash/rebase before merge)

**Used by**: GitHub (squash-and-merge, rebase-and-merge), GitLab (squash and merge), general git convention.

**How it works**: Rather than trusting the description to stay terse, the commit history itself is rewritten before merge so exploratory/false-start/"oops" commits never survive. Interactive rebase reorders, squashes, and edits commits into a coherent argument; GitHub's squash-and-merge automates the simplest version.

**Strengths**: Mechanical, not prose-dependent — there's no diary left to summarize badly.

**Weaknesses**: Only addresses commit history, not the PR description itself, which is a separate artifact an author can still narrate into even after a clean squash. Not directly applicable here since this repo's workflow rules don't currently mandate squash-merge.

**Example**: https://docs.gitlab.com/user/project/merge_requests/squash_and_merge/

### Pattern 3: Template-Enforced Fields (structure as the terseness mechanism)

**Used by**: Kubernetes (`PULL_REQUEST_TEMPLATE.md` + `/kind` classification bot), React Native (mandatory single-line `## Changelog` field, structurally separated from free-form context).

**How it works**: The template only offers slots for what's supposed to survive — a classification, a "what and why" field, or a strict single-line changelog entry visually separated from longer reviewer-only context. No field is shaped like "narrate your process," so going off-template takes conscious effort.

**Strengths**: The strongest enforcement rung short of a linter — matches this repo's own `encode-lessons-in-structure.md` principle (pick the strongest rung; an empty box constrains more reliably than an instruction to "be concise").

**Weaknesses**: Constrains shape, not length or content within a field — an author can still write a wall of text inside one slot.

**Example**: https://github.com/kubernetes/kubernetes/blob/master/.github/PULL_REQUEST_TEMPLATE.md

## Anti-Patterns

- **Line-by-line diff narration** — freeCodeCamp/HackerOne both explicitly instruct against describing the diff line by line.
- **Verbose, cheap-to-produce-but-expensive-to-consume writing**, named specifically for AI-generated PR/review content — narrating design decisions "unprompted" burns reviewer attention without adding decision-relevant information. (https://dev.to/cseeman/return-on-attention-why-ai-code-reviews-are-wearing-us-out-2hh0)
- **Vague, information-free summaries** ("Fix bug," "Phase 1") — Google's mirror-image failure. Worth naming because terse-but-empty is as much an anti-pattern as verbose-and-narrated — the fix isn't "shorter," it's "only durable what/why content."
- **Messy WIP/fix-typo/oops commit trails reaching the default branch** — universally treated as something squash-and-merge exists to prevent.

## Emerging Trends

Multiple 2026 sources treat "LLM-authored PR content defaults to narrated, exploration-heavy prose" as an actively-discussed, named failure mode (not hypothetical) — the dev.to "Return on Attention" piece frames it as a direct cost to reviewer attention, distinct from and in addition to Google's decade-old what/why guidance. This matches the exact prompt for this survey: AI authorship makes the old implicit human norm (a person wouldn't bother writing all that down) newly violable by default, which is why it now needs to be stated explicitly rather than assumed.

## Relevance to Us

This repo already has the two ingredients Pattern 1 needs (a place to state what/why, and `writing-discipline.md`'s general cutting rules) but they aren't wired together for PR descriptions specifically, and `mine-create-pr/worker.md` actively pushes the opposite way ("comprehensive," motivation/tradeoffs with no bound). Pattern 2 (squash/rebase) isn't a fit — nothing in this repo's workflow currently mandates squash-merge, and adopting it would be a bigger workflow change than the ask. Pattern 3 (template-enforced fields) is the strongest mechanism but Claude generates the description directly rather than filling a GitHub PR template UI, so the "empty box" has to be simulated as an explicit generation-time rule rather than a literal template file.

## Recommendation

Adopt Pattern 1 (What/Why, durable-only) as the content rule, applied at the point where it's actually generated:

1. **Add a "PR Description Content" subsection to `rules/common/git-workflow.md`**, sibling to the existing Changelog Timing section (same file, same audience, same "generated at PR-creation time" framing already established there). State the rule as: PR descriptions capture the shipped state and its durable rationale, not the development process that produced it — explicitly excluding "tried X, ended up doing Y because Z" framing and other mid-PR narration, even when true. This gives the rule a stable, cross-referenceable home (matches how `mine-review`/`mine-humanize` could point at it too) rather than burying it inside one skill's worker file.
2. **Tighten `skills/mine-create-pr/worker.md` Step 5**: drop "comprehensive," add an explicit reference to the new git-workflow.md rule, and narrow the "why/motivation/tradeoffs" instruction so it can't be read as license to narrate exploration — the fix should target the exact sentence that currently invites it, not just add a rule alongside it.
3. Treat vague terseness ("Fix bug") as an equally real failure the new rule should guard against — don't let "cut the narration" regress into "cut the rationale too."

No new standalone rule file is warranted; this is a narrow, well-scoped addition to an already-relevant, already-loaded file, consistent with `subtract-first.md`/`laziness-protocol.md` bias against unnecessary new files.

## Sources

### Reference implementations
- https://github.com/kubernetes/kubernetes/blob/master/.github/PULL_REQUEST_TEMPLATE.md — Kubernetes PR template with `/kind` classification, no narration field
- https://reactnative.dev/contributing/changelogs-in-pull-requests — React Native's mandatory single-line changelog field, separated from free-form context

### Blog posts & writeups
- https://graphite.com/guides/github-pr-description-best-practices — Summary + Context, link to docs instead of re-narrating
- https://www.freecodecamp.org/news/how-to-write-a-pull-request-description/ — explicit "don't describe the diff line by line"
- https://www.hackerone.com/blog/writing-great-pull-request-description — What/Why/How structure
- https://cloudcity.io/blog/2022/08/08/what-to-include-in-a-pull-request-description/ — What/Why/How template
- https://dev.to/cseeman/return-on-attention-why-ai-code-reviews-are-wearing-us-out-2hh0 — AI-specific narration anti-pattern, "cheap to produce, expensive to consume"
- https://css-tricks.com/interactive-rebase-clean-up-your-commit-history/ — interactive rebase for coherent history
- https://www.cloudbees.com/blog/git-squash-how-to-condense-your-commit-history — squash-and-merge rationale

### Documentation & standards
- https://google.github.io/eng-practices/review/developer/cl-descriptions.html — canonical What/Why CL description guide
- https://docs.gitlab.com/user/project/merge_requests/squash_and_merge/ — squash-and-merge as first-class merge strategy
- https://keepachangelog.com/en/1.0.0/ — changelog written for a reader with no session memory
- https://conventionalcomments.org/ — adjacent: labeled review-comment structure
