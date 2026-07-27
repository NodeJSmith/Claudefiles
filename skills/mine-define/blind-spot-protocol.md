# Blind Spot Self-Assessment

**Skip for trivial features.**

After all information gathering is complete (discovery, codebase reconnaissance, research) and before writing the design doc, surface your own uncertainty. This is not the Phase 2 completeness self-check (which asks "could I write each section?") — this is epistemic: where is your understanding weakest, and what might you not be seeing at all.

Present to the user:

> Before I write the design doc, three things I want to surface:
>
> **What I'm least confident about:**
> [List 2-5 specific areas where your understanding is thin, your assumptions are unverified, or you took something at face value without investigating. Be concrete — "I assumed the auth middleware passes user context downstream but didn't verify" not "I'm not sure about auth."]
>
> **What might be missing from the picture:**
> [List 1-3 concerns, adjacent effects, or perspectives that haven't come up yet — including things you noticed during investigation but chose not to pursue. This covers both things that never surfaced and things you actively deprioritized. "I saw that the notification module also subscribes to these events but didn't investigate whether our change affects that path" not "there might be edge cases."]
>
> **Tradeoffs of the current direction:**
> [List 1-3 known costs or constraints that the approach we've been discussing imposes. Not defects — legitimate tradeoffs where the chosen direction makes something else harder, forecloses a future option, or accepts a known limitation. "This approach means we'll maintain two serialization paths until the v1 API is retired" not "this might have issues."]
>
> Do you have concerns about any of these?

If the user wants to address items: investigate or ask follow-up questions as needed, then present the updated assessment. If the user says to proceed, note unaddressed items in the design doc's Open Questions section.

The value of this step is that it catches a different class of gap than the structured checklist — things where the information gathering itself had blind spots, not things where a template section is unfilled. The tradeoff probe catches a third class: known costs the user hasn't explicitly accepted.
