"""Validation module for jamb's native storage layer."""

import logging
from dataclasses import dataclass
from typing import Literal

from jamb.core.models import TraceabilityGraph
from jamb.storage.document_dag import DocumentDAG
from jamb.storage.items import compute_content_hash, read_item

logger = logging.getLogger("jamb")


@dataclass
class ValidationIssue:
    """A single validation issue.

    Attributes:
        level (str): Severity — ``"error"``, ``"warning"``, or ``"info"``.
        uid (str | None): UID of the item involved, or ``None`` for document-level
            issues.
        prefix (str | None): Document prefix involved, or ``None`` when not
            applicable.
        message (str): Human-readable description of the issue.
    """

    level: Literal["error", "warning", "info"]
    uid: str | None
    prefix: str | None
    message: str

    def __str__(self) -> str:
        """Return a human-readable representation of the validation issue."""
        parts = [f"[{self.level.upper()}]"]
        if self.uid and self.prefix:
            parts.append(f"{self.prefix}:{self.uid}")
        elif self.uid:
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

    # 2. Link validity and conformance
    if check_links:
        issues.extend(_check_links(dag, graph, skip, check_self_links))

    # 3. Suspect link detection
    if check_suspect:
        issues.extend(_check_suspect_links(dag, graph, skip))

    # 4. Review status
    if check_review:
        issues.extend(_check_review_status(graph, skip))

    # 5. Child link check
    if check_children:
        issues.extend(_check_children(dag, graph, skip))

    # 6. Empty documents
    if check_empty_docs:
        issues.extend(_check_empty_documents(dag, graph, skip))

    # 7. Empty text
    if check_empty_text:
        issues.extend(_check_empty_text(graph, skip))

    # 8. Item link cycles
    if check_item_cycles:
        issues.extend(_check_item_link_cycles(graph, skip))

    # 9. Unlinked normative items in child docs
    if check_unlinked:
        issues.extend(_check_unlinked_items(dag, graph, skip))

    return issues


def _check_links(
    dag: DocumentDAG,
    graph: TraceabilityGraph,
    skip: set[str],
    check_self_links: bool = True,
) -> list[ValidationIssue]:
    """Check link validity and conformance.

    Validates every link on every active, non-skipped item in the
    traceability graph.  The following conditions are flagged:

    * Self-links (item links to its own UID).
    * Links to non-existent items.
    * Links to inactive items.
    * Links from non-normative items (items that have links but are not
      of type ``requirement``).
    * Links to non-normative target items.
    * Links that violate parent-document conformance (the target item
      belongs to a document that is not a parent of the source item's
      document in the DAG).

    Args:
        dag: The document DAG used to determine parent-child document
            relationships.
        graph: The traceability graph containing all items and their
            links.
        skip: Set of document prefixes to exclude from validation.
        check_self_links: Whether to flag items that link to themselves.

    Returns:
        A list of ``ValidationIssue`` objects, one per detected problem.
        Self-links, links to inactive items, and links to non-existent
        items are reported as errors or warnings depending on severity.
    """
    issues = []

    for uid, item in graph.items.items():
        if item.document_prefix in skip:
            continue
        if not item.active:
            continue

        parents = dag.get_parents(item.document_prefix) if item.document_prefix in dag.documents else []

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


def _check_suspect_links(dag: DocumentDAG, graph: TraceabilityGraph, skip: set[str]) -> list[ValidationIssue]:
    """Check for suspect links by comparing stored hashes to current content.

    A link is considered *suspect* when the content hash stored at the
    time the link was created no longer matches the current content hash
    of the target item.  This indicates that the target item has been
    modified since the link was last verified.  Links that have no
    stored hash at all are also flagged, since they cannot be verified.

    For each active, non-skipped item the function reads the raw YAML
    file to obtain ``link_hashes``, recomputes the content hash of every
    linked target, and compares the two values.

    Args:
        dag: The document DAG, used to resolve file paths for raw item
            data.
        graph: The traceability graph containing all items and their
            links.
        skip: Set of document prefixes to exclude from validation.

    Returns:
        A list of ``ValidationIssue`` objects with level ``warning`` for
        each suspect link (hash mismatch) and each link missing a stored
        hash.
    """
    issues = []

    for uid, item in graph.items.items():
        if item.document_prefix in skip:
            continue
        if not item.active:
            continue

        # Read raw item to get link hashes
        doc_path = dag.document_paths.get(item.document_prefix)
        if doc_path is None:
            logger.warning("Document path not found for prefix: %s", item.document_prefix)
            continue

        item_path = doc_path / f"{uid}.yml"
        if not item_path.exists():
            logger.warning("Item file not found: %s", item_path)
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
                        f"suspect link to {link_uid} (content may have changed; run 'jamb review clear' to re-verify)",
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
                    f"link to {link_uid} has no stored hash (run 'jamb review clear' to verify links)",
                )
            )

    return issues


def _check_review_status(graph: TraceabilityGraph, skip: set[str]) -> list[ValidationIssue]:
    """Check that items have been reviewed and review hash matches current content.

    Ensures every active normative (``requirement``) item has been
    reviewed.  Two conditions are flagged:

    * The item has never been reviewed (``reviewed`` field is falsy).
    * The item has been modified since its last review, detected by
      comparing the stored review hash against a freshly computed
      content hash.

    Args:
        graph: The traceability graph containing all items.
        skip: Set of document prefixes to exclude from validation.

    Returns:
        A list of ``ValidationIssue`` objects with level ``warning`` for
        each unreviewed or stale-reviewed item.
    """
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
                    "warning",
                    uid,
                    item.document_prefix,
                    "has not been reviewed (run 'jamb review mark' to mark as reviewed)",
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
                        "has been modified since last review (run 'jamb review mark' to re-approve)",
                    )
                )

    return issues


def _check_children(dag: DocumentDAG, graph: TraceabilityGraph, skip: set[str]) -> list[ValidationIssue]:
    """Check that non-leaf document items have children linking to them.

    For every active normative item that belongs to a non-leaf document
    (i.e., a document that has child documents in the DAG), verifies
    that at least one active item in the graph links to it.  Items in
    leaf documents are excluded because they have no child documents
    from which links would originate.

    Args:
        dag: The document DAG, used to identify leaf documents.
        graph: The traceability graph containing all items and their
            links.
        skip: Set of document prefixes to exclude from validation.

    Returns:
        A list of ``ValidationIssue`` objects with level ``warning`` for
        each non-leaf-document item that has no children linking to it.
    """
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


def _check_empty_documents(dag: DocumentDAG, graph: TraceabilityGraph, skip: set[str]) -> list[ValidationIssue]:
    """Check for documents that contain no items.

    Iterates over every document registered in the DAG and flags those
    that have zero items in the traceability graph.  Empty documents
    may indicate a misconfiguration or an incomplete import.

    Args:
        dag: The document DAG, providing the set of known document
            prefixes.
        graph: The traceability graph containing all items.
        skip: Set of document prefixes to exclude from validation.

    Returns:
        A list of ``ValidationIssue`` objects with level ``warning`` for
        each document that contains no items.
    """
    issues = []

    prefixes_with_items = {item.document_prefix for item in graph.items.values()}

    for prefix in dag.documents:
        if prefix in skip:
            continue
        if prefix not in prefixes_with_items:
            issues.append(
                ValidationIssue(
                    "warning",
                    None,
                    prefix,
                    "document contains no items",
                )
            )

    return issues


def _check_empty_text(graph: TraceabilityGraph, skip: set[str]) -> list[ValidationIssue]:
    """Check for items with empty or whitespace-only text.

    Flags every active item whose ``text`` field is empty or contains
    only whitespace characters.  Such items are unlikely to be
    intentional and may indicate incomplete authoring.

    Args:
        graph: The traceability graph containing all items.
        skip: Set of document prefixes to exclude from validation.

    Returns:
        A list of ``ValidationIssue`` objects with level ``warning`` for
        each item that has empty text.
    """
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


def _check_item_link_cycles(graph: TraceabilityGraph, skip: set[str]) -> list[ValidationIssue]:
    """Detect cycles in the item-to-item link graph using DFS.

    Builds a directed graph where each active, non-skipped item is a
    node and each link from one item to another is an edge.  A
    depth-first search with three-color marking (white/gray/black) is
    used to detect back edges, which indicate cycles.

    Each unique cycle (identified by its set of member UIDs) is reported
    at most once.  The issue message includes the full cycle path.

    Args:
        graph: The traceability graph containing all items and their
            links.
        skip: Set of document prefixes to exclude from validation.

    Returns:
        A list of ``ValidationIssue`` objects with level ``error`` for
        each distinct cycle found in the item link graph.
    """
    issues: list[ValidationIssue] = []
    reported_cycles: set[frozenset[str]] = set()

    # Build adjacency: item -> items it links to (only active, non-skipped)
    active_uids = {uid for uid, item in graph.items.items() if item.active and item.document_prefix not in skip}

    adjacency: dict[str, list[str]] = {}
    for uid in active_uids:
        adjacency[uid] = [lk for lk in graph.items[uid].links if lk in active_uids]

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {uid: WHITE for uid in active_uids}
    path: list[str] = []

    for start_uid in active_uids:
        if color[start_uid] != WHITE:
            continue

        # Stack of (uid, iterator_over_links)
        stack: list[tuple[str, int]] = [(start_uid, 0)]
        color[start_uid] = GRAY
        path.append(start_uid)

        while stack:
            uid, link_idx = stack[-1]
            active_links = adjacency[uid]

            if link_idx < len(active_links):
                # Advance the index for the current frame
                stack[-1] = (uid, link_idx + 1)
                link = active_links[link_idx]

                if color[link] == GRAY:
                    # Found a cycle — extract it
                    cycle_start = path.index(link)
                    cycle_members = frozenset(path[cycle_start:])
                    if cycle_members not in reported_cycles:
                        reported_cycles.add(cycle_members)
                        cycle_uids = path[cycle_start:]
                        # Report all UIDs involved in the cycle for clarity
                        affected_uids = ", ".join(sorted(cycle_members))
                        issues.append(
                            ValidationIssue(
                                "error",
                                link,
                                graph.items[link].document_prefix,
                                f"cycle in item links: {' -> '.join(cycle_uids)} -> {link} (affects: {affected_uids})",
                            )
                        )
                elif color[link] == WHITE:
                    color[link] = GRAY
                    path.append(link)
                    stack.append((link, 0))
            else:
                # All links processed, backtrack
                stack.pop()
                path.pop()
                color[uid] = BLACK

    return issues


def _check_unlinked_items(dag: DocumentDAG, graph: TraceabilityGraph, skip: set[str]) -> list[ValidationIssue]:
    """Check for normative non-derived items in child documents with no links.

    In a well-formed traceability tree, every normative item in a child
    document should link upward to at least one item in a parent
    document (unless it is explicitly marked as derived).  This check
    flags active normative items that belong to a document with parent
    documents in the DAG yet have an empty links list.

    Derived items are excluded because they intentionally lack upward
    links.  Items in root documents (no parents) are also excluded.

    Args:
        dag: The document DAG, used to determine whether an item's
            document has parent documents.
        graph: The traceability graph containing all items and their
            links.
        skip: Set of document prefixes to exclude from validation.

    Returns:
        A list of ``ValidationIssue`` objects with level ``warning`` for
        each unlinked normative non-derived item in a child document.
    """
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
        parents = dag.get_parents(item.document_prefix) if item.document_prefix in dag.documents else []
        if not parents:
            continue

        if not item.links:
            issues.append(
                ValidationIssue(
                    "warning",
                    uid,
                    item.document_prefix,
                    "normative non-derived item has no links to parent document"
                    " (add links or set 'derived: true' to suppress)",
                )
            )

    return issues
