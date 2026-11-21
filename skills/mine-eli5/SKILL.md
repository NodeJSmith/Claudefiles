---
name: mine-eli5
description: "Use when the user says: \"eli5\", \"explain like I'm 5\", \"eli5 this\", \"explain like I'm five\", or wants a dead-simple picture explainer of how something works."
user-invocable: true
---

# ELI5

Topic: $ARGUMENTS — if empty, ask the user what to explain.

Explain the topic to someone who knows nothing about it, as an `Artifact`: big pictures, very few words. Dense bulleted text is the default failure here, so cut words before adding detail, and use a real visual element (diagram, icon, simple illustration) rather than prose styled to look visual.

Keep the simplification honest: trade detail for clarity, never accuracy for cuteness. If the plain version would say something untrue, find a simpler framing that is still correct.

Write the source HTML in the scratchpad directory, never the working repo, then publish it.

Done means you checked that the artifact renders as intended, by viewing it rendered, not just reading the source. If you can't see a render, say so rather than claiming you checked. Layout bugs (a percentage height resolving against the wrong box, say) are invisible in source and obvious on screen, and for a picture explainer the picture is the whole point.
