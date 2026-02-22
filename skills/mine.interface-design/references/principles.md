# Code-Level Craft Principles

Concrete values and CSS patterns that supplement the main skill. Learn the thinking, not the exact values — yours will differ.

---

## Surface Elevation in Practice

Higher elevation = slightly lighter (dark mode) or uses shadow (light mode). Each jump: a few percentage points of lightness.

```
Level 0: Base background (app canvas)
Level 1: Cards, panels (same visual plane)
Level 2: Dropdowns, popovers (floating above)
Level 3: Stacked overlays (rare)
```

The difference between levels should be barely visible in isolation but felt when surfaces stack.

## Border Approaches

```css
/* Borders-only */
--border: rgba(0, 0, 0, 0.08);
--border-subtle: rgba(0, 0, 0, 0.05);
border: 0.5px solid var(--border);

/* Single shadow */
--shadow: 0 1px 3px rgba(0, 0, 0, 0.08);

/* Layered shadow */
--shadow-layered:
  0 0 0 0.5px rgba(0, 0, 0, 0.05),
  0 1px 2px rgba(0, 0, 0, 0.04),
  0 2px 4px rgba(0, 0, 0, 0.03),
  0 4px 8px rgba(0, 0, 0, 0.02);
```

## Symmetrical Padding

```css
/* Good */
padding: 16px;
padding: 12px 16px; /* Only when horizontal needs more room */

/* Bad — asymmetric without reason */
padding: 24px 16px 12px 16px;
```

## Alternative Backgrounds for Depth

Beyond shadows, contrasting backgrounds create depth. An "inset" background makes content feel recessed:
- Empty states in data grids
- Code blocks
- Inset panels
- Visual grouping without borders

## Custom Select Triggers

Custom select triggers must use `display: inline-flex` with `white-space: nowrap` to keep text and chevron on the same row.

## Dark Mode Specifics

- **Borders over shadows** — shadows are less visible on dark backgrounds
- **Desaturate semantic colors** — success/warning/error often too vivid on dark
- **Same hierarchy, different values** — invert the lightness progression
- In dark mode, use low opacity borders (0.05-0.12 alpha) — they blend with backgrounds naturally

## Example: Precision System

```
Direction: Precision & Density
Foundation: Cool (slate), Depth: Borders-only

Spacing: 4px base -> 4, 8, 12, 16, 24, 32
Radius: 4px, 6px, 8px (sharp, technical)
Typography: system-ui, scale 11-18, weights 400/500/600

Button: 32px h, 8px 12px pad, 4px radius, 1px border
Card: 0.5px border, 12px pad, 6px radius, no shadow
Table cell: 8px 12px pad, 13px tabular-nums
```

## Example: Warmth System

```
Direction: Warmth & Approachability
Foundation: Warm (stone), Depth: Subtle shadows

Spacing: 4px base -> 8, 12, 16, 24, 32, 48 (generous)
Radius: 8px, 12px, 16px (soft, friendly)
Typography: Inter, scale 13-24, weights 400/500/600

Button: 40px h, 12px 20px pad, 8px radius, subtle shadow
Card: no border, 20px pad, 12px radius, shadow
Input: 44px h, 12px 16px pad, 8px radius, 1.5px border
```

## Typography Cheat Sheet

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
