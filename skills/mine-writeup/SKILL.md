---
name: mine-writeup
description: "Use when the user says: \"write this up\", \"write up for my boss\", \"summarize this for leadership\", \"executive summary\", \"distill this research\", \"write a summary for leadership\", or needs to turn technical research into a readable document for a specific audience."
user-invocable: true
---

# Writeup

Turn technical research, investigation notes, or dense working documents into a document a specific reader can act on. The input is messy and thorough; the output is structured and scannable.

This skill is an **editor**, not a researcher. It works from existing material. It does not discover new findings, expand scope, or add sections the user did not ask for. See [Editorial Discipline](#editorial-discipline).

## Arguments

$ARGUMENTS — path(s) to the source material. Multiple paths separated by spaces. If empty, ask the user to point you at the documents to distill. If a given path doesn't resolve, say so explicitly rather than surfacing a raw tool error.

Read every source file end-to-end before doing anything else. **Do not edit the source files. They are read-only to this skill.**

If the user did not say where to save the writeup, run `get-skill-tmpdir mine-writeup`, write to `<dir>/writeup.md`, and tell the user where it's saved.

---

## Phase 1: Audience and Outcome

Before writing anything, settle three things. Ask them together in one `AskUserQuestion` call. Skip any already answered by the user's prompt.

```yaml
AskUserQuestion:
  questions:
    - question: "Who reads this?"
      header: "Audience"
      multiSelect: false
      options:
        - label: "My manager"
          description: "They need to understand scope and make decisions or carry the message up"
        - label: "Leadership / execs"
          description: "Time-poor, need the bottom line and what they need to decide"
        - label: "Cross-team peers"
          description: "Technical but not close to this work, need enough context to engage"
        - label: "Mixed / not sure"
          description: "Multiple audiences or you'll help me figure it out"
    - question: "What should the reader do after reading this?"
      header: "Outcome"
      multiSelect: false
      options:
        - label: "Make decisions"
          description: "There are open questions and you need answers before work can proceed"
        - label: "Understand scope"
          description: "The work is bigger or more complex than expected and they need to see why"
        - label: "Approve an approach"
          description: "You've figured out the how — you need sign-off"
        - label: "Be informed"
          description: "No action needed, just awareness"
    - question: "How long should this be?"
      header: "Length"
      multiSelect: false
      options:
        - label: "One page"
          description: "A Slack message or single page, executive summary density"
        - label: "2-3 pages"
          description: "Room for context and detail, still scannable"
        - label: "Whatever it takes"
          description: "As long as needed, but not longer"
```

Use the answers to calibrate depth, tone, and which sections to include. A one-page writeup for a manager skips the situation section entirely and leads with the bottom line. A 2-3 page writeup for leadership includes situation and curated findings. "Whatever it takes" includes every applicable section but still applies the So What test to every paragraph.

---

## Phase 2: Scope Lock

Before outlining, define the **closed-world scope**: what this writeup covers and what it does not. State it back to the user:

> "Based on the source material and what you've told me, here's what I think belongs in the writeup: [list]. Everything else stays in the source docs. Sound right?"

The user may add or remove items. Once confirmed, the scope is locked. Do not add topics, sections, or findings outside this scope unless the user asks.

---

## Phase 3: Outline

Propose an outline using the structural template below. Not every section is mandatory. Drop sections that don't apply and say which you're dropping and why.

### Structural Template

**1. Bottom line** (mandatory, 1 paragraph)
Everything the reader needs if they stop here. What you found, what it means, what you need from them. Lead with the answer, not the journey that got you there.

**2. Situation** (drop for one-pagers or when the reader already has context)
What the reader already knows. 2-3 sentences that establish shared ground without explaining things the audience already understands.

**3. What we found** (mandatory when source material contains investigation results)
Curated findings, only those that change a decision or the shape of the work. Each finding stated as: **[fact] → [so what for the project]**. Technical evidence referenced but not inlined.

Apply the **So What test**: does this finding change a decision the reader needs to make? If not, it does not belong here. It belongs in the source material, which the writeup can point to.

Apply the **Forwarding test**: if the reader forwards this to *their* boss, will this finding still make sense without the reader explaining it? If not, rewrite or cut.

**4. The real scope** (include when the work is larger or more complex than expected)
What actually has to be built or done, by whom, in what order. No hour or week estimates unless the user explicitly asks for them. Show structural dependencies (what gates what), not duration guesses.

**5. Proposed approach** (include when the outcome is "approve an approach")
What the user is recommending and why. State the approach, the key tradeoffs considered, and what sign-off enables. Keep it concrete: the reader should know exactly what they are approving.

**5a. Decisions needed** (mandatory when the outcome is "make decisions")
Table format: what needs deciding, who can decide it, what it gates. Ordered by urgency. This is what the reader takes into the room.

**6. Risks** (include when risks could change the timeline or kill the project)
Only risks that could change the shape of the work. 3-5 items max. Each stated plainly: what could go wrong, why it matters, what to do about it.

**7. Appendix pointer** (mandatory)

The So What and Forwarding tests in section 3 are duplicated from `rules/common/writing-discipline.md` by design (this skill must be self-contained). If you change the tests here, update the other file too.
One line pointing to the full source material for readers who want the evidence.

### Outline Approval

Show the proposed outline as a bullet list with one-line descriptions of what each section will contain. The user approves, adjusts, or cuts sections before any prose is written.

---

## Phase 4: Write

Write section by section, showing each to the user before moving to the next. Append to the writeup file as each section is approved.

### The Three Layers

The writeup must work at three reading speeds:

- **30 seconds** (the bottom line paragraph alone): the reader knows the answer
- **3 minutes** (section headers + first sentences): the reader knows the shape
- **30 minutes** (full read): the reader understands the reasoning

If a section only works at the 30-minute layer, it needs rewriting.

### Writing Rules

- **Answer first, evidence second.** Every section leads with its conclusion. The reasoning follows for readers who want it.
- **No jargon without earning it.** If a technical term is necessary, define it in plain language on first use. If it's not necessary, use the plain language instead.
- **Concrete over abstract.** "The network path doesn't exist yet" beats "infrastructure prerequisites remain outstanding."
- **Short paragraphs.** 2-4 sentences. A paragraph longer than 5 sentences probably contains two ideas.
- **Tables for parallel structure.** If the same shape repeats 3+ times, use a table.

Re-read the writeup file from disk before every write. Preserve user edits. If the user wants a section rewritten, edit that section in place.

---

## Editorial Discipline

This skill operates as an editor with a locked scope. These rules override the default instinct to be thorough:

- **Do not add findings, analysis, or context the user did not include in the scope lock.** The source material may contain more than the writeup needs. That is by design.
- **When the user says cut, cut.** Do not argue, do not move content to an appendix, do not summarize it into a smaller section. Delete it.
- **When the user says "shorter", make it shorter.** Do not preserve length by compressing. Remove content. The user is telling you what they don't need, not asking you to say it faster.
- **Do not re-expand.** If a section was cut or shortened, do not reintroduce that content in another section under a different framing.
- **The user's editorial judgment overrides completeness.** If the user says a finding doesn't belong, it doesn't belong, even if you think it's important. The user knows their audience.

---

## Handoff

When the writeup is complete:

> Writeup saved at `<path>`. Source material is at `<source paths>` for anyone who wants the full evidence.

If the user wants to refine the prose quality, point them at `/mine-humanize <path>`.
