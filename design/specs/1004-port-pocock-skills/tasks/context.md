# Context: Port Pocock Skills

## Problem & Motivation
Six skills from Matt Pocock's `mattpocock/skills` repo fill capability gaps in the current Claudefiles setup. The skills need adaptation to match existing conventions (naming, frontmatter, dependency wiring, trigger phrases) before they can be used.

## Key Decisions
1. All skills follow `mine-*` naming convention
2. Dependencies remap to existing equivalents: grilling → mine-grill, research → mine-research, prototype → mine-mockup
3. All 6 skills use `user-invocable: true`; mine-domain-model's description includes trigger phrases so the model can auto-invoke it during design conversations
4. Issue tracker operations prefer `gh-issue` CLI; raw `gh` acceptable for operations `gh-issue` doesn't cover (e.g., assignment)
5. Format templates go in side files (not inline) for skills that need them (domain-model, teach)
6. The writing skills (fragments, shape, beats) form a pipeline: explore → exploit, with shape and beats as alternative exploit-phase skills

## Constraints
- Do NOT reference Pocock's original skill names (/grilling, /research, /prototype, /domain-modeling) in any skill file
- Do NOT fetch Pocock's format side files — create adapted versions from the SKILL.md descriptions
- All 6 skills use `user-invocable: true` — this repo does not use `disable-model-invocation` (that's a Pocock convention, not ours)
- Source material for adaptation was fetched into a session-scoped scratchpad file during discovery (not committed to the repo) — see the individual task prompts (T01-T04) for the section headers to search for within it
