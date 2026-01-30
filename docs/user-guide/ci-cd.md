# CI/CD Integration

## GitHub Actions Workflow

Create `.github/workflows/traceability.yml`:

```yaml
name: Requirements Traceability

on: [push, pull_request]

jobs:
  traceability:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: pip install jamb pytest

      - name: Validate requirements
        run: jamb validate

      - name: Check requirement coverage
        run: jamb check

      - name: Run tests with traceability
        run: pytest --jamb --jamb-fail-uncovered --jamb-trace-matrix matrix.html

      - name: Upload traceability matrix
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: traceability-matrix
          path: matrix.html
```

## Key CI Commands

| Command | Purpose | Fails On |
|---------|---------|----------|
| `jamb validate` | Check requirements tree integrity | Broken links, cycles, conformance violations (suspect links are warnings; use `--error-all` to treat as errors) |
| `jamb check` | Static test coverage scan | Uncovered requirements in test documents |
| `pytest --jamb --jamb-fail-uncovered` | Run tests with coverage enforcement | Uncovered requirements or test failures |

> **Note:** `jamb validate` exits with a non-zero status only when errors are found. Suspect links and conformance issues are reported as warnings by default and do not cause a non-zero exit. To treat warnings as errors, use `jamb validate --error-all`.

## Pre-commit Hook

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: jamb-validate
        name: Validate requirements
        entry: jamb validate
        language: system
        pass_filenames: false
```

This runs `jamb validate` on every commit to catch broken links and suspect items early.

## Recommended Pipeline

A typical CI pipeline for a regulated project:

1. **Validate** -- `jamb validate` ensures the requirements tree is structurally sound
2. **Test** -- `pytest --jamb --jamb-fail-uncovered` runs tests and checks coverage
3. **Matrix** -- `--jamb-trace-matrix matrix.html` generates the traceability matrix artifact
4. **Publish** -- (optional) `jamb publish all ./docs --html` generates requirement documents

### Strict Mode

For maximum enforcement, use `jamb validate --error-all` to treat all warnings (including suspect links) as errors:

```yaml
- name: Strict validation
  run: jamb validate --error-all
```

### Skipping Documents

If certain documents are not yet ready for CI enforcement:

```yaml
- name: Validate (skip UT)
  run: jamb validate --skip UT
```
