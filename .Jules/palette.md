## 2026-02-04 - Keyboard Accessibility for Custom Inputs
**Learning:** `display: none` on form inputs removes them from the accessibility tree, making custom toggles/switches unreachable for keyboard users.
**Action:** Use a `.visually-hidden` utility class (opacity: 0, absolute position) to hide the native input while keeping it focusable, and use `:focus-visible` + adjacent sibling selector to style the custom control.
