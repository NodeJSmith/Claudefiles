---
name: mine-eli5
description: "Use when the user says: \"eli5\", \"explain like I'm 5\", \"eli5 this\", \"explain like I'm five\", or wants a dead-simple picture explainer of how something works."
user-invocable: true
---

# ELI5

Topic: $ARGUMENTS — if empty, ask the user what to explain.

Explain the topic to someone who knows nothing about it, using the `Artifact` tool: big pictures, very few words. The default failure mode here is dense, bulleted text explanations — resist it. Cut words before adding detail, and use an actual visual element (diagram, icon, simple illustration) rather than prose styled to look visual.

Keep the simplification honest: trade detail for clarity, never accuracy for cuteness. If the plain-language version would state something that isn't actually true, find a simpler-but-still-correct framing instead of a wrong one.
