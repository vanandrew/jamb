"""HTML traceability matrix output."""

import html as _html

from jamb.core.models import ItemCoverage, MatrixMetadata, TraceabilityGraph


def render_html(
    coverage: dict[str, ItemCoverage],
    graph: TraceabilityGraph | None,
    trace_to_ignore: frozenset[str] | set[str] = frozenset(),
    metadata: MatrixMetadata | None = None,
) -> str:
    """Render coverage as HTML traceability matrix.

    Args:
        coverage: Dict mapping UIDs to ItemCoverage objects representing
            each traceable item and its test linkage.
        graph: Optional TraceabilityGraph used to resolve ancestor chains
            for each item. When None, ancestor columns are left empty.
        trace_to_ignore: Set of document prefixes to exclude from the
            ancestor display.
        metadata: Optional matrix metadata for IEC 62304 5.7.5 compliance.

    Returns:
        A string containing a complete HTML document with embedded CSS,
        including a summary statistics banner and a styled table of all
        coverage items.
    """
    # Prepare rows
    rows = []
    for uid, cov in sorted(coverage.items()):
        # Get ancestor chain
        ancestors: list[str] = []
        if graph:
            for anc in graph.get_ancestors(uid):
                if anc.document_prefix in trace_to_ignore:
                    continue
                ancestors.append(f"{anc.uid}: {anc.display_text}")

        # Determine status (with N/A support for non-testable items)
        if not cov.is_covered:
            if not cov.item.testable:
                status_class = "na"
                status_text = "N/A"
            else:
                status_class = "uncovered"
                status_text = "Not Covered"
        elif cov.all_tests_passed:
            status_class = "passed"
            status_text = "Passed"
        else:
            status_class = "failed"
            status_text = "Failed"

        tests_html = ""
        test_actions_html = ""
        expected_results_html = ""
        actual_results_html = ""
        notes_html = ""
        for test in cov.linked_tests:
            outcome = test.test_outcome or "unknown"
            test_name = test.test_nodeid.split("::")[-1]
            tests_html += (
                f'<div class="test {_escape_html(outcome)}">'
                f"{_escape_html(test_name)} "
                f"[{_escape_html(outcome)}]</div>"
            )

            # Add test name header if this test has any logged entries
            has_actions = len(test.test_actions) > 0
            has_expected = len(test.expected_results) > 0
            has_actual = len(test.actual_results) > 0
            has_notes = len(test.notes) > 0

            if has_actions:
                test_actions_html += (
                    f'<div class="test-header">{_escape_html(test_name)}</div>'
                )
                for action in test.test_actions:
                    test_actions_html += (
                        f'<div class="action">{_escape_html(action)}</div>'
                    )

            if has_expected:
                expected_results_html += (
                    f'<div class="test-header">{_escape_html(test_name)}</div>'
                )
                for result in test.expected_results:
                    expected_results_html += (
                        f'<div class="expected-result">{_escape_html(result)}</div>'
                    )

            if has_actual:
                actual_results_html += (
                    f'<div class="test-header">{_escape_html(test_name)}</div>'
                )
                for result in test.actual_results:
                    actual_results_html += (
                        f'<div class="actual-result">{_escape_html(result)}</div>'
                    )

            if has_notes:
                notes_html += (
                    f'<div class="test-header">{_escape_html(test_name)}</div>'
                )
                for msg in test.notes:
                    msg_class = "message"
                    if msg.startswith("[FAILURE]"):
                        msg_class = "message failure"
                    elif msg.startswith("[SKIPPED]") or msg.startswith("[XFAIL]"):
                        msg_class = "message skipped"
                    notes_html += f'<div class="{msg_class}">{_escape_html(msg)}</div>'

        ancestors_html = ""
        for ancestor in ancestors:
            ancestors_html += f'<div class="ancestor">{_escape_html(ancestor)}</div>'

        rows.append(
            f"""
            <tr class="{status_class}">
                <td>{_escape_html(uid)}</td>
                <td>{_escape_html(cov.item.display_text)}</td>
                <td>{ancestors_html or "-"}</td>
                <td>{tests_html or "-"}</td>
                <td>{test_actions_html or "-"}</td>
                <td>{expected_results_html or "-"}</td>
                <td>{actual_results_html or "-"}</td>
                <td>{notes_html or "-"}</td>
                <td class="status">{status_text}</td>
            </tr>
            """
        )

    # Calculate stats
    total = len(coverage)
    covered = sum(1 for c in coverage.values() if c.is_covered)
    passed = sum(1 for c in coverage.values() if c.all_tests_passed)
    coverage_pct = f"{100 * covered / total:.1f}%" if total else "0%"

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
    <title>Traceability and Test Record Matrix</title>
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
        .ancestor {{
            font-size: 12px;
            color: #666;
            padding: 2px 0;
        }}
        .test-header {{
            font-size: 11px;
            font-weight: 600;
            color: #555;
            padding: 4px 0 2px 0;
            margin-top: 6px;
            border-bottom: 1px solid #ddd;
            font-family: monospace;
        }}
        .test-header:first-child {{
            margin-top: 0;
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
            margin: 2px 0 2px 16px;
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
    <h1>Traceability and Test Record Matrix</h1>
{metadata_html}
    <div class="stats">
        <span><strong>Total Items:</strong> {total}</span>
        <span><strong>Covered:</strong> {covered} ({coverage_pct})</span>
        <span><strong>All Tests Passing:</strong> {passed}</span>
    </div>

    <table>
        <thead>
            <tr>
                <th>UID</th>
                <th>Description</th>
                <th>Traces To</th>
                <th>Tests</th>
                <th>Test Actions</th>
                <th>Expected Results</th>
                <th>Actual Results</th>
                <th>Notes</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody>
            {"".join(rows)}
        </tbody>
    </table>
</body>
</html>
"""


def _escape_html(text: str) -> str:
    """Escape HTML special characters.

    Args:
        text: The plain text to escape.

    Returns:
        The string with ``&``, ``<``, ``>``, ``"``, and ``'`` replaced
        by their HTML entity equivalents.
    """
    return _html.escape(text, quote=True)
