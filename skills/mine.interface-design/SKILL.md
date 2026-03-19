---
name: mine.interface-design
description: "Use when the user says: \"design this UI\", \"design this dashboard\", or \"craft the interface\". Interface design for dashboards, admin panels, apps, and tools. Not for marketing sites."
user-invocable: true
---

# Interface Design

Build interfaces with craft and consistency. Make design decisions once, apply them systematically.

## Scope

**Use for:** Dashboards, admin panels, SaaS apps, tools, settings pages, data interfaces.
**Not for:** Landing pages, marketing sites, campaigns.

---

# The Problem

Without structure, AI-generated UI drifts toward generic patterns. Button heights vary (36px, 38px, 40px), spacing values scatter (14px, 17px, 22px), and every session starts from scratch. The interface looks "fine" but has no identity.

This skill forces intentional decisions and captures them in `.interface-design/system.md` so they persist across sessions.

---

# Intent First

Before touching code, answer these concretely — not in your head, out loud to the user.

**Who is this human?** Not "users." The actual person. A teacher at 7am with coffee is not a developer debugging at midnight. Their world shapes the interface.

**What must they accomplish?** Not "use the dashboard." The verb. Grade submissions. Find the broken deployment. Approve the payment.

**What should this feel like?** In words that mean something. "Clean and modern" means nothing. Warm like a notebook? Cold like a terminal? Dense like a trading floor?

If you cannot answer with specifics, stop and ask the user.

## Every Choice Must Be Intentional

For every decision, you must explain WHY — not "it's common" or "it works." If you swapped your choices for the most common alternatives and the design didn't feel meaningfully different, you defaulted instead of decided.

Intent must be systemic. Saying "warm" then using cold colors is not following through. If warm: surfaces, text, borders, accents, typography — all warm. Check every token against your stated intent.

---

# Where Defaults Hide

Defaults disguise themselves as infrastructure.

**Typography feels like a container.** But it IS your design. The weight of a headline, the personality of a label — these shape how the product feels before anyone reads a word. A bakery tool and a trading terminal both need "readable type" but they need completely different type.

**Navigation feels like scaffolding.** But it IS your product. Where you are, where you can go, what matters most. A page floating in space is a component demo, not software.

**Data feels like presentation.** But a number on screen is not design. A progress ring and a stacked label both show "3 of 10" — one tells a story, one fills space.

**Token names feel like implementation detail.** But `--ink` and `--parchment` evoke a world. `--gray-700` and `--surface-2` evoke a template.

There are no structural decisions. Everything is design.

---

# Product Domain Exploration

Generic: Task type -> Visual template -> Theme
Crafted: Task type -> Product domain -> Signature -> Structure + Expression

**Produce all four before proposing any direction:**

1. **Domain:** Concepts, metaphors, vocabulary from this product's world. Not features — territory. Minimum 5.
2. **Color world:** What colors exist naturally in this domain? If this product were a physical space, what would you see? List 5+.
3. **Signature:** One element — visual, structural, or interaction — that could only exist for THIS product.
4. **Defaults:** 3 obvious choices for this interface type. Name them so you can reject them consciously.

Your proposal must reference all four. Remove the product name from your proposal — could someone still identify what it's for? If not, explore deeper.

---

# Self-Review

Before showing the user, run these checks:

- **Swap test:** Replace your typeface/layout/colors with the most common alternatives. Would anyone notice? Where they wouldn't — you defaulted.
- **Squint test:** Blur your eyes. Can you still perceive hierarchy? Is anything jumping out harshly?
- **Signature test:** Point to five specific elements where your signature appears. "The overall feel" doesn't count.
- **Token test:** Read your CSS variables aloud. Do they sound like they belong to this product, or any project?

If any check fails, iterate before showing. Ask yourself: "If they said this lacks craft, what would they point to?" Fix that thing first.

---

# Craft Foundations

## Subtle Layering

The backbone of craft. You should barely notice the system working — when Vercel's dashboard works, you don't think "nice borders," you just understand the structure.

### Surface Elevation

Surfaces stack: dropdown > card > page. Build a numbered system where each jump is only a few percentage points of lightness. Whisper-quiet shifts you feel rather than see.

Key decisions:
- **Sidebars:** Same background as canvas. Different colors fragment visual space. A subtle border is enough separation.
- **Dropdowns:** One level above parent. If both share a level, the dropdown blends and layering is lost.
- **Inputs:** Slightly darker than surroundings. Inputs are "inset" — a darker background signals "type here" without heavy borders.

### Borders

Low opacity rgba blends with the background — defines edges without demanding attention. Build a progression: standard, softer separation, emphasis, focus rings. Match intensity to the boundary's importance.

**The squint test:** From arm's length, you should perceive hierarchy but nothing should jump out.

## Infinite Expression

Every pattern has infinite expressions. A metric display could be a hero number, sparkline, gauge, progress bar, comparison delta, or trend badge. Same sidebar + cards has infinite variations in proportion, spacing, and emphasis.

Linear's cards don't look like Notion's. Vercel's metrics don't look like Stripe's. Same concepts, different expressions. If your output looks like what any AI would produce — it's forgettable.

## Color Lives Somewhere

Every product exists in a world with colors. Before reaching for a palette, spend time in the product's world. What would you see in the physical version of this space?

Go beyond warm/cold. Is this quiet or loud? Dense or spacious? Serious or playful? A trading terminal and a meditation app are both "focused" — completely different kinds of focus.

Gray builds structure. Color communicates — status, action, emphasis, identity. One accent color used with intention beats five used without thought.

---

# Component Checkpoint

**Every time** you write UI code, state:

```
Intent: [who, what they do, how it should feel]
Palette: [colors — and WHY they fit this product's world]
Depth: [borders / shadows / layered — and WHY]
Surfaces: [elevation scale — and WHY this temperature]
Typography: [typeface — and WHY it fits the intent]
Spacing: [base unit]
```

This is mandatory. If you can't explain WHY for each, you're defaulting.

---

# Design Principles

## Token Architecture

Every color traces back to primitives: foreground (text hierarchy), background (surface elevation), border (separation hierarchy), brand, and semantic (destructive, warning, success). No random hex values.

### Text Hierarchy

Four levels: primary, secondary, tertiary, muted. Each serves a role: default, supporting, metadata, disabled/placeholder. If you're only using two, your hierarchy is too flat.

### Border Progression

Scale from standard to subtle to emphasis to maximum (focus rings). Match intensity to boundary importance.

### Control Tokens

Form controls need dedicated tokens for background, border, and focus — don't reuse surface tokens. This lets you tune interactive elements independently.

## Spacing

Pick a base unit, stick to multiples. Scale: micro (icon gaps), component (within buttons/cards), section (between groups), major (between distinct areas). Random values signal no system.

## Depth

Choose ONE and commit:
- **Borders-only** — Clean, technical. Dense tools.
- **Subtle shadows** — Soft lift. Approachable products.
- **Layered shadows** — Premium, dimensional. Cards with presence.
- **Surface color shifts** — Background tints for hierarchy without shadows.

Don't mix approaches.

## Border Radius

Sharper = technical, rounder = friendly. Build a scale: small (inputs/buttons), medium (cards), large (modals). Don't mix sharp and soft randomly.

## Typography

Distinct levels at a glance. Headlines: heavy weight, tight tracking. Body: comfortable weight. Labels: medium weight at small sizes. Data: monospace with `tabular-nums`.

## Card Layouts

A metric card doesn't look like a plan card doesn't look like a settings card. Design internal structure for specific content, but keep surface treatment consistent: same border weight, shadow depth, radius, padding scale.

## Controls

Native `<select>` and `<input type="date">` render OS-native elements that can't be styled. Build custom: trigger buttons + positioned dropdowns, calendar popovers, styled state management.

## Iconography

Icons clarify, not decorate — if removing one loses no meaning, remove it. One icon set throughout. Standalone icons get subtle background containers.

## Animation

Fast micro-interactions (~150ms), smooth easing. Larger transitions 200-250ms. Deceleration easing. No spring/bounce in professional interfaces.

## States

Every interactive element: default, hover, active, focus, disabled. Data: loading, empty, error. Missing states feel broken.

## Navigation Context

Screens need grounding. A floating data table is a component demo, not a product. Include navigation, location indicators, and user context.

## Dark Mode

Shadows are less visible — lean on borders. Semantic colors need slight desaturation. Same hierarchy system, inverted values.

---

# Avoid

- Harsh borders (if they're the first thing you see, too strong)
- Dramatic surface jumps (elevation changes should whisper)
- Inconsistent spacing (clearest sign of no system)
- Mixed depth strategies
- Missing interaction states
- Dramatic drop shadows
- Large radius on small elements
- Pure white cards on colored backgrounds
- Gradients and color for decoration
- Multiple accent colors
- Different hues for different surfaces (same hue, shift lightness only)

---

# Workflow

## Communication

Be invisible. Don't announce modes or narrate process.

**Never say:** "I'm in ESTABLISH MODE", "Let me check system.md..."
**Instead:** Jump into work. State suggestions with reasoning.

## Suggest + Ask

Lead with exploration, then confirm:

```
Domain: [concepts from this product's world]
Color world: [colors that exist in this domain]
Signature: [one element unique to this product]
Rejecting: [default] -> [alternative] for each

Direction: [approach connecting to above]
```

Then ask: "Does that direction feel right?"

## If system.md Exists

Read `.interface-design/system.md` and apply. Decisions are made.

## Before Building

Read `references/principles.md` for code-level patterns and examples.

## If No system.md

1. Explore domain (produce all four required outputs)
2. Propose direction (must reference all four)
3. Confirm with user
4. Build with principles
5. Run self-review checks before showing
6. Offer to save

## After Completing a Task

Always offer: "Want me to save these patterns to `.interface-design/system.md`?"

### What to Save

Add patterns when a component is used 2+ times, is reusable, or has specific measurements worth remembering. Don't save one-offs, experiments, or variations better handled with props.

### Consistency Checks

If system.md exists, verify: spacing on the defined grid, depth using the declared strategy throughout, colors from the defined palette, documented patterns reused not reinvented.

---

# Related

- `references/principles.md` — Code examples, specific values, dark mode patterns
