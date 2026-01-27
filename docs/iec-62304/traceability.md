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

The `jamb validate` command checks the entire traceability chain for completeness, looking for unlinked items (items that should have parent links but do not), broken links (references to items that no longer exist), missing coverage (requirements with no tests linked to them), and suspect links (where the upstream item has changed since the link was created).

Running `jamb validate` before a release provides evidence that the traceability chain is
complete and that all changes have been assessed. This is a key audit artifact for
IEC 62304 compliance.

## Further Reading

See the {doc}`/user-guide/concepts` page for detailed information on how to use jamb's
traceability features in practice.
