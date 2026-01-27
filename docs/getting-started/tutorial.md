# Tutorial

This tutorial covers requirements traceability workflows for regulated software projects. We use a Patient Monitoring System (Class B medical device software per IEC 62304) as our example.

## Prerequisites

- Python 3.10+
- Git (for version-controlled requirements)
- Basic understanding of requirements traceability

Install jamb:

```bash
pip install jamb
```

## Getting Started

### Initialize a New Project

```bash
mkdir my-project && cd my-project
git init
jamb init
```

This creates:
- `reqs/` folder with PRJ, UN, SYS, SRS, HAZ, and RC documents
- `[tool.jamb]` configuration in pyproject.toml (if exists)

### Basic Commands

```bash
# Add items
jamb item add UN
jamb item add SYS
jamb item add SRS

# Create links
jamb link add SYS001 UN001
jamb link add SRS001 SYS001

# Edit content
jamb item edit SRS001

# View structure
jamb doc list
jamb item list
```

### Link Tests to Requirements

```python
import pytest

@pytest.mark.requirement("SRS001")
def test_something():
    assert True
```

### Check Coverage

```bash
jamb check
pytest --jamb --jamb-matrix matrix.html
```

### Configuration

Add to `pyproject.toml`:

```toml
[tool.jamb]
test_documents = ["SRS", "SYS"]
fail_uncovered = false
matrix_output = "matrix.html"
matrix_format = "html"
```

## What You'll Learn

- Review cycles when requirements change
- Publishing documentation for regulatory submissions
- Batch operations for importing requirements from stakeholders
- CI/CD enforcement of traceability

## Key Concept: Git-Linked Documents

jamb documents are stored as plain text files in your git repository. This means:

- **Version control**: Every change to a requirement is a git commit with full history
- **Collaboration**: Teams can work on requirements using standard git workflows (branches, pull requests, code review)
- **Audit trail**: Git history provides the evidence auditors need for requirement evolution
- **Traceability**: The "suspect link" system uses git to detect when upstream requirements have changed since you last reviewed downstream items

When you run `jamb item add` or `jamb item edit`, you're creating or modifying files that should be committed to git like any other source file. This design makes requirements a first-class part of your codebase rather than documents stored in external tools.

## Part 1: Project Overview

### The Patient Monitoring System

This example project implements a patient vital signs monitoring system with two document hierarchies:

**Project Root:**
- **1 Project Requirement (PRJ001)**: Top-level system definition

**User Needs Hierarchy:**
- **5 User Needs (UN001-UN005)**: High-level user requirements → link to PRJ
- **8 System Requirements (SYS001-SYS008)**: System behavior specifications → link to UN
- **15 Software Requirements (SRS001-SRS015)**: Detailed software specifications → link to SYS

**Risk Management Hierarchy:**
- **2 Hazards (HAZ001-HAZ002)**: Identified hazardous situations → link to PRJ
- **2 Risk Controls (RC001-RC002)**: Mitigations for identified hazards → link to HAZ

Both hierarchies share the same project root (PRJ), allowing a unified hierarchy.

**Cross-linking:** Some SRS items also link to RC items, demonstrating that a software requirement can trace to both its functional parent (SYS) and a risk control (RC). This shows jamb's support for multi-parent traceability.

### Exploring the Hierarchy

View the document structure:

```bash
cd tutorial
jamb doc list
```

Output:
```
Found 6 documents:
  PRJ: 1 active items (parent: (root))
  UN: 5 active items (parent: PRJ)
  SYS: 8 active items (parent: UN)
  SRS: 15 active items (parent: SYS)
  HAZ: 2 active items (parent: PRJ)
  RC: 2 active items (parent: HAZ)

Hierarchy:
`-- PRJ
    |-- UN
    |   `-- SYS
    |       `-- SRS
    `-- HAZ
        `-- RC
```

List all requirements:

```bash
jamb item list
```

Inspect a single requirement:

```bash
jamb item show SRS001
```

Verify all links are valid:

```bash
jamb info
```

## Part 2: Batch Import Requirements

When requirements come from external stakeholders (product managers, clinical experts), you can import them in batch rather than creating them one by one.

### Examining the Import File

Look at `sample-import.yml`:

```yaml
# Sample requirements for import demonstration
documents: []  # Use existing documents

items:
  # Additional user need (links to project root)
  - uid: UN006
    text: |
      User shall be able to configure personal alert preferences
      for different vital sign types.
    header: Alert Preferences
    links: [PRJ001]

  # Additional system requirement
  - uid: SYS009
    text: |
      System shall allow users to customize alert thresholds
      per vital sign type within clinically safe ranges.
    header: Customizable Thresholds
    links: [UN006]

  # Additional software requirements
  - uid: SRS016
    text: |
      Software shall store user alert preferences in the database
      with per-vital-sign threshold configurations.
    header: Preference Storage
    links: [SYS009]

  - uid: SRS017
    text: |
      Software shall validate custom thresholds against
      clinically safe minimum and maximum bounds.
    header: Threshold Validation
    links: [SYS009]

  # Additional hazard (links to project root)
  - uid: HAZ003
    text: |
      Custom alert thresholds outside safe ranges could mask
      critical patient conditions.
    header: Unsafe Custom Thresholds
    links: [PRJ001]

  # Additional risk control
  - uid: RC003
    text: |
      System shall enforce clinically validated minimum and maximum
      bounds on all user-configurable thresholds.
    header: Threshold Bounds Enforcement
    links: [HAZ003]
```

### Preview the Import

Always preview before importing:

```bash
jamb import sample-import.yml --dry-run
```

Output:
```
DRY RUN - No changes will be made

Would create items:
  UN006: Alert Preferences
  SYS009: Customizable Thresholds
  SRS016: Preference Storage
  SRS017: Threshold Validation
  HAZ003: Unsafe Custom Thresholds
  RC003: Threshold Bounds Enforcement

Would create links:
  UN006 -> PRJ001
  SYS009 -> UN006
  SRS016 -> SYS009
  SRS017 -> SYS009
  HAZ003 -> PRJ001
  RC003 -> HAZ003

6 items and 6 links would be created
```

### Execute the Import

```bash
jamb import sample-import.yml -v
```

### Updating Existing Items

By default, import skips items that already exist. To update existing items, use the `--update` flag:

```bash
jamb import sample-import.yml --update
```

When updating:
- Text, header, and links are replaced with values from the import file
- Fields not in the import file (like `active`) are preserved
- The `reviewed` status is cleared, marking the item as needing re-review

Preview updates before applying:

```bash
jamb import sample-import.yml --update --dry-run
```

### Verify the Import

```bash
jamb item list
jamb info
```

You should now have 39 items (1 PRJ + 6 UN + 9 SYS + 17 SRS + 3 HAZ + 3 RC).

## Part 3: The Review Cycle

When requirements change, downstream items become "suspect" and need review.

### Making a Change

Edit a system requirement:

```bash
jamb item edit SYS001
```

Change the text (for example, add "multi-factor" to authentication):

```yaml
text: |
  System shall authenticate users with username, password, and multi-factor authentication.
```

### Checking for Suspect Links

After editing, run validation:

```bash
jamb validate
```

Output shows suspect links:
```
WARNING: SRS001 has suspect links: SYS001
WARNING: SRS002 has suspect links: SYS001
WARNING: SRS003 has suspect links: SYS001
```

The SRS items that trace to SYS001 are now suspect because their parent changed.

### Understanding the Impact

Trace which items are affected:

```bash
jamb item show SYS001
```

The `links` field shows upstream, and you can find downstream items by searching for items that link to SYS001.

### Clearing Suspect Status

After reviewing that the downstream items are still valid, you need to do two things: mark the items as reviewed (updates the reviewed hash) and clear the suspect links (updates the link hashes).

```bash
# Mark items as reviewed and clear their suspect links
jamb review mark SRS001
jamb review clear SRS001

jamb review mark SRS002
jamb review clear SRS002

jamb review mark SRS003
jamb review clear SRS003

# Or do it for an entire document at once
jamb review mark SRS
jamb review clear SRS

# Or all documents
jamb review mark all
jamb review clear all
```

You can also clear suspect links to a specific parent only:

```bash
jamb review clear SRS001 SYS001
```

Verify clean state:

```bash
jamb validate
```

## Part 4: Publishing for Regulatory Submission

Regulators need to see your requirements documentation. jamb provides multiple output formats.

### Generate HTML Documentation

Export all documents as HTML:

```bash
mkdir -p docs
jamb publish all ./docs --html
```

This creates:
- `docs/PRJ.html`
- `docs/UN.html`
- `docs/SYS.html`
- `docs/SRS.html`
- `docs/HAZ.html`
- `docs/RC.html`

### Generate Markdown for GitHub

For GitHub-friendly documentation:

```bash
jamb publish SRS ./docs/srs.md --markdown
```

### Print to Terminal

Quick review without creating files:

```bash
jamb publish UN
```

### Generate Traceability Matrix

The matrix shows requirements linked to their tests:

```bash
pytest tests/ --jamb --jamb-matrix ./docs/matrix.html
```

For different formats:

```bash
# JSON for tooling integration
pytest tests/ --jamb --jamb-matrix matrix.json --jamb-matrix-format json

# Markdown for GitHub
pytest tests/ --jamb --jamb-matrix matrix.md --jamb-matrix-format markdown
```

### What Auditors Want to See

1. **Complete traceability**: Every SRS traces to SYS, every SYS to UN; every RC traces to HAZ
2. **Risk traceability**: Software requirements implementing risk controls link to both SYS and RC
3. **Test coverage**: Every testable requirement has at least one test
4. **Review evidence**: No suspect links (all changes reviewed)
5. **Version history**: Git commits showing requirement evolution

## Part 5: Export for External Review

### Exporting Requirements

Export all requirements for stakeholder review:

```bash
mkdir -p review
jamb export ./review/all-requirements.yml
```

Export specific documents:

```bash
jamb export ./review/srs-only.yml --documents SRS
```

### Round-trip Workflow

1. **Export**: `jamb export requirements.yml`
2. **Send to stakeholders**: Email the YAML file
3. **Receive feedback**: Stakeholders edit the YAML
4. **Import changes**: `jamb import requirements.yml`

Import skips existing items and adds new ones, making it safe for incremental updates.

## Part 6: CI/CD Integration

### GitHub Actions Workflow

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
        run: pytest --jamb --jamb-fail-uncovered --jamb-matrix matrix.html

      - name: Upload traceability matrix
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: traceability-matrix
          path: matrix.html
```

### Key CI Commands

| Command | Purpose |
|---------|---------|
| `jamb validate` | Validate requirements tree (links, suspect items) |
| `jamb info` | Display document structure and hierarchy |
| `jamb check` | Check test coverage without running tests |
| `pytest --jamb --jamb-fail-uncovered` | Fail if requirements lack tests |

### Pre-commit Validation

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

## Part 7: Advanced Validation

### Detailed Tree Inspection

```bash
jamb validate -v
```

Shows the full document tree with status for each item.

### Specific Document Coverage

Check coverage for specific documents:

```bash
jamb check --documents SRS,SYS
```

### Understanding Coverage Reports

The coverage report shows:

- **Covered**: Requirements with at least one linked test
- **Uncovered**: Requirements without tests (potential gaps)
- **Passing**: Covered requirements where all tests pass
- **Failing**: Covered requirements where at least one test fails

## Troubleshooting

### Suspect Links After Changes

**Problem**: `jamb validate` shows suspect link warnings.

**Solution**: Review the changed requirement and its downstream items, then mark as reviewed and clear the suspect links:

```bash
jamb review mark <UID>
jamb review clear <UID>
```

### Missing Test Coverage

**Problem**: `jamb check` shows uncovered requirements.

**Solution**: Add tests with the `@pytest.mark.requirement` marker:

```python
@pytest.mark.requirement("SRS001")
def test_something():
    ...
```

## Part 8: Test Records in the Traceability Matrix

The traceability matrix captures structured test record data aligned with IEC 62304 §5.7.5, which is valuable for:
- Documenting what actions a test performed and what results were expected
- Showing failure details when tests fail
- Providing evidence for auditors about test execution

The `jamb_log` fixture provides three methods for structured test records:

| Method | Column | Purpose |
|--------|--------|---------|
| `jamb_log.test_action(...)` | Test Actions | What the test does (steps performed) |
| `jamb_log.expected_result(...)` | Expected Results | What should happen (acceptance criteria) |
| `jamb_log.note(...)` | Notes | Free-form observations, context, or commentary |

### Test Actions and Expected Results

Use `test_action()` and `expected_result()` to document the steps and acceptance criteria of a test. These map directly to the "Test Actions" and "Expected Results" columns in the traceability matrix:

```python
import pytest

@pytest.mark.requirement("SRS005")
def test_heart_rate_boundaries(jamb_log):
    """Test heart rate validation at boundary values."""
    jamb_log.test_action("Submit heart rate at lower boundary (30 BPM)")
    jamb_log.expected_result("Value is accepted as valid")
    assert validate_heart_rate(30) is True

    jamb_log.test_action("Submit heart rate at upper boundary (250 BPM)")
    jamb_log.expected_result("Value is accepted as valid")
    assert validate_heart_rate(250) is True

    jamb_log.test_action("Submit heart rate below minimum (29 BPM)")
    jamb_log.expected_result("Value is rejected as invalid")
    assert validate_heart_rate(29) is False
```

### Notes

Use `note()` for free-form observations that don't fit the action/result structure:

```python
@pytest.mark.requirement("SRS012")
def test_data_encryption(jamb_log):
    """Verify patient data encryption meets HIPAA requirements."""
    jamb_log.note("Using PHI sample data set #3")
    jamb_log.note("AES-256 encryption algorithm configured")

    jamb_log.test_action("Encrypt patient data")
    jamb_log.expected_result("Output is not plaintext readable")

    encrypted = encrypt_patient_data(sample_phi)
    assert is_encrypted(encrypted)
    assert sample_phi not in encrypted
```

### Generating the Matrix

When you generate the traceability matrix, all three fields appear in their own columns:

```bash
pytest tests/ --jamb --jamb-matrix matrix.html
```

The HTML matrix will show:
- Test name with pass/fail status
- Test Actions column with the steps performed
- Expected Results column with the acceptance criteria
- Notes column with free-form observations
- Failure messages (automatically captured) if the test fails

### Automatic Failure Capture

When a test fails, jamb automatically captures the failure message and includes it in the Notes column. This helps auditors understand why a test failed without needing to re-run it:

```python
@pytest.mark.requirement("SRS007")
def test_alert_threshold():
    # If this fails, the assertion message is captured
    assert current_threshold == expected, f"Threshold {current_threshold} != {expected}"
```

The matrix will show `[FAILURE] AssertionError: Threshold 95 != 100` in the Notes column.

### Test Records in Different Output Formats

Test actions, expected results, and notes appear in all matrix output formats:

| Format | How They Appear |
|--------|-----------------|
| HTML | Separate columns with styled divs; notes are color-coded for failures |
| JSON | `"test_actions"`, `"expected_results"`, and `"notes"` arrays per linked test |
| CSV | Semicolon-separated in "Test Actions", "Expected Results", and "Notes" columns |
| XLSX | Newline-separated in dedicated columns with text wrap |
| Markdown | Semicolon-separated in dedicated columns |

### When to Use Each Method

**`test_action()`** — what the test does:
- "Enter username and password"
- "Click submit button"
- "Send POST request to /api/login"

**`expected_result()`** — what should happen:
- "Login succeeds and session token is returned"
- "Error message is displayed"
- "Response status is 401 Unauthorized"

**`note()`** — additional context:
- "Using test data set #3"
- "Server configured with TLS 1.3"
- "Boundary value selected per risk analysis RA-005"

**Example for regulatory evidence:**

```python
@pytest.mark.requirement("SRS001")
def test_credential_validation(jamb_log):
    """Verify credential validation per SRS001."""
    jamb_log.test_action("Submit valid credentials (nurse1 / secure123)")
    jamb_log.expected_result("Authentication returns True")
    assert validate_credentials("nurse1", "secure123") is True

    jamb_log.test_action("Submit invalid password (nurse1 / wrong)")
    jamb_log.expected_result("Authentication returns False")
    assert validate_credentials("nurse1", "wrong") is False

    jamb_log.note("Verified both positive and negative authentication paths")
```

This provides auditors with structured evidence of what was tested, what was expected, and any additional observations.

### Import Conflicts

**Problem**: Import skips existing items.

**Solution**: Use `--update` to modify existing items:

```bash
jamb import requirements.yml --update
```

This updates text, header, and links while preserving other fields. The `reviewed` status is cleared to trigger re-review.

### Invalid Requirement References

**Problem**: Tests reference requirements that don't exist.

**Solution**: Run `jamb info` to check document structure, then verify the UID in your test matches an actual requirement.

## Summary

### Complete Workflow

1. **Develop**: Add/edit requirements with `jamb item add` and `jamb item edit`
2. **Link**: Connect requirements with `jamb link add`
3. **Validate**: Check structure with `jamb info` and `jamb validate`
4. **Test**: Run `pytest --jamb` to verify coverage
5. **Review**: Mark items reviewed with `jamb review mark` and clear suspect links with `jamb review clear`
6. **Publish**: Generate documentation with `jamb publish`

### Key Commands Reference

| Task | Command |
|------|---------|
| List documents | `jamb doc list` |
| List items | `jamb item list` |
| Show item | `jamb item show UID` |
| Add item | `jamb item add PREFIX` |
| Edit item | `jamb item edit UID` |
| Add link | `jamb link add CHILD PARENT` |
| Validate | `jamb validate` |
| Document info | `jamb info` |
| Check coverage | `jamb check` |
| Review item | `jamb review mark UID` |
| Clear suspect links | `jamb review clear UID` |
| Publish HTML | `jamb publish all ./docs --html` |
| Import batch | `jamb import file.yml` |
| Export | `jamb export file.yml` |

### CI/CD Checklist

- [ ] `jamb validate` passes (no suspect links)
- [ ] `jamb check` shows no uncovered requirements
- [ ] `pytest --jamb --jamb-fail-uncovered` passes
- [ ] Traceability matrix uploaded as artifact

## Derived Requirements for Risk Controls

Risk-driven SRS items that only implement risk controls (RC) and don't trace to a system requirement (SYS) should be marked as `derived: true`:

```yaml
# SRS item that only implements a risk control
active: true
derived: true  # No SYS parent needed
header: Input Validation
links:
- RC001  # Links to risk control only
text: |
  Software shall validate all input against buffer overflow attacks.
```

This tells jamb the requirement is intentionally not linked to the parent document (SYS) because it emerges from risk analysis rather than user needs.

**When to use `derived: true`:**
- Requirements that emerge from risk/hazard analysis
- Security hardening requirements
- Defensive coding requirements
- Any requirement that doesn't trace to a user need but implements a risk control
