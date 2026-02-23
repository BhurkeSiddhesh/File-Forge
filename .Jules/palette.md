## 2026-02-04 - SPA Focus Management
**Learning:** In Single Page Applications (SPAs) built with vanilla JS, changing "pages" (visibility toggles) does not move keyboard focus, leaving screen reader users lost in the previous container or body.
**Action:** Always programmatically move focus to the new container (with `tabindex="-1"`) or the main heading immediately after a route transition completes.
