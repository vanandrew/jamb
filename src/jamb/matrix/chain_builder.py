"""Build full chain trace matrices from a starting document."""

import warnings
from collections.abc import Iterator

from jamb.core.models import (
    ChainRow,
    FullChainMatrix,
    Item,
    ItemCoverage,
    LinkedTest,
    TraceabilityGraph,
)

# Maximum recursion depth for traversals to prevent stack overflow from cycles
MAX_RECURSION_DEPTH = 100


def get_document_paths(
    graph: TraceabilityGraph,
    start_prefix: str,
) -> list[list[str]]:
    """Get all document paths from start to leaves.

    Discovers all unique paths through the document hierarchy starting
    from the given prefix and ending at leaf documents.

    Args:
        graph: The traceability graph containing document relationships.
        start_prefix: The document prefix to start from (e.g., "UN", "PRJ").

    Returns:
        List of document paths, each path being a list of prefixes.
        E.g., start_prefix="PRJ" -> [
            ["PRJ", "UN", "SYS", "SRS"],
            ["PRJ", "HAZ", "RC", "SRS"]
        ]
        E.g., start_prefix="UN" -> [["UN", "SYS", "SRS"]]

    Raises:
        ValueError: If start_prefix is not found in the document hierarchy.
    """
    if start_prefix not in graph.document_parents:
        raise ValueError(
            f"Document '{start_prefix}' not found in hierarchy. "
            f"Available: {', '.join(sorted(graph.document_parents.keys()))}"
        )

    leaf_docs = set(graph.get_leaf_documents())
    paths: list[list[str]] = []

    def traverse(current: str, path: list[str], depth: int = 0) -> None:
        """Recursively traverse document hierarchy to find all paths."""
        if depth >= MAX_RECURSION_DEPTH:
            warnings.warn(
                f"Maximum recursion depth ({MAX_RECURSION_DEPTH}) exceeded "
                f"while traversing document hierarchy. Possible cycle at '{current}'.",
                stacklevel=3,
            )
            return

        current_path = path + [current]

        # Get children of this document
        children = graph.get_document_children(current)

        if not children or current in leaf_docs:
            # This is a leaf or has no children - complete path
            paths.append(current_path)
        else:
            # Continue traversing
            for child in children:
                traverse(child, current_path, depth + 1)

    traverse(start_prefix, [])
    return paths


def _add_tests_from_item(
    item: Item,
    coverage: dict[str, ItemCoverage],
    all_test_links: dict[str, list[LinkedTest]] | None,
    tests: list[LinkedTest],
    seen_nodeids: set[str],
) -> None:
    """Add tests from an item to the collection (mutates tests and seen_nodeids).

    Args:
        item: The item to collect tests from.
        coverage: Coverage data for test lookups.
        all_test_links: Optional dict mapping UIDs to LinkedTest lists.
        tests: List to append tests to (mutated).
        seen_nodeids: Set of already-seen nodeids (mutated).
    """
    # Check direct links first
    if all_test_links and item.uid in all_test_links:
        for lt in all_test_links[item.uid]:
            if lt.test_nodeid not in seen_nodeids:
                tests.append(lt)
                seen_nodeids.add(lt.test_nodeid)
    # Then check coverage
    if item.uid in coverage:
        for lt in coverage[item.uid].linked_tests:
            if lt.test_nodeid not in seen_nodeids:
                tests.append(lt)
                seen_nodeids.add(lt.test_nodeid)


def _collect_tests(
    graph: TraceabilityGraph,
    item: Item | None,
    coverage: dict[str, ItemCoverage],
    all_test_links: dict[str, list[LinkedTest]] | None = None,
) -> list[LinkedTest]:
    """Collect tests from an item and its descendants.

    This unified function replaces both _collect_descendant_tests and
    _collect_tests by collecting tests from the given item and
    all its descendants.

    Args:
        graph: The traceability graph.
        item: The item to collect tests from. If None, returns empty list.
        coverage: Coverage data for test lookups.
        all_test_links: Optional dict mapping UIDs to LinkedTest lists for
            tests linked to higher-order items not in coverage.

    Returns:
        List of all LinkedTest objects from this item and its descendants.
    """
    tests: list[LinkedTest] = []
    seen_nodeids: set[str] = set()

    if not item:
        return tests

    # Add tests from the item itself
    _add_tests_from_item(item, coverage, all_test_links, tests, seen_nodeids)

    # Add tests from all descendants
    for desc in graph.get_descendants(item.uid):
        _add_tests_from_item(desc, coverage, all_test_links, tests, seen_nodeids)

    return tests


def _calculate_status_from_tests(
    tests: list[LinkedTest],
    item: Item | None = None,
    graph: TraceabilityGraph | None = None,
) -> str:
    """Calculate status from a list of tests.

    Args:
        tests: List of LinkedTest objects.
        item: Optional item for testability check when no tests.
        graph: Optional graph for checking descendant testability.

    Returns:
        Status: "Passed", "Failed", "Partial", "Skipped", "Not Covered", or "N/A".
    """
    if not tests:
        # Check if item or descendants are testable
        if item and not item.testable:
            # Item is not testable - check if any descendants are testable
            if graph:
                for desc in graph.get_descendants(item.uid):
                    if desc.testable:
                        # Found a testable descendant, so item should be covered
                        return "Not Covered"
                # No testable descendants found
                return "N/A"
            else:
                # No graph to check descendants, assume N/A for non-testable item
                return "N/A"
        return "Not Covered"

    # Check test outcomes
    has_passed = False
    has_failed = False
    has_skipped = False

    for test in tests:
        if test.test_outcome == "passed":
            has_passed = True
        elif test.test_outcome in ("failed", "error"):
            has_failed = True
        elif test.test_outcome == "skipped":
            has_skipped = True

    if has_failed and has_passed:
        return "Partial"
    elif has_failed:
        return "Failed"
    elif has_passed:
        return "Passed"
    elif has_skipped:
        # All tests are skipped (none passed, none failed)
        return "Skipped"
    else:
        # All tests have unknown outcome
        return "Partial"


def calculate_rollup_status(
    graph: TraceabilityGraph,
    item: Item,
    coverage: dict[str, ItemCoverage],
    all_test_links: dict[str, list[LinkedTest]] | None = None,
) -> tuple[str, list[LinkedTest]]:
    """Calculate aggregated status and tests for an item.

    Status is determined by examining the item and all its descendants:
    - "Passed": All descendants with tests have all tests passing
    - "Failed": Any descendant has a failing test
    - "Partial": Mix of passed, failed, or uncovered
    - "Not Covered": No descendants have any tests
    - "N/A": Item is not testable (and has no testable descendants)

    This function uses `_collect_tests()` to gather tests from the item
    and all its descendants, then delegates to `_calculate_status_from_tests()`
    for status determination.

    Args:
        graph: The traceability graph.
        item: The item to calculate status for.
        coverage: Coverage data for test lookups.
        all_test_links: Optional dict mapping UIDs to LinkedTest lists for
            tests linked to higher-order items not in coverage.

    Returns:
        Tuple of (status string, list of all descendant tests).
    """
    tests = _collect_tests(graph, item, coverage, all_test_links)
    status = _calculate_status_from_tests(tests, item, graph)
    return status, tests


def _get_ancestor_uids(
    chain: dict[str, Item | None],
    doc_path: list[str],
    graph: TraceabilityGraph,
    trace_to_ignore: set[str],
    include_ancestors: bool,
) -> list[str]:
    """Get filtered ancestor UIDs for the starting item in a chain.

    Args:
        chain: The chain mapping document prefixes to items.
        doc_path: The document path from start to leaf.
        graph: The traceability graph.
        trace_to_ignore: Set of document prefixes to exclude.
        include_ancestors: Whether to include ancestors at all.

    Returns:
        List of ancestor UIDs, filtered by trace_to_ignore.
        Returns empty list if include_ancestors is False.
    """
    if not include_ancestors:
        return []
    ancestor_uids = []
    start_item = chain.get(doc_path[0])
    if start_item:
        for anc in graph.get_ancestors(start_item.uid):
            if anc.document_prefix not in trace_to_ignore:
                ancestor_uids.append(anc.uid)
    return ancestor_uids


def _build_chain_rows(
    graph: TraceabilityGraph,
    coverage: dict[str, ItemCoverage],
    doc_path: list[str],
    include_ancestors: bool,
    trace_to_ignore: set[str] | None = None,
    all_test_links: dict[str, list[LinkedTest]] | None = None,
) -> list[ChainRow]:
    """Build chain rows for a single document path.

    Args:
        graph: The traceability graph.
        coverage: Coverage data.
        doc_path: Document path from start to leaf, e.g., ["UN", "SYS", "SRS"].
        include_ancestors: Whether to include ancestor UIDs.
        trace_to_ignore: Set of document prefixes to exclude from output.
        all_test_links: Optional dict mapping UIDs to LinkedTest lists for
            tests linked to higher-order items not in coverage.

    Returns:
        List of ChainRow objects representing all trace chains in this path.
    """
    if not doc_path:
        return []

    trace_to_ignore = trace_to_ignore or set()

    start_prefix = doc_path[0]
    rows: list[ChainRow] = []

    # Get all items at the starting level
    start_items = graph.get_items_by_document(start_prefix)
    if not start_items:
        return []

    # Sort items by UID for consistent ordering
    start_items.sort(key=lambda i: i.uid)

    def build_chains(
        current_level: int,
        parent_chain: dict[str, Item | None],
        current_items: list[Item],
    ) -> Iterator[ChainRow]:
        """Recursively build chain rows."""
        current_prefix = doc_path[current_level]
        is_leaf = current_level == len(doc_path) - 1

        for item in sorted(current_items, key=lambda i: i.uid):
            # Create chain with this item
            chain = dict(parent_chain)
            chain[current_prefix] = item

            if is_leaf:
                # This is a leaf level - create row
                leaf_cov = coverage.get(item.uid)

                # Collect tests from the leaf item and its descendants only
                tests = _collect_tests(graph, item, coverage, all_test_links)
                status = _calculate_status_from_tests(tests, item, graph)

                ancestor_uids = _get_ancestor_uids(chain, doc_path, graph, trace_to_ignore, include_ancestors)

                yield ChainRow(
                    chain=chain,
                    leaf_coverage=leaf_cov,
                    rollup_status=status,
                    descendant_tests=tests,
                    ancestor_uids=ancestor_uids,
                )
            else:
                # Get children at next level
                next_prefix = doc_path[current_level + 1]
                children = graph.get_children_from_document(item.uid, next_prefix)

                # Check if this item has direct test links (tests that skip children)
                has_direct_tests = all_test_links and item.uid in all_test_links and len(all_test_links[item.uid]) > 0

                if children:
                    # If item has direct tests, create a gap row for them first
                    # This handles tests that link to SYS001 directly (skipping SRS)
                    if has_direct_tests and all_test_links:
                        # Collect ONLY direct tests on this item, not from children
                        direct_tests = list(all_test_links[item.uid])
                        status = _calculate_status_from_tests(direct_tests, item, graph)

                        ancestor_uids = _get_ancestor_uids(chain, doc_path, graph, trace_to_ignore, include_ancestors)

                        yield ChainRow(
                            chain=chain,
                            leaf_coverage=None,
                            rollup_status=status,
                            descendant_tests=direct_tests,
                            ancestor_uids=ancestor_uids,
                        )

                    # Recurse into children
                    yield from build_chains(current_level + 1, chain, children)
                else:
                    # No children at next level - create a row with gaps
                    # Collect tests from this item and its descendants only
                    tests = _collect_tests(graph, item, coverage, all_test_links)
                    status = _calculate_status_from_tests(tests, item, graph)

                    ancestor_uids = _get_ancestor_uids(chain, doc_path, graph, trace_to_ignore, include_ancestors)

                    yield ChainRow(
                        chain=chain,
                        leaf_coverage=None,
                        rollup_status=status,
                        descendant_tests=tests,
                        ancestor_uids=ancestor_uids,
                    )

    # Initialize chain with None for all prefixes
    initial_chain: dict[str, Item | None] = {p: None for p in doc_path}
    rows = list(build_chains(0, initial_chain, start_items))

    return rows


def _calculate_summary(rows: list[ChainRow]) -> dict[str, int]:
    """Calculate summary statistics from chain rows.

    Args:
        rows: List of ChainRow objects.

    Returns:
        Dict with counts for total, passed, failed, partial, skipped, not_covered, na.
    """
    summary = {
        "total": len(rows),
        "passed": 0,
        "failed": 0,
        "partial": 0,
        "skipped": 0,
        "not_covered": 0,
        "na": 0,
    }

    for row in rows:
        status = row.rollup_status.lower().replace(" ", "_")
        if status == "passed":
            summary["passed"] += 1
        elif status == "failed":
            summary["failed"] += 1
        elif status == "partial":
            summary["partial"] += 1
        elif status == "skipped":
            summary["skipped"] += 1
        elif status == "not_covered":
            summary["not_covered"] += 1
        elif status == "n/a":
            summary["na"] += 1

    return summary


def _detect_orphaned_items(
    graph: TraceabilityGraph,
    matrices: list[FullChainMatrix],
    doc_paths: list[list[str]],
) -> list[str]:
    """Detect items that exist in the graph but don't appear in any trace chain.

    These are items that have incomplete trace chains - they exist but
    don't trace back to the root document.

    Args:
        graph: The traceability graph.
        matrices: List of generated FullChainMatrix objects.
        doc_paths: All document paths from root to leaves.

    Returns:
        List of UIDs that don't appear in any trace chain.
    """
    # Collect all item UIDs that appear in any chain row
    items_in_chains: set[str] = set()
    for matrix in matrices:
        for row in matrix.rows:
            for item in row.chain.values():
                if item is not None:
                    items_in_chains.add(item.uid)

    # Get all documents that should be in the trace (union of all paths)
    docs_in_trace: set[str] = set()
    for path in doc_paths:
        docs_in_trace.update(path)

    # Find items that exist in these documents but don't appear in any chain
    # Only consider requirement type items (not headings/info)
    orphaned: list[str] = []
    for prefix in docs_in_trace:
        for item in graph.get_items_by_document(prefix):
            if item.type == "requirement" and item.active and item.uid not in items_in_chains:
                orphaned.append(item.uid)

    return orphaned


def build_full_chain_matrix(
    graph: TraceabilityGraph,
    coverage: dict[str, ItemCoverage],
    start_prefix: str,
    include_ancestors: bool = False,
    trace_to_ignore: set[str] | None = None,
    all_test_links: dict[str, list[LinkedTest]] | None = None,
) -> list[FullChainMatrix]:
    """Build full chain matrices from starting document.

    Returns one FullChainMatrix per unique document path from the
    starting document to leaf documents.

    Args:
        graph: The traceability graph.
        coverage: Coverage data mapping UIDs to ItemCoverage.
        start_prefix: Document prefix to start tracing from.
        include_ancestors: Whether to include "Traces To" column.
        trace_to_ignore: Set of document prefixes to exclude from output.
            Documents in this set will be filtered from the hierarchy columns
            and from the "Traces To" ancestor UIDs.
        all_test_links: Optional dict mapping UIDs to LinkedTest lists for
            tests linked to higher-order items not in coverage.

    Returns:
        List of FullChainMatrix objects, one per unique path.
        If start document has diverging children, returns multiple matrices.

    Raises:
        ValueError: If start_prefix is not found in document hierarchy.
    """
    trace_to_ignore = trace_to_ignore or set()

    # Get all document paths from start
    doc_paths = get_document_paths(graph, start_prefix)

    matrices: list[FullChainMatrix] = []

    for doc_path in doc_paths:
        # Filter out ignored documents from the path
        filtered_path = [p for p in doc_path if p not in trace_to_ignore]

        # Skip paths where all documents are filtered out
        if not filtered_path:
            warnings.warn(
                f"All documents filtered from path: {' -> '.join(doc_path)}. Skipping this path.",
                stacklevel=2,
            )
            continue

        # Build path name (e.g., "PRJ -> UN -> SYS -> SRS")
        path_name = " -> ".join(filtered_path)

        # Build rows for this path (use full path for traversal, filter later)
        rows = _build_chain_rows(
            graph,
            coverage,
            doc_path,
            include_ancestors,
            trace_to_ignore,
            all_test_links,
        )

        # Filter chain keys to remove ignored documents
        for row in rows:
            row.chain = {k: v for k, v in row.chain.items() if k not in trace_to_ignore}

        # Calculate summary
        summary = _calculate_summary(rows)

        matrices.append(
            FullChainMatrix(
                path_name=path_name,
                document_hierarchy=filtered_path,
                rows=rows,
                summary=summary,
                include_ancestors=include_ancestors,
            )
        )

    if not matrices:
        warnings.warn(
            "No traceability matrices generated. All document paths were filtered by trace_to_ignore or had no items.",
            stacklevel=2,
        )

    # Detect items that exist but don't appear in any trace chain
    orphaned = _detect_orphaned_items(graph, matrices, doc_paths)
    if orphaned:
        sample = orphaned[:5]
        msg = f"Found {len(orphaned)} items with incomplete trace chains: {', '.join(sample)}"
        if len(orphaned) > 5:
            msg += f" (and {len(orphaned) - 5} more)"
        warnings.warn(
            msg + ". These items don't trace back to the root document.",
            stacklevel=2,
        )

    return matrices
