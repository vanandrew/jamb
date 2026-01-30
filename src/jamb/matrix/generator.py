"""Generate traceability matrix in various formats."""

import re
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

# Pattern to extract number from TC ID like "TC001", "TC42"
TC_NUMBER_PATTERN = re.compile(r"^TC(\d+)$")


def _get_base_nodeid(nodeid: str) -> str:
    """Extract base test function nodeid without parametrize suffix.

    Args:
        nodeid: Full pytest nodeid like "test_foo.py::test_bar[param1]".

    Returns:
        Base nodeid without parameter suffix, e.g., "test_foo.py::test_bar".
    """
    bracket_idx = nodeid.find("[")
    if bracket_idx == -1:
        return nodeid
    return nodeid[:bracket_idx]


def _num_to_suffix(n: int) -> str:
    """Convert 0-indexed number to alphabetic suffix.

    Args:
        n: Zero-indexed number (0=a, 25=z, 26=aa, 27=ab, ...).

    Returns:
        Alphabetic suffix string.
    """
    result = []
    n += 1  # Convert to 1-indexed
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result.append(chr(ord("a") + remainder))
    return "".join(reversed(result))


def _extract_reserved_numbers(manual_tc_ids: dict[str, str]) -> set[int]:
    """Extract reserved TC numbers from manual IDs.

    Manual IDs matching pattern TC### reserve that number from auto-generation.

    Args:
        manual_tc_ids: Dict mapping nodeid to manual TC ID.

    Returns:
        Set of reserved TC numbers.
    """
    reserved: set[int] = set()
    for tc_id in manual_tc_ids.values():
        match = TC_NUMBER_PATTERN.match(tc_id)
        if match:
            reserved.add(int(match.group(1)))
    return reserved


def _group_nodeids_by_base(nodeids: list[str]) -> dict[str, list[str]]:
    """Group nodeids by their base test function.

    Parameterized tests share a base function and will be grouped together.

    Args:
        nodeids: List of pytest nodeids.

    Returns:
        Dict mapping base nodeid to list of full nodeids (sorted by param order).
    """
    groups: dict[str, list[str]] = {}
    for nodeid in nodeids:
        base = _get_base_nodeid(nodeid)
        groups.setdefault(base, []).append(nodeid)
    return groups


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


def build_test_id_mapping(
    coverage: dict[str, ItemCoverage],
    manual_tc_ids: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build a mapping from test nodeid to TC ID.

    Uses the same sorting logic as build_test_records to ensure consistent
    TC numbering across test records and trace matrices.

    For parameterized tests, all parameter variations share a base TC number
    with alphabetic suffixes (TC001a, TC001b, etc.).

    Manual TC IDs (from @pytest.mark.tc_id) take precedence. IDs matching
    pattern TC### reserve that number from auto-generation.

    Args:
        coverage: Coverage data mapping UIDs to ItemCoverage.
        manual_tc_ids: Optional dict mapping nodeid to manual TC ID.

    Returns:
        Dict mapping test nodeid to TC ID (e.g., "test.py::test_foo" -> "TC001").
    """
    if manual_tc_ids is None:
        manual_tc_ids = {}

    sorted_nodeids, tests_by_nodeid, _ = group_tests_by_nodeid(coverage)

    if not sorted_nodeids:
        return {}

    # Group nodeids by base function (for parameterized test detection)
    groups = _group_nodeids_by_base(sorted_nodeids)

    # Get reserved numbers from manual IDs
    reserved = _extract_reserved_numbers(manual_tc_ids)

    # Build mapping from base nodeid to manual TC ID (if any node in group has one)
    base_manual_ids: dict[str, str] = {}
    for nodeid, tc_id in manual_tc_ids.items():
        base = _get_base_nodeid(nodeid)
        base_manual_ids[base] = tc_id

    # Sort base nodeids using first nodeid in each group's sort key
    def base_sort_key(base: str) -> tuple[str, str]:
        # Use the first nodeid in the group for sorting
        first_nodeid = groups[base][0]
        # Get first requirement for this test (same logic as group_tests_by_nodeid)
        links = tests_by_nodeid.get(first_nodeid, [])
        reqs = sorted(set(lk.item_uid for lk in links))
        first_req = reqs[0] if reqs else ""
        return (first_req, first_nodeid)

    sorted_bases = sorted(groups.keys(), key=base_sort_key)

    # Calculate width based on number of test groups (not individual tests)
    width = max(3, len(str(len(sorted_bases))))

    # Assign TC IDs
    tc_mapping: dict[str, str] = {}
    auto_counter = 1

    for base in sorted_bases:
        nodeids_in_group = groups[base]
        is_parameterized = len(nodeids_in_group) > 1

        # Check if this group has a manual TC ID
        if base in base_manual_ids:
            base_tc_id = base_manual_ids[base]
        else:
            # Auto-assign: find next available number
            while auto_counter in reserved:
                auto_counter += 1
            base_tc_id = f"TC{str(auto_counter).zfill(width)}"
            auto_counter += 1

        if is_parameterized:
            # Assign suffixed IDs to each parameter variation
            for i, nodeid in enumerate(nodeids_in_group):
                suffix = _num_to_suffix(i)
                tc_mapping[nodeid] = f"{base_tc_id}{suffix}"
        else:
            # Single test, no suffix needed
            tc_mapping[nodeids_in_group[0]] = base_tc_id

    return tc_mapping


def build_test_records(
    coverage: dict[str, ItemCoverage],
    manual_tc_ids: dict[str, str] | None = None,
) -> list[TestRecord]:
    """Transform coverage data to test-centric records.

    Collects all tests linked to items in the coverage data and produces
    a list of ``TestRecord`` objects sorted by the first requirement UID
    (alphabetically), with nodeid as tiebreaker.

    For parameterized tests, all parameter variations share a base TC number
    with alphabetic suffixes (TC001a, TC001b, etc.).

    Args:
        coverage: Coverage data mapping UIDs to ItemCoverage.
        manual_tc_ids: Optional dict mapping nodeid to manual TC ID.

    Returns:
        List of TestRecord objects, one per unique test.
    """
    sorted_nodeids, tests_by_nodeid, _ = group_tests_by_nodeid(coverage)

    # Build TC ID mapping with manual IDs and parameterized support
    tc_mapping = build_test_id_mapping(coverage, manual_tc_ids)

    records = []
    for nodeid in sorted_nodeids:
        links = tests_by_nodeid[nodeid]
        first = links[0]
        records.append(
            TestRecord(
                test_id=tc_mapping.get(nodeid, "TC???"),
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
    elif isinstance(content, str):
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
    elif isinstance(content, str):
        path.write_text(content, encoding="utf-8")
