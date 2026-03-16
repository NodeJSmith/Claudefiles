# Skill Graphs > SKILL.md — Heinrich (@arscontexta)

Source: https://x.com/arscontexta/status/2023957499183829467

## Core Concept

Skill graphs are networks of skill files connected with wikilinks. Instead of one big file, many small composable pieces reference each other. Each file is one complete thought/technique/skill, and wikilinks create a traversable graph.

## Key Mechanism: Progressive Disclosure

```
index → descriptions → links → sections → full content
```

Most decisions happen before reading a single full file. Each node has YAML frontmatter with descriptions the agent can scan without reading the whole file.

## Primitives

- **Wikilinks** that read as prose (carry meaning, not just references)
- **YAML frontmatter** with descriptions for scanning
- **MOCs (Maps of Content)** that organize clusters into navigable sub-topics

## Index File Pattern

The index isn't a lookup table — it's an entry point that directs attention. Agent reads it, understands the landscape, follows links that matter for current conversation.

```markdown
# knowledge-work

Agents need tools for thought too...

## Synthesis
- [[the system is the argument]] — philosophy with proof of work
- [[coherent architecture emerges from wiki links...]] — foundational triangle

## Topic MOCs
- [[graph-structure]] — wiki links, topology, linking patterns
- [[agent-cognition]] — how agents think through external structures
  - [[agent-cognition-hooks]] — hook enforcement, composition
  - [[agent-cognition-platforms]] — platform capability tiers
- [[discovery-retrieval]] — descriptions, progressive disclosure, search
- [[processing-workflow]] — throughput, sessions, handoffs

## Cross-Domain Claims
- [[forced engagement produces weak connections]] — ...

## Explorations Needed
- Missing: comparison between human and agent traversal patterns
- Scaling limits: at what system size does human curation fail?
```

## Each Node Structure

Each linked file is a standalone methodology claim (= skill) with:
- YAML frontmatter (description for scanning)
- Wikilinks inside prose that tell the agent *when and why* to follow them
- Self-contained thought/technique

## Use Cases

- Therapy: CBT patterns, attachment theory, active listening, emotional regulation
- Trading: risk management, market psychology, position sizing, technical analysis
- Legal: contract patterns, compliance, jurisdiction specifics, precedent chains
- Company: org structure, product knowledge, processes, culture

## Key Insight

"This is the difference between an agent that follows instructions and an agent that understands a domain."

Skills = curated knowledge injected where it matters.
Skill graphs = agent navigates a knowledge structure, pulling in exactly what the situation requires.

## Implementation

- Doesn't need to live in `.claude/skills/`
- Key is an index file that tells the agent what exists and how to traverse it
- arscontexta plugin automates setup with `/learn` and `/reduce` commands
- Manual approach: create index + linked markdown files with frontmatter
