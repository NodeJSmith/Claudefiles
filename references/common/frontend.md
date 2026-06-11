# Frontend

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

Preact is the default framework. Use `class=` in JSX, not `className=`. Preact maps `class` directly to the DOM attribute.

## Component Design

Functional components only. No class components.

Keep components small and focused. A component that does one thing well is better than a component that handles three concerns with conditional rendering. Extract when a block has its own state or its own reason to re-render.

## Props

Use destructuring in the function signature. Define prop types with `interface` when the component is exported, inline when it is not.

Avoid prop drilling past two levels. If a value needs to reach deeply nested components, use context or signals.

## Hooks

### Rules

- Import hooks from `preact/hooks` (not `react`).
- Custom hooks start with `use`. Extract one when the same stateful pattern appears in two components, or when a single component's hook logic exceeds ~15 lines.

### Effect Cleanup

Every `useEffect` that subscribes, listens, or starts a timer must return a cleanup function. Forgetting cleanup causes memory leaks and stale callbacks.

### Avoid Effects for Derived State

If a value can be computed from props or other state, compute it during render. Do not use `useEffect` to synchronize derived values.

```tsx
// bad: effect for derived state
const [fullName, setFullName] = useState("");
useEffect(() => {
  setFullName(`${first} ${last}`);
}, [first, last]);

// good: compute during render
const fullName = `${first} ${last}`;
```

## Signals (Preact)

When using `@preact/signals`, prefer signals over `useState` for state that is read by many components. Signals skip the virtual DOM diffing for subscribers.

```tsx
import { signal, computed } from "@preact/signals";

const count = signal(0);
const doubled = computed(() => count.value * 2);

function Counter() {
  return <button onClick={() => count.value++}>{doubled}</button>;
}
```

Signals are not a full replacement for `useState`. Use `useState` for component-local state that no other component reads. Use signals for shared or frequently-updated state.

## CSS and Styling

### CSS Modules or Utility-First

Prefer CSS Modules (`.module.css`) for component-scoped styles. Utility-first (Tailwind/UnoCSS) is acceptable when the project already uses it. Do not mix approaches within a project.

### No Inline Styles for Layout

Inline `style={}` is acceptable for dynamic values (positions, transforms, colors from data). Do not use inline styles for static layout, spacing, or typography — those belong in classes.

### Design Tokens

Define spacing, color, and typography scales as CSS custom properties. Reference tokens instead of hardcoding values.

```css
:root {
  --space-xs: 0.25rem;
  --space-sm: 0.5rem;
  --space-md: 1rem;
  --space-lg: 2rem;
  --color-primary: #2563eb;
  --radius-md: 0.5rem;
}
```

## Accessibility

### Minimum Requirements

- All interactive elements are keyboard-accessible (`button`, `a`, or explicit `role` + `tabindex`).
- Images have `alt` text. Decorative images use `alt=""`.
- Form inputs have associated `<label>` elements.
- Color is not the sole indicator of state (add icons, text, or patterns).
- Focus is visible and managed on route changes and modal open/close.

### Semantic HTML

Use the correct element for the job. `<button>` for actions, `<a>` for navigation, `<nav>` for navigation containers, `<main>` for primary content. Do not use `<div onClick>` for interactive elements.

## Vite Conventions

### Imports

Use path aliases (`@/components/...`) configured in `vite.config.ts` and `tsconfig.json` instead of deep relative paths (`../../../components/...`).

### Environment Variables

Access via `import.meta.env.VITE_*`. Only variables prefixed with `VITE_` are exposed to client code. Never put secrets in `VITE_` variables.

### Code Splitting

Use dynamic `import()` for routes and heavy components. Vite handles chunking automatically.

```tsx
// requires preact/compat aliases in vite.config.ts and tsconfig.json
import { lazy } from "preact/compat";
const Settings = lazy(() => import("./pages/Settings"));
```

## Performance

### Avoid Unnecessary Re-renders

- Memoize expensive computations with `useMemo`.
- Memoize callback references with `useCallback` when passed as props to child components that implement `memo`.
- Do not wrap every function in `useCallback` or every value in `useMemo` by default. Only when profiling shows a re-render problem.
- Components that subscribe to signals already avoid unnecessary re-renders. `memo` and `useCallback` are less relevant there.

### Lists Need Keys

Every item in a rendered list needs a stable, unique `key`. Do not use array index as key when items can be reordered, added, or removed.

### Images

Use `loading="lazy"` for below-the-fold images. Provide `width` and `height` attributes to prevent layout shift.

## Testing

Follow `references/common/testing.md` for test discovery and execution rules. When starting a new project, prefer Vitest for unit tests with `@testing-library/preact` (not `@testing-library/react`) and Playwright for E2E. Test user behavior, not implementation details.

Prefer `getByRole`, `getByLabelText`, `getByText` over `getByTestId`. Test IDs are a last resort.

## Workflow

### Scope Before Coding (CRITICAL)

When asked to change **anything** on a UI page, before writing a single line of code:

1. **Screenshot with Playwright** — if Playwright MCP tools are available and the app is running, take a live screenshot of the affected page(s)
2. **Identify the full surface** — find *everything* on the page related to the request, not just the literal ask
3. **Check sibling pages** — the same pattern almost always appears on related pages (e.g., one list page → all list pages; one sort column → all sort columns; one form → all forms)
4. **Present the full scope to the user** — one plan covering all of it, before implementing anything

Scoping to the literal request creates 3-4 follow-up prompts. One screenshot + sibling check prevents the entire loop.

**Wrong approach:**
> User: "add sort indicators to the dashboard"
> Claude: *implements dashboard sort indicators only*
> User: "now do the same for the schedule list"
> (repeat for each page)

**Right approach:**
> User: "add sort indicators to the dashboard"
> Claude: *screenshots dashboard and schedule list, notices list has the same unsorted pattern*
> Claude: "I see the dashboard and schedule list both need this. Here's the plan for both."

### Verify After Implementing

Take fresh screenshots to verify the change looks right before committing. Visual bugs only appear in screenshots — code review alone is not sufficient for UI work.

### Screenshots Before Design Review (MANDATORY)

Before running **any** frontend design review — UX audit, interface design critique, HCD review, anti-pattern scan — always get visual context first:

1. If Playwright MCP tools are available and a dev server is running, take fresh screenshots of all main pages — screenshots are used for immediate inline review and do not need to be saved to disk
2. Read each screenshot alongside the code — visual review catches overflow, clipping, empty states, contrast failures, and density issues that are invisible in code alone

This applies regardless of which skill or command triggers the review.
