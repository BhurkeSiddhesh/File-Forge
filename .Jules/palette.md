## 2026-01-31 - Interactive Divs Accessibility Pattern
**Learning:** The application heavily relies on `div` elements for interactive components (Cards, Drop Zones) without semantic HTML or ARIA roles, making them inaccessible to keyboard users.
**Action:** When creating custom interactive components that cannot use native `<button>` or `<a>` tags, strictly enforce the pattern: `role="button"`, `tabindex="0"`, and explicit keyboard event listeners (Enter/Space) in JS. Always pair with `:focus-visible` styles.
