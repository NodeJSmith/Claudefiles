# Sketch Before Building

An issue, a parent design, or a research brief settles *what* to build. It rarely settles the decisions underneath: data shape, API and module boundaries, edge-case behavior, test strategy. When code gets written straight from one of those, the agent makes those decisions silently as it goes, and the user first sees them in review, after they are expensive to change.

So before writing code for a change, ask whether it leaves a decision the user would want a say in: one that is hard to reverse, would surprise them in review, or isn't dictated by the codebase's existing conventions. Choices you can make from conventions are not open decisions, and answers the user already gave in conversation count as settled.

When there are open decisions, the kind of decision picks the path:

- **Decide inline, then build** when they're independent calls that fit in one `AskUserQuestion` call (four questions): no answer changes another's options, each stays local, and each is cheap to reverse. Lay each one out in the message with its options and your recommendation, ask them together, then build in the same session.
- **Propose `/mine-sketch`** when the decisions interact, when the change reshapes data or a module boundary, when something new has no natural home in the current structure, when a choice is hard to reverse, or when there are more questions than one call holds. Sketch puts each decision in a ledger, has the user ratify it, and challenges the result before any code exists.

If asking inline turns up new decisions, or the questions start depending on each other's answers, stop and offer sketch instead. Don't keep going inline into what has become a sketch without its challenge.

This needs to come to mind on its own. The failure is rarely deciding to skip the questions; it is never thinking of them while a deep dive or plan rolls into code. A skill menu offering "Build it" doesn't settle the question either: when the change has open decisions, the menu should offer the inline path or sketch too.

Build directly when the user asked for that, when the change is mechanical or a bug fix with a known cause, when the run is unattended with no one to ratify a ledger or answer inline questions, or when you are already building from a ratified ledger.
