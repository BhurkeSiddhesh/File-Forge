## 2026-02-03 - Drag-and-Drop Accessibility
**Learning:** Drag-and-drop interfaces are inherently inaccessible to keyboard-only users.
**Action:** Always implement a click-to-add alternative for draggable items. Ensure these items have `role="button"`, `tabindex="0"`, and explicit keyboard event handlers (or rely on a robust global handler). Visual feedback (animations) is critical to confirm the "add" action when it happens instantly via click.
