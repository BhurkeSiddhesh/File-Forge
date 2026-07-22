```markdown
# File-Forge Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches the core development patterns and conventions used in the File-Forge Python codebase. You'll learn about file naming, import/export styles, commit message habits, and how to approach testing and workflows within this repository. This guide is ideal for contributors aiming for consistency and maintainability in File-Forge.

## Coding Conventions

### File Naming
- **Style:** Use `snake_case` for all file names.
- **Example:**  
  ```
  file_processor.py
  data_utils.py
  ```

### Import Style
- **Style:** Use relative imports within the package.
- **Example:**  
  ```python
  from .utils import parse_file
  from .models import FileModel
  ```

### Export Style
- **Style:** Use named exports (explicitly declare what is exported).
- **Example:**  
  ```python
  __all__ = ['FileProcessor', 'parse_file']
  ```

### Commit Messages
- **Type:** Freeform, no strict prefixes.
- **Average Length:** ~58 characters.
- **Example:**  
  ```
  Add initial file parsing logic for CSV and JSON formats
  ```

## Workflows

### General Development
**Trigger:** When adding new features or fixing bugs  
**Command:** `/develop`

1. Create a new branch for your feature or bugfix.
2. Follow snake_case naming for new files.
3. Use relative imports for any internal modules.
4. Add named exports to `__all__` in modules as needed.
5. Write clear, concise commit messages (no strict prefix required).
6. Push your changes and open a pull request.

### Testing
**Trigger:** When verifying functionality or before merging changes  
**Command:** `/test`

1. Identify or create test files using the `*.test.ts` pattern (note: testing framework is currently unknown).
2. Write or update tests to cover your changes.
3. Run the test suite (refer to project-specific instructions if available).
4. Ensure all tests pass before submitting your pull request.

## Testing Patterns

- **Test File Naming:** Use `*.test.ts` for test files.
- **Testing Framework:** Not specified; check with maintainers or project documentation.
- **Example:**  
  ```
  file_processor.test.ts
  ```
- **Best Practice:** Ensure each feature or module has corresponding tests in the same naming pattern.

## Commands
| Command    | Purpose                                      |
|------------|----------------------------------------------|
| /develop   | Start a new feature or bugfix workflow       |
| /test      | Run or add tests for your changes            |
```
