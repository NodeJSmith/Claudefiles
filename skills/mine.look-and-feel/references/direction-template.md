# direction.md Template

Use this format when writing `design/direction.md` (or `design/direction-{scope}.md`).

## Completeness Variants

- **`completeness: full`** — All sections populated with rationale. Produced by mine.look-and-feel's full workflow. Contains Intent, References, Domain, Tokens (all subsections), Anti-patterns, and Component Notes.
- **`completeness: lightweight`** — Intent + Tokens sections only. No References, Domain, or Anti-patterns. Produced by mine.mockup's inline persist (step 7) when no full direction exists. mine.build may suggest running `/mine.look-and-feel` for the full treatment when it detects a lightweight direction.

## Writing Guidance

- Every token value must be justified against intent and domain. "It's common" is not a reason.
- Use semantic token names that evoke the product's world (`--ink`, `--parchment`) not generic names (`--gray-700`, `--surface-2`).
- The closed token layer constraint: every CSS value in code must reference a token from this document. No raw hex values, no magic numbers.
- Dark mode values use the same token names with different values — same hierarchy, inverted lightness.
- Keep the document framework-agnostic at the decision level. Token values can reference CSS custom properties, but the decisions themselves should work for any stack.

---

## Template

```markdown
# Design Direction: [Product/Feature Name]

**Date:** YYYY-MM-DD
**Updated:** YYYY-MM-DD
**Completeness:** full | lightweight

## Intent
- **Who**: [specific person in specific context — not "users"]
- **Task**: [the verb — not "use the app"]
- **Feel**: [specific aesthetic language — not "clean and modern"]

## References
- [App/site name]: [what to take from it — e.g., "the density and monospace feel"]
- [App/site name]: [what to take from it]

## Domain
- **Concepts**: [5+ domain-specific concepts]
- **Color world**: [colors that exist naturally in this domain]
- **Signature**: [one element unique to THIS product]
- **Rejected defaults**: [obvious choices and why they're wrong for this]

## Tokens

### Color
| Token | Value | Role |
|-------|-------|------|
| `--bg` | #... | Page background |
| `--surface` | #... | Card/panel background |
| `--border` | rgba(...) | Separation |
| `--text` | #... | Primary text |
| `--text-dim` | #... | Secondary text |
| `--accent` | #... | Primary action/emphasis |
| `--accent-dim` | #... | Accent backgrounds |
| `--destructive` | #... | Error/danger |
| `--success` | #... | Positive/complete |
| `--warning` | #... | Caution |

Dark mode values in a second table (same token names, different values).

**Rationale**: [how colors connect to domain and intent]

### Typography
- **Primary**: [font name] — [why]
- **Mono**: [font name] — [for code/data]
- **Scale**: [specific sizes: xs, sm, base, lg, xl, 2xl, 3xl]
- **Weights**: [which weights, for what purpose]

### Spacing
- **Base**: [value, e.g., 4px or 0.25rem]
- **Scale**: micro (1×), sm (2×), md (4×), lg (8×), xl (12×), 2xl (16×)

### Depth
- **Strategy**: [borders-only | subtle shadows | layered | surface tints]
- **Why**: [connection to intent and feel]
- **Levels**: [specific values for each elevation tier]

### Border Radius
- **Scale**: sm (inputs/buttons), md (cards), lg (modals)
- **Character**: [sharp=technical, round=friendly — where on the spectrum]

### Motion
- **Micro**: [~150ms, easing]
- **Transition**: [200-250ms, easing]
- **Entrance**: [if applicable]

## Anti-patterns
- [Specific things to avoid for THIS product — not generic advice]

## Component Notes
- [Any component-specific decisions from exploration]
```

---

## Surface Elevation Reference

Surfaces stack in numbered levels. Each jump should be only a few percentage points of lightness — whisper-quiet shifts you feel rather than see.

```
Level 0: Base background (app canvas)
Level 1: Cards, panels (same visual plane)
Level 2: Dropdowns, popovers (floating above)
Level 3: Stacked overlays (rare)
```

Key decisions:
- **Sidebars:** Same background as canvas. Different colors fragment visual space. A subtle border is enough separation.
- **Dropdowns:** One level above parent. If both share a level, the dropdown blends and layering is lost.
- **Inputs:** Slightly darker than surroundings. A darker background signals "type here" without heavy borders.

In dark mode, higher elevation = slightly lighter. Shadows are less visible — lean on borders instead. Use low opacity borders (0.05-0.12 alpha) that blend with backgrounds naturally.

## Typography Reference

Avoid generic defaults (Inter, Roboto, Arial, Open Sans, system fonts). Choose fonts that signal the product's identity.

| Vibe | Fonts |
|------|-------|
| **Code / Technical** | JetBrains Mono, Fira Code, Space Grotesk |
| **Editorial / Literary** | Playfair Display, Crimson Pro, Fraunces, Newsreader |
| **Startup / Modern** | Clash Display, Satoshi, Cabinet Grotesk |
| **Technical / Corporate** | IBM Plex family, Source Sans 3 |
| **Distinctive / Bold** | Bricolage Grotesque, Obviously |

**Pairing principle:** High contrast = interesting. Display + monospace, serif + geometric sans, variable font across weights.

**Use extremes:** 100/200 weight vs 800/900, not 400 vs 600. Size jumps of 3x+, not 1.5x. Pick one distinctive font, use it decisively. Load from Google Fonts.
