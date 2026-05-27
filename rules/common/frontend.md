# Frontend

Preact is the default framework. Use `class=` in JSX, not `className=`. Preact maps `class` directly to the DOM attribute.

## Component Design

Functional components only. No class components.

Keep components small and focused. A component that does one thing well is better than a component that handles three concerns with conditional rendering. Extract when a block has its own state or its own reason to re-render.

```tsx
// bad: mixed concerns
function Dashboard({ user, items, notifications }) {
  return (
    <div>
      <header>{/* 30 lines of user menu */}</header>
      <main>{/* 40 lines of item grid */}</main>
      <aside>{/* 25 lines of notification panel */}</aside>
    </div>
  );
}

// good: each piece owns its state
function Dashboard() {
  return (
    <div>
      <UserMenu />
      <ItemGrid />
      <NotificationPanel />
    </div>
  );
}
```

## Props

Use destructuring in the function signature. Define prop types with `interface` when the component is exported, inline when it is not.

```tsx
interface ItemCardProps {
  item: Item;
  onSelect: (id: ItemId) => void;
  selected?: boolean;
}

function ItemCard({ item, onSelect, selected = false }: ItemCardProps) {
  return (
    <div class={selected ? "card selected" : "card"} onClick={() => onSelect(item.id)}>
      {item.name}
    </div>
  );
}
```

Avoid prop drilling past two levels. If a value needs to reach deeply nested components, use context or signals.

## Hooks

### Rules

- Import hooks from `preact/hooks` (not `react`).
- Hooks at the top of the component, before any early returns or conditional logic.
- Never call hooks inside conditions, loops, or nested functions.
- Custom hooks start with `use` and extract reusable stateful logic.

### Custom Hooks Over Inline Logic

Extract a custom hook when the same stateful pattern appears in two components, or when a single component's hook logic exceeds ~15 lines.

```tsx
function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}
```

### Effect Cleanup

Every `useEffect` that subscribes, listens, or starts a timer must return a cleanup function. Forgetting cleanup causes memory leaks and stale callbacks.

```tsx
useEffect(() => {
  const controller = new AbortController();
  fetchData(controller.signal).then(setData);
  return () => controller.abort();
}, [url]);
```

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

Inline `style={}` is acceptable for dynamic values (positions, transforms, colors from data). Do not use inline styles for static layout, spacing, or typography.

```tsx
// bad: static layout in inline style
<div style={{ display: "flex", gap: "1rem", padding: "2rem" }}>

// good: class-based
<div class={styles.container}>

// good: inline for dynamic values
<div style={{ transform: `translateX(${offset}px)` }}>
```

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

```tsx
// bad
{items.map((item, i) => <Item key={i} item={item} />)}

// good
{items.map((item) => <Item key={item.id} item={item} />)}
```

### Images

Use `loading="lazy"` for below-the-fold images. Provide `width` and `height` attributes to prevent layout shift.

## Testing

Follow `testing.md` for test discovery and execution rules. When starting a new project, prefer Vitest for unit tests with `@testing-library/preact` (not `@testing-library/react`) and Playwright for E2E. Test user behavior, not implementation details.

```tsx
// bad: testing implementation
expect(component.state.count).toBe(1);

// good: testing behavior
await user.click(screen.getByRole("button", { name: "Increment" }));
expect(screen.getByText("Count: 1")).toBeInTheDocument();
```

Prefer `getByRole`, `getByLabelText`, `getByText` over `getByTestId`. Test IDs are a last resort.
