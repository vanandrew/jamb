"""Excel (XLSX) traceability matrix output."""

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from jamb.core.models import ItemCoverage, TraceabilityGraph

# Color definitions
HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
HEADER_FONT = Font(bold=True, color="FFFFFF")
PASSED_FILL = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
FAILED_FILL = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
UNCOVERED_FILL = PatternFill(
    start_color="FFEB9C", end_color="FFEB9C", fill_type="solid"
)


def render_xlsx(
    coverage: dict[str, ItemCoverage],
    graph: TraceabilityGraph | None,
    trace_to_ignore: frozenset[str] | set[str] = frozenset(),
) -> bytes:
    """Render coverage as Excel traceability matrix.

    Args:
        coverage: Dict mapping UIDs to ItemCoverage objects representing
            each traceable item and its test linkage.
        graph: Optional TraceabilityGraph used to resolve ancestor chains
            for each item. When None, ancestor columns are left empty.
        trace_to_ignore: Set of document prefixes to exclude from the
            ancestor display.

    Returns:
        Bytes containing an XLSX workbook with a styled header, a
        summary section, and color-coded status cells (green for passed,
        red for failed, yellow for uncovered).
    """
    wb = Workbook()
    ws: Worksheet = wb.active  # type: ignore[assignment]
    ws.title = "Traceability Matrix"

    # Calculate stats
    total = len(coverage)
    covered = sum(1 for c in coverage.values() if c.is_covered)
    passed = sum(1 for c in coverage.values() if c.all_tests_passed)
    coverage_pct = (100 * covered / total) if total else 0

    # Summary section
    ws["A1"] = "Traceability Matrix"
    ws["A1"].font = Font(bold=True, size=14)
    ws.merge_cells("A1:I1")

    ws["A3"] = "Total Items:"
    ws["B3"] = total
    ws["A4"] = "Covered:"
    ws["B4"] = f"{covered} ({coverage_pct:.1f}%)"
    ws["A5"] = "All Tests Passing:"
    ws["B5"] = passed

    # Header row (row 7)
    headers = [
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
    header_row = 7
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
        test_actions_str = "\n".join(all_test_actions) if all_test_actions else ""
        expected_results_str = (
            "\n".join(all_expected_results) if all_expected_results else ""
        )
        notes_str = "\n".join(all_notes) if all_notes else ""

        # Status and fill color
        if not cov.is_covered:
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
        ws.cell(row=row, column=3, value=cov.item.document_prefix)
        ws.cell(row=row, column=4, value=traces_to)
        ws.cell(row=row, column=5, value=tests_str)
        actions_cell = ws.cell(row=row, column=6, value=test_actions_str)
        actions_cell.alignment = Alignment(wrap_text=True, vertical="top")
        results_cell = ws.cell(row=row, column=7, value=expected_results_str)
        results_cell.alignment = Alignment(wrap_text=True, vertical="top")
        notes_cell = ws.cell(row=row, column=8, value=notes_str)
        notes_cell.alignment = Alignment(wrap_text=True, vertical="top")
        status_cell = ws.cell(row=row, column=9, value=status)
        status_cell.fill = fill

        row += 1

    # Auto-adjust column widths
    column_widths = [12, 50, 12, 20, 40, 40, 40, 50, 15]
    for col, width in enumerate(column_widths, start=1):
        ws.column_dimensions[get_column_letter(col)].width = width

    # Save to bytes
    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()
