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
| `--jamb-trace-to-ignore PREFIX` | Exclude document prefix from trace matrix (repeatable) |

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

# Exclude specific documents from trace matrix
pytest --jamb --jamb-matrix matrix.html \
    --jamb-trace-to-ignore PRJ \
    --jamb-trace-to-ignore HAZ
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

| Feature | `jamb check` (static) | `pytest --jamb` (runtime) | `jamb matrix` (post-run) |
|---------|----------------------|--------------------------|--------------------------|
| Runs tests | No | Yes | No |
| Detects `@pytest.mark.requirement` | Yes | Yes | Uses saved data |
| Reports pass/fail status | No | Yes | Uses saved data |
| Captures `jamb_log` output | No | Yes | Uses saved data |
| Generates traceability matrix | No | Yes (with `--jamb-matrix`) | Yes |
| Generates test records matrix | No | No | Yes (with `--test-records`) |
| Speed | Fast | Depends on test suite | Fast |

Use `jamb check` for quick feedback during development. Use `pytest --jamb` in CI for full traceability evidence. Use `jamb matrix` to regenerate matrices from saved coverage data without re-running tests.

## Matrix Output Formats

The traceability matrix can be generated in several formats:

| Format | Flag | Best For |
|--------|------|----------|
| HTML | `--jamb-matrix-format html` | Regulatory submissions, standalone viewing |
| Markdown | `--jamb-matrix-format markdown` | GitHub/GitLab rendering |
| JSON | `--jamb-matrix-format json` | Tooling integration, programmatic access |
| CSV | `--jamb-matrix-format csv` | Spreadsheet import, large datasets |
| XLSX | `--jamb-matrix-format xlsx` | Excel, stakeholder review |

**Performance Note:** When generating HTML or XLSX matrices with more than 5,000 rows, jamb emits a warning recommending CSV format for better performance and memory usage.

### Format Details

#### Matrix Metadata

When using `--jamb-tester-id` and `--jamb-software-version`, the matrix includes a metadata header section with:

- **Software Version**: The version being tested (from CLI flag, `[tool.jamb].software_version`, or `[project].version`)
- **Tester**: Who ran the tests (from `--jamb-tester-id`)
- **Date**: When the tests were executed (ISO 8601 UTC timestamp)
- **Environment**: Test environment details (OS, Python version, platform, processor, hostname, CPU count)
- **Test Tools**: Versions of all pytest plugins used (pytest, jamb, pytest-cov, etc.)

This metadata satisfies IEC 62304 Clause 5.7.5 requirements for software system test records.

#### Test Records Matrix Example

The test records matrix is test-centric, showing one row per test:

| Test Case | Test Name | Outcome | Requirements | Test Actions | Expected Results | Actual Results | Notes | Timestamp |
|-----------|-----------|---------|--------------|--------------|------------------|----------------|-------|-----------|
| TC001 | test_credential_validation | passed | SRS001 | Submit valid credentials | Authentication returns True | auth_user() returned True | Verified both auth paths | 2024-01-15T10:30:00Z |
| TC002 | test_account_lockout | failed | SRS002 | Submit 3 invalid passwords | Account is locked | account.locked = False | [FAILURE] AssertionError | 2024-01-15T10:30:05Z |
| TC003 | test_heart_rate_boundaries | passed | SRS005 | Submit heart rate at boundary | Value is accepted | validate_heart_rate(30) returned True | Boundary values per RA-005 | 2024-01-15T10:30:10Z |

#### Trace Matrix Example

The trace matrix is requirement-centric, showing the full traceability chain from a starting document through the hierarchy:

| Traces To | UN | SYS | SRS | Tests | Status |
|-----------|----|-----|-----|-------|--------|
| - | UN001: User Authentication | SYS001: Authentication System | SRS001: The system shall authenticate users | TC001: test_credential_validation [passed] | Passed |
| - | UN001: User Authentication | SYS001: Authentication System | SRS002: The system shall lock accounts | TC002: test_account_lockout [failed] | Failed |
| - | UN002: Heart Rate Monitoring | SYS002: Vital Signs Display | SRS003: Display heart rate in real-time | - | Not Covered |
| - | UN003: Documentation | SYS003: User Manual | SRS099: User manual shall be provided | - | N/A |

**Status Values**:
- **Passed** (green): All linked tests passed
- **Failed** (red): One or more linked tests failed
- **Partial** (orange): Mix of passed and failed tests
- **Skipped** (amber): All linked tests were skipped (none passed, none failed)
- **Not Covered** (yellow): No tests linked to this requirement
- **N/A** (gray): Requirement marked as `testable: false` (verified by other means)

**HTML** -- Standalone document with inline CSS. Includes summary statistics banner, styled tables, and color-coded status. Test records matrix shows test actions, expected/actual results, and notes in separate columns. Trace matrix shows document hierarchy columns with bold UIDs and full requirement text.

**Markdown** -- Pipe-delimited table with summary section. Test records show one row per test with semicolon-separated actions/results. Trace matrix shows document hierarchy with combined UID and text.

**JSON** -- Structured data with arrays of test records or trace chain objects. Test records include `test_actions`, `expected_results`, `actual_results`, and `notes` arrays. Trace matrix includes nested chain objects per document level. Suitable for custom tooling.

**CSV** -- Standard comma-separated values with summary rows at the top. Test records show one row per test. Trace matrix shows document hierarchy as separate columns. Recommended for large datasets (5,000+ rows).

**XLSX** -- Excel workbook with summary rows, text wrapping, and color-coded status cells. Test records and trace matrices are formatted with appropriate column widths and styling.

## Matrix Columns

### Test Records Matrix Columns

| Column | Description |
|--------|-------------|
| Test Case | Sequential test ID (TC001, TC002, etc.) |
| Test Name | pytest function name |
| Outcome | Test result: passed, failed, skipped, or error |
| Requirements | Item UIDs covered by this test |
| Test Actions | Steps performed (from `jamb_log.test_action()`) |
| Expected Results | Acceptance criteria (from `jamb_log.expected_result()`) |
| Actual Results | Observed outcomes (from `jamb_log.actual_result()`) |
| Notes | Observations and failure messages (from `jamb_log.note()`) |
| Timestamp | ISO 8601 UTC timestamp of test execution |

### Trace Matrix Columns

| Column | Description |
|--------|-------------|
| Traces To | Ancestor UIDs (optional, enabled with `--include-ancestors`) |
| [Document Columns] | One column per document in hierarchy (e.g., UN, SYS, SRS), showing UID and requirement text |
| Tests | pytest tests linked to leaf items, with TC IDs and outcomes |
| Status | Passed, Failed, Not Covered, Partial, or N/A |
