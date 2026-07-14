# Proportional Discovery Protocol

**Ask one question per `AskUserQuestion` call. Wait for each answer before asking the next.** Do NOT batch multiple questions into a single call. Use free-text input unless the protocol explicitly provides structured options.

This phase combines problem discovery (what to build) with architecture interrogation (how to build it) into a single proportional flow. Questions are ordered from problem space to solution space.

## Always ask (all complexity levels)

1. **Problem grounding** (skip if already clear from the request):

```
AskUserQuestion:
  question: "What problem does this solve? Who experiences it?"
  header: "Problem"
```

2. **Success definition:**

```
AskUserQuestion:
  question: "How will you know this is working correctly? What does done look like?"
  header: "Success"
```

## Scope mode selection (moderate+ only)

After the user answers problem grounding and success definition, present a scope mode selection. Skip for trivial features — trivial features are always `hold` (use this value when writing the `**Scope-mode:**` header in Phase 4). On resume from an existing feature directory, check the design doc header for a `**Scope-mode:**` field — if present, skip re-asking and announce the recovered mode.

```
AskUserQuestion:
  question: "You described the problem as [X] and success as [Y]. Given that and what I found in the codebase, how should we scope this?"
  header: "Scope mode"
  multiSelect: false
  options:
    - label: "Expand — build the ambitious version"
      description: "Push scope up. What would make this 10x better? What adjacent improvements would make it sing?"
    - label: "Hold — make this bulletproof"
      description: "Accept the scope as stated. Focus on making it solid, complete, and well-tested."
    - label: "Reduce — strip to essentials"
      description: "Find the minimum viable version. Cut everything that isn't core. What can be a follow-up?"
```

Where `[X]` is the user's answer to problem grounding (or a one-sentence paraphrase of the stated problem if Q1 was skipped) and `[Y]` is their answer to success definition.

## Ask for moderate and complex features

The remaining questions are shaped by the selected scope mode. Prefix each AskUserQuestion header with the mode — e.g., `[Expand] Non-goals`, `[Hold] User flow`, `[Reduce] Edge cases` — so the mode is visible on every interaction turn.

3. **Scope boundary:**

Mode-specific framing:
- **Expand**: "What's phase 1 vs phase 2? What should we build now, and what's a natural follow-on?"
- **Hold**: "Anything I should explicitly NOT include? (e.g., 'no admin UI', 'skip migration for now'). 'None' is a perfectly good answer."
- **Reduce**: "What can we cut entirely? What's the absolute minimum that ships value?"

```
AskUserQuestion:
  question: "<mode-specific question above>"
  header: "[<mode>] Non-goals"
```

4. **Primary user flow:**

```
AskUserQuestion:
  question: "Walk me through the main scenario: who is this person, what's their situation, and what do they do step by step?"
  header: "[<mode>] User flow"
```

Mode-specific follow-up (ask only the one matching the selected mode):
- **Expand only:** "Are there adjacent flows or related scenarios we should include?"
- **Hold:** skip — no follow-up
- **Reduce only:** "Which of these steps could be manual or deferred for now?"

## Ask for complex features only

5. **Edge cases:**

```
AskUserQuestion:
  question: "What are the important edge cases or failure modes?"
  header: "[<mode>] Edge cases"
```

6. **Dependencies:**

```
AskUserQuestion:
  question: "What external systems, services, or teams does this touch?"
  header: "[<mode>] Deps"
```

7. **Security / access:**

```
AskUserQuestion:
  question: "Who should and shouldn't have access? Any data sensitivity concerns?"
  header: "[<mode>] Security"
```

8. **Performance:**

```
AskUserQuestion:
  question: "Any scale, latency, or throughput requirements?"
  header: "[<mode>] Perf"
```

9. **Rollback / reversibility:**

```
AskUserQuestion:
  question: "If this goes wrong, what does rollback or recovery look like?"
  header: "[<mode>] Rollback"
```

## Implementation preferences (moderate+ only)

After the tier-appropriate problem-space questions, surface concrete implementation decisions before they become implicit defaults:

```
AskUserQuestion:
  question: "Are there specific implementation preferences I should lock in — frameworks, libraries, patterns, conventions, or tooling choices? For example: CLI framework, logging approach, serialization format, auth pattern, config management."
  header: "[<mode>] Impl prefs"
```

If the user names preferences, record them for the Implementation Preferences section of design.md. If they say "no" or "follow conventions", note that and move on.

This question is deliberately open-ended rather than a checklist — the relevant details vary by feature type. The examples prime the user to think about the category of decision without limiting it to a fixed set.

## Adaptive follow-up (all complexity levels)

After the tier-appropriate questions above, review what you've learned. For each answer the user gave, check: does it open a decision branch that hasn't been resolved? Walk down those branches.

**Task flow probing (moderate+ features with UI):** For each step in the user's described flow, probe for what's needed to design screens:
- "At this step, what information does the user need to see to act?" — surfaces data requirements per screen
- "Does the user make a choice here? What do they need to know to decide?" — surfaces decision points
- "What happens right after?" — surfaces system responses and transitions

**Data impact probing (moderate+ features touching data models, schemas, or storage):** If Phase 1.5 found data models, database schemas, file formats, config structures, or persistent state in the affected code, ask:
- "This touches [specific data model/schema]. What happens to existing data when this changes?"
- "Are there consumers of this data format that need to stay compatible?"

Skip if Phase 1.5 found no data-related code in the affected area.

For each decision branch, check whether the codebase already constrains the answer (from Phase 1.5 findings or a quick targeted search). Ask only about branches where the code doesn't decide for you.

Ask follow-up questions one at a time. Apply judgment proportional to complexity and scope mode:
- **Expand**: more follow-ups than the tier suggests; explore opportunity branches and adjacent use cases
- **Hold**: standard follow-ups per the complexity tier — for trivial features, 1–2 follow-ups max; for moderate, 3–5; for complex, as many as needed
- **Reduce**: fewer follow-ups; bias toward deferring unresolved branches rather than probing deeper

If you're exceeding the tier's original question count by more than double, pause and ask the user whether to continue or descope the remaining branches.

If the user says "I don't know yet" or "let's figure that out later", probe deeper — rephrase the question, offer concrete options, or explore the codebase to narrow the possibilities. Only move on when the branch is resolved or the user explicitly descopes it.

## Completeness self-check (moderate+ only)

After adaptive follow-ups, mentally walk through each section of the design doc template. For each section, ask: "Could I write this right now without guessing?" If any section would require inventing details the user hasn't provided and the codebase doesn't constrain, you have more questions to ask.

Common gaps that survive the structured questions:
- Implementation Preferences: the user described what to build but not which frameworks, libraries, or tooling conventions to use
- Architecture: the approach is clear but specific technology/library choices aren't locked in
- Edge Cases: the happy path is defined but failure modes weren't discussed
- Migration: data changes are implied but the migration strategy wasn't addressed
- Test Strategy: what to test is clear but how (fixtures, mocking approach, test data) isn't

For each gap found, ask the user — one question at a time, same as adaptive follow-ups. Do not ask about sections the codebase already answers (from Phase 1.5) or sections that are genuinely N/A for this feature.

When every section can be written from what you know, proceed. Do not announce this check to the user — it's an internal quality pass, not a visible gate. The user sees only any additional questions it generates.

## Confirm intent summary

Before proceeding, present a structured summary starting with the pain point. Include the scope mode so the user can detect drift before the design doc is written.

> **Scope mode:** <Expand|Hold|Reduce>
> **Understood pain point:** <the underlying problem or frustration>
>
> <one-paragraph summary of what will be defined>

**Anti-drift rule:** If a later question or finding suggests a different mode would be better, note it once — do not act on it unless the user explicitly changes mode.

Then ask:

```
AskUserQuestion:
  question: "Here's what I understood:\n\n<summary>\n\nDoes this capture it correctly?"
  header: "Confirm intent"
  multiSelect: false
  options:
    - label: "Yes — proceed"
    - label: "No — let me clarify"
      description: "Tell me what's wrong (including scope mode) and I'll adjust"
```

If "No", ask what's wrong and revise your understanding, then confirm again.

## Caller perspective (API/module designs only)

If the artifact being designed is an API, module, library, or public interface (not a workflow, feature, or internal refactor), insert this step before proceeding.

Ask:

```
AskUserQuestion:
  question: "Before defining the interface, write 2-3 realistic call sites. What does the caller's code look like when using this?"
  header: "Caller view"
```

The user's answer becomes the spec. When the call-site ergonomics conflict with the type definitions later, reconcile types to match the caller's perspective — not the reverse. Hold these call sites internally; they'll inform the Architecture section and be included as examples in Phase 4.

If the user already provided call-site examples during discovery (e.g., in their problem description or flow walkthrough), skip this step and note: "Using the call sites you described earlier as the design anchor."

## Existing code leverage (moderate+ only)

After confirming intent and before research dispatch, revisit the Phase 1.5 codebase findings. Decompose the user's confirmed intent into 3-7 sub-problems using the discovery answers, scope mode, and the code findings from Phase 1.5. For each sub-problem, map it to existing code:

```markdown
| Sub-problem | Existing code | Coverage |
|---|---|---|
| Validate user email | `src/validators.py` — has `validate_email()` | Full — reuse as-is |
| Rate limit API calls | `src/middleware.py` — rate limiter exists but only for auth endpoints | Partial — handles auth but not general API |
| Send notification on failure | (none found) | None — new code needed |
```

Coverage vocabulary: `Full — reuse as-is` (existing code solves this entirely), `Partial — <what's missing>` (existing code solves part of it), `Replace — <what's being superseded>` (existing code is being intentionally replaced by the new approach — implementers should migrate or remove it, not preserve it), `None — new code needed` (nothing found).

Present the table with: "Here's what I found. Sub-problems with existing coverage should reuse that code rather than rebuilding. Sub-problems marked `Replace` indicate old code being superseded — implementers will remove or migrate it rather than preserving it. Correct me if I'm wrong about any of these."

If Phase 1.5 found no existing code at all, present an empty table with a note: "No existing code found for any sub-problem — all new code needed."

If the user corrects any row (e.g., "that validator is deprecated, don't reuse it"), update the table and present it once more before proceeding.

Skip for trivial features (Phase 1.5 doesn't run for trivial, so no code findings to revisit).

## Convention examples checkpoint (moderate+ only)

After the code leverage table is confirmed, present the code examples collected in Phase 1.5 to the user:

> "I've identified these convention examples for the design doc. They'll flow through to implementers via `context.md` during orchestration. Let me know if any should be swapped out."

Then list each example briefly (pattern name, source file, 1-line description). The actual snippets will be written to the `## Convention Examples` section of `design.md` in Phase 4.

If the user asks to change examples, note the changes. Don't re-confirm — proceed to Phase 3.

If Phase 1.5 found no meaningful conventions to extract (e.g., greenfield project, no similar code exists), skip this step and note: "No convention examples to extract — the codebase has no similar patterns to reference."
