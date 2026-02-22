# UX Anti-Pattern Detection Heuristics

## 1. Layout Stability

### 1.1 Elements that shift after render

Content injected after initial paint displaces interactive elements. User aims for one button, clicks another.

**Detect:** Images/media without explicit dimensions. Containers depending on async content with no `min-height` or skeleton. Late-injected DOM nodes (cookie banners, chat widgets) in content flow instead of fixed/sticky with reserved space.

**Fix:** Reserve space for every async element before it loads — explicit dimensions, `aspect-ratio`, skeletons, or `min-height`.

### 1.2 Click targets that shift on hover/focus

**Detect:** Hover/focus rules using `padding`, `margin`, `font-size`, `width`, `height`, or `border-width` changes.

**Fix:** Declare layout-affecting properties on the base selector too, or use layout-neutral properties (`transform`, `box-shadow`, `outline`, `opacity`, `background`, `color`).

```css
/* Bad: no base border, added on hover — shifts by 2px */
.btn:hover { border: 2px solid blue; }

/* Fix: transparent border on base */
.btn { border: 2px solid transparent; }
.btn:hover { border-color: blue; }
```

---

## 2. Feedback & Responsiveness

### 2.1 No immediate feedback on action

**Detect:** Submit/action handlers with no loading/pending state. Async operations that don't immediately update UI. Missing `:active` styles.

**Fix:** Every async action should immediately produce a visual state change before the operation completes.

### 2.2 Optimistic UI that silently reverts

**Detect:** Optimistic state updates lacking error/rollback handlers. Rollback logic with no user-visible notification.

**Fix:** If rolling back, show an explicit notification explaining what happened and offer retry.

### 2.3 Long operations with no progress indication

**Detect:** Operations >5s with only a spinner or "Loading..." — no percentage, step count, or status message.

**Fix:** Show determinate progress for >5s operations. If unavailable, show updating status messages ("Preparing...", "Processing...", "Almost done...").

---

## 3. Error Handling & Recovery

### 3.1 Error messages without recovery guidance

**Detect:** Static error strings with no context. Raw HTTP codes or exception names shown to user. Error UI with no actionable element.

**Fix:** Every error: (1) what failed in user language, (2) why if known, (3) what to do about it.

### 3.2 Disabled controls with no explanation

**Detect:** `disabled` attribute with no adjacent hint, tooltip, or explanatory text.

**Fix:** Explain the precondition for enabling it, or keep enabled and validate on interaction.

```html
<!-- Bad -->
<button disabled>Submit</button>

<!-- Fix -->
<button disabled aria-describedby="hint">Submit</button>
<p id="hint">Complete all required fields to submit.</p>
```

### 3.3 Errors that block unrelated work

**Detect:** No per-section error containment (error boundaries, isolated try/catch per module).

**Fix:** Contain failures to the affected region. Rest of UI stays functional.

---

## 4. Forms & Input Interference

### 4.1 Paste blocked

**Detect:** `paste` event listeners calling `preventDefault()`. `onpaste="return false"`. `user-select: none` on inputs.

**Fix:** Never block paste. Validate input instead.

### 4.2 Required fields not marked until submission

**Detect:** Required inputs without visual indicators before interaction. Required state only via form-level validation errors.

**Fix:** Mark required fields from the start with visual indicators and `aria-required`.

### 4.3 Autocorrect/autofill interference

**Detect:** Password/code/token inputs missing `autocorrect="off"`, `autocapitalize="off"`, appropriate `inputmode` and `autocomplete`.

**Fix:** Set correct `type`, `inputmode`, `autocomplete`, `autocorrect`, `autocapitalize` for every input.

### 4.4 Hostile formatters

**Detect:** Input handlers replacing entire value on each keystroke without tracking/restoring cursor position.

**Fix:** Manage caret position after reformatting, or format on blur instead of on keystroke.

### 4.5 Custom inputs breaking standard editing

**Detect:** Custom components with `onKeyDown` + `preventDefault()` blocking standard editing shortcuts (select all, arrow keys, undo/redo).

**Fix:** Custom inputs must support all standard editing interactions for their platform.

### 4.6 Multi-step forms losing data on back

**Detect:** Step-based forms where each step unmounts previous state. Wizard state only in component-local state. No `beforeunload` guard.

**Fix:** Persist form state across steps (session storage, URL params, global state). Warn before navigation that discards data.

---

## 5. Focus

### 5.1 Focus stealing

**Detect:** `autofocus` or `.focus()` calls firing after initial page load (async events, timers, state changes). Live-search re-renders grabbing focus.

**Fix:** Never move focus while user is interacting elsewhere. Safe times: initial page/modal load, or direct response to user's own action.

---

## 6. Notifications, Interruptions & Dialogs

### 6.1 Repeated notifications

**Detect:** Notification dispatch with no deduplication or throttle.

**Fix:** Deduplicate identical notifications. Batch similar ones ("3 new messages" not 3 toasts).

### 6.2 Overlays obscuring content

**Detect:** Fixed/sticky elements overlapping scrollable content, especially on mobile. No minimize/collapse option.

**Fix:** Floating elements must not obscure primary content. Provide minimize or responsive repositioning.

### 6.3 Modals not dismissible with standard gestures

**Detect:** No `Escape` key handler. No backdrop click handler. Missing/obscured close button.

**Fix:** Support: (1) visible close button, (2) Escape key, (3) click outside to dismiss. Exception: critical destructive confirmations may omit Escape/click-outside.

### 6.4 Destructive actions with no confirmation

**Detect:** Delete/remove/clear handlers executing immediately with no confirmation and no undo.

**Fix:** At least one safety net: confirmation dialog naming consequences, OR undo window. High-stakes: use both.

---

## 7. Navigation & State Persistence

### 7.1 Redirects losing original target

**Detect:** Auth redirects not storing/restoring the original URL. No `returnUrl` or equivalent.

**Fix:** Persist original URL through redirect chain and navigate there after auth.

### 7.2 State not reflected in URL

**Detect:** Filters, search, sort, pagination in component state only — not synced to URL params.

**Fix:** Meaningful UI state (anything worth sharing, bookmarking, or recovering on refresh) belongs in the URL.

---

## 8. Scroll & Viewport

### 8.1 No scroll position recovery

**Detect:** Infinite scroll without position caching. List->detail->back losing scroll offset.

**Fix:** Cache scroll position and loaded data. Restore both on back-navigation.

### 8.2 Sticky elements consuming excessive viewport

**Detect:** Multiple fixed/sticky elements stacking. Combined height >15-20% of mobile viewport.

**Fix:** Minimize fixed elements. Auto-hide on scroll-down. Cookie banners and notifications should be dismissible and stay dismissed.

### 8.3 Horizontal overflow on mobile

**Detect:** Fixed widths > mobile viewport. Tables/code without `overflow-x: auto` wrappers. Missing viewport meta tag.

**Fix:** All content fits viewport at smallest breakpoint. Wrap overflow-prone content in scrollable containers.

### 8.4 Gesture conflicts

**Detect:** Touch handlers for swipe without considering pull-to-refresh, edge-swipe, or overscroll. Missing `overscroll-behavior`.

**Fix:** `overscroll-behavior: contain` for containers. Inset touch targets from screen edges. Use velocity/direction thresholds.

---

## 9. Timing & Race Conditions

### 9.1 Duplicate submission

**Detect:** Submit handlers with no guard against rapid re-invocation. Buttons staying enabled during async processing.

**Fix:** Disable on first click, re-enable on completion/error. Server-side idempotency for critical operations.

### 9.2 Stale response overwriting newer intent

**Detect:** Async operations from user input without AbortController, request sequencing, or version checking.

**Fix:** Cancel/ignore stale requests. Verify response matches current input before applying.

```js
// Bad: stale result can overwrite
async function search(query) {
  setResults(await (await fetch(`/search?q=${query}`)).json());
}

// Fix: abort previous
let controller;
async function search(query) {
  controller?.abort();
  controller = new AbortController();
  const res = await fetch(`/search?q=${query}`, { signal: controller.signal });
  setResults(await res.json());
}
```

### 9.3 Session expiry during active use

**Detect:** Session timeout triggering hard redirect with no state preservation. 401/403 responses without client-side handling.

**Fix:** (1) Warn before expiry. (2) Attempt silent token refresh. (3) Preserve in-progress state before redirecting. (4) Restore state after re-auth.

---

## 10. Accessibility as UX

### 10.1 Focus indicators removed

**Detect:** `outline: none` on `:focus` without replacement.

**Fix:** Use `:focus-visible` for keyboard-only focus rings. Never remove globally.

```css
:focus:not(:focus-visible) { outline: none; }
:focus-visible { outline: 2px solid var(--focus-color); outline-offset: 2px; }
```

### 10.2 Hover-only information

**Detect:** Content/controls shown only in `:hover` with no `:focus`/`:focus-within` equivalent.

**Fix:** Anything accessible on hover must also work on focus (keyboard) and tap/long-press (touch).

### 10.3 Touch targets too small

**Detect:** Interactive elements < 44x44px. Adjacent targets with < 8px gap.

**Fix:** Meet minimum touch target sizes. Expand hit areas with padding if visual element must be small.

### 10.4 Color as sole indicator

**Detect:** Status indicators relying only on color. Form validation only changing border color.

**Fix:** Supplement color with icon, text label, pattern, or weight change.

### 10.5 Contrast failures

**Detect:** Text below WCAG AA thresholds (4.5:1 normal, 3:1 large). Unreadable placeholders. Indistinguishable disabled states.

**Fix:** Meet WCAG AA. Disabled states need multiple visual cues, not just slight dimming.

### 10.6 Keyboard traps

**Detect:** Custom focus-traps that don't release on Escape. Widgets intercepting Tab with no escape.

**Fix:** All focus traps escapable. Follow WAI-ARIA patterns for keyboard interaction.

---

## 11. Visual Layering

### 11.1 Z-index chaos

**Detect:** Arbitrary escalating z-index (999, 9999, 99999). Elements clipped by parent `overflow: hidden`. No z-index scale.

**Fix:** Define named z-index layers. Render overlays via portal to escape parent clipping.

```css
:root {
  --z-dropdown: 100;
  --z-sticky: 200;
  --z-overlay: 300;
  --z-modal: 400;
  --z-toast: 500;
}
```

---

## 12. Mobile & Viewport-Specific

### 12.1 Virtual keyboard covers input

**Detect:** Input fields in lower viewport half with no keyboard handling. Fixed elements overlapping keyboard area.

**Fix:** Use `visualViewport` API. Ensure focused inputs scroll into view. Adjust fixed elements.

### 12.2 `100vh` jitter

**Detect:** `100vh` for full-screen layouts on mobile.

**Fix:** Use `100dvh`, `100svh`, or JS-based viewport detection.

---

## 13. Cumulative Decay

### 13.1 Updates resetting preferences

**Detect:** Update/migration code overwriting preferences. Default init not checking for saved values.

**Fix:** Never overwrite user preferences on update. Merge defaults under saved values.

### 13.2 Cache/storage bloat

**Detect:** Caching with no TTL, eviction, or size limit.

**Fix:** TTL-based cache with max entries. Monitor storage usage.

### 13.3 Stale feature flags

**Detect:** Flags enabled/disabled for all users but still in code. Conditional rendering with no documented experiment.

**Fix:** Clean up flags when experiments conclude.
