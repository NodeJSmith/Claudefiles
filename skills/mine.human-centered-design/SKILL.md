---
name: mine.human-centered-design
description: "Use when the user says: \"accessible design\" or \"inclusive patterns\". Human-centered frontend design — empathy, accessibility, progressive enhancement. Use when building or reviewing user-facing interfaces."
---

# Human-Centered Design

The mindset layer. Understand the human before designing the interface.

Every interface decision — color, spacing, interaction, copy — either respects or disregards the person on the other end. This skill builds the habit of asking "who is this for?" before "how should this look?" It sits upstream of visual craft and code review: get the human right first, then design, then verify.

## Scope

**Use for:** Any user-facing frontend — dashboards, forms, tools, apps, public pages.
**Not for:** Backend-only code, CLI tools, API-only services, design token docs without implementation.

---

## HCD vs UX

These overlap but aren't the same thing.

| | UX | HCD |
|---|---|---|
| **Core question** | Can they complete the task? | Does this respect the full human? |
| **Focus** | Task flow, efficiency, satisfaction | Empathy, inclusion, context, emotion |
| **Considers** | The user performing the action | Non-users, bystanders, edge-case humans |
| **Abilities** | Assumes a typical user | Permanent, temporary, situational spectrum |
| **Environment** | Desktop or mobile | 7am coffee, crowded bus, bright sun, screen reader |
| **Success metric** | Task completion rate | No one excluded, no one frustrated |
| **Failure mode** | Confusing flow | Entire populations can't use it |

Good UX can still exclude people. HCD asks: who did we forget?

---

## The Human First

Before code, before wireframes, answer these. Not in your head — out loud to the user.

### Who is this person?

Not "users." The actual human. A nurse on a 12-hour shift is not a developer at a standing desk. Their fatigue, literacy, device, connection speed, assistive tech, emotional state, and physical environment shape every design decision.

### What's their environment?

- 7am with coffee at a desk? Crowded bus holding a phone one-handed?
- Screen reader? Magnified 200%? High-contrast mode?
- Fast fiber? Spotty mobile data?
- Quiet focus? Interrupted every 30 seconds?

The same interface needs to survive all of these.

### What are they trying to accomplish?

The verb, not "use the app." Grade submissions. Find the broken deployment. Pay the invoice. Book the appointment.

### What could go wrong for them?

- Error with no explanation
- Lost input after a timeout
- Action that can't be undone
- Jargon they don't understand
- A flow that requires two hands when they have one

### Who might be excluded by your defaults?

Microsoft's persona spectrum: every exclusion exists on a continuum.

| Permanent | Temporary | Situational |
|-----------|-----------|-------------|
| One arm | Arm in cast | Holding a child |
| Blind | Eye infection | Driving |
| Deaf | Ear infection | Loud environment |
| Non-verbal | Laryngitis | Heavy accent + voice UI |
| Cognitive disability | Concussion | Sleep-deprived |

Design for the permanent case. Temporary and situational users benefit automatically.

---

## Design Principles

Two established frameworks, used as checklists — not theory to memorize.

### Norman's 7 Principles

| Principle | Meaning | Frontend example |
|-----------|---------|-----------------|
| **Visibility** | Current state is apparent | Active nav item highlighted, form progress shown |
| **Feedback** | Every action has a response | Button state changes on click, loading indicator appears |
| **Constraints** | Prevent invalid actions | Disabled submit until required fields filled, `maxlength` on inputs |
| **Mapping** | Controls relate to effects | Slider left = decrease, toggle right = on |
| **Consistency** | Same action = same result | All delete actions use same confirmation pattern |
| **Affordance** | Form suggests function | Buttons look clickable, text inputs look editable |
| **Signifiers** | Clues for correct action | Placeholder text, helper text, icons next to labels |

### Nielsen's 10 Heuristics

| Heuristic | Frontend check |
|-----------|---------------|
| **System status visibility** | Loading states, progress bars, `aria-live` announcements |
| **Match real world** | Natural language labels, familiar icons, domain vocabulary |
| **User control & freedom** | Undo, back navigation, dismiss/close on all overlays |
| **Consistency & standards** | Same patterns across pages, platform conventions honored |
| **Error prevention** | Confirmation on destructive actions, input constraints, `hx-confirm` |
| **Recognition over recall** | Visible options, recent items, autocomplete, breadcrumbs |
| **Flexibility & efficiency** | Keyboard shortcuts, bulk actions, skip links |
| **Aesthetic & minimal** | No decorative clutter, information density matches task |
| **Error recovery** | Clear messages, actionable suggestions, preserved input |
| **Help & documentation** | Inline help text, tooltips, contextual guidance |

---

## Progressive Enhancement

Build in layers. Each layer enhances — none are required for core function.

### Layer 1: Semantic HTML

Works everywhere. Accessible by default. This IS your baseline.

```html
<!-- Navigation is a nav, not a div -->
<nav aria-label="Main">
  <a href="/dashboard">Dashboard</a>
  <a href="/reports" aria-current="page">Reports</a>
</nav>

<!-- A form that works without JS -->
<form method="post" action="/search">
  <label for="query">Search</label>
  <input type="search" id="query" name="q" required>
  <button type="submit">Search</button>
</form>
```

### Layer 2: CSS

Visual enhancement. Respect user preferences.

```css
/* Layer 2 enhances — doesn't break without it */
@media (prefers-reduced-motion: no-preference) {
  .card { transition: transform 150ms ease; }
  .card:hover { transform: translateY(-2px); }
}

@media (prefers-color-scheme: dark) {
  :root { --surface: #1a1a2e; --text: #e0e0e0; }
}
```

### Layer 3: JS / HTMX / Alpine

Behavioral enhancement. Core function still works without it.

```html
<!-- HTMX: progressive enhancement of a standard form -->
<form method="post" action="/search"
      hx-post="/search" hx-target="#results" hx-swap="innerHTML">
  <label for="query">Search</label>
  <input type="search" id="query" name="q" required>
  <button type="submit">Search</button>
</form>

<!-- Without JS: full page post + redirect -->
<!-- With HTMX: inline results, no page reload -->
```

```html
<!-- Alpine: enhanced disclosure, works without JS via open attribute -->
<details x-data="{ open: false }" :open="open">
  <summary @click.prevent="open = !open">More info</summary>
  <div x-show="open" x-transition x-cloak>
    <p>Additional details here.</p>
  </div>
</details>
```

HTMX's `hx-boost` upgrades standard `<a>` and `<form>` elements to AJAX — the most natural progressive enhancement.

---

## Inclusive Design

Concrete patterns that make interfaces work for more humans.

### User Preference Queries

```css
/* Motion: respect vestibular disorders */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}

/* Contrast: respect low-vision users */
@media (prefers-contrast: more) {
  :root { --border: 2px solid #000; }
}

/* Forced colors: Windows high-contrast mode */
@media (forced-colors: active) {
  .btn { border: 1px solid ButtonText; }
}
```

### Sizing

- **Text:** `rem`/`em` units — never `px`. Users set their base font size for a reason.
- **Fluid type:** `font-size: clamp(1rem, 0.5rem + 1.5vw, 1.5rem);`
- **Touch targets:** 44x44px minimum (`min-height: 2.75rem; min-width: 2.75rem;`)
- **Spacing:** Relative units so layouts breathe when text scales

### Color Independence

Never convey meaning through color alone.

```html
<!-- Bad: only color indicates error -->
<input style="border-color: red;">

<!-- Good: color + icon + text -->
<input aria-invalid="true" aria-describedby="email-error">
<p id="email-error" role="alert">
  <svg aria-hidden="true"><!-- error icon --></svg>
  Enter a valid email address.
</p>
```

### Language and Direction

```html
<html lang="en" dir="ltr">
<!-- Use logical properties for RTL support -->
```

```css
/* Physical (breaks in RTL) */
margin-left: 1rem;

/* Logical (works in any direction) */
margin-inline-start: 1rem;
```

---

## Self-Review Checklist

Before showing work to the user, walk through each:

- [ ] **Keyboard:** Can you reach everything with Tab / Enter / Escape / Arrow keys?
- [ ] **Screen reader:** Does it make sense read aloud? (Headings, labels, live regions, alt text)
- [ ] **Zoom 200%:** Does the layout still work? No horizontal scroll, no clipped content?
- [ ] **Persona spectrum:** Who might this exclude? (One-handed, low-vision, cognitive load, slow connection)
- [ ] **Error path:** What happens when things go wrong? (Clear message, input preserved, way forward)
- [ ] **No-JS test:** Does the core function still work without JavaScript?
- [ ] **Preference queries:** Does it respect `prefers-reduced-motion`, `prefers-color-scheme`?
- [ ] **Touch targets:** Are all interactive elements at least 44x44px?

If any check fails, fix it before showing. These aren't nice-to-haves — they're the minimum for respecting the human.

---

## Workflow

### Skill Pipeline

1. **Start here** — Understand the human (this skill)
2. **Then `mine.interface-design`** — Craft the visual system with intent
3. **Then `mine.ux-antipatterns`** — Verify the implementation catches no one off guard

### Within This Skill

1. Answer the five "Human First" questions
2. Check against Norman's 7 and Nielsen's 10
3. Build with progressive enhancement layers
4. Apply inclusive design patterns from `references/patterns.md`
5. Run the self-review checklist
6. Validate with `references/testing.md`

---

## Related

- `references/patterns.md` — Code-level patterns: semantic HTML, ARIA, keyboard, forms, HTMX, Alpine.js
- `references/testing.md` — Automated tools, manual testing, continuous monitoring
- `mine.interface-design` skill — Visual craft and consistency (downstream)
- `mine.ux-antipatterns` skill — Anti-pattern detection in code (downstream)
