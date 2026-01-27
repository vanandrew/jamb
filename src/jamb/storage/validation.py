"""Validation module for jamb's native storage layer."""

from dataclasses import dataclass

from jamb.core.models import TraceabilityGraph
from jamb.storage.document_dag import DocumentDAG
from jamb.storage.items import compute_content_hash, read_item


@dataclass
class ValidationIssue:
    """A single validation issue."""

    level: str  # "error", "warning", "info"
    uid: str | None
    prefix: str | None
    message: str

    def __str__(self) -> str:
        parts = [f"[{self.level.upper()}]"]
        if self.uid:
            parts.append(self.uid)
        elif self.prefix:
            parts.append(self.prefix)
        parts.append(self.message)
        return " ".join(parts)


def validate(
    dag: DocumentDAG,
    graph: TraceabilityGraph,
    *,
    check_links: bool = True,
    check_suspect: bool = True,
    check_review: bool = True,
    check_children: bool = True,
    check_empty_docs: bool = True,
    check_empty_text: bool = True,
    check_self_links: bool = True,
    check_item_cycles: bool = True,
    check_unlinked: bool = True,
    skip_prefixes: list[str] | None = None,
) -> list[ValidationIssue]:
    """Run validation checks on the document tree.

    Args:
        dag: The document DAG.
        graph: The traceability graph with items.
        check_links: Check link validity and conformance.
        check_suspect: Check for suspect links (hash mismatch).
        check_review: Check review status.
        check_children: Check that non-leaf docs have children linking to them.
        check_empty_docs: Check for documents with no items.
        check_empty_text: Check for items with empty text.
        check_self_links: Check for items linking to themselves.
        check_item_cycles: Check for cycles in item-to-item links.
        check_unlinked: Check for unlinked normative items in child documents.
        skip_prefixes: Document prefixes to skip during validation.

    Returns:
        List of ValidationIssue objects.
    """
    issues: list[ValidationIssue] = []
    skip = set(skip_prefixes or [])

    # 1. DAG acyclicity
    cycle_errors = dag.validate_acyclic()
    for error in cycle_errors:
        issues.append(ValidationIssue("error", None, None, error))

    # 2-3. Link validity and conformance
    if check_links:
        issues.extend(_check_links(dag, graph, skip, check_self_links))

    # 4. Suspect link detection
    if check_suspect:
        issues.extend(_check_suspect_links(dag, graph, skip))

    # 6. Review status
    if check_review:
        issues.extend(_check_review_status(graph, skip))

    # 7. Child link check
    if check_children:
        issues.extend(_check_children(dag, graph, skip))

    # 8. Empty documents
    if check_empty_docs:
        issues.extend(_check_empty_documents(dag, graph, skip))

    # 9. Empty text
    if check_empty_text:
        issues.extend(_check_empty_text(graph, skip))

    # 11. Item link cycles
    if check_item_cycles:
        issues.extend(_check_item_link_cycles(graph, skip))

    # 12. Unlinked normative items in child docs
    if check_unlinked:
        issues.extend(_check_unlinked_items(dag, graph, skip))

    return issues


def _check_links(
    dag: DocumentDAG,
    graph: TraceabilityGraph,
    skip: set[str],
    check_self_links: bool = True,
) -> list[ValidationIssue]:
    """Check link validity and conformance."""
    issues = []

    for uid, item in graph.items.items():
        if item.document_prefix in skip:
            continue
        if not item.active:
            continue

        parents = (
            dag.get_parents(item.document_prefix)
            if item.document_prefix in dag.documents
            else []
        )

        # Check non-normative item has links
        if item.type != "requirement" and item.links:
            issues.append(
                ValidationIssue(
                    "warning",
                    uid,
                    item.document_prefix,
                    "non-normative item has links",
                )
            )

        for link in item.links:
            # Check self-link
            if check_self_links and link == uid:
                issues.append(
                    ValidationIssue(
                        "warning",
                        uid,
                        item.document_prefix,
                        "links to itself",
                    )
                )
                continue

            # Check link target exists
            if link not in graph.items:
                issues.append(
                    ValidationIssue(
                        "error",
                        uid,
                        item.document_prefix,
                        f"links to non-existent item: {link}",
                    )
                )
                continue

            # Check link to inactive item
            target = graph.items[link]
            if not target.active:
                issues.append(
                    ValidationIssue(
                        "error",
                        uid,
                        item.document_prefix,
                        f"links to inactive item: {link}",
                    )
                )
                continue

            # Check link to non-normative item
            if target.type != "requirement":
                issues.append(
                    ValidationIssue(
                        "warning",
                        uid,
                        item.document_prefix,
                        f"links to non-normative item: {link}",
                    )
                )

            # Check link conformance (links to parent document)
            if parents:
                if target.document_prefix not in parents:
                    issues.append(
                        ValidationIssue(
                            "warning",
                            uid,
                            item.document_prefix,
                            f"links to {link} in document {target.document_prefix}, "
                            f"which is not a parent document "
                            f"(expected: {', '.join(parents)})",
                        )
                    )

    return issues


def _check_suspect_links(
    dag: DocumentDAG, graph: TraceabilityGraph, skip: set[str]
) -> list[ValidationIssue]:
    """Check for suspect links by comparing stored hashes to current content."""
    issues = []

    for uid, item in graph.items.items():
        if item.document_prefix in skip:
            continue
        if not item.active:
            continue

        # Read raw item to get link hashes
        doc_path = dag.document_paths.get(item.document_prefix)
        if doc_path is None:
            continue

        item_path = doc_path / f"{uid}.yml"
        if not item_path.exists():
            continue

        raw_item = read_item(item_path, item.document_prefix)
        link_hashes = raw_item.get("link_hashes", {})

        for link_uid, stored_hash in link_hashes.items():
            if link_uid not in graph.items:
                continue

            if not graph.items[link_uid].active:
                continue

            # Compute current hash of linked item
            target = graph.items[link_uid]
            target_data = {
                "text": target.text,
                "header": target.header,
                "links": target.links,
                "type": target.type,
            }
            current_hash = compute_content_hash(target_data)

            if stored_hash != current_hash:
                issues.append(
                    ValidationIssue(
                        "warning",
                        uid,
                        item.document_prefix,
                        f"suspect link to {link_uid} (content may have changed)",
                    )
                )

        # Check for links with no stored hash
        for link_uid in item.links:
            if link_uid in link_hashes:
                continue  # already checked above
            if link_uid not in graph.items:
                continue  # broken link, caught by _check_links
            if not graph.items[link_uid].active:
                continue
            issues.append(
                ValidationIssue(
                    "warning",
                    uid,
                    item.document_prefix,
                    f"link to {link_uid} has no stored hash (not verified)",
                )
            )

    return issues


def _check_review_status(
    graph: TraceabilityGraph, skip: set[str]
) -> list[ValidationIssue]:
    """Check that items have been reviewed."""
    issues = []

    for uid, item in graph.items.items():
        if item.document_prefix in skip:
            continue
        if not item.active:
            continue
        if item.type != "requirement":
            continue

        if not item.reviewed:
            issues.append(
                ValidationIssue(
                    "warning", uid, item.document_prefix, "has not been reviewed"
                )
            )
        else:
            item_data = {
                "text": item.text,
                "header": item.header,
                "links": item.links,
                "type": item.type,
            }
            current_hash = compute_content_hash(item_data)
            if item.reviewed != current_hash:
                issues.append(
                    ValidationIssue(
                        "warning",
                        uid,
                        item.document_prefix,
                        "has been modified since last review",
                    )
                )

    return issues


def _check_children(
    dag: DocumentDAG, graph: TraceabilityGraph, skip: set[str]
) -> list[ValidationIssue]:
    """Check that non-leaf document items have children linking to them."""
    issues = []
    leaf_docs = set(dag.get_leaf_documents())

    # Build set of UIDs that are linked to (only from active items)
    linked_to: set[str] = set()
    for item in graph.items.values():
        if not item.active:
            continue
        for link in item.links:
            linked_to.add(link)

    for uid, item in graph.items.items():
        if item.document_prefix in skip:
            continue
        if not item.active:
            continue
        if item.type != "requirement":
            continue
        if item.document_prefix in leaf_docs:
            continue

        # Check if any child document item links to this item
        if uid not in linked_to:
            issues.append(
                ValidationIssue(
                    "warning",
                    uid,
                    item.document_prefix,
                    "has no children linking to it from child documents",
                )
            )

    return issues


def _check_empty_documents(
    dag: DocumentDAG, graph: TraceabilityGraph, skip: set[str]
) -> list[ValidationIssue]:
    """Check for documents that contain no items."""
    issues = []

    for prefix in dag.documents:
        if prefix in skip:
            continue
        items = [i for i in graph.items.values() if i.document_prefix == prefix]
        if not items:
            issues.append(
                ValidationIssue(
                    "warning",
                    None,
                    prefix,
                    "document contains no items",
                )
            )

    return issues


def _check_empty_text(
    graph: TraceabilityGraph, skip: set[str]
) -> list[ValidationIssue]:
    """Check for items with empty or whitespace-only text."""
    issues = []

    for uid, item in graph.items.items():
        if item.document_prefix in skip:
            continue
        if not item.active:
            continue
        if not item.text or not item.text.strip():
            issues.append(
                ValidationIssue(
                    "warning",
                    uid,
                    item.document_prefix,
                    "has empty text",
                )
            )

    return issues


def _check_item_link_cycles(
    graph: TraceabilityGraph, skip: set[str]
) -> list[ValidationIssue]:
    """Detect cycles in item-to-item link graph using DFS."""
    issues = []
    reported_cycles: set[frozenset[str]] = set()

    # Build adjacency: item -> items it links to (only active, non-skipped)
    active_uids = {
        uid
        for uid, item in graph.items.items()
        if item.active and item.document_prefix not in skip
    }

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {uid: WHITE for uid in active_uids}
    path: list[str] = []

    def dfs(uid: str) -> None:
        color[uid] = GRAY
        path.append(uid)

        item = graph.items[uid]
        for link in item.links:
            if link not in active_uids:
                continue
            if color[link] == GRAY:
                # Found a cycle — extract it
                cycle_start = path.index(link)
                cycle_members = frozenset(path[cycle_start:])
                if cycle_members not in reported_cycles:
                    reported_cycles.add(cycle_members)
                    cycle_uids = path[cycle_start:]
                    issues.append(
                        ValidationIssue(
                            "warning",
                            link,
                            graph.items[link].document_prefix,
                            f"cycle in item links: {' -> '.join(cycle_uids)} -> {link}",
                        )
                    )
            elif color[link] == WHITE:
                dfs(link)

        path.pop()
        color[uid] = BLACK

    for uid in active_uids:
        if color[uid] == WHITE:
            dfs(uid)

    return issues


def _check_unlinked_items(
    dag: DocumentDAG, graph: TraceabilityGraph, skip: set[str]
) -> list[ValidationIssue]:
    """Check for normative non-derived items in child documents with no links."""
    issues = []

    for uid, item in graph.items.items():
        if item.document_prefix in skip:
            continue
        if not item.active:
            continue
        if item.type != "requirement":
            continue
        if item.derived:
            continue

        # Check if this document has parents (i.e., it's a child document)
        parents = (
            dag.get_parents(item.document_prefix)
            if item.document_prefix in dag.documents
            else []
        )
        if not parents:
            continue

        if not item.links:
            issues.append(
                ValidationIssue(
                    "warning",
                    uid,
                    item.document_prefix,
                    "normative non-derived item has no links to parent document",
                )
            )

    return issues
