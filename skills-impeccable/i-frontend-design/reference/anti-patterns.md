# Anti-Patterns

Last reviewed: 2026-05-07 (upstream [skill-v3.0.7](https://github.com/pbakaus/impeccable/releases/tag/skill-v3.0.7))

These are the fingerprints of AI-generated work from 2024-2025. If your output matches these patterns, it will look generic regardless of how much effort went into the code.

## The AI Slop Test

If you showed this interface to someone and said "AI made this," would they believe you immediately? If yes, that's the problem. A distinctive interface should make someone ask "how was this made?" not "which AI made this?"

## Typography
- **DON'T**: Use overused fonts — Inter, Roboto, Arial, Open Sans, system defaults; also now flagged: Fraunces, Geist, Mona Sans, Plus Jakarta Sans, Space Grotesk, Recoleta, Instrument Sans
- **DON'T**: Use italic-serif display fonts as a hero headline — Fraunces, Recoleta, Newsreader, Playfair, Cormorant, Tiempos (especially italic weights) are now a recognized AI-generated marketing fingerprint
- **DON'T**: Use monospace typography as lazy shorthand for "technical/developer" vibes
- **DON'T**: Put large icons with rounded corners above every heading — they rarely add value and make sites look templated
- **DON'T**: Set one or two accent words of an upright headline in italic ("Build *faster*, ship *calmer*") — a default emphasis move, not a design decision
- **DON'T**: Use monospace for eyebrows, section labels, or metadata by default — the label variant of the "technical vibes" shorthand

## Color & Theme
- **DON'T**: Use gray text on colored backgrounds — it looks washed out; use a shade of the background color instead
- **DON'T**: Use pure black (#000) or pure white (#fff) — always tint; pure black/white never appears in nature
- **DON'T**: Use the AI color palette: cyan-on-dark, purple-to-blue gradients, neon accents on dark backgrounds
- **DON'T**: Use gradient text for "impact" — especially on metrics or headings; it's decorative rather than meaningful
- **DON'T**: Default to dark mode with glowing accents — it looks "cool" without requiring actual design decisions
- **DON'T**: Default to a cream, beige, or warm off-white page background — the light-mode counterpart of dark-with-glow; pick the surface color from the brand, not the reflex

## Layout & Space
- **DON'T**: Wrap everything in cards — not everything needs a container
- **DON'T**: Nest cards inside cards — visual noise, flatten the hierarchy
- **DON'T**: Use identical card grids — same-sized cards with icon + heading + text, repeated endlessly
- **DON'T**: Use the hero metric layout template — big number, small label, supporting stats, gradient accent
- **DON'T**: Center everything — left-aligned text with asymmetric layouts feels more designed
- **DON'T**: Use the same spacing everywhere — without rhythm, layouts feel monotonous
- **DON'T**: Number sections with "01 / 02 / 03" labels unless the content is genuinely sequential

## Visual Details
- **DON'T**: Use glassmorphism everywhere — blur effects, glass cards, glow borders used decoratively rather than purposefully
- **DON'T**: Use rounded elements with thick colored border on one side — a lazy accent that almost never looks intentional
- **DON'T**: Use sparklines as decoration — tiny charts that look sophisticated but convey nothing meaningful
- **DON'T**: Use rounded rectangles with generic drop shadows — safe, forgettable, could be any AI output
- **DON'T**: Use modals unless there's truly no better alternative — modals are lazy

## Motion
- **DON'T**: Animate layout properties (width, height, padding, margin) — use transform and opacity only
- **DON'T**: Use bounce or elastic easing — they feel dated and tacky. Spring physics without visible overshoot is acceptable (high tension, high friction); real objects decelerate smoothly, they don't bounce.

## Interaction & Copy
- **DON'T**: Use uppercase letter-spaced eyebrow chips above hero headings (e.g. `TRUSTED BY 500+ TEAMS`) — including the pill-chip variant; this is a top AI-generated marketing fingerprint
- **DON'T**: Repeat the same information — redundant headers, intros that restate the heading
- **DON'T**: Make every button primary — use ghost buttons, text links, secondary styles; hierarchy matters
- **DON'T**: Default to fully pill-shaped (`border-radius: 9999px`) buttons and chips — choose the radius from the design context's sharp-to-round position
- **DON'T**: Hide critical functionality on mobile — adapt the interface, don't amputate it
- **DON'T**: Repeat information users can already see
