"""CSV traceability matrix output."""

import csv
import io

from jamb.core.models import FullChainMatrix, MatrixMetadata, TestRecord


def render_test_records_csv(
    records: list[TestRecord],
    metadata: MatrixMetadata | None = None,
) -> str:
    """Render test records as CSV.

    Args:
        records: List of TestRecord objects to render.
        metadata: Optional matrix metadata for IEC 62304 5.7.5 compliance.

    Returns:
        A string containing CSV data with metadata rows (if provided),
        a header row, and one row per test record.
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
                tools = [f"{name} {ver}" for name, ver in sorted(env.test_tools.items())]
                writer.writerow(["Test Tools", ", ".join(tools)])
        writer.writerow([])  # Empty row separator

    # Summary rows
    total = len(records)
    passed = sum(1 for r in records if r.outcome == "passed")
    failed = sum(1 for r in records if r.outcome == "failed")
    skipped = sum(1 for r in records if r.outcome == "skipped")
    error = sum(1 for r in records if r.outcome == "error")
    pass_rate = f"{100 * passed / total:.1f}%" if total else "0%"

    writer.writerow(["Total Tests", total])
    writer.writerow(["Passed", passed])
    writer.writerow(["Failed", failed])
    writer.writerow(["Skipped", skipped])
    writer.writerow(["Error", error])
    writer.writerow(["Pass Rate", pass_rate])
    writer.writerow([])  # Empty row separator

    # Header row
    writer.writerow(
        [
            "Test Case",
            "Test Name",
            "Outcome",
            "Requirements",
            "Test Actions",
            "Expected Results",
            "Actual Results",
            "Notes",
            "Timestamp",
        ]
    )

    for rec in records:
        requirements_str = ", ".join(rec.requirements) if rec.requirements else ""
        test_actions_str = "; ".join(rec.test_actions) if rec.test_actions else ""
        expected_results_str = "; ".join(rec.expected_results) if rec.expected_results else ""
        actual_results_str = "; ".join(rec.actual_results) if rec.actual_results else ""
        notes_str = "; ".join(rec.notes) if rec.notes else ""

        writer.writerow(
            [
                rec.test_id,
                rec.test_name,
                rec.outcome,
                requirements_str,
                test_actions_str,
                expected_results_str,
                actual_results_str,
                notes_str,
                rec.execution_timestamp or "",
            ]
        )

    return output.getvalue()


def render_full_chain_csv(
    matrices: list[FullChainMatrix],
    tc_mapping: dict[str, str] | None = None,
) -> str:
    """Render full chain trace matrices as CSV.

    Args:
        matrices: List of FullChainMatrix objects to render.
        tc_mapping: Optional mapping from test nodeid to TC ID for display.

    Returns:
        A string containing CSV data with all matrices.
    """
    tc_mapping = tc_mapping or {}
    output = io.StringIO()
    writer = csv.writer(output)

    # Overall summary
    total = sum(m.summary.get("total", 0) for m in matrices)
    passed = sum(m.summary.get("passed", 0) for m in matrices)
    failed = sum(m.summary.get("failed", 0) for m in matrices)
    not_covered = sum(m.summary.get("not_covered", 0) for m in matrices)

    writer.writerow(["Traceability Matrix"])
    writer.writerow([])
    writer.writerow(["Total Items", total])
    writer.writerow(["Passed", passed])
    writer.writerow(["Failed", failed])
    writer.writerow(["Not Covered", not_covered])
    writer.writerow([])

    for matrix in matrices:
        # Build header
        headers = []
        if matrix.include_ancestors:
            headers.append("Traces To")
        headers.extend(matrix.document_hierarchy)
        headers.extend(["Tests", "Status"])
        writer.writerow(headers)

        # Build rows
        for row in matrix.rows:
            cells = []

            # Traces To column
            if matrix.include_ancestors:
                cells.append(", ".join(row.ancestor_uids) or "-")

            # Document columns
            for prefix in matrix.document_hierarchy:
                item = row.chain.get(prefix)
                if item:
                    cells.append(f"{item.uid}: {item.full_display_text}")
                else:
                    cells.append("")

            # Tests column
            tests = []
            for test in row.descendant_tests:
                test_name = test.test_nodeid.split("::")[-1]
                outcome = test.test_outcome or "unknown"
                tc_id = tc_mapping.get(test.test_nodeid, "")
                tc_prefix = f"{tc_id}: " if tc_id else ""
                tests.append(f"{tc_prefix}{test_name} [{outcome}]")
            cells.append(", ".join(tests))

            # Status column
            cells.append(row.rollup_status)

            writer.writerow(cells)

        writer.writerow([])

    return output.getvalue()
