---
name: mine-teach
description: "Use when the user says: \"teach me\", \"learn about\", \"study this\", \"lesson on\", \"help me learn\", \"tutorial on\", or wants structured learning over multiple sessions."
user-invocable: true
---

# Teach

The user has asked to learn something. This is a stateful request — they intend to learn the topic over multiple sessions, not just this one.

## Teaching Workspace

Treat the current directory as a teaching workspace. The state of the user's learning lives in these files:

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

- **`MISSION.md`** — the *reason* the user is interested in the topic. Grounds all teaching. Use the format in [mission-format.md](./mission-format.md).
- **`RESOURCES.md`** — high-quality resources to ground teaching in contextual knowledge or acquire wisdom. Use the format in [resources-format.md](./resources-format.md).
- **`learning-records/*.md`** — non-obvious lessons and key insights, loosely equivalent to architecture decision records. Titled `0001-<kebab-case-name>.md`, incrementing. Used to calculate the zone of proximal development. Use the format in [learning-record-format.md](./learning-record-format.md).
- **`lessons/*.html`** — the primary unit of teaching. A lesson is a single, self-contained HTML file that teaches one tightly-scoped thing tied to the mission. Titled `0001-<kebab-case-name>.html`, incrementing.
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

A lesson is the main artifact — the unit in which knowledge and skills reach the user. Each lesson is one self-contained HTML file, saved to `./lessons/` and titled `0001-<kebab-case-name>.html`.

**Self-contained means self-contained.** No CDN links — no Tailwind CDN, no external font or script loads, no network dependency of any kind. Inline all CSS and JS directly in the file. A lesson opened offline, months later, must render exactly as it did the day it was written.

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

If the user is unclear about the mission, or `MISSION.md` isn't populated, the first job is to question the user on why they want to learn this. Use the format in [mission-format.md](./mission-format.md).

Skipping this grounds nothing: without a mission, knowledge acquisition floats free of real-world goals, lessons feel abstract, and there's no basis for judging what to teach next.

Missions can change as the user develops skills and knowledge — that's normal. Confirm the change with the user, then update `MISSION.md` and add a learning record capturing why it changed.

## Zone of Proximal Development

Each lesson should challenge the user *just enough* — not so easy it's boring, not so hard it stalls.

If the user hasn't specified an exact thing to learn, find their zone of proximal development by:

1. Reading their `learning-records/`
2. Cross-referencing against the mission
3. Teaching the most relevant thing that fits what they're ready for

## Knowledge

Design lessons around a skill the user is going to acquire. Include only the knowledge required for that skill — teach the knowledge first, then drive practice through an interactive feedback loop.

Gather knowledge from trusted resources first; track them in `RESOURCES.md`. Cite sources throughout a lesson — links to external material backing any claim made. Citations are what make a lesson trustworthy.

For knowledge acquisition, difficulty is the enemy: it eats the working memory needed for understanding. Keep the knowledge portion of a lesson easy.

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

Look for high-reputation communities and record them in `RESOURCES.md`. If the user says they don't want to join a community, respect it and don't push.

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
