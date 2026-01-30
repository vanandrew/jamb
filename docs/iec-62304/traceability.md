# Traceability Requirements

## Bidirectional Traceability

IEC 62304 requires tracing in both directions through the development lifecycle. **Forward traceability** runs from requirements to design to code to tests, answering the question "how is this requirement implemented and verified?" **Backward traceability** runs from tests to code to design to requirements, answering the question "why does this test exist, and what requirement does it verify?"

Every requirement must trace to its parent (where it came from) and to the tests that
verify it (proving it works). Gaps in either direction indicate incomplete coverage and
are findings in an audit.

## How jamb's Document DAG Implements Traceability

Documents in jamb form a directed acyclic graph (DAG) that represents the hierarchy of
specifications. PRJ (project requirements) sits at the top, with UN (user needs) linking upward to PRJ items, SYS (system requirements) linking upward to UN items, and SRS (software requirements) linking upward to SYS items. Tests link to SRS items via `@pytest.mark.requirement`.

Items link *upward* to parent items, establishing backward traceability from detailed
requirements to high-level needs. The pytest plugin links tests *downward* to requirements,
establishing forward traceability from requirements to verification. Together, these two
directions form complete bidirectional traceability.

## Suspect Link Detection as Change Impact Analysis

When an upstream requirement changes, jamb detects the content hash mismatch and flags
downstream links as **suspect**. This implements the IEC 62304 requirement for change
impact analysis (Clause 8.2).

For example, if a SYS item changes:

1. jamb records the new content hash for the SYS item.
2. Any SRS item that links to the changed SYS item now has a suspect link, because the
   hash it recorded at link time no longer matches.
3. `jamb validate` reports the suspect links, alerting the team to review whether the
   downstream SRS items need to be updated.
4. Once the SRS items are reviewed and updated (or confirmed unchanged), the links are
   re-acknowledged and the suspect flag clears.

This mechanism ensures that no change propagates silently through the traceability chain.
Every change is surfaced and must be explicitly addressed.

## Trace Completeness with `jamb validate`

The `jamb validate` command checks the entire traceability chain for completeness, looking for unlinked items (items that should have parent links but do not), broken links (references to items that no longer exist), and suspect links (where the upstream item has changed since the link was created). Test coverage is checked separately by `jamb check` (static scan) or `pytest --jamb --jamb-fail-uncovered` (runtime).

Running `jamb validate` before a release provides evidence that the traceability chain is
complete and that all changes have been assessed. This is a key audit artifact for
IEC 62304 compliance.

## Test Record Contents (Clause 5.7.5)

IEC 62304 Clause 5.7.5 specifies what information must be included in software system test records. jamb's traceability matrix includes all required fields:

| IEC 62304 5.7.5 Requirement | jamb Implementation |
|----------------------------|---------------------|
| Test identification | Test name from pytest node ID |
| Software version tested | `--jamb-software-version` flag or auto-detected from pyproject.toml |
| Test date | Automatically captured execution timestamp (ISO 8601 UTC) |
| Tester identification | `--jamb-tester-id` flag |
| Test environment | Automatically captured (OS, Python version, platform, processor, hostname, CPU count) |
| Test tools | Automatically captured (all loaded pytest plugins with versions) |
| Pass/fail criteria | `jamb_log.expected_result()` entries |
| Actual results | `jamb_log.actual_result()` entries |
| Pass/fail determination | Status column (Passed/Failed/Not Covered/N/A) |

### Generating Compliant Test Records

```bash
pytest --jamb --jamb-trace-matrix matrix.html \
    --jamb-tester-id "QA Team / CI Pipeline" \
    --jamb-software-version "1.2.3"
```

The generated matrix includes a metadata header with:

- **Software Version**: Version under test
- **Tester**: Who executed the tests
- **Date**: Execution timestamp
- **Environment**: OS name/version, Python version, platform, processor, hostname, CPU count
- **Test Tools**: All loaded pytest plugins with versions (pytest, jamb, pytest-cov, etc.)

### Non-Testable Requirements

Some requirements cannot be verified by automated tests (e.g., documentation requirements, process requirements). Mark these with `testable: false` in the YAML file:

```yaml
header: Documentation Requirements
testable: false
text: |
  User manual shall be provided with each software release.
```

These items show "N/A" status instead of "Not Covered", indicating they are verified by other means (inspection, analysis, demonstration).

## Further Reading

See the {doc}`/user-guide/concepts` page for detailed information on how to use jamb's
traceability features in practice.
