## 2026-01-31 - Retrofitting Accessibility
**Learning:** This app relies heavily on `div` elements with `onclick` handlers, which is a common pattern but inaccessible.
**Action:** Instead of rewriting every component to `<button>`, a cost-effective retrofit is adding `role="button"`, `tabindex="0"`, and a single global delegate listener for `Enter`/`Space` keys. This instantly makes the entire UI keyboard-friendly with minimal code churn (< 20 lines of JS).

## 2026-02-05 - Click-to-Add for Drag & Drop
**Learning:** Drag & Drop interfaces are inherently inaccessible to keyboard users. A simple "Click-to-Add" handler on the draggable elements provides an immediate, low-cost accessible alternative without changing the visual design.
**Action:** Whenever implementing DnD, always bind a click/enter handler to the source element to perform the "drop" action programmatically.
