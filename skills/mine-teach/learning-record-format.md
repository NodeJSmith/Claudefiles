# Learning Record Format

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

## Rules

- **Title** names the insight itself, not the lesson topic ("Recursion clicks when framed as delegation, not repetition" — not "Recursion lesson notes").
- Only record something genuinely non-obvious — a surprising misconception corrected, a mental model that finally worked, a gap the user didn't know they had. Routine lesson completions don't need a record.
- **Evidence** ties the insight to something concrete that happened in the session, not a restatement of the insight.
- **Implications** is what makes this useful later — it should change what gets taught next, not just document the past.
- Never edit a record's Insight after the fact to reflect new understanding. Write a new record, set the old one's Status to `revised by NNNN`.
- These records are what zone-of-proximal-development tracking reads from — before designing the next lesson, read the recent ones to see what's already landed and what's still shaky.
