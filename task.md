# Task: Implement Modern Web UI for File Forge

The user wants a premium-looking web interface for File Forge with a main menu for file types and a drill-down page for PDF actions.

## Steps
- [x] Initialize FastAPI backend
    - [x] Install `fastapi` and `uvicorn`
    - [x] Create `main.py` to serve the API and static files
    - [x] Refactor `pdf_password_remover.py` functionality into a reusable module/function
- [x] Create Modern Frontend
    - [x] Design and implement `index.html` with a grid layout for file types (PDF, DOC, etc.)
    - [x] Implement `style.css` with premium aesthetics (dark mode, glassmorphism, transitions)
    - [x] Create the "Drill-down" view for PDF actions
    - [x] Implement JavaScript logic for navigation and API calls
- [x] Implement File Handling Workflow
    - [x] Create an `outputs` folder if it doesn't exist
    - [x] Implement file upload and processing logic
    - [x] Save processed files to the `outputs` directory
- [x] Verification
    - [x] VERIFY: Run the FastAPI server and navigate the UI
    - [x] VERIFY: Upload a protected PDF and remove its password through the UI
    - [x] VERIFY: Check if the file is correctly saved in the `outputs` folder
- [x] Update `AGENTS.md` and Change Log
