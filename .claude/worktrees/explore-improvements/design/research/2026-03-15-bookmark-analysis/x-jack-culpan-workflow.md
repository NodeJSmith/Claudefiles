# Workflow Orchestration Prompt — Jack Culpan (@JackCulpan)

Source: https://x.com/JackCulpan/status/2029478582352003150

## Summary

A CLAUDE.md-style prompt covering plan mode, subagents, self-improvement, verification, and task management. Mostly basic advice already covered by the user's setup.

## Notable Pattern: Self-Improvement Loop

```markdown
### Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project
```

This is essentially a more aggressive version of the user's existing `capture_lesson` command + feedback memory type. The difference: it's mandatory after EVERY correction, not optional.

## Nothing Novel

The rest (plan mode default, subagent strategy, verification before done, task management) is already implemented in the user's setup through plan mode rules, agent orchestration, code-reviewer loop, and TodoWrite/Task usage.
