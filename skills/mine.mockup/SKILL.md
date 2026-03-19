---
name: mine.mockup
user-invocable: true
description: "Use when the user says: \"mockup this UI\", \"show me what it looks like\", \"HTML mockup\", \"UI preview\", or \"generate a mockup\". Generate self-contained HTML mockup files. Reads design/direction.md if present for consistent styling."
---

# Mockup

Generate self-contained HTML files for UI mockups, technical diagrams, visualizations, and data tables. Always open the result in the browser. Never fall back to ASCII art when this skill is loaded.

## Workflow

### 1. Check for Direction Files

Look for `design/direction*.md` in the project.

- **If one found**: Read it, use its tokens and direction for styling. Skip to step 3.
- **If multiple found**: Ask which applies to this mockup. Read the selected one. Skip to step 3.
- **If none found**: Ask the user: "No design direction found. Run a quick inline direction phase, or run `/mine.look-and-feel` first?"
  - If inline: proceed to step 2.
  - If redirect: tell the user to run `/mine.look-and-feel` and stop.

### 2. Quick Direction (only if no direction.md and user chose inline)

Lightweight direction — ~30 seconds, not the full look-and-feel workflow.

**Who is looking?** A developer understanding a system? A PM seeing the big picture? A team reviewing a proposal? This shapes information density and visual complexity.

**What type of content?** Architecture, flowchart, sequence, data flow, schema/ER, state machine, mind map, class diagram, C4 architecture, data table, timeline, dashboard, or UI mockup. Each has distinct layout needs and rendering approaches.

**What aesthetic?** Pick one and commit. The constrained aesthetics are safer — they have specific requirements that prevent generic output.

**Constrained aesthetics (prefer these):**
- Blueprint (technical drawing feel, subtle grid background, deep slate/blue palette, monospace labels, precise borders)
- Editorial (serif headlines like Instrument Serif or Crimson Pro, generous whitespace, muted earth tones or deep navy + gold)
- Paper/ink (warm cream `#faf7f5` background, terracotta/sage accents, informal feel)
- Monochrome terminal (green/amber on near-black, monospace everything, CRT glow optional)

**Flexible aesthetics (use with caution):**
- IDE-inspired (borrow a real, named color scheme: Dracula, Nord, Catppuccin Mocha/Latte, Solarized Dark/Light, Gruvbox, One Dark, Rose Pine) — commit to the actual palette, don't approximate
- Data-dense (small type, tight spacing, maximum information, muted colors)

**Explicitly forbidden:**
- Neon dashboard (cyan + magenta + purple on dark) — always produces AI slop
- Gradient mesh (pink/purple/cyan blobs) — too generic
- Any combination of Inter font + violet/indigo accents + gradient text

Pick font pairing, color palette, depth strategy. Vary the choice each time. The swap test: if you replaced your styling with a generic dark theme and nobody would notice the difference, you haven't designed anything.

### 3. Structure

**Read the reference material** before generating. Don't memorize it — read it each time to absorb the patterns.
- For text-heavy architecture overviews (card content matters more than topology): read `./templates/architecture.html`
- For flowcharts, sequence diagrams, ER, state machines, mind maps, class diagrams, C4: read `./templates/mermaid-flowchart.html`
- For data tables, comparisons, audits, feature matrices: read `./templates/data-table.html`
- For prose-heavy publishable pages (READMEs, articles, blog posts, essays): read the "Prose Page Elements" section in `./references/css-patterns.md` and "Typography by Content Voice" in `./references/libraries.md`

**For CSS/layout patterns and SVG connectors**, read `./references/css-patterns.md`.

**For pages with 4+ sections** (reviews, recaps, dashboards), also read `./references/responsive-nav.md` for section navigation with sticky sidebar TOC on desktop and horizontal scrollable bar on mobile.

**Choosing a rendering approach:**

| Content type | Approach | Why |
|---|---|---|
| Architecture (text-heavy) | CSS Grid cards + flow arrows | Rich card content (descriptions, code, tool lists) needs CSS control |
| Architecture (topology-focused) | **Mermaid** | Visible connections between components need automatic edge routing |
| Flowchart / pipeline | **Mermaid** | Automatic node positioning and edge routing |
| Sequence diagram | **Mermaid** | Lifelines, messages, and activation boxes need automatic layout |
| Data flow | **Mermaid** with edge labels | Connections and data descriptions need automatic edge routing |
| ER / schema diagram | **Mermaid** | Relationship lines between many entities need auto-routing |
| State machine | **Mermaid** | State transitions with labeled edges need automatic layout |
| Mind map | **Mermaid** | Hierarchical branching needs automatic positioning |
| Class diagram | **Mermaid** | Inheritance, composition, aggregation lines with automatic routing |
| C4 architecture | **Mermaid** | Use `graph TD` + `subgraph` for C4 (not native `C4Context` — it ignores themes) |
| Data table | HTML `<table>` | Semantic markup, accessibility, copy-paste behavior |
| Timeline | CSS (central line + cards) | Simple linear layout doesn't need a layout engine |
| Dashboard | CSS Grid + Chart.js | Card grid with embedded charts |

**Mermaid theming:** Always use `theme: 'base'` with custom `themeVariables` so colors match your page palette. Use `layout: 'elk'` for complex graphs (requires the `@mermaid-js/layout-elk` package — see `./references/libraries.md` for the CDN import). Override Mermaid's SVG classes with CSS for pixel-perfect control. See `./references/libraries.md` for full theming guide.

**Mermaid containers:** Always center Mermaid diagrams with `display: flex; justify-content: center;`. Add zoom controls (+/-/reset/expand) to every `.mermaid-wrap` container. Include the click-to-expand JavaScript so clicking the diagram (or the expand button) opens it full-size in a new tab.

**Never use bare `<pre class="mermaid">`.** It renders but has no zoom/pan controls — diagrams become tiny and unusable. Always use the full `diagram-shell` pattern from `templates/mermaid-flowchart.html`: the HTML structure (`.diagram-shell` > `.mermaid-wrap` > `.zoom-controls` + `.mermaid-viewport` > `.mermaid-canvas`), the CSS, and the JS module for zoom/pan/fit. Copy it wholesale.

**Mermaid scaling:** Diagrams with 10+ nodes render too small by default. For 10-12 nodes, increase `fontSize` in themeVariables to 18-20px and set `INITIAL_ZOOM` to 1.5-1.6. For 15+ elements, don't try to scale — use the hybrid pattern instead (simple Mermaid overview + CSS Grid cards). See "Architecture / System Diagrams" in the diagram types section below.

**Mermaid layout direction:** Prefer `flowchart TD` (top-down) over `flowchart LR` (left-to-right) for complex diagrams. LR spreads horizontally and makes labels unreadable when there are many nodes. Use LR only for simple 3-4 node linear flows.

**Mermaid line breaks in flowchart labels:** Use `<br/>` inside quoted labels. Never use escaped newlines like `\n` (Mermaid renders them as literal text in HTML output).

**Mermaid CSS class collision constraint:** Never define `.node` as a page-level CSS class. Mermaid.js uses `.node` internally on SVG `<g>` elements with `transform: translate(x, y)` for positioning. Use the namespaced `.ve-card` class for card components instead.

### 4. Style

Apply direction.md tokens (or inline direction) to the HTML. If a direction.md exists, every CSS value must reference a token from that document — no raw hex values, no magic numbers.

**Typography is the diagram.** Pick a distinctive font pairing from the list in `./references/libraries.md`. Every page should use a different pairing from recent generations.

**Forbidden as `--font-body`:** Inter, Roboto, Arial, Helvetica, system-ui alone. These are AI slop signals.

**Good pairings (use these):**
- DM Sans + Fira Code (technical, precise)
- Instrument Serif + JetBrains Mono (editorial, refined)
- IBM Plex Sans + IBM Plex Mono (reliable, readable)
- Bricolage Grotesque + Fragment Mono (bold, characterful)
- Plus Jakarta Sans + Azeret Mono (rounded, approachable)

Load via `<link>` in `<head>`. Include a system font fallback in the `font-family` stack for offline resilience.

**Color tells a story.** Use CSS custom properties for the full palette. Define at minimum: `--bg`, `--surface`, `--border`, `--text`, `--text-dim`, and 3-5 accent colors. Each accent should have a full and a dim variant. Name variables semantically. Support both themes.

**Forbidden accent colors:** `#8b5cf6` `#7c3aed` `#a78bfa` (indigo/violet), `#d946ef` (fuchsia), the cyan-magenta-pink combination. These are Tailwind defaults that signal zero design intent.

**Good accent palettes (use these):**
- Terracotta + sage (`#c2410c`, `#65a30d`) — warm, earthy
- Teal + slate (`#0891b2`, `#0369a1`) — technical, precise
- Rose + cranberry (`#be123c`, `#881337`) — editorial, refined
- Amber + emerald (`#d97706`, `#059669`) — data-focused
- Deep blue + gold (`#1e3a5f`, `#d4a73a`) — premium, sophisticated

Put your primary aesthetic in `:root` and the alternate in the media query:

```css
/* Light-first (editorial, paper/ink, blueprint): */
:root { /* light values */ }
@media (prefers-color-scheme: dark) { :root { /* dark values */ } }

/* Dark-first (IDE-inspired, terminal): */
:root { /* dark values */ }
@media (prefers-color-scheme: light) { :root { /* light values */ } }
```

**Surfaces whisper, they don't shout.** Build depth through subtle lightness shifts (2-4% between levels), not dramatic color changes. Borders should be low-opacity rgba — visible when you look, invisible when you don't.

**Backgrounds create atmosphere.** Don't use flat solid colors for the page background. Subtle gradients, faint grid patterns via CSS, or gentle radial glows behind focal areas.

**Visual weight signals importance.** Not every section deserves equal visual treatment. Hero sections should dominate. Reference sections should be compact. Use `<details>/<summary>` for sections that are useful but not primary.

**Surface depth creates hierarchy.** Vary card depth to signal what matters. Hero sections get elevated shadows and accent-tinted backgrounds. Body content stays flat. Code blocks feel recessed. See the depth tiers in `./references/css-patterns.md`.

**Animation earns its place.** Staggered fade-ins on page load guide the eye. Mix animation types by role: `fadeUp` for cards, `fadeScale` for KPIs, `drawIn` for SVG connectors, `countUp` for hero numbers. Always respect `prefers-reduced-motion`. For orchestrated multi-element sequences, anime.js via CDN is available (see `./references/libraries.md`).

**Forbidden animations:**
- Animated glowing box-shadows — this is AI slop
- Pulsing/breathing effects on static content
- Continuous animations that run after page load (except progress indicators)

### 5. Quality Checks

Before delivering, verify:
- **The squint test**: Blur your eyes. Can you still perceive hierarchy? Are sections visually distinct?
- **The swap test**: Would replacing your fonts and colors with a generic dark theme make this indistinguishable from a template? If yes, push the aesthetic further.
- **Both themes**: Toggle between light and dark mode. Both should look intentional, not broken.
- **Information completeness**: Does the mockup actually convey what the user asked for? Pretty but incomplete is a failure.
- **No overflow**: Resize the browser to different widths. No content should clip or escape its container. Every grid and flex child needs `min-width: 0`. Side-by-side panels need `overflow-wrap: break-word`. Never use `display: flex` on `<li>` for marker characters — use absolute positioning for markers instead. See the Overflow Protection section in `./references/css-patterns.md`.
- **Mermaid zoom controls**: Every `.mermaid-wrap` container must have zoom controls, Ctrl/Cmd+scroll zoom, click-and-drag panning, and click-to-expand.
- **File opens cleanly**: No console errors, no broken font loads, no layout shifts.

### 6. Deliver

**Output location:** Write to `~/.claude/diagrams/`. Use a descriptive filename based on content: `dashboard-mockup.html`, `pipeline-flow.html`, `schema-overview.html`. The directory persists across sessions.

**Open in browser:**
- macOS: `open ~/.claude/diagrams/filename.html`
- Linux: `xdg-open ~/.claude/diagrams/filename.html`

**Tell the user** the file path so they can re-open or share it.

### 7. Offer to Persist (only if step 2 was used)

After delivering the mockup, offer: "Save this direction to `design/direction.md` so future mockups and builds use it?"

If yes, write a lightweight direction.md from the inline choices with `completeness: lightweight` in the frontmatter. Use this format:

```markdown
# Design Direction: [Product/Feature Name]

**Date:** YYYY-MM-DD
**Completeness:** lightweight

## Intent
- **Who**: [audience from step 2]
- **Task**: [what they're doing]
- **Feel**: [aesthetic chosen]

## Tokens

### Color
| Token | Value | Role |
|-------|-------|------|
| `--bg` | #... | Page background |
| ... | ... | ... |

### Typography
- **Primary**: [font name]
- **Mono**: [font name]
```

This lets mine.build distinguish full vs. lightweight directions and suggest running `/mine.look-and-feel` for the full treatment when appropriate.

## Diagram Types

### Architecture / System Diagrams
Three approaches depending on complexity:

**Simple topology (under 10 elements):** Use Mermaid with custom `themeVariables`.

**Text-heavy overviews (under 15 elements):** CSS Grid with explicit row/column placement. The reference template at `./templates/architecture.html` demonstrates this pattern. Use when cards need descriptions, code references, tool lists, or other rich content.

**Complex architectures (15+ elements):** Use the **hybrid pattern** — a simple Mermaid overview (5-8 nodes) followed by detailed CSS Grid cards. Never cram 15+ elements into a single Mermaid diagram.

### Data Tables / Comparisons / Audits
Use a real `<table>` element. The reference template at `./templates/data-table.html` demonstrates all patterns. Layout: sticky `<thead>`, alternating row backgrounds, responsive wrapper with `overflow-x: auto`, row hover highlight.

### Implementation Plans
Show **file structure with descriptions**, not full source files. Show **key snippets only**. Use **collapsible sections** for full code if truly needed. See code block patterns in `./references/css-patterns.md`.

## File Structure

Every mockup is a single self-contained `.html` file. No external assets except CDN links (fonts, optional libraries). Structure:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Descriptive Title</title>
  <link href="https://fonts.googleapis.com/css2?family=...&display=swap" rel="stylesheet">
  <style>
    /* CSS custom properties, theme, layout, components — all inline */
  </style>
</head>
<body>
  <!-- Semantic HTML: sections, headings, lists, tables, inline SVG -->
  <!-- Optional: <script> for Mermaid, Chart.js, or anime.js when used -->
</body>
</html>
```

## Anti-Patterns (AI Slop)

These patterns are explicitly forbidden. Review every generated page against this list.

### Typography
**Forbidden fonts as primary `--font-body`:** Inter, Roboto, Arial, Helvetica, system-ui/sans-serif alone.

### Color Palette
**Forbidden accent colors:** Indigo-500/violet-500 (`#8b5cf6`, `#7c3aed`, `#a78bfa`). The cyan + magenta + pink neon gradient combination.

**Forbidden color effects:** Gradient text on headings (`background-clip: text`). Animated glowing box-shadows. Multiple overlapping radial glows creating a "neon haze."

### Section Headers
**Forbidden:** Emoji icons in section headers. Section headers that all use the same icon-in-rounded-box pattern.

**Required:** Use styled monospace labels with colored dot indicators, numbered badges, or asymmetric section dividers. If an icon is genuinely needed, use an inline SVG — not emoji.

### Layout & Hierarchy
**Forbidden:** Perfectly centered everything with uniform padding. All cards styled identically. Every section getting equal visual treatment. Symmetric layouts.

**Required:** Vary visual weight. Hero sections should dominate. Use the depth tiers (hero > elevated > default > recessed). Asymmetric layouts create interest.

### Template Patterns
**Forbidden:** Three-dot window chrome on code blocks. KPI cards with identical gradient text. "Neon Dashboard" aesthetic. Gradient meshes with pink/purple/cyan blobs.

### The Slop Test
Before delivering: **Would a developer looking at this page immediately think "AI generated this"?** Telltale signs: Inter/Roboto with purple gradient accents, `background-clip: text` gradients on every heading, emoji section headers, glowing cards, cyan-magenta-pink on dark, uniform card grid, three-dot code block chrome. If two or more are present, regenerate with a constrained aesthetic.
