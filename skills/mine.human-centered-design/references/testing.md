# Accessibility Testing & Validation

How to verify that human-centered design decisions survive implementation.

---

## Automated Tools

| Tool | What it catches | Integration |
|------|----------------|-------------|
| **axe-core** | WCAG violations, ARIA misuse, color contrast | Playwright, Cypress, browser extension |
| **Lighthouse** | Accessibility audit + performance + best practices | Chrome DevTools, CI via `lighthouse-ci` |
| **pa11y** | WCAG 2.1 AA/AAA compliance | CLI, CI pipeline, dashboard mode |
| **HTML validator** | Invalid nesting, missing attributes, broken semantics | W3C validator, `html-validate` in CI |

Start with axe-core in CI — it catches the most with the least setup.

---

## axe-core in Playwright

```javascript
// tests/a11y.spec.js
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('accessibility', () => {
  test('home page has no a11y violations', async ({ page }) => {
    await page.goto('/');

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
      .analyze();

    expect(results.violations).toEqual([]);
  });

  test('form page has no a11y violations', async ({ page }) => {
    await page.goto('/register');

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .exclude('.third-party-widget')  // exclude what you can't control
      .analyze();

    expect(results.violations).toEqual([]);
  });

  test('dark mode has no contrast violations', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'dark' });
    await page.goto('/');

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2aa'])
      .analyze();

    expect(results.violations).toEqual([]);
  });
});
```

Run on every PR. A single violation fails the build.

---

## Manual Testing Checklist

Automated tools catch ~30-40% of accessibility issues. The rest requires a human.

### Keyboard-Only Walkthrough

- [ ] Tab through the entire page — can you reach every interactive element?
- [ ] Is focus order logical (follows visual order)?
- [ ] Are focus indicators visible on every focused element?
- [ ] Can you open/close all menus, modals, and dropdowns with keyboard?
- [ ] Does Escape dismiss overlays and return focus to the trigger?
- [ ] Can you submit forms with Enter?
- [ ] Are there any keyboard traps (focus stuck, can't leave)?

### Screen Reader Test

Use NVDA (Windows) or VoiceOver (macOS). Test these:

- [ ] Page has a meaningful `<title>`
- [ ] Headings form a logical hierarchy (`h1` > `h2` > `h3`)
- [ ] Images have descriptive `alt` text (or `alt=""` for decorative)
- [ ] Form inputs have associated labels
- [ ] Dynamic updates announced via `aria-live` regions
- [ ] Buttons and links have clear, unique names
- [ ] Tables have headers (`<th>`) and captions

### Zoom & Reflow

- [ ] Content readable at 200% zoom (no horizontal scrollbar)
- [ ] Content usable at 400% zoom (may reflow to single column)
- [ ] Text doesn't get clipped or overlap at any zoom level
- [ ] Touch targets remain large enough when zoomed

### Contrast & Color

- [ ] Text meets 4.5:1 contrast ratio (3:1 for large text)
- [ ] UI components meet 3:1 contrast against background
- [ ] No information conveyed by color alone
- [ ] Interface usable in Windows High Contrast mode

### Cognitive Walkthrough

- [ ] Can a first-time user complete the primary task without help?
- [ ] Are error messages actionable ("Enter a valid email" not "Error 422")?
- [ ] Is required vs optional clearly indicated?
- [ ] Are destructive actions clearly labeled and confirmed?
- [ ] Does the interface use plain language (no jargon)?

---

## Continuous Monitoring

### Core Web Vitals

| Metric | Target | What it measures |
|--------|--------|-----------------|
| **LCP** | < 2.5s | Largest Contentful Paint — perceived load speed |
| **INP** | < 200ms | Interaction to Next Paint — responsiveness |
| **CLS** | < 0.1 | Cumulative Layout Shift — visual stability |

### Regression Prevention

- Run axe-core tests in CI on every PR
- Add Lighthouse CI with score thresholds (accessibility >= 90)
- Monitor CLS in production — layout shifts harm everyone but especially assistive tech users
- Track error rates on forms — rising errors often signal an accessibility regression

### When to Re-Test Manually

- New page or major feature added
- Navigation structure changed
- Form flow modified
- Third-party widget integrated
- CSS framework or design system updated
