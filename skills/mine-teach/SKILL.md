---
name: mine-teach
description: "Use when the user says: \"teach me\", \"help me learn a new topic\", \"lesson on\", \"tutorial on\", or wants structured learning over multiple sessions. Not for explaining code in the current repo — that's mine-how or mine-document."
user-invocable: true
---

# Teach

The user has asked to learn something. This is a stateful request — they intend to learn the topic over multiple sessions, not just this one.

## Getting Started

Check the current directory for `MISSION.md` before doing anything else.

- **No `MISSION.md`, or it's empty** — this is a first run. Ask why the user wants to learn the topic (see [The Mission](#the-mission)) before writing any file — and per [Teaching Workspace](#teaching-workspace), confirm the directory itself before that first write.
- **`MISSION.md` exists** — this is a returning session. Read `MISSION.md`, then `RESOURCES.md` and `learning-records/` if they exist yet (both are created lazily, so an early returning session may not have either), state briefly where the user left off, then propose the next lesson using [Zone of Proximal Development](#zone-of-proximal-development).

## Teaching Workspace

Treat the current directory as a teaching workspace. Before creating any file here for the first time, confirm with the user that this directory is where they want the teaching workspace — especially if it looks like an existing code repo rather than a dedicated learning space. The state of the user's learning lives in these files:

```
/
├── MISSION.md
├── RESOURCES.md
├── NOTES.md
├── learning-records/
│   └── 0001-<kebab-case-name>.md
├── lessons/
│   └── 0001-<kebab-case-name>.html
├── reference/
│   └── *.html
└── assets/
    └── *
```

- **`MISSION.md`** — the *reason* the user is interested in the topic. Grounds all teaching. Format in [The Mission](#the-mission).
- **`RESOURCES.md`** — high-quality resources to ground teaching in contextual knowledge or acquire wisdom. Format in [Knowledge](#knowledge).
- **`learning-records/*.md`** — non-obvious lessons and key insights, loosely equivalent to architecture decision records. Titled `0001-<kebab-case-name>.md`, incrementing. Used to calculate the zone of proximal development. Format in [Zone of Proximal Development](#zone-of-proximal-development).
- **`lessons/*.html`** — the primary unit of teaching. A lesson teaches one tightly-scoped thing tied to the mission, with no network dependency (see [Lessons](#lessons) for what "self-contained" means here). Titled `0001-<kebab-case-name>.html`, incrementing.
- **`reference/*.html`** — compressed learnings distilled from lessons: cheat sheets, reference algorithms, syntax, glossaries. Designed for quick lookup, not narrative reading.
- **`assets/*`** — reusable components shared across lessons: stylesheets, quiz widgets, simulators, diagram helpers. See [Assets](#assets).
- **`NOTES.md`** — a scratchpad for the user's preferences and working notes on how they want to be taught.

Create files lazily — only when there's something to write. Don't scaffold empty directories up front.

## Philosophy

Deep learning needs three things:

- **Knowledge**, captured from high-quality, high-trust resources
- **Skills**, acquired through highly-relevant interactive lessons built from that knowledge
- **Wisdom**, which comes from interacting with other learners and practitioners

Before `RESOURCES.md` is well-populated, focus on finding high-quality resources that will help the user acquire knowledge. Never trust parametric knowledge over a cited source.

Some topics lean more on knowledge (theoretical physics), others more on skills (yoga). Read the topic and weight lessons accordingly.

### Fluency vs Storage Strength

Split between two types of learning:

- **Fluency strength** — in-the-moment retrieval of knowledge
- **Storage strength** — long-term retention of knowledge

Fluency gives an illusory sense of mastery; storage strength is the real goal. Design lessons for long-term retention through desirable difficulty:

- **Retrieval practice** — recall from memory, not re-reading
- **Spacing** — distribute practice over sessions rather than cramming
- **Interleaving** — mix related-but-distinct topics in skills practice

## Lessons

A lesson is the main artifact — the unit in which knowledge and skills reach the user. Each lesson is an HTML file, saved to `./lessons/` and titled `0001-<kebab-case-name>.html`.

**Self-contained means no network dependency, not no local links.** No CDN links — no Tailwind CDN, no external font or script loads, no dependency on the internet at all. Inline any CSS or JS that isn't already a shared workspace component; for shared components, use relative-path links to `./assets/` instead of duplicating them (see [Assets](#assets)). The portable unit is the whole teaching workspace — `lessons/`, `assets/`, and `reference/` kept together — not each HTML file in isolation. Keep the workspace directory intact: a lesson opened offline, months later, must still render exactly as it did the day it was written.

A lesson should be **beautiful** — clean, readable typography and layout, in the spirit of Tufte — since the user will return to it later to review.

Keep lessons short and quickly completable. Working memory is small; each lesson should deliver one tangible win the user can build on. It should tie directly to the mission and sit in the user's zone of proximal development.

If a CLI command exists to open the file for the user (e.g. a browser opener), run it after writing the lesson.

Each lesson should:
- Link via HTML anchors to related lessons and reference documents
- Recommend a primary source — the highest-quality, highest-trust resource found on the topic
- Remind the user to ask follow-up questions in the session — you are their teacher and can clarify anything unclear

## Assets

Lessons are built from reusable **components**, stored in `./assets/`: stylesheets, quiz widgets, simulators, diagram helpers — anything a second lesson could reuse.

Reuse is the default, not the exception. Before authoring a lesson, read `./assets/` and build from what's already there. When a lesson needs something new and reusable, write it as a component in `./assets/` and link to it — never inline code a future lesson would duplicate.

A shared stylesheet is the first component every workspace earns: every lesson links it, so the lessons read as one consistent course rather than a pile of one-offs. Grow the component library as the workspace grows.

## The Mission

Every lesson ties back to the mission — the reason the user wants to learn this topic.

If the user is unclear about the mission, or `MISSION.md` isn't populated, the first job is to question the user on why they want to learn this — use the format below.

Skipping this grounds nothing: without a mission, knowledge acquisition floats free of real-world goals, lessons feel abstract, and there's no basis for judging what to teach next.

### MISSION.md Format

`MISSION.md` captures *why* the user wants to learn this topic — the reason all teaching in the workspace is grounded against. Without it, lessons drift toward generic coverage instead of what actually serves the user.

```markdown
# Mission

## Why I'm Learning This
<The reason — what goal this serves, what problem it solves>

## Current Level
<Where the user is now — beginner, some exposure, practitioner switching domains>

## Target
<What "done" looks like — what the user wants to be able to do>

## Constraints
<Time budget, preferred learning style, tools available>
```

#### MISSION.md Rules

- Write this before the first lesson. If the user hasn't stated a mission, ask why they want to learn the topic before doing anything else — a lesson built on an unstated mission is a guess.
- **Current Level** is self-reported, not tested. Don't quiz the user to calibrate this on day one; let the first lesson or two calibrate it naturally and revise if it was off.
- **Target** should be concrete enough to judge progress against ("read production Rust without looking up syntax", not "learn Rust"). If the user gives a vague target, ask a follow-up to sharpen it.
- **Constraints** matters for lesson pacing — a user with 15 minutes a day needs shorter, more frequent lessons than one doing a weekend deep-dive.

Missions can change as the user develops skills and knowledge — that's normal. When you notice a shift, confirm it before editing anything:

```
AskUserQuestion:
  question: "Your mission looks like it's shifted — update MISSION.md to reflect it?"
  header: "Mission"
  multiSelect: false
  options:
    - label: "Yes, update it"
      description: "Rewrite MISSION.md and add a learning record noting why the mission changed"
    - label: "Not yet"
      description: "Keep the current mission — this was a one-off tangent"
```

## Zone of Proximal Development

Each lesson should challenge the user *just enough* — not so easy it's boring, not so hard it stalls.

If the user hasn't specified an exact thing to learn, find their zone of proximal development by:

1. Reading their `learning-records/`
2. Cross-referencing against the mission
3. Teaching the most relevant thing that fits what they're ready for

### Learning Record Format

Learning records live in `./learning-records/`, one file per record, named `NNNN-kebab-case-name.md` (4-digit sequential number, incrementing, kebab-case slug). They capture non-obvious lessons and key insights — loosely equivalent to architecture decision records, but for what the user has learned rather than what a team decided.

```markdown
# NNNN: <Title>

**Date:** YYYY-MM-DD
**Lesson:** <which lesson this came from>
**Status:** active | revised by NNNN | deprecated

## Insight
<What was learned — the non-obvious takeaway>

## Evidence
<What demonstrated this — the exercise, example, or experience>

## Implications
<What this changes about future learning — what to do differently>
```

#### Learning Record Rules

- **Title** names the insight itself, not the lesson topic ("Recursion clicks when framed as delegation, not repetition" — not "Recursion lesson notes").
- Only record something genuinely non-obvious — a surprising misconception corrected, a mental model that finally worked, a gap the user didn't know they had. Routine lesson completions don't need a record.
- **Evidence** ties the insight to something concrete that happened in the session, not a restatement of the insight.
- **Implications** is what makes this useful later — it should change what gets taught next, not just document the past.
- Never edit a record's Insight after the fact to reflect new understanding. Write a new record, set the old one's Status to `revised by NNNN`.
- These records are what zone-of-proximal-development tracking reads from — before designing the next lesson, read the recent ones to see what's already landed and what's still shaky.

## Knowledge

Design lessons around a skill the user is going to acquire. Include only the knowledge required for that skill — teach the knowledge first, then drive practice through an interactive feedback loop.

Gather knowledge from trusted resources first; track them in `RESOURCES.md`. Cite sources throughout a lesson — links to external material backing any claim made. Citations are what make a lesson trustworthy.

For knowledge acquisition, difficulty is the enemy: it eats the working memory needed for understanding. Keep the knowledge portion of a lesson easy.

### RESOURCES.md Format

`RESOURCES.md` tracks high-quality learning resources — what grounds lessons in real knowledge instead of parametric recall, and what points the user toward practitioner communities for wisdom.

```markdown
# Resources

## Primary Sources
<Official docs, canonical textbooks, first-party references>

| Resource | Type | Trust | Notes |
|----------|------|-------|-------|
| <name + URL> | docs/book/video/course | high/medium | <why it's useful> |

## Community
<Forums, subreddits, Discord servers, local groups>

## To Evaluate
<Resources found but not yet vetted>
```

#### RESOURCES.md Rules

- **Primary Sources** are what lessons cite. Prefer official docs and first-party material over blog posts and secondhand tutorials — trust decays with distance from the source.
- **Trust** is a judgment call: `high` for material the author is directly authoritative on (language spec, official docs, a domain expert's own writing), `medium` for solid but secondhand coverage (a well-regarded course, a respected blogger). If a resource doesn't clear `medium`, it goes in **To Evaluate**, not **Primary Sources**.
- **Community** entries are for acquiring wisdom, not knowledge — places the user can test skills against real practitioners. Only add communities with a real reputation for quality; don't pad this section for the sake of having entries.
- **To Evaluate** is a holding pen. Move an entry to **Primary Sources** or **Community** once it's been checked, or drop it if it turns out weak. Don't let this section grow without being revisited.
- Update this file as resources surface during teaching — don't batch it up for later.

## Skills

If knowledge is about acquisition, skills are about durability and flexibility — making the knowledge stick.

For skill acquisition, difficulty is the tool. Effortful retrieval builds storage strength. Teach skills through interactive lessons:

- Interactive quizzes and light in-browser tasks
- Lessons that walk the user through real-world steps (e.g. a sequence of physical poses, a checklist to run against real equipment)

Each should run on a tight **feedback loop** — the user gets feedback on their performance as immediately and automatically as possible.

For quizzes, keep every answer the same length in words and characters where possible — don't leak the answer through formatting.

## Acquiring Wisdom

Wisdom comes from real-world interaction — testing skills outside the learning environment.

When a question needs wisdom rather than knowledge or skill, answer what you can, but ultimately point the user toward a **community**: a forum, subreddit, real-world class, or local interest group where they can test their skills against other practitioners.

Look for high-reputation communities and record them in `RESOURCES.md` (see [RESOURCES.md Format](#resourcesmd-format)). If the user says they don't want to join a community, respect it and don't push.

## Reference Documents

Alongside lessons, build reference documents in `./reference/`. Lessons are rarely revisited; reference documents are. A reference document is the compressed essence of a lesson, formatted for quick lookup rather than narrative reading.

Topics that lend themselves to reference documents:

- Syntax and code snippets for programming
- Algorithms and flowcharts for processes
- Pose or movement sequences for physical practices
- Exercises and routines for fitness
- Glossaries for any topic with its own nomenclature

### Glossaries

A glossary is a reference document listing the topic's terms as term → definition pairs, kept short enough to scan in one pass:

```markdown
# <Topic> Glossary

**<Term>** — <one-sentence definition, in plain language, no jargon in the definition itself>

**<Term>** — <definition>
```

Once a glossary exists for a topic, every later lesson uses its terms consistently — don't introduce a synonym for a term the glossary already names.

## `NOTES.md`

Record user preferences and working notes here as they come up in conversation — how they like to be taught, formats they respond to, topics to avoid, pacing preferences. Refer back to it when designing the next lesson.
