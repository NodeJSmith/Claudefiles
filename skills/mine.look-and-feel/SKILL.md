---
name: mine.look-and-feel
description: "Use when the user says: \"design this UI\", \"design this dashboard\", \"look and feel\", \"establish design tokens\", \"plan the look and feel\", \"UI planning\", \"design system for this project\", \"craft the interface\". Plans UI design direction before writing code — produces design/direction.md."
user-invocable: true
---

# Look and Feel

Plan UI design direction before writing code. Produce a `design/direction.md` that persists across sessions and feeds into `/mine.mockup` and `/mine.build`.

---

## Phase 1: Check for Spec and Existing Direction

### Read the spec (if it exists)

Look for `design/specs/*/spec.md`.

- **If none found**, proceed without a spec and ask all Phase 2 questions normally.
- **If exactly one exists**, read it.
- **If multiple exist**, list the discovered feature directories and ask the user which feature this UI work targets.

For the chosen spec (if any), read the **User Scenarios** section — it contains structured actor/goal/context data and step-by-step task flows with information needs. Use this to pre-populate answers for Phase 2: if the spec already names actors, goals, and context, skip Questions 1 and 2 and only ask Question 3 (aesthetic feel). This prevents re-asking what the user already described during specify.

### Check for existing direction

Look for `design/direction*.md` in the project.

**If found**, read the file(s) and ask:

```
AskUserQuestion:
  question: "A design direction already exists. What would you like to do?"
  header: "Direction"
  multiSelect: false
  options:
    - label: "Update it"
      description: "Revise the existing direction with new decisions"
    - label: "Start fresh"
      description: "Replace it entirely"
    - label: "Create a scoped variant"
      description: "e.g., direction-admin.md for a separate visual context"
```

If updating, read the existing file and carry forward decisions not being changed.

If creating a scoped variant, ask for the scope name (e.g., "admin", "docs", "marketing").

**If not found**, proceed to Phase 2.

---

## Phase 2: Gather Intent

Ask three focused questions, one at a time. Do not ask open-ended "describe your vision" — probe for specifics.

**Question 1:**
> **Who is this person?** Not "users." The actual person — a teacher at 7am with coffee, a developer debugging at midnight, a manager scanning reports between meetings.

**Question 2:**
> **What must they accomplish?** The verb. Grade submissions, find the broken deployment, approve the payment. Not "use the dashboard."

**Question 3:**
> **What should this feel like?** Specific language. "Warm like a notebook" or "cold like a terminal" or "dense like a trading floor." Not "clean and modern."

Use AskUserQuestion for each, one at a time. If any answer is vague ("users", "clean and modern", "use the app"), push back with a concrete alternative and ask the user to confirm or revise.

---

## Phase 3: Collect References

Ask for visual references — apps or sites whose *feel* (not features) matches the stated intent.

Ask the user directly:

> Name 2-3 apps or sites whose *feel* matches what you described. Not to copy — to articulate direction.

If the user cannot name any, suggest 3 options based on the domain and intent. For each reference, identify what to take from it (e.g., "the density and monospace feel" or "the warm paper texture and generous spacing").

---

## Phase 4: Domain Exploration

Run the four-part exploration. Present all four before proposing any direction.

1. **Domain concepts** — Concepts, metaphors, vocabulary from this product's world. Not features — territory. Minimum 5.
2. **Color world** — What colors exist naturally in this domain? If this product were a physical space, what would you see? List 5+.
3. **Signature element** — One element — visual, structural, or interaction — that could only exist for THIS product.
4. **Defaults to reject** — 3 obvious choices for this interface type. Name them so you can reject them consciously. For each: the default, why it's wrong for this product, and a better alternative.

Present exploration results to the user. Remove the product name — could someone still identify what it's for? If not, explore deeper.

---

## Phase 5: Self-Review

After completing domain exploration, draft your token decisions internally. Before presenting them to the user, run these checks:

- **Swap test:** Replace your typeface, layout choices, and colors with the most common alternatives. Would anyone notice? Where they wouldn't — you defaulted.
- **Squint test:** Blur your eyes at the token set. Can you perceive hierarchy? Is anything jarring?
- **Signature test:** Point to five specific places where the signature element appears in your token decisions. "The overall feel" doesn't count.
- **Token test:** Read your CSS variable names aloud. Do they sound like they belong to this product, or any project?

If any check fails, iterate before presenting. Ask yourself: "If they said this lacks craft, what would they point to?" Fix that first.

---

## Phase 6: Propose Direction

Present concrete token decisions. Every value must be justified against intent and domain — not "it's common" or "it works." If you swapped your choices for the most common alternatives and nothing felt different, you defaulted instead of decided.

Present a summary covering:

- **Color palette** — Hex values with semantic names. Light and dark mode. How colors connect to the domain's color world.
- **Typography** — Specific fonts and why they fit this product. Scale (xs through 3xl). Weights and their purposes. Avoid generic defaults (Inter, Roboto, Arial, Open Sans, system fonts).
- **Spacing** — Base unit and scale. How density connects to intent.
- **Depth strategy** — One of: borders-only, subtle shadows, layered shadows, surface tints. Why this choice fits the feel.
- **Border radius** — Scale (sm, md, lg). Where on the sharp-to-round spectrum and why.
- **Motion** — Micro-interaction timing, transition timing, easing functions.

Ask the user to confirm or revise before saving.

---

## Phase 7: Confirm and Save

After user confirmation, write `design/direction.md` (or the scoped variant).

Read `references/direction-template.md` for the exact format. Include `**Completeness:** full` in the metadata header. Every section must be populated with rationale — no placeholder text.

Create the `design/` directory if it does not exist.

**Also write `.impeccable.md`** in the project root with the brand context gathered in Phases 2-3. This bridges to the Impeccable (`i-*`) design skills so they don't re-ask these questions:

```markdown
## Design Context

### Users
[From Phase 2, Question 1 — who the person is, their context]

### Brand Personality
[From Phase 2 — emotional feel, aesthetic tone the user wants]

### Aesthetic Direction
[From Phase 3 — visual references and what to take from them; from Phase 4 — signature element and aesthetics to avoid]

### Design Principles
[3-5 principles derived from the direction decisions]
```

If `.impeccable.md` already exists, update the Design Context section in place.

---

## Phase 8: Hand Off to Mockup

After saving, offer the next step:

```
AskUserQuestion:
  question: "Direction saved. Want to see what it looks like?"
  header: "Next step"
  options:
    - label: "Generate a mockup"
      description: "Run /mine.mockup to produce an HTML preview using these tokens"
    - label: "Done for now"
      description: "Direction is saved — I'll use it next time I touch UI code"
```

If the user chooses mockup, invoke `/mine.mockup`.

---

## Communication Style

Be invisible. Don't announce modes or narrate process.

**Never say:** "I'm now entering the exploration phase", "Let me check for existing files..."
**Instead:** Jump into work. Present exploration, then direction, then confirm.
