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
    check_levels: bool = True,
    check_suspect: bool = True,
    check_review: bool = True,
    check_children: bool = True,
    skip_prefixes: list[str] | None = None,
) -> list[ValidationIssue]:
    """Run validation checks on the document tree.

    Args:
        dag: The document DAG.
        graph: The traceability graph with items.
        check_links: Check link validity and conformance.
        check_levels: Check level ordering within documents.
        check_suspect: Check for suspect links (hash mismatch).
        check_review: Check review status.
        check_children: Check that non-leaf docs have children linking to them.
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
        issues.extend(_check_links(dag, graph, skip))

    # 4. Level ordering
    if check_levels:
        issues.extend(_check_levels(graph, skip))

    # 5. Suspect link detection
    if check_suspect:
        issues.extend(_check_suspect_links(dag, graph, skip))

    # 6. Review status
    if check_review:
        issues.extend(_check_review_status(graph, skip))

    # 7. Child link check
    if check_children:
        issues.extend(_check_children(dag, graph, skip))

    return issues


def _check_links(
    dag: DocumentDAG, graph: TraceabilityGraph, skip: set[str]
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

        for link in item.links:
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

            # Check link conformance (links to parent document)
            if parents:
                target = graph.items[link]
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


def _check_levels(graph: TraceabilityGraph, skip: set[str]) -> list[ValidationIssue]:
    """Check level ordering within documents."""
    issues = []

    doc_items: dict[str, list] = {}
    for item in graph.items.values():
        if item.document_prefix in skip:
            continue
        if not item.active:
            continue
        doc_items.setdefault(item.document_prefix, []).append(item)

    for prefix, items in doc_items.items():
        sorted_items = sorted(items, key=lambda i: i.uid)
        prev_level = 0.0
        for item in sorted_items:
            level = item.level if item.level else 1.0
            if level > prev_level + 1.0 and prev_level > 0:
                issues.append(
                    ValidationIssue(
                        "warning",
                        item.uid,
                        prefix,
                        f"level {level} skips from previous level {prev_level}",
                    )
                )
            prev_level = level

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

            # Compute current hash of linked item
            target = graph.items[link_uid]
            target_data = {
                "text": target.text,
                "header": target.header,
                "links": target.links,
                "type": target.type,
                "level": target.level,
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

    return issues


def _check_children(
    dag: DocumentDAG, graph: TraceabilityGraph, skip: set[str]
) -> list[ValidationIssue]:
    """Check that non-leaf document items have children linking to them."""
    issues = []
    leaf_docs = set(dag.get_leaf_documents())

    # Build set of UIDs that are linked to
    linked_to: set[str] = set()
    for item in graph.items.values():
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
