"""Markdown traceability matrix output."""

from jamb.core.models import ItemCoverage, TraceabilityGraph


def render_markdown(
    coverage: dict[str, ItemCoverage],
    graph: TraceabilityGraph | None,
    trace_to_ignore: frozenset[str] | set[str] = frozenset(),
) -> str:
    """Render coverage as Markdown traceability matrix.

    Args:
        coverage: Dict mapping UIDs to ItemCoverage objects representing
            each traceable item and its test linkage.
        graph: Optional TraceabilityGraph used to resolve ancestor chains
            for each item. When None, ancestor columns are left empty.
        trace_to_ignore: Set of document prefixes to exclude from the
            ancestor display.

    Returns:
        A string containing a Markdown document with a summary section
        and a pipe-delimited table of all coverage items.
    """
    # Calculate stats
    total = len(coverage)
    covered = sum(1 for c in coverage.values() if c.is_covered)
    passed = sum(1 for c in coverage.values() if c.all_tests_passed)

    lines = [
        "# Traceability Matrix",
        "",
        "## Summary",
        "",
        f"- **Total Items:** {total}",
        f"- **Covered:** {covered} ({100 * covered / total:.1f}%)"
        if total
        else "- **Covered:** 0",
        f"- **All Tests Passing:** {passed}",
        "",
        "## Coverage Details",
        "",
        "| UID | Description | Traces To "
        "| Tests | Test Actions | Expected Results "
        "| Notes | Status |",
        "|-----|-------------|-----------|"
        "-------|--------------|------------------"
        "|-------|--------|",
    ]

    for uid, cov in sorted(coverage.items()):
        description = cov.item.display_text.replace("|", "\\|")

        # Get ancestors
        ancestors = []
        if graph:
            for ancestor in graph.get_ancestors(uid):
                if ancestor.document_prefix in trace_to_ignore:
                    continue
                ancestors.append(ancestor.uid)
        traces_to = ", ".join(ancestors) if ancestors else "-"

        # Get tests, test actions, expected results, and notes
        tests = []
        all_notes = []
        all_test_actions = []
        all_expected_results = []
        for test in cov.linked_tests:
            test_name = test.test_nodeid.split("::")[-1]
            outcome = test.test_outcome or "?"
            tests.append(f"`{test_name}` [{outcome}]")
            all_notes.extend(test.notes)
            all_test_actions.extend(test.test_actions)
            all_expected_results.extend(test.expected_results)
        tests_str = ", ".join(tests) if tests else "-"
        # Escape pipe characters and truncate long content for markdown table
        test_actions_str = (
            "; ".join(
                a.replace("|", "\\|").replace("\n", " ")[:100] for a in all_test_actions
            )
            if all_test_actions
            else "-"
        )
        expected_results_str = (
            "; ".join(
                r.replace("|", "\\|").replace("\n", " ")[:100]
                for r in all_expected_results
            )
            if all_expected_results
            else "-"
        )
        notes_str = (
            "; ".join(
                msg.replace("|", "\\|").replace("\n", " ")[:100] for msg in all_notes
            )
            if all_notes
            else "-"
        )

        # Status
        if not cov.is_covered:
            status = "Not Covered"
        elif cov.all_tests_passed:
            status = "Passed"
        else:
            status = "Failed"

        lines.append(
            f"| {uid} | {description} "
            f"| {traces_to} | {tests_str} | {test_actions_str} "
            f"| {expected_results_str} | {notes_str} | {status} |"
        )

    return "\n".join(lines)
