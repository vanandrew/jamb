"""HTML traceability matrix output."""

import html as _html
import warnings

from jamb.core.models import FullChainMatrix, MatrixMetadata, TestRecord

# Threshold for warning about large datasets
LARGE_DATASET_WARNING_THRESHOLD = 5000

# Explicit status to CSS class mapping (replaces brittle string manipulation)
STATUS_CSS_CLASSES: dict[str, str] = {
    "Passed": "passed",
    "Failed": "failed",
    "Not Covered": "uncovered",
    "Partial": "uncovered",
    "N/A": "na",
}


def _escape_html(text: str) -> str:
    """Escape HTML special characters.

    Args:
        text: The plain text to escape.

    Returns:
        The string with ``&``, ``<``, ``>``, ``"``, and ``'`` replaced
        by their HTML entity equivalents.
    """
    return _html.escape(text, quote=True)


def render_test_records_html(
    records: list[TestRecord],
    metadata: MatrixMetadata | None = None,
) -> str:
    """Render test records as HTML test records matrix.

    Args:
        records: List of TestRecord objects to render.
        metadata: Optional matrix metadata for IEC 62304 5.7.5 compliance.

    Returns:
        A string containing a complete HTML document with embedded CSS,
        including a summary statistics banner and a styled table of all
        test records.
    """
    if len(records) > LARGE_DATASET_WARNING_THRESHOLD:
        warnings.warn(
            f"Large matrix ({len(records)} rows) may use significant memory. "
            "Consider using CSV format for large datasets.",
            stacklevel=2,
        )

    # Prepare rows
    rows = []
    for rec in records:
        outcome_class = rec.outcome.lower() if rec.outcome else "unknown"

        requirements_html = ", ".join(_escape_html(r) for r in rec.requirements) or "-"

        # Build test actions, expected results, actual results, notes
        test_actions_html = ""
        for action in rec.test_actions:
            test_actions_html += f'<div class="action">{_escape_html(action)}</div>'

        expected_results_html = ""
        for result in rec.expected_results:
            expected_results_html += f'<div class="expected-result">{_escape_html(result)}</div>'

        actual_results_html = ""
        for result in rec.actual_results:
            actual_results_html += f'<div class="actual-result">{_escape_html(result)}</div>'

        notes_html = ""
        for msg in rec.notes:
            msg_class = "message"
            if msg.startswith("[FAILURE]"):
                msg_class = "message failure"
            elif msg.startswith("[SKIPPED]") or msg.startswith("[XFAIL]"):
                msg_class = "message skipped"
            notes_html += f'<div class="{msg_class}">{_escape_html(msg)}</div>'

        timestamp = _escape_html(rec.execution_timestamp or "-")

        rows.append(
            f"""
            <tr class="{outcome_class}">
                <td>{_escape_html(rec.test_id)}</td>
                <td class="test-name">{_escape_html(rec.test_name)}</td>
                <td class="outcome">{_escape_html(rec.outcome)}</td>
                <td>{requirements_html}</td>
                <td>{test_actions_html or "-"}</td>
                <td>{expected_results_html or "-"}</td>
                <td>{actual_results_html or "-"}</td>
                <td>{notes_html or "-"}</td>
                <td>{timestamp}</td>
            </tr>
            """
        )

    # Calculate stats
    total = len(records)
    passed = sum(1 for r in records if r.outcome == "passed")
    failed = sum(1 for r in records if r.outcome == "failed")
    skipped = sum(1 for r in records if r.outcome == "skipped")
    error = sum(1 for r in records if r.outcome == "error")
    pass_rate = f"{100 * passed / total:.1f}%" if total else "0%"

    # Build metadata section
    metadata_html = ""
    if metadata:
        env = metadata.environment
        env_str = ""
        tools_str = ""
        if env:
            env_str = (
                f"{env.os_name} {env.os_version}, Python {env.python_version}, "
                f"{env.platform}, {env.processor}, {env.hostname}, "
                f"{env.cpu_count} cores"
            )
            tools = [f"{name} {ver}" for name, ver in sorted(env.test_tools.items())]
            tools_str = ", ".join(tools) if tools else "Unknown"
        version_val = _escape_html(metadata.software_version or "Unknown")
        tester_val = _escape_html(metadata.tester_id)
        date_val = _escape_html(metadata.execution_timestamp or "Unknown")
        env_val = _escape_html(env_str) if env_str else "Unknown"
        tools_val = _escape_html(tools_str)
        metadata_html = f"""
    <div class="metadata">
        <div><strong>Software Version:</strong> {version_val}</div>
        <div><strong>Tester:</strong> {tester_val}</div>
        <div><strong>Date:</strong> {date_val}</div>
        <div><strong>Environment:</strong> {env_val}</div>
        <div><strong>Test Tools:</strong> {tools_val}</div>
    </div>
"""

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Test Records</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                sans-serif;
            margin: 20px;
            background: #f5f5f5;
        }}
        h1 {{ color: #333; }}
        .metadata {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 15px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            font-size: 14px;
        }}
        .metadata div {{
            margin-bottom: 5px;
        }}
        .stats {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .stats span {{
            margin-right: 30px;
            font-size: 14px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border-radius: 8px;
            overflow: hidden;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background: #333;
            color: white;
            font-weight: 500;
        }}
        tr:hover {{ background: #f9f9f9; }}
        tr.passed {{ }}
        tr.failed {{ background: #fff0f0; }}
        tr.skipped {{ background: #fffbeb; }}
        tr.error {{ background: #fff0f0; }}
        tr.unknown {{ background: #f0f0f0; }}
        .outcome {{ font-weight: 500; }}
        tr.passed .outcome {{ color: #22863a; }}
        tr.failed .outcome {{ color: #cb2431; }}
        tr.skipped .outcome {{ color: #b08800; }}
        tr.error .outcome {{ color: #cb2431; }}
        tr.unknown .outcome {{ color: #666; }}
        .test-name {{
            font-family: monospace;
            font-size: 12px;
        }}
        .action, .expected-result, .actual-result {{
            font-size: 12px;
            color: #333;
            padding: 2px 6px;
            margin: 2px 0;
        }}
        .action {{
            border-left: 2px solid #4472C4;
            background: #f0f5ff;
        }}
        .expected-result {{
            border-left: 2px solid #22863a;
            background: #f0fff4;
        }}
        .actual-result {{
            border-left: 2px solid #6f42c1;
            background: #f5f0ff;
        }}
        .message {{
            font-size: 11px;
            color: #666;
            padding: 4px 8px;
            margin: 2px 0;
            border-left: 2px solid #ddd;
            white-space: pre-wrap;
            font-family: monospace;
        }}
        .message.failure {{
            border-left-color: #cb2431;
            color: #cb2431;
            background: #fff5f5;
        }}
        .message.skipped {{
            border-left-color: #b08800;
            color: #735c0f;
        }}
    </style>
</head>
<body>
    <h1>Test Records</h1>
{metadata_html}
    <div class="stats">
        <span><strong>Total Tests:</strong> {total}</span>
        <span><strong>Passed:</strong> {passed}</span>
        <span><strong>Failed:</strong> {failed}</span>
        <span><strong>Skipped:</strong> {skipped}</span>
        <span><strong>Error:</strong> {error}</span>
        <span><strong>Pass Rate:</strong> {pass_rate}</span>
    </div>

    <table>
        <thead>
            <tr>
                <th>Test Case</th>
                <th>Test Name</th>
                <th>Outcome</th>
                <th>Requirements</th>
                <th>Test Actions</th>
                <th>Expected Results</th>
                <th>Actual Results</th>
                <th>Notes</th>
                <th>Timestamp</th>
            </tr>
        </thead>
        <tbody>
            {"".join(rows)}
        </tbody>
    </table>
</body>
</html>
"""


def render_full_chain_html(
    matrices: list[FullChainMatrix],
    tc_mapping: dict[str, str] | None = None,
) -> str:
    """Render full chain trace matrices as HTML.

    Args:
        matrices: List of FullChainMatrix objects to render.
        tc_mapping: Optional mapping from test nodeid to TC ID for display.

    Returns:
        A string containing a complete HTML document with all matrices.
    """
    total_rows = sum(len(m.rows) for m in matrices)
    if total_rows > LARGE_DATASET_WARNING_THRESHOLD:
        warnings.warn(
            f"Large matrix ({total_rows} rows) may use significant memory. "
            "Consider using CSV format for large datasets.",
            stacklevel=2,
        )

    tc_mapping = tc_mapping or {}

    # Build tables for each matrix
    tables_html = []
    total_summary = {"total": 0, "passed": 0, "failed": 0, "not_covered": 0}

    for matrix in matrices:
        # Update totals
        total_summary["total"] += matrix.summary.get("total", 0)
        total_summary["passed"] += matrix.summary.get("passed", 0)
        total_summary["failed"] += matrix.summary.get("failed", 0)
        total_summary["not_covered"] += matrix.summary.get("not_covered", 0)

        # Build header row
        headers = []
        if matrix.include_ancestors:
            headers.append("Traces To")
        headers.extend(matrix.document_hierarchy)
        headers.extend(["Tests", "Status"])

        header_cells = "".join(f"<th>{_escape_html(h)}</th>" for h in headers)

        # Build data rows
        rows = []
        for row in matrix.rows:
            # Determine status class using explicit mapping
            status = row.rollup_status
            status_class = STATUS_CSS_CLASSES.get(status, "na")

            cells = []

            # Traces To column (ancestors)
            if matrix.include_ancestors:
                ancestors_html = ", ".join(_escape_html(uid) for uid in row.ancestor_uids)
                cells.append(f"<td>{ancestors_html or '-'}</td>")

            # Document columns
            for prefix in matrix.document_hierarchy:
                item = row.chain.get(prefix)
                if item:
                    # Bold UID and header, unbold text
                    if item.header:
                        uid_header = f"{item.uid}: {item.header}"
                        cell_html = f"<strong>{_escape_html(uid_header)}</strong> - {_escape_html(item.text)}"
                    else:
                        uid_part = f"{item.uid}:"
                        cell_html = f"<strong>{_escape_html(uid_part)}</strong> {_escape_html(item.text)}"
                    cells.append(f"<td>{cell_html}</td>")
                else:
                    cells.append("<td>-</td>")

            # Tests column
            tests_html = ""
            for test in row.descendant_tests:
                outcome = test.test_outcome or "unknown"
                test_name = test.test_nodeid.split("::")[-1]
                tc_id = tc_mapping.get(test.test_nodeid, "")
                tc_prefix = f"{tc_id}: " if tc_id else ""
                tests_html += (
                    f'<div class="test {_escape_html(outcome)}">'
                    f"{_escape_html(tc_prefix)}{_escape_html(test_name)} "
                    f"[{_escape_html(outcome)}]</div>"
                )
            cells.append(f"<td>{tests_html or '-'}</td>")

            # Status column
            cells.append(f'<td class="status">{_escape_html(status)}</td>')

            rows.append(f'<tr class="{status_class}">{"".join(cells)}</tr>')

        table_html = f"""
        <table>
            <thead><tr>{header_cells}</tr></thead>
            <tbody>{"".join(rows)}</tbody>
        </table>
        """
        tables_html.append(table_html)

    # Overall summary
    overall_html = (
        f"<div class='stats overall'>"
        f"<span><strong>Total Items:</strong> {total_summary['total']}</span>"
        f"<span><strong>Passed:</strong> {total_summary['passed']}</span>"
        f"<span><strong>Failed:</strong> {total_summary['failed']}</span>"
        f"<span><strong>Not Covered:</strong> {total_summary['not_covered']}</span>"
        f"</div>"
    )

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Traceability Matrix</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                sans-serif;
            margin: 20px;
            background: #f5f5f5;
        }}
        h1 {{ color: #333; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .stats {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .stats.overall {{
            background: #e8f4fc;
        }}
        .stats span {{
            margin-right: 30px;
            font-size: 14px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border-radius: 8px;
            overflow: hidden;
            margin-bottom: 30px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background: #333;
            color: white;
            font-weight: 500;
        }}
        tr:hover {{ background: #f9f9f9; }}
        tr.passed {{ }}
        tr.failed {{ background: #fff0f0; }}
        tr.uncovered {{ background: #fffbeb; }}
        tr.na {{ background: #f0f0f0; }}
        .status {{ font-weight: 500; }}
        tr.passed .status {{ color: #22863a; }}
        tr.failed .status {{ color: #cb2431; }}
        tr.uncovered .status {{ color: #b08800; }}
        tr.na .status {{ color: #666; }}
        .test {{
            font-family: monospace;
            font-size: 12px;
            padding: 2px 6px;
            margin: 2px 0;
            border-radius: 3px;
        }}
        .test.passed {{ background: #dcffe4; color: #22863a; }}
        .test.failed {{ background: #ffeef0; color: #cb2431; }}
        .test.skipped {{ background: #fff5b1; color: #735c0f; }}
    </style>
</head>
<body>
    <h1>Traceability Matrix</h1>
    {overall_html}
    {"".join(tables_html)}
</body>
</html>
"""
