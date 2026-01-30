# Tutorial

This tutorial covers requirements traceability workflows for regulated software projects. We use a Patient Monitoring System (Class B medical device software per IEC 62304) as our example.

## Prerequisites

You'll need Python 3.10+, Git (for version-controlled requirements), and a basic understanding of requirements traceability.

Install jamb:

```bash
pip install jamb
```

:::{tip}
A complete example project is available in the [`tutorial/`](https://github.com/vanandrew/jamb/tree/main/tutorial) directory of the GitHub repository. Clone it to follow along:
```bash
git clone https://github.com/vanandrew/jamb.git
cd jamb/tutorial
```
:::

## Getting Started

### Initialize a New Project

jamb uses git as its storage backend, so every project starts as a git repository. The `jamb init` command scaffolds the standard IEC 62304 document hierarchy — a set of directories and config files that define how requirements trace from high-level user needs down to testable software specifications.

```bash
mkdir my-project && cd my-project
git init
jamb init
```

This creates a `reqs/` folder with PRJ, UN, SYS, SRS, HAZ, and RC documents, along with a `[tool.jamb]` configuration section in pyproject.toml (if the file exists).

### Basic Commands

The core workflow is: create items (individual requirements) within documents, then link child items to parent items to build the traceability chain. Links always point upward — an SRS item links to the SYS item it implements, and a SYS item links to the UN item it satisfies. This upward linking is how jamb records that every low-level requirement traces back to a user need.

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

The final link in the traceability chain connects tests to requirements. The `@pytest.mark.requirement` marker tells jamb which requirement a test verifies. When pytest runs with `--jamb`, it collects these markers and records pass/fail results per requirement — closing the loop from user need to verified implementation.

```python
import pytest

@pytest.mark.requirement("SRS001")
def test_something():
    assert True
```

### Check Coverage

There are two ways to verify coverage. `jamb check` is static — it scans test files for requirement markers without running tests. `pytest --jamb` is runtime — it executes tests and records outcomes. In CI, you typically use both: `jamb check` for fast feedback and `pytest --jamb` for the full traceability matrix.

```bash
jamb check
pytest --jamb --jamb-trace-matrix matrix.html
```

### Configuration

The `test_documents` setting tells jamb which documents require test coverage (usually the leaf documents like SRS). Setting `fail_uncovered` to true makes CI fail if any requirement lacks a test. The matrix options control where the matrices are written.

Add to `pyproject.toml`:

```toml
[tool.jamb]
test_documents = ["SRS", "SYS"]
fail_uncovered = false
trace_matrix_output = "traceability.html"
test_matrix_output = "test-records.html"
```

> **Tip:** When `trace_matrix_output` or `test_matrix_output` is set in `[tool.jamb]`, the matrices are automatically generated at the specified paths on each `pytest --jamb` run, without needing to pass `--jamb-trace-matrix` or `--jamb-test-matrix` on the command line. This is useful for ensuring the matrices are always up to date.

## What You'll Learn

The rest of this tutorial walks through the full lifecycle of a regulated project: handling review cycles when requirements change, publishing documentation for regulatory submissions, batch-importing requirements from stakeholders, and enforcing traceability in CI/CD pipelines.

## Key Concept: Git-Linked Documents

jamb documents are stored as plain text files in your git repository. Every change to a requirement is a git commit with full history, so teams can collaborate on requirements using standard git workflows — branches, pull requests, and code review. Git history provides the audit trail that regulators need to see how requirements evolved, and the "suspect link" system uses content hashing to detect when upstream requirements have changed since downstream items were last reviewed.

When you run `jamb item add` or `jamb item edit`, you're creating or modifying files that should be committed to git like any other source file. This design makes requirements a first-class part of your codebase rather than documents stored in external tools.

## Part 1: Project Overview

### The Patient Monitoring System

This example project implements a patient vital signs monitoring system with two document hierarchies. The following breakdown shows each document type and its item count:

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
  PRJ: 1 active items (parents: (root))
  UN: 5 active items (parents: PRJ)
  SYS: 8 active items (parents: UN)
  SRS: 15 active items (parents: SYS, RC)
  HAZ: 2 active items (parents: PRJ)
  RC: 2 active items (parents: HAZ)

Hierarchy:
`-- PRJ
    |-- UN (parents: PRJ)
    |   `-- SYS (parents: UN)
    |       `-- SRS (parents: SYS, RC)
    `-- HAZ (parents: PRJ)
        `-- RC (parents: HAZ)
            `-- SRS (parents: SYS, RC)
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

In regulated workflows, requirements often originate in Word documents, spreadsheets, or design review meetings. Rather than manually creating each item via `jamb item add`, you can author them in a single YAML file and import the batch. This is especially useful at project kickoff or when incorporating feedback from clinical experts who don't use the CLI.

### Examining the Import File

The import file has a `documents` section (for creating new document types, left empty here since we're using existing ones) and an `items` section where each entry specifies a UID, text, header, and links. The `links` field establishes traceability — each item points to its parent, just like items created via the CLI.

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

In a regulated project, unintended changes to the requirements baseline can trigger review cycles and audit findings. The `--dry-run` flag shows exactly what will be created without modifying any files, so you can verify the import before committing to it.

Always preview before importing:

```bash
jamb import sample-import.yml --dry-run
```

Output:
```
Dry run - no changes will be made:
  Would create item: UN006 (links: PRJ001)
  Would create item: SYS009 (links: UN006)
  Would create item: SRS016 (links: SYS009)
  Would create item: SRS017 (links: SYS009)
  Would create item: HAZ003 (links: PRJ001)
  Would create item: RC003 (links: HAZ003)

Would create 6 items
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

When updating, text, header, and links are replaced with values from the import file, while fields not in the import file (like `active`) are preserved. The `reviewed` status is cleared, marking the item as needing re-review.

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

IEC 62304 requires change impact analysis — when a requirement changes, you must assess whether downstream artifacts (more detailed requirements, tests) are still valid. jamb automates the detection side: it stores a content hash in each link, and when the parent item's content changes, the hash no longer matches, flagging the link as "suspect." This section walks through the full cycle: making a change, seeing the suspect flags, reviewing the impact, and clearing the flags.

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

`jamb validate` compares the stored link hashes against the current content of each parent item. Any mismatch means the parent changed after the link was last reviewed. The output tells you exactly which child items need attention and which parent triggered the suspect flag.

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

In practice, you'd read the changed requirement to understand what was modified, then check each suspect downstream item to decide whether it needs updating. In a real project, this review might involve the original author, a domain expert, or a formal review meeting — the tooling flags the items, but the engineering judgment is yours.

Trace which items are affected:

```bash
jamb item show SYS001
```

The `links` field shows upstream, and you can find downstream items by searching for items that link to SYS001.

### Clearing Suspect Status

Clearing suspect status is a two-step process. `jamb review mark` records that you've reviewed the item's *content* (updating the reviewed hash), and `jamb review clear` records that you've reviewed the item's *links* to its parents (updating the link hashes). Both steps are needed because a change might affect either the item itself or its relationship to its parent. Once both hashes are current, `jamb validate` will report a clean state.

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

A regulatory submission package typically includes human-readable requirement documents for each specification level, a traceability matrix showing the chain from user needs through software requirements to test results, and evidence that all changes have been reviewed. jamb's publish and matrix commands generate these artifacts directly from your requirements data, so the documentation stays in sync with the source of truth.

### Generate HTML Documentation

Export all documents as a single combined HTML file:

```bash
jamb publish all ./docs/requirements.html --html
```

This creates a single `docs/requirements.html` file containing all documents.

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

The traceability matrix is the central audit artifact — it shows every requirement, its parent chain, the tests that verify it, and whether those tests passed. Auditors use this to confirm that every requirement is implemented and verified. The matrix is generated from a live test run, so it reflects the actual state of the codebase.

```bash
pytest tests/ --jamb --jamb-trace-matrix ./docs/matrix.html
```

For different formats (inferred from file extension):

```bash
# JSON for tooling integration
pytest tests/ --jamb --jamb-trace-matrix matrix.json

# Markdown for GitHub
pytest tests/ --jamb --jamb-trace-matrix matrix.md
```

For IEC 62304 compliant test records, include tester and version metadata:

```bash
pytest tests/ --jamb --jamb-trace-matrix matrix.html \
    --jamb-tester-id "QA Team" \
    --jamb-software-version "1.0.0"
```

For example, a markdown matrix renders as:

#### Metadata

- **Software Version:** 1.0.0
- **Tester:** QA Team
- **Date:** 2026-01-28T14:30:00Z
- **Environment:** Darwin 25.2.0, Python 3.12.0, arm64, arm, dev-machine, 10 cores
- **Test Tools:** jamb 1.2.0, pytest 8.0.0, pytest-cov 4.1.0

#### Coverage Details

| UID | Description | Traces To | Tests | Test Actions | Expected Results | Actual Results | Notes | Status |
|-----|-------------|-----------|-------|--------------|------------------|----------------|-------|--------|
| SRS001 | Software shall authenticate users | SYS001, UN001 | `test_credential_validation` [passed] | Submit valid credentials | Auth returns True | auth() returned True | Verified auth paths | Passed |
| SRS002 | Software shall lock account after 3 failed attempts | SYS001, UN001 | `test_account_lockout` [failed] | Submit 3 invalid passwords | Account is locked | account.locked = False | [FAILURE] AssertionError | Failed |
| SRS003 | Software shall display heart rate in real-time | SYS002, UN002 | - | - | - | - | - | Not Covered |
| SRS099 | User manual shall be provided | SYS003 | - | - | - | - | Verified by inspection | N/A |

### What Auditors Want to See

Auditors look for a complete traceability chain — every SRS traces to SYS, every SYS to UN, and every RC traces to HAZ — with software requirements that implement risk controls linking to both SYS and RC. They expect every testable requirement to have at least one linked test, no suspect links (demonstrating that all changes have been reviewed), and git commit history showing how requirements evolved over time.

The traceability matrix and test records are one component of the evidence package auditors review. You will also need design documentation, risk management files (ISO 14971), software development plans, and other lifecycle artifacts that jamb does not generate.

## Part 5: Export for External Review

`jamb export` serializes your requirements into a portable YAML file that stakeholders can review outside the repository. This supports a round-trip workflow: export your current requirements, send them to a clinical expert or product manager for review, receive the edited YAML back, and import the changes. Because the import command handles conflicts safely (skipping existing items by default), this workflow supports incremental collaboration.

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

This workflow bridges the gap between engineering teams working in git and domain experts working in documents. The YAML format is simple enough for non-developers to read and edit, and the import/export cycle keeps the requirements repository as the single source of truth.

1. **Export**: `jamb export requirements.yml`
2. **Send to stakeholders**: Email the YAML file
3. **Receive feedback**: Stakeholders edit the YAML
4. **Import changes**: `jamb import requirements.yml`

Import skips existing items and adds new ones, making it safe for incremental updates.

## Part 6: CI/CD Integration

Automated pipelines should enforce traceability on every commit by validating the requirements tree, checking test coverage, and generating the traceability matrix as a build artifact. This catches broken links, missing coverage, and unreviewed changes before they reach the main branch — preventing audit findings from accumulating.

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
        run: pytest --jamb --jamb-fail-uncovered --jamb-trace-matrix matrix.html

      - name: Upload traceability matrix
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: traceability-matrix
          path: matrix.html
```

In this workflow, `jamb validate` checks the structural integrity of the requirements tree (links, cycles, suspect items). `jamb check` verifies that every requirement in the configured test documents has at least one linked test. `pytest --jamb --jamb-fail-uncovered` runs the actual tests and fails if any requirement lacks coverage. Finally, the artifact upload preserves the matrix for review.

### Key CI Commands

| Command | Purpose |
|---------|---------|
| `jamb validate` | Validate requirements tree (links, suspect items) |
| `jamb info` | Display document structure and hierarchy |
| `jamb check` | Check test coverage without running tests |
| `pytest --jamb --jamb-fail-uncovered` | Fail if requirements lack tests |

### Pre-commit Validation

Pre-commit hooks catch validation errors before they even enter a commit, giving developers immediate feedback when they break a link or leave an item unreviewed.

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

`jamb validate` runs a suite of independent checks covering structural integrity, content correctness, and completeness. By default all checks run, but verbose mode (`-v`) includes info-level issues in addition to warnings and errors, giving you more detail about the validation results.

### Detailed Tree Inspection

```bash
jamb validate -v
```

Shows all validation issues including info-level details.

### Specific Document Coverage

Check coverage for specific documents:

```bash
jamb check --documents SRS,SYS
```

### Understanding Coverage Reports

The coverage report summarizes how well your test suite covers the requirements. In a regulatory context, uncovered requirements are gaps that auditors will flag, and failing requirements indicate verification issues that must be resolved before release.

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

The traceability matrix captures structured test record data aligned with IEC 62304 §5.7.5. This is valuable for documenting what actions a test performed and what results were expected, showing failure details when tests fail, and providing evidence for auditors about test execution.

The `jamb_log` fixture provides four methods for structured test records:

| Method | Column | Purpose |
|--------|--------|---------|
| `jamb_log.test_action(...)` | Test Actions | What the test does (steps performed) |
| `jamb_log.expected_result(...)` | Expected Results | What should happen (acceptance criteria) |
| `jamb_log.actual_result(...)` | Actual Results | What actually happened (observed behavior) |
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

When you generate the traceability matrix, all four fields appear in their own columns:

```bash
pytest tests/ --jamb --jamb-trace-matrix matrix.html
```

The HTML matrix will show each test's name with its pass/fail status, a Test Actions column listing the steps performed, an Expected Results column with the acceptance criteria, an Actual Results column with observed behavior, a Notes column with free-form observations, and automatically captured failure messages if the test fails.

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

Test actions, expected results, actual results, and notes appear in all matrix output formats:

| Format | How They Appear |
|--------|-----------------|
| HTML | Separate columns with styled divs; notes are color-coded for failures |
| JSON | `"test_actions"`, `"expected_results"`, `"actual_results"`, and `"notes"` arrays per linked test |
| CSV | Semicolon-separated in "Test Actions", "Expected Results", "Actual Results", and "Notes" columns |
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

**`actual_result()`** — what actually happened:
- "auth() returned True"
- "Response status was 200 OK"
- "Threshold value was 95"

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
| Publish HTML | `jamb publish all ./docs/requirements.html --html` |
| Import batch | `jamb import file.yml` |
| Export | `jamb export file.yml` |

### CI/CD Checklist

- [ ] `jamb validate` passes (no suspect links)
- [ ] `jamb check` shows no uncovered requirements
- [ ] `pytest --jamb --jamb-fail-uncovered` passes
- [ ] Traceability matrix uploaded as artifact

## Derived Requirements

Items that don't link to any parent, should be marked as `derived: true`:

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

This tells jamb the requirement is intentionally not linked to the parent document (SYS) because it emerges from outside considerations.
