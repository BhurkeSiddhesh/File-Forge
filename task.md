# Task: Check Stitch Integration and Add Design

## Plan
1. [x] **Jules Watchdog Protocol** (Mandatory Pre-Flight)
    - [x] Fetch all branches (`git fetch --all`)
    - [x] Check for `jules/` branches (None found)
    - [x] Update `JULES_LOG.json`
2. [x] **Check Stitch Availability**
    - [x] Call `list_projects` (Failed - Connection Closed)
3. [ ] **Add Design**
    - [ ] **BLOCKED**: Stitch MCP is unavailable.
    - [ ] Waiting for user direction (Standard CSS vs Retry Stitch).
4. [x] **Workflow Visual Progress**
    - [x] **Fix Backend Blocking**: Wrap synchronous PDF/Image tasks in `run_in_threadpool` to unleash SSE stream.
    - [x] **Frontend SSE**: `runWorkflow` consumes `step_start`/`step_complete` events.
    - [x] **Visual Feedback**: Apply `.processing` (pulse) and `.completed` (green) classes dynamically.
    - [x] **Status Text**: Update "Step X of Y" real-time.
