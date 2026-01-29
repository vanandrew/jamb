"""Generate traceability matrix in various formats."""

from collections.abc import Callable
from pathlib import Path

from jamb.core.models import (
    FullChainMatrix,
    ItemCoverage,
    LinkedTest,
    MatrixMetadata,
    TestRecord,
    TraceabilityGraph,
)
from jamb.matrix.utils import group_tests_by_nodeid

# Type aliases for formatter functions
TestRecordsFormatter = Callable[[list[TestRecord], MatrixMetadata | None], str | bytes]
FullChainFormatter = Callable[[list[FullChainMatrix], dict[str, str] | None], str | bytes]


def _get_test_records_formatter(output_format: str) -> TestRecordsFormatter:
    """Get the formatter function for test records by format name.

    Args:
        output_format: Output format: "html", "markdown", "json", "csv", or "xlsx".

    Returns:
        A callable that renders test records to string or bytes.

    Raises:
        ValueError: If the format is unknown.
    """
    if output_format == "html":
        from jamb.matrix.formats.html import render_test_records_html

        return render_test_records_html
    elif output_format == "markdown":
        from jamb.matrix.formats.markdown import render_test_records_markdown

        return render_test_records_markdown
    elif output_format == "json":
        from jamb.matrix.formats.json import render_test_records_json

        return render_test_records_json
    elif output_format == "csv":
        from jamb.matrix.formats.csv import render_test_records_csv

        return render_test_records_csv
    elif output_format == "xlsx":
        from jamb.matrix.formats.xlsx import render_test_records_xlsx

        return render_test_records_xlsx
    else:
        raise ValueError(f"Unknown format: {output_format}")


def _get_full_chain_formatter(output_format: str) -> FullChainFormatter:
    """Get the formatter function for full chain matrix by format name.

    Args:
        output_format: Output format: "html", "markdown", "json", "csv", or "xlsx".

    Returns:
        A callable that renders full chain matrices to string or bytes.

    Raises:
        ValueError: If the format is unknown.
    """
    if output_format == "html":
        from jamb.matrix.formats.html import render_full_chain_html

        return render_full_chain_html
    elif output_format == "markdown":
        from jamb.matrix.formats.markdown import render_full_chain_markdown

        return render_full_chain_markdown
    elif output_format == "json":
        from jamb.matrix.formats.json import render_full_chain_json

        return render_full_chain_json
    elif output_format == "csv":
        from jamb.matrix.formats.csv import render_full_chain_csv

        return render_full_chain_csv
    elif output_format == "xlsx":
        from jamb.matrix.formats.xlsx import render_full_chain_xlsx

        return render_full_chain_xlsx
    else:
        raise ValueError(f"Unknown format: {output_format}")


def build_test_id_mapping(coverage: dict[str, ItemCoverage]) -> dict[str, str]:
    """Build a mapping from test nodeid to TC ID.

    Uses the same sorting logic as build_test_records to ensure consistent
    TC numbering across test records and trace matrices.

    Args:
        coverage: Coverage data mapping UIDs to ItemCoverage.

    Returns:
        Dict mapping test nodeid to TC ID (e.g., "test.py::test_foo" -> "TC001").
    """
    sorted_nodeids, _, width = group_tests_by_nodeid(coverage)

    return {nodeid: f"TC{str(i + 1).zfill(width)}" for i, nodeid in enumerate(sorted_nodeids)}


def build_test_records(coverage: dict[str, ItemCoverage]) -> list[TestRecord]:
    """Transform coverage data to test-centric records.

    Collects all tests linked to items in the coverage data and produces
    a list of ``TestRecord`` objects sorted by the first requirement UID
    (alphabetically), with nodeid as tiebreaker.

    Args:
        coverage: Coverage data mapping UIDs to ItemCoverage.

    Returns:
        List of TestRecord objects, one per unique test.
    """
    sorted_nodeids, tests_by_nodeid, width = group_tests_by_nodeid(coverage)

    records = []
    for i, nodeid in enumerate(sorted_nodeids):
        links = tests_by_nodeid[nodeid]
        first = links[0]
        records.append(
            TestRecord(
                test_id=f"TC{str(i + 1).zfill(width)}",
                test_name=nodeid.split("::")[-1],
                test_nodeid=nodeid,
                outcome=first.test_outcome or "unknown",
                requirements=sorted(set(lk.item_uid for lk in links)),
                test_actions=first.test_actions,
                expected_results=first.expected_results,
                actual_results=first.actual_results,
                notes=first.notes,
                execution_timestamp=first.execution_timestamp,
            )
        )
    return records


def generate_test_records_matrix(
    records: list[TestRecord],
    output_path: str,
    output_format: str = "html",
    metadata: MatrixMetadata | None = None,
) -> None:
    """Generate test records matrix in specified format.

    Args:
        records: List of TestRecord objects to render.
        output_path: Path to write the output file.
        output_format: Output format: "html", "markdown", "json", "csv", or "xlsx".
        metadata: Optional matrix metadata for IEC 62304 5.7.5 compliance.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    formatter = _get_test_records_formatter(output_format)
    content = formatter(records, metadata)

    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


def generate_full_chain_matrix(
    coverage: dict[str, ItemCoverage],
    graph: TraceabilityGraph,
    output_path: str,
    output_format: str,
    trace_from: str,
    include_ancestors: bool = False,
    tc_mapping: dict[str, str] | None = None,
    trace_to_ignore: set[str] | None = None,
    all_test_links: dict[str, list[LinkedTest]] | None = None,
) -> None:
    """Generate full chain trace matrix starting from a document prefix.

    Creates a matrix showing complete traceability from a starting document
    through the hierarchy to tests. When the starting document has multiple
    child paths (diverging hierarchy), generates multiple tables.

    Args:
        coverage: Coverage data for test spec items.
        graph: The full traceability graph for traversal.
        output_path: Path to write the output file.
        output_format: Output format: "html", "markdown", "json", "csv", or "xlsx".
        trace_from: Starting document prefix (e.g., "UN", "SYS", "PRJ").
        include_ancestors: If True, add "Traces To" column showing ancestors.
        tc_mapping: Optional mapping from test nodeid to TC ID for display.
        trace_to_ignore: Set of document prefixes to exclude from the matrix.
        all_test_links: Optional dict mapping UIDs to LinkedTest lists for
            tests linked to higher-order items not in coverage.

    Raises:
        ValueError: If trace_from prefix is not found or format is unknown.
    """
    from jamb.matrix.chain_builder import build_full_chain_matrix

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Build TC mapping if not provided
    if tc_mapping is None:
        tc_mapping = build_test_id_mapping(coverage)

    # Build the full chain matrices
    matrices = build_full_chain_matrix(
        graph,
        coverage,
        trace_from,
        include_ancestors=include_ancestors,
        trace_to_ignore=trace_to_ignore,
        all_test_links=all_test_links,
    )

    formatter = _get_full_chain_formatter(output_format)
    content = formatter(matrices, tc_mapping)

    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
