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

If the user did not say where to save the writeup, run `mktemp -d <scratchpad>/mine-writeup-XXXXXX`, write to `<dir>/writeup.md`, and tell the user where it's saved.

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

Before outlining, define the **closed-world scope**: what this writeup covers and what it does not. Carry it into the outline as one line above the outline itself:

> "In scope: [list]. Everything else stays in the source docs."

The outline approval in Phase 3 is the single gate for both scope and structure: a reader who disagrees with the scope sees it there. Once the outline is approved, the scope is locked. Do not add topics, sections, or findings outside it unless the user asks.

---

## Phase 3: Outline

Propose an outline using the structural template below. Not every section is mandatory. Drop sections that don't apply and say which you're dropping and why.

### Structural Template

**1. Bottom line** (mandatory, 1 paragraph)
Everything the reader needs if they stop here. What you found, what it means, what you need from them. Lead with the answer, not the journey that got you there.

**2. Situation** (drop for one-pagers or when the reader already has context)
What the reader already knows. Just enough to establish shared ground, without explaining things the audience already understands.

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
Only risks that could change the shape of the work — the few that matter, not an inventory. Each stated plainly: what could go wrong, why it matters, what to do about it.

**7. Appendix pointer** (mandatory)
One line pointing to the full source material for readers who want the evidence.

The So What and Forwarding tests in section 3 are duplicated from `rules/common/writing-discipline.md` by design (this skill must be self-contained). If you change the tests here, update the other file too.

### Reader Brief

Alongside the outline, draft the brief that Phase 5's cold reader will get. Phase 1's audience answer is a label. The reader needs knowledge boundaries, so infer them from the audience answer and the source material:

- **Persona:** the reader's role, what they **know** (their domain, the business context), and what they **do NOT know** (this work's internal vocabulary, methods, earlier drafts, anything only the source docs contain). Be specific: "doesn't know statistics vocabulary (precision, holdout, confidence interval)" beats "non-technical."
- **Reading goal:** what this reader needs to do with the document, from Phase 1's outcome answer plus anything the user said.
- **Intent:** `decide` for "Make decisions", `recommend` for "Approve an approach", `describe` for "Understand scope" or "Be informed".
- **Deliberate positions:** statements the writeup will make on purpose that might look like they break the intent, such as firm requirements in a descriptive writeup. Often none.
- **Intended takeaways:** the 3–5 things the reader should be able to repeat after one read, with the key number for each where there is one. The reader never sees these. Phase 5 compares them against what the reader reports.

### Outline Approval

Show the scope line, then the proposed outline as a bullet list with one-line descriptions of what each section will contain, then the reader brief.

```yaml
AskUserQuestion:
  question: "Here's the scope, outline, and reader brief. Approve, adjust, or cut anything before I start writing."
  header: "Outline"
  multiSelect: false
  options:
    - label: "Approved"
      description: "Write the full draft"
    - label: "Adjust"
      description: "I'll tell you what to change or cut"
```

If "Adjust": apply changes and re-confirm. No prose is written until the outline is approved.

---

## Phase 4: Write

Write the full draft to the writeup file once the outline is approved. Run Phase 5 before presenting it. If the user wants a section rewritten, cut, or shortened, edit it in place.

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
- **Short paragraphs.** One idea each. A paragraph doing two jobs gets split.
- **Tables for parallel structure.** If the same shape repeats 3+ times, use a table.

Re-read the writeup file from disk before every write. Preserve user edits. If the user wants a section rewritten, edit that section in place.

---

## Phase 5: Reader Test

The three-layer check above is the author's self-check, and an author can't un-know what they meant. Before presenting the draft, have a cold reader with the persona's knowledge read it. The reader's findings are hypotheses about the text. The user's scope and the stated intent outrank the reader's reactions.

Skip this phase when the gap is small: a short writeup for a reader who already shares the context, with few numbers to check. Say that you skipped it and why. Run it whenever the reader is far from the work or the writeup leans on numbers.

### Isolate and dispatch

1. Run `mktemp -d <scratchpad>/mine-writeup-reader-XXXXXX` and copy the writeup into it as `document.<ext>` (keep the original extension). Nothing else goes in this directory.
2. Run `mktemp -d <scratchpad>/mine-writeup-key-XXXXXX` and write the intended takeaways to `<key-dir>/intended-takeaways.md`. Never give the reader this path or quote the takeaways in its prompt.
3. Dispatch the `cold-reader` agent with the brief from Phase 3: `document` (the copied path), `persona` (role, knows, does NOT know), `reading_goal`, `intent`, and `deliberate_positions`. Pass the brief only. Don't add your own commentary about the document.

If it returns `{"error": "incomplete brief", ...}`, fill in the named fields and dispatch again.

### Compare and verify

**Teach-back against takeaways.** For each intended takeaway, mark it `landed`, `partly` (it's there, but late, vague, or missing its key number), `missed`, or `misread`. Also note any teach-back key point that isn't among the takeaways. A point the reader took away that the author didn't intend is often a misreading caused by emphasis.

Every takeaway marked `partly`, `missed`, or `misread` is a fix in its own right, whether or not the reader raised a finding about it. The reader can only quote text that exists, so a takeaway the draft leaves out may produce no finding at all. Write each fix from the scope-locked sources: add the missing point, move it earlier, or give it its key number. For a `misread`, reword or re-emphasize the passage that misled the reader. If the sources can't support the fix (the key number isn't in them), don't invent it. List the takeaway for the user as a possible follow-up, like an out-of-scope finding.

**Perceived asks against intent.** For `decide` and `recommend`, check that the reader's `perceived_asks` names the actual decision or recommendation. A reader who walks away with the wrong ask is the most expensive failure for those writeups. For `describe`, the reader should perceive no ask. If it does, something in the writeup reads like a request.

A wrong, missing, or unwanted perceived ask is a fix too, planned the same way as a takeaway fix: an omitted ask leaves nothing to quote, so the reader may raise no finding about it. State the decision or recommendation plainly and early, or reword the passage that reads as a request. Write it from the scope-locked sources and the stated intent.

**Verify every finding before presenting it.** The reader only has the document, so its findings are hypotheses about the text:

- `unsupported-number`: check it against the source material. Fix it if the number is wrong or doesn't reconcile. If it's right but the document doesn't show why, add the denominator, population, or period.
- A finding that conflicts with the stated intent or a deliberate position (the reader slipped anyway): set it aside.
- A finding that asks for content outside the Phase 2 scope (a cost analysis the sources don't contain, a new section): don't add it. List it for the user as a possible follow-up. The scope lock still holds.
- Everything else: decide whether it's real for this audience. Set it aside if not, and give a one-line reason.

Keep the reader's `works_well` passages intact when planning fixes: a revision that removes what already worked leaves the reader worse off. A verified fix still wins when the passage itself is the problem, such as a wrong number or content outside the scope. Flag that conflict next to the fix.

### Present

Show the user, before the draft:

1. The takeaway table (takeaway → landed / partly / missed / misread), plus the perceived ask if it's wrong.
2. The fixes you plan to make, grouped by section: verified findings, each with the quote and the fix, takeaway fixes, each with the takeaway and the fix, and the ask fix, if any, with the perceived and intended ask.
3. Out-of-scope requests and set-aside findings, each with its one-line reason.
4. The reader's `overall_verdict`, its `forwardable` answer, and the `works_well` passages.

If every takeaway landed and nothing needs fixing, say so and present the draft. There's nothing to ask. If the verdict is `lost`, or several takeaways were missed or misread, line-level fixes won't help: recommend restructuring the sections that lost the reader, and offer it as an option in place of "Pick fixes". Otherwise ask:

```yaml
AskUserQuestion:
  question: "The cold reader's results are above. How should I handle the fixes?"
  header: "Reader"
  multiSelect: false
  options:
    - label: "Apply the fixes"
      description: "Edit the draft with the planned fixes; I'll offer a second cold read if they change numbers, rewrite whole sections, add or move a takeaway, or change the ask"
    - label: "Pick fixes"
      description: "I'll tell you which to apply"
    - label: "Skip"
      description: "Present the draft as-is"
```

After applying fixes, whether all of them or a picked subset, offer a second cold read when the fixes changed numbers, rewrote whole sections, added or moved a takeaway, or changed the ask. Use a fresh dispatch on a freshly copied document. A second read finds problems the first missed, especially in numbers that the fixes introduced. Don't loop beyond that unless the user asks.

Then present the draft. From here, Phase 4's editing rules apply: when the user wants a section rewritten, cut, or shortened, edit it in place.

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
