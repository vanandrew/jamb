"""Markdown traceability matrix output."""

from jamb.core.models import ItemCoverage, MatrixMetadata, TraceabilityGraph


def _truncate_for_table(text: str, max_len: int = 200) -> str:
    """Truncate text for markdown table with ellipsis indicator.

    Escapes pipe characters and newlines, then truncates with '...'
    if the result exceeds max_len.
    """
    escaped = text.replace("|", "\\|").replace("\n", " ")
    if len(escaped) > max_len:
        return escaped[: max_len - 3] + "..."
    return escaped


def render_markdown(
    coverage: dict[str, ItemCoverage],
    graph: TraceabilityGraph | None,
    trace_to_ignore: frozenset[str] | set[str] = frozenset(),
    metadata: MatrixMetadata | None = None,
) -> str:
    """Render coverage as Markdown traceability matrix.

    Args:
        coverage: Dict mapping UIDs to ItemCoverage objects representing
            each traceable item and its test linkage.
        graph: Optional TraceabilityGraph used to resolve ancestor chains
            for each item. When None, ancestor columns are left empty.
        trace_to_ignore: Set of document prefixes to exclude from the
            ancestor display.
        metadata: Optional matrix metadata for IEC 62304 5.7.5 compliance.

    Returns:
        A string containing a Markdown document with a metadata section,
        summary section, and a pipe-delimited table of all coverage items.
    """
    # Calculate stats
    total = len(coverage)
    covered = sum(1 for c in coverage.values() if c.is_covered)
    passed = sum(1 for c in coverage.values() if c.all_tests_passed)

    lines = [
        "# Traceability and Test Record Matrix",
        "",
    ]

    # Add metadata section if provided
    if metadata:
        lines.extend(
            [
                "## Metadata",
                "",
                f"- **Software Version:** {metadata.software_version or 'Unknown'}",
                f"- **Tester:** {metadata.tester_id}",
                f"- **Date:** {metadata.execution_timestamp or 'Unknown'}",
            ]
        )
        if metadata.environment:
            env = metadata.environment
            env_str = (
                f"{env.os_name} {env.os_version}, Python {env.python_version}, "
                f"{env.platform}, {env.processor}, {env.hostname}, "
                f"{env.cpu_count} cores"
            )
            lines.append(f"- **Environment:** {env_str}")
            if env.test_tools:
                tools = [
                    f"{name} {ver}" for name, ver in sorted(env.test_tools.items())
                ]
                lines.append(f"- **Test Tools:** {', '.join(tools)}")
        lines.append("")

    lines.extend(
        [
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
            "| Tests | Test Actions | Expected Results | Actual Results "
            "| Notes | Status |",
            "| " + " | ".join(["---"] * 9) + " |",
        ]
    )

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

        # Get tests, test actions, expected results, actual results, and notes
        # Group entries by test name for clarity
        tests = []
        all_test_actions = []
        all_expected_results = []
        all_actual_results = []
        all_notes = []
        for test in cov.linked_tests:
            test_name = test.test_nodeid.split("::")[-1]
            outcome = test.test_outcome or "?"
            escaped_outcome = outcome.replace("|", "\\|")
            tests.append(f"`{test_name}` [{escaped_outcome}]")
            # Prefix each entry with test name if there are multiple tests
            prefix = f"[{test_name}] " if len(cov.linked_tests) > 1 else ""
            for action in test.test_actions:
                all_test_actions.append(f"{prefix}{action}")
            for result in test.expected_results:
                all_expected_results.append(f"{prefix}{result}")
            for result in test.actual_results:
                all_actual_results.append(f"{prefix}{result}")
            for note in test.notes:
                all_notes.append(f"{prefix}{note}")
        tests_str = ", ".join(tests) if tests else "-"
        # Escape pipe characters and truncate long content for markdown table
        test_actions_str = (
            "; ".join(_truncate_for_table(a) for a in all_test_actions)
            if all_test_actions
            else "-"
        )
        expected_results_str = (
            "; ".join(_truncate_for_table(r) for r in all_expected_results)
            if all_expected_results
            else "-"
        )
        actual_results_str = (
            "; ".join(_truncate_for_table(r) for r in all_actual_results)
            if all_actual_results
            else "-"
        )
        notes_str = (
            "; ".join(_truncate_for_table(msg) for msg in all_notes)
            if all_notes
            else "-"
        )

        # Status (with N/A support for non-testable items)
        if not cov.is_covered:
            status = "N/A" if not cov.item.testable else "Not Covered"
        elif cov.all_tests_passed:
            status = "Passed"
        else:
            status = "Failed"

        lines.append(
            f"| {uid} | {description} "
            f"| {traces_to} | {tests_str} | {test_actions_str} "
            f"| {expected_results_str} | {actual_results_str} "
            f"| {notes_str} | {status} |"
        )

    return "\n".join(lines)
