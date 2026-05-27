# Instruction Quality

Quality criteria for writing rules and skills that shape agent behavior. These apply to any file loaded into context as instructions — rule files in `rules/common/`, SKILL.md files, agent definitions, and REFERENCE.md files.

The difference between instructions that get followed and instructions that get skimmed is not length or formatting. It is whether the instructions teach the agent to recognize the problem in the moment, or merely describe the desired end state.

## The Five Checks

Apply these when writing or editing any instruction file.

### 1. Diagnostic Questions Over Thresholds

Does the instruction give the agent a question to ask itself, or only a metric to check against?

A threshold ("max 800 lines") covers the cases you anticipated. A diagnostic question ("can a new reader answer 'where does X come from?' in under 30 seconds?") generalizes to situations the threshold does not cover. Prefer the question. Include the threshold too if it helps, but the question is the load-bearing part.

### 2. Named Failure Modes

Does each rule name the specific trap it guards against?

"Don't do X" is weaker than "agents tend to do X because Y — counter it by Z." Naming the trap helps the agent recognize when it is falling into it. "Verify your work" is a rule. "Agents report what they intended, not always what happened — inspect the diff, not the summary" is a named failure mode that fires at the right moment.

### 3. AI-Specific Bias Acknowledgment

Does the instruction call out what AI agents specifically get wrong in this domain?

Generic engineering advice reads as background knowledge and gets skimmed. "Agents tend to X because generation is free — counter it by Y" gets attention because it names the specific tendency. Rules that acknowledge the agent's tendencies are more effective than rules that describe ideal behavior in the abstract.

### 4. A Generative Value

Is there a one-sentence stance that would produce correct behavior even if the rest of the instruction were deleted?

"If a human developer would find the code exhausting to maintain, it is a bad solution." "Code is cheap, attention is scarce." A generative value helps agents make judgment calls in situations no specific rule covers. If the instruction is only a checklist with no underlying principle, it will be applied literally and miss edge cases.

### 5. "Why" Before "What"

Does each major rule explain the trap it guards against before stating the rule?

Understanding why the rule exists lets agents apply the spirit in edge cases rather than following the letter and missing the point. "Never claim work is done without evidence" is a rule. "Indirect verification feels cheaper than direct observation, but acting on a wrong inference costs far more than checking the source" is the reasoning that makes the rule stick.

## Applying the Checks

These are not hard requirements for every line. A simple factual rule ("use `X | None`, not `Optional[X]`") does not need a generative value or an AI bias acknowledgment. Apply the checks proportionally:

- **Simple factual rules** (syntax, naming, tool usage): state the rule, maybe a brief "why." Checks 1-5 are optional.
- **Behavioral rules** (how to approach debugging, when to refactor, how to verify): checks 2 and 5 are the minimum. The agent needs to understand the trap to follow the spirit.
- **Principles** (laziness protocol, reader load, experience first): all five checks matter. These are the rules that shape judgment, and judgment requires understanding.
