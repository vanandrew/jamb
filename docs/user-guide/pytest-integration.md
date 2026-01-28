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
| `--jamb-tester-id ID` | Tester identification for traceability matrix (default: "Unknown") |
| `--jamb-software-version VERSION` | Software version for traceability matrix (overrides pyproject.toml) |

**Note:** All pytest CLI options override their corresponding `[tool.jamb]` settings in `pyproject.toml`. For example, `--jamb-fail-uncovered` on the command line takes effect even if `fail_uncovered = false` in the config. When no CLI flag is given, the config file value is used.

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

# Generate matrix with IEC 62304 metadata
pytest --jamb --jamb-matrix matrix.html \
    --jamb-tester-id "CI Pipeline" \
    --jamb-software-version "1.2.3"
```

## The `jamb_log` Fixture

The `jamb_log` fixture provides structured test record logging aligned with IEC 62304 §5.7.5. Use it to document test actions, expected results, actual results, and notes that appear in the traceability matrix.

### Methods

| Method | Matrix Column | Purpose |
|--------|--------------|---------|
| `jamb_log.test_action(text)` | Test Actions | What the test does (steps performed) |
| `jamb_log.expected_result(text)` | Expected Results | What should happen (acceptance criteria) |
| `jamb_log.actual_result(text)` | Actual Results | What actually happened (observed outcomes) |
| `jamb_log.note(text)` | Notes | Free-form observations or context |

### Example

```python
import pytest

@pytest.mark.requirement("SRS005")
def test_heart_rate_boundaries(jamb_log):
    """Test heart rate validation at boundary values."""
    jamb_log.test_action("Submit heart rate at lower boundary (30 BPM)")
    jamb_log.expected_result("Value is accepted as valid")
    result = validate_heart_rate(30)
    jamb_log.actual_result(f"validate_heart_rate(30) returned {result}")
    assert result is True

    jamb_log.test_action("Submit heart rate below minimum (29 BPM)")
    jamb_log.expected_result("Value is rejected as invalid")
    result = validate_heart_rate(29)
    jamb_log.actual_result(f"validate_heart_rate(29) returned {result}")
    assert result is False

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

#### Matrix Metadata

When using `--jamb-tester-id` and `--jamb-software-version`, the matrix includes a metadata header section with:

- **Software Version**: The version being tested (from CLI flag, `[tool.jamb].software_version`, or `[project].version`)
- **Tester**: Who ran the tests (from `--jamb-tester-id`)
- **Date**: When the tests were executed (ISO 8601 UTC timestamp)
- **Environment**: Test environment details (OS, Python version, platform, processor, hostname, CPU count)
- **Test Tools**: Versions of all pytest plugins used (pytest, jamb, pytest-cov, etc.)

This metadata satisfies IEC 62304 Clause 5.7.5 requirements for software system test records.

#### Example

| UID | Description | Traces To | Tests | Test Actions | Expected Results | Actual Results | Notes | Status |
|-----|-------------|-----------|-------|--------------|------------------|----------------|-------|--------|
| SRS001 | Software shall authenticate users with username and password | SYS001, UN001 | `test_credential_validation` [passed] | Submit valid credentials | Authentication returns True | auth_user() returned True | Verified both auth paths | Passed |
| SRS002 | Software shall lock account after 3 failed login attempts | SYS001, UN001 | `test_account_lockout` [failed] | Submit 3 invalid passwords | Account is locked | account.locked = False | [FAILURE] AssertionError | Failed |
| SRS003 | Software shall display heart rate in real-time | SYS002, UN002 | - | - | - | - | - | Not Covered |
| SRS099 | User manual shall be provided | SYS003 | - | - | - | - | Verified by inspection | N/A |

**Status Values**:
- **Passed** (green): All linked tests passed
- **Failed** (red): One or more linked tests failed
- **Not Covered** (yellow): No tests linked to this requirement
- **N/A** (gray): Requirement marked as `testable: false` (verified by other means)

**HTML** -- Standalone document with inline CSS. Includes metadata header, styled tables, color-coded status, and hyperlinked UIDs. Test actions, expected results, actual results, and notes appear in separate columns. When multiple tests are linked to a requirement, entries are grouped under test name headers.

**Markdown** -- Pipe-delimited table with metadata section. Test actions, expected results, actual results, and notes are semicolon-separated within their columns. When multiple tests are linked, entries are prefixed with `[test_name]`.

**JSON** -- Structured data with `metadata` object and `test_actions`, `expected_results`, `actual_results`, and `notes` arrays per linked test. Each item includes a `testable` field. Suitable for custom tooling.

**CSV** -- Standard comma-separated values with metadata rows at the top. Test actions, expected results, actual results, and notes are semicolon-separated within their columns. When multiple tests are linked, entries are prefixed with `[test_name]`.

**XLSX** -- Excel workbook with metadata rows, text wrapping, and color-coded status cells. Test actions, expected results, actual results, and notes are newline-separated within dedicated columns. When multiple tests are linked, entries are grouped under `[test_name]` headers.

## Matrix Columns

The generated matrix includes:

| Column | Description |
|--------|-------------|
| UID | Item identifier (e.g., SRS001) |
| Description | Requirement text |
| Traces To | Parent requirements this item links to |
| Tests | pytest tests linked via `@pytest.mark.requirement` |
| Test Actions | Steps performed (from `jamb_log.test_action()`) |
| Expected Results | Acceptance criteria (from `jamb_log.expected_result()`) |
| Actual Results | Observed outcomes (from `jamb_log.actual_result()`) |
| Notes | Observations and failure messages (from `jamb_log.note()`) |
| Status | Passed, Failed, Not Covered, or N/A |
