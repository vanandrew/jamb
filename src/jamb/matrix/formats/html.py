"""HTML traceability matrix output."""

from jamb.core.models import ItemCoverage, TraceabilityGraph


def render_html(
    coverage: dict[str, ItemCoverage],
    graph: TraceabilityGraph | None,
    trace_to_ignore: frozenset[str] | set[str] = frozenset(),
) -> str:
    """Render coverage as HTML traceability matrix."""
    # Prepare rows
    rows = []
    for uid, cov in sorted(coverage.items()):
        # Get ancestor chain
        ancestors = []
        if graph:
            for ancestor in graph.get_ancestors(uid):
                if ancestor.document_prefix in trace_to_ignore:
                    continue
                ancestors.append(f"{ancestor.uid}: {ancestor.display_text}")

        status_class = "uncovered"
        status_text = "Not Covered"
        if cov.is_covered:
            if cov.all_tests_passed:
                status_class = "passed"
                status_text = "Passed"
            else:
                status_class = "failed"
                status_text = "Failed"

        tests_html = ""
        test_actions_html = ""
        expected_results_html = ""
        notes_html = ""
        for test in cov.linked_tests:
            outcome = test.test_outcome or "unknown"
            test_name = test.test_nodeid.split("::")[-1]
            tests_html += f'<div class="test {outcome}">{test_name} [{outcome}]</div>'
            for action in test.test_actions:
                test_actions_html += f'<div class="action">{_escape_html(action)}</div>'
            for result in test.expected_results:
                expected_results_html += (
                    f'<div class="expected-result">{_escape_html(result)}</div>'
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
                <td>{uid}</td>
                <td>{_escape_html(cov.item.display_text)}</td>
                <td>{cov.item.document_prefix}</td>
                <td>{ancestors_html or "-"}</td>
                <td>{tests_html or "-"}</td>
                <td>{test_actions_html or "-"}</td>
                <td>{expected_results_html or "-"}</td>
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

    return f"""<!DOCTYPE html>
<html>
<head>
    <title>Traceability Matrix</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                sans-serif;
            margin: 20px;
            background: #f5f5f5;
        }}
        h1 {{ color: #333; }}
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
        .status {{ font-weight: 500; }}
        tr.passed .status {{ color: #22863a; }}
        tr.failed .status {{ color: #cb2431; }}
        tr.uncovered .status {{ color: #b08800; }}
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
        .action, .expected-result {{
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
    <h1>Traceability Matrix</h1>

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
                <th>Document</th>
                <th>Traces To</th>
                <th>Tests</th>
                <th>Test Actions</th>
                <th>Expected Results</th>
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
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
