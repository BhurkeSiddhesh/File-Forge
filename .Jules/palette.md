## 2026-01-31 - Retrofitting Accessibility
**Learning:** This app relies heavily on `div` elements with `onclick` handlers, which is a common pattern but inaccessible.
**Action:** Instead of rewriting every component to `<button>`, a cost-effective retrofit is adding `role="button"`, `tabindex="0"`, and a single global delegate listener for `Enter`/`Space` keys. This instantly makes the entire UI keyboard-friendly with minimal code churn (< 20 lines of JS).
