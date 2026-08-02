---
task_id: "T04"
title: "create mine-fragments, mine-shape, and mine-beats skills"
status: "done"
depends_on: []
implements: ["FR#4", "FR#5", "FR#6", "FR#9", "AC#1", "AC#7"]
---

## Target Files

- create: `skills/mine-fragments/SKILL.md`
- create: `skills/mine-shape/SKILL.md`
- create: `skills/mine-beats/SKILL.md`

## Prompt

Create the three writing pipeline skills. These form a pipeline: explore (fragments) → exploit (shape OR beats). Shape and beats are alternative exploit-phase approaches, not sequential.

All three are user-invoked (`user-invocable: true`).

### mine-fragments

Adapted from Pocock's `writing-fragments` skill (search for `### 30. \`skills/in-progress/writing-fragments/SKILL.md\`` in the source material file).

Frontmatter description: "Use when the user says: \"mine fragments\", \"explore writing\", \"raw material\", \"capture fragments\", \"start writing\", \"brainstorm an article\", or wants to mine raw ideas before committing to structure."

Keep intact:
- The fragment concept (any piece that might survive into the final article — sharp sentences, claims, vignettes, half-thoughts, quotes, lists, leading words)
- The file format (H1 title, fragments separated by `---`)
- The writing rhythm (append silently, re-read before every write, preserve user edits)
- The leading word concept (compact metaphor the whole piece can hang on — the most valuable fragment)
- The "novelist's diary" framing

Adaptations:
- If the user doesn't specify a path, use `get-tmp-filename` to create a temp file (not `ask once and remember` — the session may not persist)

### mine-shape

Adapted from Pocock's `writing-shape` skill (search for `### 31. \`skills/in-progress/writing-shape/SKILL.md\`` in the source material file).

Frontmatter description: "Use when the user says: \"shape this article\", \"write paragraph by paragraph\", \"shape this writing\", \"structure this material\", or has raw material ready to shape into a finished article."

Keep intact:
- The full grounding discipline (every concept grounded before later sections lean on it — prerequisite vs introduced)
- The 6-step loop (read pile → establish prerequisites → draft openings → grow paragraph by paragraph → append as you go → loop until done)
- The conversational feel section (push back, refuse weak transitions, specific challenging moves)
- The pulling-from-the-pile section (treat raw material as quarry, name gaps explicitly)
- The format arguments section (prose vs list, inline vs callout, table vs repeated structure, quote vs paraphrase, code block vs inline)
- The writing rhythm (append per block, re-read from disk before every write)

Adaptations:
- The raw material file is passed as $ARGUMENTS or asked for if empty

### mine-beats

Adapted from Pocock's `writing-beats` skill (search for `### 29. \`skills/in-progress/writing-beats/SKILL.md\`` in the source material file).

Frontmatter description: "Use when the user says: \"write in beats\", \"beat by beat\", \"choose your own adventure writing\", \"journey-style article\", or wants to assemble an article as a series of beats the user picks between."

Keep intact:
- The full grounding discipline (same as mine-shape — prerequisite vs introduced, running grounded list)
- The beat concept (one move in the journey — sets a scene, lands a point, asks a question, drops an aside)
- The choose-your-own-adventure loop (establish prerequisites → offer 2-3 starting beats → user picks → write one beat → offer 2-3 next beats → loop)
- The beat sizing (single sentence to multiple paragraphs — if it needs five paragraphs and three subheadings, it's two beats)
- The pulling-from-the-pile section
- The writing rhythm (one beat at a time, re-read before every write, user can rewrite or go back)

Adaptations:
- Same as mine-shape: raw material file via $ARGUMENTS or asked for

## Verify

- [ ] FR#4: `skills/mine-fragments/SKILL.md` exists with fragment concept, file format, and writing rhythm
- [ ] FR#5: `skills/mine-shape/SKILL.md` exists with grounding discipline, 6-step loop, and format arguments
- [ ] FR#6: `skills/mine-beats/SKILL.md` exists with grounding discipline, beat concept, and choose-your-own-adventure loop
- [ ] AC#1: All three have `user-invocable: true` in frontmatter
