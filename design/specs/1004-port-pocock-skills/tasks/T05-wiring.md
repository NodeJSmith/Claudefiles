---
task_id: "T05"
title: "add trigger phrases to capabilities-core.md and entries to REFERENCE.md"
status: "done"
depends_on: ["T01", "T02", "T03", "T04"]
implements: ["FR#7", "FR#8", "AC#5", "AC#6"]
---

## Target Files

- modify: `rules/common/capabilities-core.md`
- modify: `REFERENCE.md`

## Prompt

Wire the 6 new skills into the routing and reference tables.

### capabilities-core.md

Add trigger phrases to the Intent Routing table in `rules/common/capabilities-core.md`. Insert them in a logical position — group the writing skills together, and place domain-model, wayfinder, and teach near related entries.

Entries to add (follow the exact `| "trigger phrases" | \`/mine-skill\` |` format):

```
| "domain model", "glossary", "sharpen terminology", "define this term", "what does X mean in this codebase", "ubiquitous language" | `/mine-domain-model` |
| "wayfinder", "chart this effort", "too big for one session", "multi-session plan", "foggy effort", "progressive discovery" | `/mine-wayfinder` |
| "teach me", "learn about", "study this", "lesson on", "help me learn", "tutorial on" | `/mine-teach` |
| "mine fragments", "explore writing", "raw material", "capture fragments", "start writing", "brainstorm an article" | `/mine-fragments` |
| "shape this article", "write paragraph by paragraph", "shape this writing", "structure this material" | `/mine-shape` |
| "write in beats", "beat by beat", "choose your own adventure writing", "journey-style article" | `/mine-beats` |
```

### REFERENCE.md

Add entries to the Core Skills (`mine-*`) table in `REFERENCE.md`. Insert alphabetically among existing entries. Follow the exact `| \`mine-skill\` | Description |` format.

Entries to add:

```
| `mine-beats` | Writing exploit (beat-by-beat) — assemble raw material into a journey of beats with choose-your-own-adventure branching and grounding discipline |
| `mine-domain-model` | Active domain glossary — maintain CONTEXT.md and ADRs during design conversations, challenge fuzzy language, cross-reference code |
| `mine-fragments` | Writing explore — mine raw fragments through grilling, append to a markdown file with no structure imposed |
| `mine-shape` | Writing exploit (paragraph-by-paragraph) — shape raw material into an article with grounding discipline and collaborative construction |
| `mine-teach` | Structured learning — stateful workspace with mission, lessons, learning records, reference docs, and zone-of-proximal-development tracking |
| `mine-wayfinder` | Multi-session decision mapping — chart foggy efforts as a map of decision tickets on the issue tracker, resolve via progressive discovery |
```

## Verify

- [ ] AC#5: `grep -c "mine-domain-model\|mine-wayfinder\|mine-teach\|mine-fragments\|mine-shape\|mine-beats" rules/common/capabilities-core.md` returns 6
- [ ] AC#6: `grep -c "mine-domain-model\|mine-wayfinder\|mine-teach\|mine-fragments\|mine-shape\|mine-beats" REFERENCE.md` returns 6
- [ ] FR#7, FR#8: All 6 skills appear in both files
