---
tool: claude  # harness-only: routes to the mine-sketch skill, which only Claude Code has
---

# Sketch Before Building

An issue, a parent design, or a research brief settles *what* to build. It rarely settles the decisions underneath: data shape, API and module boundaries, edge-case behavior, test strategy. When code gets written straight from one of those, the agent makes those decisions silently as it goes, and the user first sees them in review, after they are expensive to change.

So before writing code for a change, ask whether it leaves a decision the user would want a say in: one that is hard to reverse, would surprise them in review, or isn't dictated by the codebase's existing conventions. If it does, propose `/mine-sketch`, which surfaces each such decision and has the user ratify it before any code exists. Choices you can make from conventions are not open decisions, and answers the user already gave in conversation count as settled.

This needs to come to mind on its own. The failure is rarely deciding to skip sketch; it is never thinking of it while a deep dive or plan rolls into code. A skill menu offering "Build it" doesn't settle the question either: when the change has open decisions, the menu should offer sketch too.

Build directly when the user asked for that, when the change is mechanical or a bug fix with a known cause, when the run is unattended with no one to ratify a ledger, or when you are already building from a ratified ledger.
