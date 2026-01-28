"""Excel (XLSX) traceability matrix output."""

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from jamb.core.models import ItemCoverage, MatrixMetadata, TraceabilityGraph

# Color definitions
HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
HEADER_FONT = Font(bold=True, color="FFFFFF")
PASSED_FILL = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
FAILED_FILL = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
UNCOVERED_FILL = PatternFill(
    start_color="FFEB9C", end_color="FFEB9C", fill_type="solid"
)
NA_FILL = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")


def render_xlsx(
    coverage: dict[str, ItemCoverage],
    graph: TraceabilityGraph | None,
    trace_to_ignore: frozenset[str] | set[str] = frozenset(),
    metadata: MatrixMetadata | None = None,
) -> bytes:
    """Render coverage as Excel traceability matrix.

    Args:
        coverage: Dict mapping UIDs to ItemCoverage objects representing
            each traceable item and its test linkage.
        graph: Optional TraceabilityGraph used to resolve ancestor chains
            for each item. When None, ancestor columns are left empty.
        trace_to_ignore: Set of document prefixes to exclude from the
            ancestor display.
        metadata: Optional matrix metadata for IEC 62304 5.7.5 compliance.

    Returns:
        Bytes containing an XLSX workbook with a styled header, metadata
        section, summary section, and color-coded status cells (green for
        passed, red for failed, yellow for uncovered, gray for N/A).
    """
    wb = Workbook()
    ws: Worksheet = wb.active  # type: ignore[assignment]
    ws.title = "Traceability Matrix"

    # Calculate stats
    total = len(coverage)
    covered = sum(1 for c in coverage.values() if c.is_covered)
    passed = sum(1 for c in coverage.values() if c.all_tests_passed)
    coverage_pct = (100 * covered / total) if total else 0

    # Title
    ws["A1"] = "Traceability and Test Record Matrix"
    ws["A1"].font = Font(bold=True, size=14)
    ws.merge_cells("A1:I1")

    # Metadata section
    current_row = 3
    if metadata:
        ws.cell(row=current_row, column=1, value="Software Version:")
        ws.cell(row=current_row, column=2, value=metadata.software_version or "Unknown")
        current_row += 1

        ws.cell(row=current_row, column=1, value="Tester:")
        ws.cell(row=current_row, column=2, value=metadata.tester_id)
        current_row += 1

        ws.cell(row=current_row, column=1, value="Date:")
        ws.cell(
            row=current_row, column=2, value=metadata.execution_timestamp or "Unknown"
        )
        current_row += 1

        if metadata.environment:
            env = metadata.environment
            env_str = (
                f"{env.os_name} {env.os_version}, Python {env.python_version}, "
                f"{env.platform}, {env.processor}, {env.hostname}, "
                f"{env.cpu_count} cores"
            )
            ws.cell(row=current_row, column=1, value="Environment:")
            ws.cell(row=current_row, column=2, value=env_str)
            current_row += 1

            if env.test_tools:
                tools = [
                    f"{name} {ver}" for name, ver in sorted(env.test_tools.items())
                ]
                ws.cell(row=current_row, column=1, value="Test Tools:")
                ws.cell(row=current_row, column=2, value=", ".join(tools))
                current_row += 1

        current_row += 1  # Empty row separator

    # Summary section
    ws.cell(row=current_row, column=1, value="Total Items:")
    ws.cell(row=current_row, column=2, value=total)
    current_row += 1
    ws.cell(row=current_row, column=1, value="Covered:")
    ws.cell(row=current_row, column=2, value=f"{covered} ({coverage_pct:.1f}%)")
    current_row += 1
    ws.cell(row=current_row, column=1, value="All Tests Passing:")
    ws.cell(row=current_row, column=2, value=passed)
    current_row += 2  # Extra row before header

    # Header row
    headers = [
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
    header_row = current_row
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=col, value=header)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")

    # Data rows
    row = header_row + 1
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
            # Add test name header if there are multiple tests
            multi_test = len(cov.linked_tests) > 1
            if multi_test and test.test_actions:
                all_test_actions.append(f"[{test_name}]")
            for action in test.test_actions:
                all_test_actions.append(action)
            if multi_test and test.expected_results:
                all_expected_results.append(f"[{test_name}]")
            for result in test.expected_results:
                all_expected_results.append(result)
            if multi_test and test.actual_results:
                all_actual_results.append(f"[{test_name}]")
            for result in test.actual_results:
                all_actual_results.append(result)
            if multi_test and test.notes:
                all_notes.append(f"[{test_name}]")
            for note in test.notes:
                all_notes.append(note)
        tests_str = ", ".join(tests) if tests else ""
        test_actions_str = "\n".join(all_test_actions) if all_test_actions else ""
        expected_results_str = (
            "\n".join(all_expected_results) if all_expected_results else ""
        )
        actual_results_str = "\n".join(all_actual_results) if all_actual_results else ""
        notes_str = "\n".join(all_notes) if all_notes else ""

        # Status and fill color (with N/A support for non-testable items)
        if not cov.is_covered:
            if not cov.item.testable:
                status = "N/A"
                fill = NA_FILL
            else:
                status = "Not Covered"
                fill = UNCOVERED_FILL
        elif cov.all_tests_passed:
            status = "Passed"
            fill = PASSED_FILL
        else:
            status = "Failed"
            fill = FAILED_FILL

        # Write row
        ws.cell(row=row, column=1, value=uid)
        ws.cell(row=row, column=2, value=description)
        ws.cell(row=row, column=3, value=traces_to)
        ws.cell(row=row, column=4, value=tests_str)
        actions_cell = ws.cell(row=row, column=5, value=test_actions_str)
        actions_cell.alignment = Alignment(wrap_text=True, vertical="top")
        expected_cell = ws.cell(row=row, column=6, value=expected_results_str)
        expected_cell.alignment = Alignment(wrap_text=True, vertical="top")
        actual_cell = ws.cell(row=row, column=7, value=actual_results_str)
        actual_cell.alignment = Alignment(wrap_text=True, vertical="top")
        notes_cell = ws.cell(row=row, column=8, value=notes_str)
        notes_cell.alignment = Alignment(wrap_text=True, vertical="top")
        status_cell = ws.cell(row=row, column=9, value=status)
        status_cell.fill = fill

        row += 1

    # Auto-adjust column widths
    column_widths = [12, 50, 20, 40, 40, 40, 40, 50, 15]
    for col, width in enumerate(column_widths, start=1):
        ws.column_dimensions[get_column_letter(col)].width = width

    # Save to bytes
    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()
