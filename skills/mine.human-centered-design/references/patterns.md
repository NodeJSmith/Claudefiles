# Human-Centered Design Patterns

Code-level patterns for building inclusive, accessible interfaces. All examples use HTML, CSS, HTMX, and Alpine.js.

---

## Semantic HTML

Semantic elements provide structure, accessibility, and meaning — for free.

### Good Structure

```html
<body>
  <header>
    <nav aria-label="Main">
      <a href="/">Home</a>
      <a href="/reports" aria-current="page">Reports</a>
    </nav>
  </header>

  <main>
    <h1>Monthly Reports</h1>

    <article>
      <h2>January Summary</h2>
      <p>Revenue increased 12% over December.</p>
      <time datetime="2025-02-01">February 1, 2025</time>
    </article>

    <aside aria-label="Quick stats">
      <p>Total: $42,000</p>
    </aside>
  </main>

  <footer>
    <p>&copy; 2025 Acme Corp</p>
  </footer>
</body>
```

### Bad: Div Soup

```html
<!-- No landmarks, no semantics, invisible to assistive tech -->
<div class="header">
  <div class="nav">
    <div class="link active">Reports</div>
  </div>
</div>
<div class="content">
  <div class="title">Monthly Reports</div>
</div>
```

### Native Disclosure

```html
<!-- Works without JS. Accessible by default. -->
<details>
  <summary>Advanced options</summary>
  <fieldset>
    <legend>Notification preferences</legend>
    <label><input type="checkbox" name="email"> Email</label>
    <label><input type="checkbox" name="sms"> SMS</label>
  </fieldset>
</details>
```

---

## ARIA Patterns

Use ARIA only when semantic HTML isn't enough. The first rule of ARIA: don't use ARIA if a native element works.

### Live Regions

```html
<!-- Announce dynamic content to screen readers -->
<div aria-live="polite" aria-atomic="true" id="status">
  <!-- HTMX or Alpine injects status messages here -->
</div>

<!-- For urgent announcements (errors, alerts) -->
<div role="alert" id="error-banner">
  <!-- Only populate when there's an actual error -->
</div>
```

### Described By

```html
<label for="password">Password</label>
<input type="password" id="password"
       aria-describedby="password-help password-error"
       aria-invalid="false">
<p id="password-help">At least 8 characters, one number.</p>
<p id="password-error" role="alert" hidden></p>
```

### Expanded State

```html
<button aria-expanded="false" aria-controls="menu-panel"
        x-data="{ open: false }"
        :aria-expanded="open"
        @click="open = !open">
  Menu
</button>
<div id="menu-panel" x-show="open" x-transition role="region">
  <!-- menu content -->
</div>
```

### Focus Trap for Modals

```html
<!-- Alpine x-trap keeps focus inside the modal -->
<div x-data="{ showModal: false }">
  <button @click="showModal = true">Open settings</button>

  <div x-show="showModal" x-trap.noscroll="showModal"
       role="dialog" aria-modal="true" aria-label="Settings"
       @keydown.escape.window="showModal = false">
    <h2>Settings</h2>
    <!-- modal content -->
    <button @click="showModal = false">Close</button>
  </div>
</div>
```

---

## Keyboard Navigation

### Skip Link

```html
<!-- First element in body, visible on focus -->
<a href="#main-content" class="skip-link">Skip to main content</a>

<!-- ... header, nav ... -->
<main id="main-content" tabindex="-1">
```

```css
.skip-link {
  position: absolute;
  left: -9999px;
}
.skip-link:focus {
  position: fixed;
  top: 0;
  left: 0;
  z-index: 9999;
  padding: 0.75rem 1.5rem;
  background: var(--surface-emphasis);
  color: var(--text-primary);
}
```

### Focus Visible

```css
/* Only show focus rings for keyboard users */
:focus-visible {
  outline: 2px solid var(--focus-ring);
  outline-offset: 2px;
}

/* Remove default focus for mouse users */
:focus:not(:focus-visible) {
  outline: none;
}
```

### Roving Tabindex

```html
<!-- Tab group: one tab stop, arrow keys navigate within -->
<div role="tablist" x-data="{ active: 0, tabs: ['Overview', 'Details', 'History'] }">
  <template x-for="(tab, i) in tabs" :key="i">
    <button role="tab"
            :tabindex="active === i ? 0 : -1"
            :aria-selected="active === i"
            @click="active = i"
            @keydown.right.prevent="active = (active + 1) % tabs.length"
            @keydown.left.prevent="active = (active - 1 + tabs.length) % tabs.length"
            x-text="tab">
    </button>
  </template>
</div>
```

---

## User Preference Media Queries

### Reduced Motion

```css
/* Default: no animation */
.toast { opacity: 1; }

/* Enhance only when motion is acceptable */
@media (prefers-reduced-motion: no-preference) {
  .toast {
    animation: slide-in 200ms ease-out;
  }
}

@keyframes slide-in {
  from { transform: translateY(-1rem); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}
```

### Color Scheme

```css
:root {
  color-scheme: light dark;

  --surface: #ffffff;
  --text: #1a1a2e;
  --border: rgba(0, 0, 0, 0.12);
}

@media (prefers-color-scheme: dark) {
  :root {
    --surface: #1a1a2e;
    --text: #e0e0e0;
    --border: rgba(255, 255, 255, 0.12);
  }
}
```

### High Contrast

```css
@media (prefers-contrast: more) {
  :root {
    --border: 2px solid #000;
    --text-secondary: #333;  /* stronger than normal secondary */
  }
}

/* Windows high-contrast mode */
@media (forced-colors: active) {
  .btn {
    border: 1px solid ButtonText;
    forced-color-adjust: none;  /* only when you need custom styling */
  }
}
```

### Layering Queries

```css
/* Combine: dark mode + high contrast */
@media (prefers-color-scheme: dark) and (prefers-contrast: more) {
  :root {
    --surface: #000;
    --text: #fff;
    --border: 2px solid #fff;
  }
}
```

---

## Error Prevention & Recovery

### Inline Validation on Blur

```html
<!-- Validate when the user leaves the field, not while typing -->
<form x-data="{ email: '', emailError: '' }">
  <label for="email">Email</label>
  <input type="email" id="email" name="email"
         x-model="email"
         :aria-invalid="emailError !== ''"
         aria-describedby="email-error"
         @blur="emailError = email && !email.includes('@') ? 'Enter a valid email address.' : ''">
  <p id="email-error" role="alert" x-text="emailError" x-show="emailError"></p>
</form>
```

### Forgiving Inputs

```html
<!-- Accept multiple formats, normalize server-side -->
<label for="phone">Phone number</label>
<input type="tel" id="phone" name="phone"
       inputmode="tel"
       placeholder="(555) 123-4567"
       aria-describedby="phone-help">
<p id="phone-help">Any format works — we'll figure it out.</p>
```

### Undo Pattern (Toast + Soft Delete)

```html
<!-- Instead of "Are you sure?" — let them undo -->
<div x-data="{ deleted: null, timer: null }" aria-live="polite">
  <template x-if="deleted">
    <div class="toast" role="status">
      <span x-text="`${deleted.name} deleted.`"></span>
      <button @click="
        clearTimeout(timer);
        /* restore the item */
        deleted = null;
      ">Undo</button>
    </div>
  </template>
</div>
```

### Unsaved Changes Guard

```html
<form x-data="{ dirty: false }"
      @input="dirty = true"
      @submit="dirty = false"
      x-effect="
        if (dirty) {
          window.onbeforeunload = () => true;
        } else {
          window.onbeforeunload = null;
        }
      ">
  <!-- form fields -->
</form>
```

---

## Feedback & System Status

### HTMX Loading Indicators

```html
<!-- Show spinner during HTMX request -->
<button hx-post="/api/save" hx-target="#result"
        hx-indicator="#save-spinner"
        hx-disabled-elt="this">
  Save
</button>
<span id="save-spinner" class="htmx-indicator" role="status">
  <span class="spinner" aria-hidden="true"></span>
  Saving...
</span>
```

```css
.htmx-indicator { display: none; }
.htmx-request .htmx-indicator,
.htmx-request.htmx-indicator { display: inline-flex; }
```

### Alpine Loading State

```html
<div x-data="{ loading: false }">
  <button @click="loading = true; $dispatch('submit')"
          :disabled="loading"
          :aria-busy="loading">
    <span x-show="!loading">Submit</span>
    <span x-show="loading" role="status">Submitting...</span>
  </button>
</div>
```

### Live Region Updates

```html
<!-- Announce results to screen readers -->
<div id="search-results" aria-live="polite" aria-atomic="false">
  <!-- HTMX swaps results here -->
</div>

<!-- Announce count separately -->
<p aria-live="polite" role="status" id="result-count">
  <!-- "12 results found" swapped by HTMX -->
</p>
```

### Skeleton Screens

```html
<!-- Show structure while content loads -->
<div class="skeleton-card" aria-hidden="true">
  <div class="skeleton-line" style="width: 60%;"></div>
  <div class="skeleton-line" style="width: 90%;"></div>
  <div class="skeleton-line" style="width: 40%;"></div>
</div>

<!-- Announce to screen readers -->
<p class="sr-only" aria-live="polite" role="status">Loading dashboard data...</p>
```

---

## Cognitive Load Reduction

### Progressive Disclosure

```html
<!-- Reveal complexity only when needed -->
<form method="post" action="/create-event">
  <label for="title">Event title</label>
  <input type="text" id="title" name="title" required>

  <label for="date">Date</label>
  <input type="date" id="date" name="date" required>

  <details>
    <summary>Advanced settings</summary>
    <label for="capacity">Max attendees</label>
    <input type="number" id="capacity" name="capacity">

    <label for="reminder">Reminder (hours before)</label>
    <input type="number" id="reminder" name="reminder" value="24">
  </details>

  <button type="submit">Create event</button>
</form>
```

### Multi-Step Forms

```html
<form x-data="{ step: 1, totalSteps: 3 }">
  <progress :value="step" :max="totalSteps"
            :aria-label="`Step ${step} of ${totalSteps}`"></progress>

  <fieldset x-show="step === 1">
    <legend>Personal info</legend>
    <!-- fields -->
    <button type="button" @click="step++">Next</button>
  </fieldset>

  <fieldset x-show="step === 2">
    <legend>Address</legend>
    <!-- fields -->
    <button type="button" @click="step--">Back</button>
    <button type="button" @click="step++">Next</button>
  </fieldset>

  <fieldset x-show="step === 3">
    <legend>Review & confirm</legend>
    <!-- summary -->
    <button type="button" @click="step--">Back</button>
    <button type="submit">Submit</button>
  </fieldset>
</form>
```

---

## Responsive & Fluid Design

### Mobile-First Grid

```css
.grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
}

@media (min-width: 40rem) {
  .grid { grid-template-columns: repeat(2, 1fr); }
}

@media (min-width: 64rem) {
  .grid { grid-template-columns: repeat(3, 1fr); }
}
```

### Fluid Typography

```css
:root {
  /* Minimum 1rem, scales with viewport, maximum 1.5rem */
  --text-body: clamp(1rem, 0.875rem + 0.5vw, 1.25rem);
  --text-heading: clamp(1.5rem, 1rem + 1.5vw, 2.5rem);
}

body { font-size: var(--text-body); }
h1 { font-size: var(--text-heading); }
```

### Container Queries

```css
.card-container { container-type: inline-size; }

.card { padding: 1rem; }

@container (min-width: 30rem) {
  .card {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 1.5rem;
  }
}
```

### Dynamic Viewport Height

```css
/* Accounts for mobile browser chrome */
.full-screen {
  min-height: 100dvh;
}
```

---

## Forms

### Inclusive Form Pattern

```html
<form method="post" action="/register"
      hx-post="/register" hx-target="#form-result">

  <div class="field">
    <label for="name">Full name <span aria-hidden="true">*</span></label>
    <input type="text" id="name" name="name"
           required autocomplete="name"
           aria-required="true">
  </div>

  <div class="field">
    <label for="email">Email <span aria-hidden="true">*</span></label>
    <input type="email" id="email" name="email"
           required autocomplete="email"
           inputmode="email"
           aria-required="true"
           aria-describedby="email-help">
    <p id="email-help" class="help-text">We'll send a confirmation link.</p>
  </div>

  <div class="field">
    <label for="dob">Date of birth</label>
    <input type="date" id="dob" name="dob"
           autocomplete="bday">
  </div>

  <button type="submit">Register</button>
  <div id="form-result" aria-live="polite"></div>
</form>
```

Key form principles:
- Every `<input>` has a visible `<label>` (not just placeholder)
- `autocomplete` attributes for browser autofill
- `inputmode` for appropriate mobile keyboards
- Required indicators visible and announced
- Help text linked via `aria-describedby`
- Error messages in `aria-live` regions

---

## HTMX-Specific Patterns

### Progressive Enhancement with hx-boost

```html
<!-- Every link and form becomes AJAX — zero JS to write -->
<body hx-boost="true">
  <nav>
    <a href="/dashboard">Dashboard</a>  <!-- AJAX navigation -->
    <a href="/settings">Settings</a>
  </nav>
  <main id="content">
    <!-- page content swapped by hx-boost -->
  </main>
</body>
```

### Confirmation on Destructive Actions

```html
<button hx-delete="/api/items/42"
        hx-target="closest tr"
        hx-swap="outerHTML swap:500ms"
        hx-confirm="Delete this item? This can't be undone.">
  Delete
</button>
```

### Submission Guards

```html
<!-- Prevent double-submission -->
<form hx-post="/api/orders"
      hx-disabled-elt="find button[type='submit']"
      hx-indicator="#order-spinner">
  <!-- fields -->
  <button type="submit">Place order</button>
  <span id="order-spinner" class="htmx-indicator" role="status">
    Processing...
  </span>
</form>
```

### Swap Strategies for Feedback

```html
<!-- Append to a list (don't replace it) -->
<form hx-post="/api/comments" hx-target="#comment-list"
      hx-swap="beforeend" hx-on::after-request="this.reset()">
  <textarea name="body" required></textarea>
  <button type="submit">Add comment</button>
</form>
<ul id="comment-list">
  <!-- existing comments -->
</ul>
```

---

## Alpine.js-Specific Patterns

### Transitions for Feedback

```html
<!-- Smooth reveal communicates state change -->
<div x-data="{ saved: false }">
  <button @click="saved = true; setTimeout(() => saved = false, 3000)">
    Save
  </button>
  <p x-show="saved"
     x-transition:enter="transition ease-out duration-200"
     x-transition:enter-start="opacity-0 transform translate-y-1"
     x-transition:enter-end="opacity-100 transform translate-y-0"
     x-transition:leave="transition ease-in duration-150"
     x-transition:leave-start="opacity-100"
     x-transition:leave-end="opacity-0"
     role="status">
    Saved successfully.
  </p>
</div>
```

### Focus Management with x-trap

```html
<!-- Keep focus inside dropdown when open -->
<div x-data="{ open: false }" @keydown.escape="open = false">
  <button @click="open = !open" :aria-expanded="open">
    Options
  </button>
  <div x-show="open" x-trap="open" x-transition
       role="menu" aria-label="Options">
    <button role="menuitem" @click="/* action */; open = false">Edit</button>
    <button role="menuitem" @click="/* action */; open = false">Duplicate</button>
    <button role="menuitem" @click="/* action */; open = false">Delete</button>
  </div>
</div>
```

### Collapse for Progressive Disclosure

```html
<div x-data="{ expanded: false }">
  <button @click="expanded = !expanded"
          :aria-expanded="expanded"
          aria-controls="extra-info">
    <span x-text="expanded ? 'Show less' : 'Show more'"></span>
  </button>
  <div id="extra-info" x-show="expanded" x-collapse>
    <p>Additional details revealed progressively.</p>
  </div>
</div>
```

### Escape to Dismiss

```html
<!-- Consistent dismissal pattern across all overlays -->
<div x-data="{ open: false }">
  <button @click="open = true">Open panel</button>
  <div x-show="open"
       @keydown.escape.window="open = false"
       @click.outside="open = false"
       x-transition>
    <h2>Side panel</h2>
    <!-- content -->
    <button @click="open = false">Close</button>
  </div>
</div>
```
