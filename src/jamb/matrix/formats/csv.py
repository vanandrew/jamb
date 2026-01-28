"""CSV traceability matrix output."""

import csv
import io

from jamb.core.models import ItemCoverage, MatrixMetadata, TraceabilityGraph


def render_csv(
    coverage: dict[str, ItemCoverage],
    graph: TraceabilityGraph | None,
    trace_to_ignore: frozenset[str] | set[str] = frozenset(),
    metadata: MatrixMetadata | None = None,
) -> str:
    """Render coverage as CSV traceability matrix.

    Args:
        coverage: Dict mapping UIDs to ItemCoverage objects representing
            each traceable item and its test linkage.
        graph: Optional TraceabilityGraph used to resolve ancestor chains
            for each item. When None, ancestor columns are left empty.
        trace_to_ignore: Set of document prefixes to exclude from the
            ancestor display.
        metadata: Optional matrix metadata for IEC 62304 5.7.5 compliance.

    Returns:
        A string containing CSV data with metadata rows (if provided),
        a header row, and one row per traceable item.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Metadata rows
    if metadata:
        writer.writerow(["Software Version", metadata.software_version or "Unknown"])
        writer.writerow(["Tester", metadata.tester_id])
        writer.writerow(["Date", metadata.execution_timestamp or "Unknown"])
        if metadata.environment:
            env = metadata.environment
            env_str = (
                f"{env.os_name} {env.os_version}, Python {env.python_version}, "
                f"{env.platform}, {env.processor}, {env.hostname}, "
                f"{env.cpu_count} cores"
            )
            writer.writerow(["Environment", env_str])
            if env.test_tools:
                tools = [
                    f"{name} {ver}" for name, ver in sorted(env.test_tools.items())
                ]
                writer.writerow(["Test Tools", ", ".join(tools)])
        writer.writerow([])  # Empty row separator

    # Header row
    writer.writerow(
        [
            "UID",
            "Description",
            "Traces To",
            "Tests",
            "Test Actions",
            "Expected Results",
            "Actual Results",
            "Notes",
            "Status",
        ]
    )

    for uid, cov in sorted(coverage.items()):
        description = cov.item.display_text

        # Get ancestors
        ancestors = []
        if graph:
            for ancestor in graph.get_ancestors(uid):
                if ancestor.document_prefix in trace_to_ignore:
                    continue
                ancestors.append(ancestor.uid)
        traces_to = ", ".join(ancestors) if ancestors else ""

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
            tests.append(f"{test_name} [{outcome}]")
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
        tests_str = ", ".join(tests) if tests else ""
        test_actions_str = "; ".join(all_test_actions) if all_test_actions else ""
        expected_results_str = (
            "; ".join(all_expected_results) if all_expected_results else ""
        )
        actual_results_str = "; ".join(all_actual_results) if all_actual_results else ""
        notes_str = "; ".join(all_notes) if all_notes else ""

        # Status (with N/A support for non-testable items)
        if not cov.is_covered:
            status = "N/A" if not cov.item.testable else "Not Covered"
        elif cov.all_tests_passed:
            status = "Passed"
        else:
            status = "Failed"

        writer.writerow(
            [
                uid,
                description,
                traces_to,
                tests_str,
                test_actions_str,
                expected_results_str,
                actual_results_str,
                notes_str,
                status,
            ]
        )

    return output.getvalue()
