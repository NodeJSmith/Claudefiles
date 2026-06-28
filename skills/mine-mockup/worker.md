# Mockup — Worker Instructions

Generate a self-contained HTML file for a UI mockup, technical diagram, visualization, or data table. Open the result in the browser. Never fall back to ASCII art.

You receive: a description of what to generate, an aesthetic direction (font pairing, color palette, depth strategy), and optionally a design context file path.

## Step 1: Read Design Context

If a design context path was provided, read it and use its tokens and direction for styling. If it includes a Design Tokens section, every CSS value must reference a token from that document.

## Step 2: Read Reference Material

Read the appropriate reference material **before** generating. Don't skip this.

- For text-heavy architecture overviews (card content matters more than topology): read `${CLAUDE_HOME:-~/.claude}/skills/mine-mockup/templates/architecture.html`
- For flowcharts, sequence diagrams, ER, state machines, mind maps, class diagrams, C4: read `${CLAUDE_HOME:-~/.claude}/skills/mine-mockup/templates/mermaid-flowchart.html`
- For data tables, comparisons, audits, feature matrices: read `${CLAUDE_HOME:-~/.claude}/skills/mine-mockup/templates/data-table.html`
- For prose-heavy publishable pages (READMEs, articles, blog posts, essays): read the "Prose Page Elements" section in `${CLAUDE_HOME:-~/.claude}/skills/mine-mockup/references/css-patterns.md` and "Typography by Content Voice" in `${CLAUDE_HOME:-~/.claude}/skills/mine-mockup/references/libraries.md`

**For CSS/layout patterns and SVG connectors**, read `${CLAUDE_HOME:-~/.claude}/skills/mine-mockup/references/css-patterns.md`.

**For pages with 4+ sections** (reviews, recaps, dashboards), also read `${CLAUDE_HOME:-~/.claude}/skills/mine-mockup/references/responsive-nav.md` for section navigation.

## Step 3: Choose Rendering Approach

| Content type | Approach | Why |
|---|---|---|
| Architecture (text-heavy) | CSS Grid cards + flow arrows | Rich card content needs CSS control |
| Architecture (topology-focused) | **Mermaid** | Connections need automatic edge routing |
| Flowchart / pipeline | **Mermaid** | Automatic node positioning and edge routing |
| Sequence diagram | **Mermaid** | Lifelines, messages, activation boxes |
| Data flow | **Mermaid** with edge labels | Connections and data descriptions |
| ER / schema diagram | **Mermaid** | Relationship lines between entities |
| State machine | **Mermaid** | State transitions with labeled edges |
| Mind map | **Mermaid** | Hierarchical branching |
| Class diagram | **Mermaid** | Inheritance, composition, aggregation |
| C4 architecture | **Mermaid** | Use `graph TD` + `subgraph` (not native `C4Context`) |
| Data table | HTML `<table>` | Semantic markup, accessibility, copy-paste |
| Timeline | CSS (central line + cards) | Simple linear layout |
| Dashboard | CSS Grid + Chart.js | Card grid with embedded charts |

**Mermaid rules** (theming, `elk` layout, scaling, direction, label breaks, `.node` CSS class-collision) live in `${CLAUDE_HOME:-~/.claude}/skills/mine-mockup/references/libraries.md`. Two non-negotiables:

- **Never use bare `<pre class="mermaid">`.** Copy the full `diagram-shell` pattern from `templates/mermaid-flowchart.html` wholesale (HTML structure + CSS + zoom/pan/fit JS). Give every `.mermaid-wrap` zoom controls plus click-to-expand.
- For 15+ elements, use the hybrid pattern (simple Mermaid overview + CSS Grid cards).

### Architecture / System Diagrams

Three approaches depending on complexity:
- **Simple topology (under 10 elements):** Mermaid with custom `themeVariables`.
- **Text-heavy overviews (under 15 elements):** CSS Grid with explicit row/column placement.
- **Complex architectures (15+ elements):** Hybrid pattern — simple Mermaid overview (5-8 nodes) followed by detailed CSS Grid cards.

### Data Tables / Comparisons / Audits

Real `<table>` element. Sticky `<thead>`, alternating row backgrounds, responsive wrapper with `overflow-x: auto`, row hover highlight.

### Implementation Plans

Show file structure with descriptions, not full source files. Key snippets only. Collapsible sections for full code if needed.

## Step 4: Style

Apply the provided aesthetic direction. If design context tokens exist, use them.

**Typography is the diagram.** Use the font pairing from the direction. Load via `<link>` in `<head>`. Include system font fallbacks.

**Color tells a story.** Use CSS custom properties for the full palette. Define at minimum: `--bg`, `--surface`, `--border`, `--text`, `--text-dim`, and 3-5 accent colors with full and dim variants. Name variables semantically. Support both themes.

Put your primary aesthetic in `:root` and the alternate in the media query:

```css
/* Light-first (editorial, paper/ink, blueprint): */
:root { /* light values */ }
@media (prefers-color-scheme: dark) { :root { /* dark values */ } }

/* Dark-first (IDE-inspired, terminal): */
:root { /* dark values */ }
@media (prefers-color-scheme: light) { :root { /* light values */ } }
```

**Surfaces whisper, they don't shout.** Build depth through subtle lightness shifts (2-4% between levels). Borders should be low-opacity rgba.

**Backgrounds create atmosphere.** Subtle gradients, faint grid patterns, or gentle radial glows behind focal areas.

**Visual weight signals importance.** Hero sections dominate. Reference sections are compact. Use `<details>/<summary>` for sections that are useful but not primary.

**Surface depth creates hierarchy.** Vary card depth to signal what matters. Hero sections get elevated shadows and accent-tinted backgrounds. Code blocks feel recessed.

**Animation earns its place.** Staggered fade-ins on page load guide the eye. Mix animation types by role: `fadeUp` for cards, `fadeScale` for KPIs, `drawIn` for SVG connectors, `countUp` for hero numbers. Always respect `prefers-reduced-motion`.

## Step 5: Quality Checks

Before delivering, verify:
- **The squint test**: Blur your eyes. Can you still perceive hierarchy?
- **The swap test**: Would replacing your fonts and colors with a generic dark theme make this indistinguishable from a template? If yes, push the aesthetic further.
- **Both themes**: Toggle between light and dark mode. Both should look intentional.
- **Information completeness**: Does the mockup convey what was asked for?
- **No overflow**: Resize the browser to different widths. No content should clip or escape its container. Every grid and flex child needs `min-width: 0`. Side-by-side panels need `overflow-wrap: break-word`. Never use `display: flex` on `<li>` for marker characters.
- **Mermaid zoom controls**: Every `.mermaid-wrap` container must have zoom controls, Ctrl/Cmd+scroll zoom, click-and-drag panning, and click-to-expand.
- **File opens cleanly**: No console errors, no broken font loads, no layout shifts.

## Step 6: Deliver

Run `get-skill-tmpdir mine-mockup` and write to `<tmpdir>/`. Use a descriptive filename: `dashboard-mockup.html`, `pipeline-flow.html`, `schema-overview.html`.

Open in browser:
- macOS: `open <tmpdir>/filename.html`
- Linux: `xdg-open <tmpdir>/filename.html`

## Step 7: Return

Your final message must be the file path. Nothing else.

## Reference

### File Structure

Every mockup is a single self-contained `.html` file. No external assets except CDN links.

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

### Motion

**Forbidden animations:** Animated glowing box-shadows. Pulsing/breathing effects on static content. Continuous animations after page load (except progress indicators).

### Section Headers

**Forbidden:** Emoji icons in section headers. Section headers that all use the same icon-in-rounded-box pattern.

**Required:** Styled monospace labels with colored dot indicators, numbered badges, or asymmetric section dividers. If an icon is genuinely needed, use an inline SVG.

### Layout & Hierarchy

**Forbidden:** Perfectly centered everything with uniform padding. All cards styled identically. Every section getting equal visual treatment. Symmetric layouts.

**Required:** Vary visual weight. Hero sections dominate. Use depth tiers (hero > elevated > default > recessed). Asymmetric layouts create interest.

### Template Patterns

**Forbidden:** Three-dot window chrome on code blocks. KPI cards with identical gradient text. "Neon Dashboard" aesthetic. Gradient meshes with pink/purple/cyan blobs.

### The Slop Test

Before delivering: **Would a developer look at this and immediately think "AI generated this"?** Telltale signs: Inter/Roboto with purple gradient accents, `background-clip: text` gradients on every heading, emoji section headers, glowing cards, cyan-magenta-pink on dark, uniform card grid, three-dot code block chrome. If two or more are present, regenerate with a constrained aesthetic.
