"""Markdown traceability matrix output."""

from jamb.core.models import FullChainMatrix, MatrixMetadata, TestRecord


def _escape_markdown(text: str) -> str:
    """Escape markdown special characters for table cells.

    Escapes characters that could break markdown table rendering:
    - | (table separator)
    - * (bold/italic)
    - ` (code)
    - [ and ] (links)
    - \\ (escape character itself)
    - newlines (converted to spaces)

    Args:
        text: The plain text to escape.

    Returns:
        The string with special characters escaped.
    """
    # Order matters: escape backslash first
    text = text.replace("\\", "\\\\")
    text = text.replace("|", "\\|")
    text = text.replace("*", "\\*")
    text = text.replace("`", "\\`")
    text = text.replace("[", "\\[")
    text = text.replace("]", "\\]")
    text = text.replace("\n", " ")
    return text


def _truncate_for_table(text: str, max_len: int = 200) -> str:
    """Escape and truncate text for markdown table with ellipsis indicator.

    Escapes markdown special characters and truncates with '...'
    if the result exceeds max_len.

    Args:
        text: The text to escape and truncate.
        max_len: Maximum length before truncation (default: 200).

    Returns:
        The escaped and possibly truncated string.
    """
    escaped = _escape_markdown(text)
    if len(escaped) > max_len:
        return escaped[: max_len - 3] + "..."
    return escaped


def render_test_records_markdown(
    records: list[TestRecord],
    metadata: MatrixMetadata | None = None,
) -> str:
    """Render test records as Markdown.

    Args:
        records: List of TestRecord objects to render.
        metadata: Optional matrix metadata for IEC 62304 5.7.5 compliance.

    Returns:
        A string containing a Markdown document with a metadata section,
        summary section, and a pipe-delimited table of all test records.
    """
    # Calculate stats
    total = len(records)
    passed = sum(1 for r in records if r.outcome == "passed")
    failed = sum(1 for r in records if r.outcome == "failed")
    skipped = sum(1 for r in records if r.outcome == "skipped")
    error = sum(1 for r in records if r.outcome == "error")
    pass_rate = f"{100 * passed / total:.1f}%" if total else "0%"

    lines = [
        "# Test Records",
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
                tools = [f"{name} {ver}" for name, ver in sorted(env.test_tools.items())]
                lines.append(f"- **Test Tools:** {', '.join(tools)}")
        lines.append("")

    lines.extend(
        [
            "## Summary",
            "",
            f"- **Total Tests:** {total}",
            f"- **Passed:** {passed}",
            f"- **Failed:** {failed}",
            f"- **Skipped:** {skipped}",
            f"- **Error:** {error}",
            f"- **Pass Rate:** {pass_rate}",
            "",
            "## Test Records",
            "",
        ]
    )
    # Build header row with explicit list for maintainability
    headers = [
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
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

    for rec in records:
        test_name = _escape_markdown(rec.test_name)
        outcome = _escape_markdown(rec.outcome)
        requirements_str = _escape_markdown(", ".join(rec.requirements)) or "-"
        test_actions_str = "; ".join(_truncate_for_table(a) for a in rec.test_actions) if rec.test_actions else "-"
        expected_results_str = (
            "; ".join(_truncate_for_table(r) for r in rec.expected_results) if rec.expected_results else "-"
        )
        actual_results_str = (
            "; ".join(_truncate_for_table(r) for r in rec.actual_results) if rec.actual_results else "-"
        )
        notes_str = "; ".join(_truncate_for_table(n) for n in rec.notes) if rec.notes else "-"
        timestamp = _escape_markdown(rec.execution_timestamp or "-")

        lines.append(
            f"| {rec.test_id} | `{test_name}` "
            f"| {outcome} | {requirements_str} | {test_actions_str} "
            f"| {expected_results_str} | {actual_results_str} "
            f"| {notes_str} | {timestamp} |"
        )

    return "\n".join(lines)


def render_full_chain_markdown(
    matrices: list[FullChainMatrix],
    tc_mapping: dict[str, str] | None = None,
) -> str:
    """Render full chain trace matrices as Markdown.

    Args:
        matrices: List of FullChainMatrix objects to render.
        tc_mapping: Optional mapping from test nodeid to TC ID for display.

    Returns:
        A string containing Markdown with all matrices.
    """
    tc_mapping = tc_mapping or {}
    lines = ["# Traceability Matrix", ""]

    # Overall summary
    total = sum(m.summary.get("total", 0) for m in matrices)
    passed = sum(m.summary.get("passed", 0) for m in matrices)
    failed = sum(m.summary.get("failed", 0) for m in matrices)
    not_covered = sum(m.summary.get("not_covered", 0) for m in matrices)

    lines.extend(
        [
            "## Summary",
            "",
            f"- **Total Items:** {total}",
            f"- **Passed:** {passed}",
            f"- **Failed:** {failed}",
            f"- **Not Covered:** {not_covered}",
            "",
        ]
    )

    for matrix in matrices:
        # Build header
        headers = []
        if matrix.include_ancestors:
            headers.append("Traces To")
        headers.extend(matrix.document_hierarchy)
        headers.extend(["Tests", "Status"])

        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

        # Build rows
        for row in matrix.rows:
            cells = []

            # Traces To column
            if matrix.include_ancestors:
                ancestors = _escape_markdown(", ".join(row.ancestor_uids))
                cells.append(ancestors if ancestors else "-")

            # Document columns
            for prefix in matrix.document_hierarchy:
                item = row.chain.get(prefix)
                if item:
                    # Bold UID and header, unbold text
                    if item.header:
                        uid_header = f"{item.uid}: {item.header}"
                        cell_text = f"**{uid_header}** - {item.text}"
                    else:
                        uid_part = f"{item.uid}:"
                        cell_text = f"**{uid_part}** {item.text}"
                    cells.append(_truncate_for_table(cell_text))
                else:
                    cells.append("-")

            # Tests column
            tests = []
            for test in row.descendant_tests:
                test_name = test.test_nodeid.split("::")[-1]
                outcome = test.test_outcome or "unknown"
                escaped_name = _escape_markdown(test_name)
                escaped_outcome = _escape_markdown(outcome)
                tc_id = tc_mapping.get(test.test_nodeid, "")
                tc_prefix = f"{tc_id}: " if tc_id else ""
                tests.append(f"`{tc_prefix}{escaped_name}` [{escaped_outcome}]")
            cells.append(", ".join(tests) if tests else "-")

            # Status column
            cells.append(row.rollup_status)

            lines.append("| " + " | ".join(cells) + " |")

        lines.append("")

    return "\n".join(lines)
