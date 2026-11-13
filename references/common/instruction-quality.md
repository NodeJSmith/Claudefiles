# Instruction Quality

Quality criteria for writing rules and skills that shape agent behavior. These apply to any file loaded into context as instructions — rule files in `rules/common/`, SKILL.md files, agent definitions, and REFERENCE.md files.

## The Standard: Goal First, Steps Only for Contracts

**Exact where something outside the agent depends on it; a goal everywhere else.**

An instruction states what the work is for, why it matters, and what done looks like. The agent decides how.

Current models apply a stated goal well. A list of steps, an enumeration of cases to check, or a fixed template gets followed literally. The agent checks exactly the listed things and misses what the author didn't picture, or fills a section that has nothing to say. "Close candidates are tasks where X, Y, or Z" misses a task that's done by evidence the list didn't name. "Find tasks whose work is actually finished, and cite the evidence" doesn't.

Something outside the agent depends on a step when it is one of these:

- State another skill, a later run, or a service reads (file names, formats, carry-over blocks)
- Output a script parses
- The order of side effects (write the success marker only after publishing)
- Irreversible or outward-facing actions, and the gates in front of them
- Facts the agent can't find out itself (API recipes, URL formats, where things live)

Those stay exact. Anything else becomes the goal and the reason.

A goal still needs a clear definition of done. Loose wording fails too: an instruction to show the user something "as text" was satisfied by a `cat` whose output the user never saw. The fix was the reason (the user decides from what's on screen) plus what doesn't count, not a procedure.

## Fixing a Miss

When an instruction produced a miss, the instinct is to add the missed case. That makes the list longer, and the next case nobody listed gets missed the same way. Ask instead why the agent didn't see the case from the goal. Usually the goal was missing, buried under steps, or the definition of done was vague. Sharpen that, and delete steps the goal now covers. Add an exact step only when the miss broke a contract.

The same holds for review findings on instruction files: a finding that asks for another condition, branch, or exemption is usually a sign the goal isn't clear.

## Supporting Checks

These make a goal-first instruction work. Apply them proportionally; none of them is a reason to add a list.

1. **Diagnostic questions over thresholds.** A question the agent asks itself ("can a new reader answer 'where does X come from?' in 30 seconds?") generalizes to cases a threshold ("max 800 lines") doesn't.
2. **Name the trap.** "X goes wrong because Y" helps the agent recognize the situation in the moment. Name the trap, not the steps around it.
3. **State the mechanism, not the reader's tendencies.** "Generation is free, so an extra layer costs the writer nothing" lands; "you tend to over-engineer" gets over-applied.
4. **A generative value.** One sentence that would produce the right behavior if the rest were deleted. "If a human developer would find the code exhausting to maintain, it is a bad solution."
5. **Why before what.** The reason lets the agent apply the spirit where the letter doesn't fit.

## User Prompts

A prompt fired straight from a script or lookup result, with no point where the agent judges whether the result matters, is the most common prescriptive failure. So is a fixed option menu whose right options depend on what the agent just found: it omits the obvious next step, offers a meaningless one, or pins a "(Recommended)" the situation contradicts. Describe when to ask and which outcomes to offer, and let the agent build the menu (see `rules/common/interaction.md`). A fixed set is fine when every plausible outcome of the skill would call for the same options (approve or abandon a plan).

## Proportion

- **Simple factual rules** (syntax, naming, tool usage): state the rule, maybe a brief why.
- **Behavioral rules and skills:** the goal, the why, and what done looks like; contract steps where they apply.
- **Principles** (laziness protocol, reader load): all of the above, plus a generative value.

Less is usually better. Before adding a sentence, ask what the agent would do wrong without it. If you can't name it, leave it out.
