## 2025-01-30 - Keyboard Accessibility for Div-based Interactions
**Learning:** Found critical navigation elements (tool cards) implemented as `div`s with `onclick` but missing semantic roles and keyboard support. This completely blocked keyboard-only users.
**Action:** Systematically audit `onclick` handlers on non-button elements and ensure they have `role="button"`, `tabindex="0"`, and `keydown` listeners for Enter/Space.
