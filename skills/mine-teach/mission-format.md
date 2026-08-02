# MISSION.md Format

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

## Rules

- Write this before the first lesson. If the user hasn't stated a mission, ask why they want to learn the topic before doing anything else — a lesson built on an unstated mission is a guess.
- **Current Level** is self-reported, not tested. Don't quiz the user to calibrate this on day one; let the first lesson or two calibrate it naturally and revise if it was off.
- **Target** should be concrete enough to judge progress against ("read production Rust without looking up syntax", not "learn Rust"). If the user gives a vague target, ask a follow-up to sharpen it.
- **Constraints** matters for lesson pacing — a user with 15 minutes a day needs shorter, more frequent lessons than one doing a weekend deep-dive.
- Missions change as the user's skills grow. When it changes, confirm with the user first, then edit this file in place and add a learning record noting why the mission shifted.
