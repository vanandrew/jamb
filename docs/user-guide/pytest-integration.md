# pytest Integration

jamb integrates with pytest to link tests to requirements and generate traceability matrices.

## Marking Tests

Use `@pytest.mark.requirement` to link a test to one or more requirements:

```python
import pytest

@pytest.mark.requirement("SRS001")
def test_single_requirement():
    assert True

@pytest.mark.requirement("SRS001", "SRS002")
def test_multiple_requirements():
    assert True
```

The marker accepts any number of item UIDs as positional arguments.

## pytest Command-Line Options

| Option | Description |
|--------|-------------|
| `--jamb` | Enable traceability checking |
| `--jamb-matrix PATH` | Output traceability matrix to PATH |
| `--jamb-matrix-format FORMAT` | Set matrix format (`html`, `markdown`, `json`, `csv`, `xlsx`) |
| `--jamb-fail-uncovered` | Fail if any test spec items lack coverage |
| `--jamb-documents PREFIXES` | Comma-separated document prefixes to check |

### Examples

```bash
# Enable traceability checking
pytest --jamb

# Generate HTML matrix
pytest --jamb --jamb-matrix matrix.html

# Generate markdown matrix
pytest --jamb --jamb-matrix matrix.md --jamb-matrix-format markdown

# Fail if requirements lack coverage
pytest --jamb --jamb-fail-uncovered

# Check specific documents only
pytest --jamb --jamb-documents SRS
```

## The `jamb_log` Fixture

The `jamb_log` fixture provides structured test record logging aligned with IEC 62304 §5.7.5. Use it to document test actions, expected results, and notes that appear in the traceability matrix.

### Methods

| Method | Matrix Column | Purpose |
|--------|--------------|---------|
| `jamb_log.test_action(text)` | Test Actions | What the test does (steps performed) |
| `jamb_log.expected_result(text)` | Expected Results | What should happen (acceptance criteria) |
| `jamb_log.note(text)` | Notes | Free-form observations or context |

### Example

```python
import pytest

@pytest.mark.requirement("SRS005")
def test_heart_rate_boundaries(jamb_log):
    """Test heart rate validation at boundary values."""
    jamb_log.test_action("Submit heart rate at lower boundary (30 BPM)")
    jamb_log.expected_result("Value is accepted as valid")
    assert validate_heart_rate(30) is True

    jamb_log.test_action("Submit heart rate below minimum (29 BPM)")
    jamb_log.expected_result("Value is rejected as invalid")
    assert validate_heart_rate(29) is False

    jamb_log.note("Boundary values selected per risk analysis RA-005")
```

### Automatic Failure Capture

When a test fails, jamb automatically captures the failure message and includes it in the Notes column of the matrix. No extra code needed.

## Static vs Runtime Checking

| Feature | `jamb check` (static) | `pytest --jamb` (runtime) |
|---------|----------------------|--------------------------|
| Runs tests | No | Yes |
| Detects `@pytest.mark.requirement` | Yes | Yes |
| Reports pass/fail status | No | Yes |
| Captures `jamb_log` output | No | Yes |
| Generates traceability matrix | No | Yes (with `--jamb-matrix`) |
| Speed | Fast | Depends on test suite |

Use `jamb check` for quick feedback during development. Use `pytest --jamb` in CI for full traceability evidence.

## Matrix Output Formats

The traceability matrix can be generated in several formats:

| Format | Flag | Best For |
|--------|------|----------|
| HTML | `--jamb-matrix-format html` | Regulatory submissions, standalone viewing |
| Markdown | `--jamb-matrix-format markdown` | GitHub/GitLab rendering |
| JSON | `--jamb-matrix-format json` | Tooling integration, programmatic access |
| CSV | `--jamb-matrix-format csv` | Spreadsheet import |
| XLSX | `--jamb-matrix-format xlsx` | Excel, stakeholder review |

### Format Details

#### Example

| UID | Description | Traces To | Tests | Test Actions | Expected Results | Notes | Status |
|-----|-------------|-----------|-------|--------------|------------------|-------|--------|
| SRS001 | Software shall authenticate users with username and password | SYS001, UN001 | `test_credential_validation` [passed] | Submit valid credentials (nurse1 / secure123); Submit invalid password (nurse1 / wrong) | Authentication returns True; Authentication returns False | Verified both positive and negative authentication paths | Passed |
| SRS002 | Software shall lock account after 3 failed login attempts | SYS001, UN001 | `test_account_lockout` [failed] | Submit 3 invalid passwords | Account is locked | [FAILURE] AssertionError: Account not locked after 3 attempts | Failed |
| SRS003 | Software shall display heart rate in real-time | SYS002, UN002 | - | - | - | - | Not Covered |

**HTML** -- Standalone document with inline CSS. Includes styled tables, color-coded status, and hyperlinked UIDs. Test actions, expected results, and notes appear in separate columns.

**Markdown** -- Pipe-delimited table. Test actions, expected results, and notes are semicolon-separated within their columns.

**JSON** -- Structured data with `test_actions`, `expected_results`, and `notes` arrays per linked test. Suitable for custom tooling.

**CSV** -- Standard comma-separated values. Test actions, expected results, and notes are semicolon-separated within their columns.

**XLSX** -- Excel workbook with text wrapping. Test actions, expected results, and notes are newline-separated within dedicated columns.

## Matrix Columns

The generated matrix includes:

| Column | Description |
|--------|-------------|
| UID | Item identifier (e.g., SRS001) |
| Description | Requirement text |
| Traces To | Parent requirements this item links to |
| Tests | pytest tests linked via `@pytest.mark.requirement` |
| Status | PASSED (green), FAILED (red), or UNCOVERED (yellow) |
| Test Actions | Steps performed (from `jamb_log.test_action()`) |
| Expected Results | Acceptance criteria (from `jamb_log.expected_result()`) |
| Notes | Observations and failure messages (from `jamb_log.note()`) |
