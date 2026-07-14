# Development Guide

This guide outlines the recommended development workflow to help maintain code quality and reduce issues during pull requests.

## Recommended Workflow

* After **every commit**, ensure that **all tests pass** before pushing your changes.
* Fixing issues immediately is much easier than rewriting commit history or adding follow-up commits just to resolve broken code.
* Always verify your changes locally before opening or updating a pull request.

---

# Running Tests

## Ruff (Linting)

Run Ruff to check for linting issues:

```bash
ruff check
```

> **Important:** Ensure there are **no linting errors or warnings** before creating or updating a pull request, as lint failures can block the merge.

---

## Pytest

### Run the entire test suite

From the project root directory:

```bash
pytest tests/
```

### Run a specific test file

```bash
pytest tests/test_aqi_tools.py
```

For more information about writing, organizing, and running tests, see [Pytest Guide](pytest_guide.md).
