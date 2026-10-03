# Presenting Decisions

How to present a choice to the user when you have a recommendation. Applies before any question that asks the user to pick among options and marks one as recommended.

## Why

The agent usually knows the codebase better than the user does at the moment of asking, so its recommendation is usually what gets picked. That makes the recommendation the point where a wrong call gets in. A bare "A (recommended)" gives the user nothing to push back on. The reasoning has to be visible, and laid out so a weak recommendation looks weak.

The bias to watch for is writing the pros and cons after choosing. They then read as a justification of the pick, and a recommendation shown before the options narrows what the reader considers.

## The Rubric

1. **Deciding factor first.** Name, in one line, what the recommendation optimizes: "no breaking change", "fewest moving parts", "matches how the rest of the module does it". If you can't name it, you don't have a recommendation yet.
2. **Same criteria for every option.** Use a criteria × options table. Every option is scored on every row, so a recommendation that wins on one row and loses on three shows up as a bad trade rather than as a shorter list of cons.
3. **"Pick X instead if"** for every option you don't recommend: the condition under which it would be the right call. This tells the user which facts would flip the answer, which is what they are best placed to know.
4. **Fill in the table before choosing.** Write the criteria and score every option, then pick. Don't pick and then write the table to support it.
5. **Persist the reasoning.** When the decision lives in an artifact (a design doc, a ledger), the table and the recommendation go in the artifact, not only in chat. Critics can then attack the reasoning, not only the outcome.

## Shape

Write this as message text before the `AskUserQuestion` call, per `rules/common/interaction.md` item 5 (message text, not the question or options; read the source, then write it out). If the reasoning lives in a file, reformat it into the markdown below, even if you wrote that file yourself moments ago: the user saw the Write, not its content.

```markdown
**Deciding factor:** <what the recommendation optimizes>

| | A: <option> | B: <option> |
|---|---|---|
| <criterion> | <how A fares> | <how B fares> |
| <criterion> | <how A fares> | <how B fares> |

**Recommendation:** A, because <reason tied to the deciding factor>.
**Pick B instead if** <condition>.
```

Then ask the question. Keep option labels and descriptions short; the table carries the reasoning.

A choice with one obvious answer that is easy to reverse can skip the table. Keep the deciding factor, the recommendation, and "pick X instead if".
