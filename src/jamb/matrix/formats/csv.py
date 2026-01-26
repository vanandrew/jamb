"""CSV traceability matrix output."""

import csv
import io

from jamb.core.models import ItemCoverage, TraceabilityGraph


def render_csv(
    coverage: dict[str, ItemCoverage],
    graph: TraceabilityGraph | None,
    trace_to_ignore: frozenset[str] | set[str] = frozenset(),
) -> str:
    """Render coverage as CSV traceability matrix."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow(
        [
            "UID",
            "Description",
            "Document",
            "Traces To",
            "Tests",
            "Test Actions",
            "Expected Results",
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

        # Get tests, test actions, expected results, and notes
        tests = []
        all_notes = []
        all_test_actions = []
        all_expected_results = []
        for test in cov.linked_tests:
            test_name = test.test_nodeid.split("::")[-1]
            outcome = test.test_outcome or "?"
            tests.append(f"{test_name} [{outcome}]")
            all_notes.extend(test.notes)
            all_test_actions.extend(test.test_actions)
            all_expected_results.extend(test.expected_results)
        tests_str = ", ".join(tests) if tests else ""
        test_actions_str = "; ".join(all_test_actions) if all_test_actions else ""
        expected_results_str = (
            "; ".join(all_expected_results) if all_expected_results else ""
        )
        notes_str = "; ".join(all_notes) if all_notes else ""

        # Status
        if not cov.is_covered:
            status = "Not Covered"
        elif cov.all_tests_passed:
            status = "Passed"
        else:
            status = "Failed"

        writer.writerow(
            [
                uid,
                description,
                cov.item.document_prefix,
                traces_to,
                tests_str,
                test_actions_str,
                expected_results_str,
                notes_str,
                status,
            ]
        )

    return output.getvalue()
