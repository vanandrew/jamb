"""YAML import/export for requirements."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict

import yaml

if TYPE_CHECKING:
    from jamb.core.models import Item
    from jamb.storage.document_dag import DocumentDAG


class _ItemDictOptional(TypedDict, total=False):
    """Optional fields for ItemDict."""

    header: str
    links: list[str]
    type: str
    derived: bool
    testable: bool


class ItemDict(_ItemDictOptional):
    """TypedDict for item export structure.

    Represents an item in YAML export format with required uid and text
    fields, and optional header and links fields inherited from
    _ItemDictOptional.
    """

    uid: str
    text: str


def _dump_yaml(data: dict[str, Any], stream: Any) -> None:
    """Write YAML using block scalar style for multiline strings."""
    from jamb.storage.items import dump_yaml

    dump_yaml(data, stream)


def export_items_to_yaml(
    output_path: Path,
    item_uids: list[str],
    include_neighbors: bool = False,
    prefixes: list[str] | None = None,
    root: Path | None = None,
) -> None:
    """Export specific items (and optionally their neighbors) to YAML file.

    Args:
        output_path: Path to write YAML file.
        item_uids: List of item UIDs to export.
        include_neighbors: If True, include ancestors and descendants.
        prefixes: Optional list of document prefixes to filter by.
        root: Optional project root directory.
    """
    from jamb.storage import build_traceability_graph, discover_documents

    dag = discover_documents(root)
    graph = build_traceability_graph(dag)

    # Collect UIDs to export
    uids_to_export: set[str] = set()
    for uid in item_uids:
        if uid in graph.items:
            uids_to_export.add(uid)
            if include_neighbors:
                for neighbor in graph.get_neighbors(uid):
                    uids_to_export.add(neighbor.uid)

    # Filter by document prefixes if specified
    if prefixes:
        uids_to_export = {
            uid for uid in uids_to_export if uid in graph.items and graph.items[uid].document_prefix in prefixes
        }

    # Determine which documents contain these items
    doc_prefixes_needed: set[str] = set()
    for uid in uids_to_export:
        if uid in graph.items:
            doc_prefixes_needed.add(graph.items[uid].document_prefix)

    data: dict[str, Any] = {"documents": [], "items": []}

    # Compute search root for relative paths
    search_root = (root or Path.cwd()).resolve()

    # Get documents in topological order
    for prefix in dag.topological_sort():
        if prefix in doc_prefixes_needed:
            config = dag.documents[prefix]
            doc_path = dag.document_paths.get(prefix)
            if doc_path:
                try:
                    rel_path = str(doc_path.resolve().relative_to(search_root))
                except ValueError:
                    rel_path = str(doc_path)
            else:
                rel_path = prefix.lower()
            doc_dict: dict[str, Any] = {
                "prefix": prefix,
                "path": rel_path,
            }
            if config.parents:
                doc_dict["parents"] = config.parents
            data["documents"].append(doc_dict)

    # Export items in document order
    for prefix in dag.topological_sort():
        if prefix not in doc_prefixes_needed:
            continue
        for item in graph.get_items_by_document(prefix):
            if item.active and item.uid in uids_to_export:
                data["items"].append(_graph_item_to_dict(item))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        _dump_yaml(data, f)


def export_to_yaml(
    output_path: Path,
    prefixes: list[str] | None = None,
    root: Path | None = None,
) -> None:
    """Export document tree to YAML file.

    Args:
        output_path: Path to write YAML file.
        prefixes: Optional list of document prefixes to export.
        root: Optional project root directory.
    """
    from jamb.storage import build_traceability_graph, discover_documents

    dag = discover_documents(root)
    graph = build_traceability_graph(dag)

    data: dict[str, Any] = {"documents": [], "items": []}

    # Compute search root for relative paths
    search_root = (root or Path.cwd()).resolve()

    for prefix in dag.topological_sort():
        if prefixes is not None and prefix not in prefixes:
            continue

        config = dag.documents[prefix]
        doc_path = dag.document_paths.get(prefix)
        if doc_path:
            try:
                rel_path = str(doc_path.resolve().relative_to(search_root))
            except ValueError:
                rel_path = str(doc_path)
        else:
            rel_path = prefix.lower()
        doc_dict: dict[str, Any] = {
            "prefix": prefix,
            "path": rel_path,
        }
        if config.parents:
            doc_dict["parents"] = config.parents
        data["documents"].append(doc_dict)

        for item in graph.get_items_by_document(prefix):
            if item.active:
                data["items"].append(_graph_item_to_dict(item))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        _dump_yaml(data, f)


def _graph_item_to_dict(item: Item) -> ItemDict:
    """Convert a graph Item to dict with plain Python types."""
    d: ItemDict = {
        "uid": str(item.uid),
        "text": str(item.text),
    }
    if item.header:
        d["header"] = str(item.header)
    if item.links:
        d["links"] = [str(link) for link in item.links]
    if item.type != "requirement":
        d["type"] = item.type
    if item.derived:
        d["derived"] = True
    if not item.testable:
        d["testable"] = False
    return d


def load_import_file(path: Path, echo: Callable[[str], object] | None = None) -> dict[str, Any]:
    """Load and validate YAML import file.

    Args:
        path: Path to YAML file.
        echo: Optional callable for warning output (e.g., print or click.echo).

    Returns:
        Dict with 'documents' and 'items' keys.

    Raises:
        ValueError: If file is invalid.
    """
    import warnings

    if echo is None:
        echo = print

    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except OSError as e:
        raise OSError(f"Failed to read file {path}: {e}") from e
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in file {path}: {e}") from e

    # Handle null/empty YAML files
    if data is None:
        warnings.warn(f"File {path} is empty or contains only null", stacklevel=2)
        data = {}
    elif not isinstance(data, dict):
        raise ValueError(f"Expected dict in {path}, got {type(data).__name__}")

    # Warn about unrecognized top-level keys
    recognized_keys = {"documents", "items"}
    unrecognized = set(data.keys()) - recognized_keys
    if unrecognized:
        echo(f"Warning: unrecognized top-level keys: {', '.join(sorted(unrecognized))}")

    # Normalize: ensure both keys exist
    data.setdefault("documents", [])
    data.setdefault("items", [])

    # Warn if both sections are empty
    if not data["documents"] and not data["items"]:
        echo("Warning: YAML file contains no documents and no items")

    # Validate documents
    for doc in data["documents"]:
        if "prefix" not in doc:
            raise ValueError(f"Document missing 'prefix': {repr(doc)[:200]}")
        if "path" not in doc:
            raise ValueError(f"Document missing 'path': {repr(doc)[:200]}")

    # Validate items
    for item in data["items"]:
        if "uid" not in item:
            raise ValueError(f"Item missing 'uid': {repr(item)[:200]}")
        if "text" not in item:
            raise ValueError(f"Item missing 'text': {repr(item)[:200]}")

    # Check for duplicate UIDs
    seen = set()
    duplicates = set()
    for item in data["items"]:
        uid = item["uid"]
        if uid in seen:
            duplicates.add(uid)
        seen.add(uid)
    if duplicates:
        raise ValueError(f"Duplicate UIDs in import file: {', '.join(sorted(duplicates))}")

    return data


def import_from_yaml(
    path: Path,
    dry_run: bool = False,
    update: bool = False,
    verbose: bool = False,
    echo: Callable[[str], object] | None = None,
) -> dict[str, int]:
    """Import documents and items from YAML file.

    Args:
        path: Path to YAML file.
        dry_run: If True, don't make changes, just report what would happen.
        update: If True, update existing items instead of skipping them.
        verbose: If True, print verbose output.
        echo: Optional function for output (defaults to print).

    Returns:
        Dict with counts: {'documents_created', 'items_created',
            'items_updated', 'skipped'}
    """
    if echo is None:
        echo = print

    from jamb.storage import discover_documents

    data = load_import_file(path, echo=echo)
    stats = {
        "documents_created": 0,
        "items_created": 0,
        "items_updated": 0,
        "skipped": 0,
    }

    dag = discover_documents()

    # Import documents first (in order - parents before children)
    for doc_spec in data["documents"]:
        result = _create_document(doc_spec, dry_run, verbose, echo, dag=dag)
        if result == "created":
            stats["documents_created"] += 1
            # Re-discover after creating a document so items can find it
            dag = discover_documents()
        elif result == "skipped":
            stats["skipped"] += 1

    # Import items
    for item_spec in data["items"]:
        result = _create_item(item_spec, dry_run, update, verbose, echo, dag=dag)
        if result == "created":
            stats["items_created"] += 1
        elif result == "updated":
            stats["items_updated"] += 1
        elif result == "skipped":
            stats["skipped"] += 1

    return stats


def _create_document(
    spec: dict[str, Any],
    dry_run: bool,
    verbose: bool,
    echo: Callable[[str], object],
    dag: DocumentDAG | None = None,
) -> str:
    """Create a document from spec.

    Args:
        spec: A dict containing document specification with required keys
            'prefix' and 'path', and optional keys 'parents' (list of
            parent document prefixes) and 'digits' (number of digits in
            item numbering, defaults to 3).
        dry_run: If True, report what would happen without making changes.
        verbose: If True, print detailed output including skip messages.
        echo: Callable for output (e.g., print or click.echo).
        dag: Optional pre-built DAG to avoid repeated discovery.

    Returns:
        A string indicating the result: 'created', 'skipped', or 'error'.
    """
    from jamb.storage.document_config import DocumentConfig, save_document_config

    prefix = spec["prefix"]
    path = spec["path"]
    parents: list[str] = []
    if "parents" in spec:
        parents = spec["parents"]
    digits = spec.get("digits", 3)

    # Check if document already exists
    if _document_exists(prefix, dag=dag):
        if verbose:
            echo(f"  Skipping document {prefix} (already exists)")
        return "skipped"

    if dry_run:
        parent_str = f" (parents: {', '.join(parents)})" if parents else ""
        echo(f"  Would create document: {prefix} at {path}{parent_str}")
        return "created"

    config = DocumentConfig(
        prefix=prefix,
        parents=parents,
        digits=digits,
    )
    doc_path = Path(path)
    # Guard against path traversal
    try:
        resolved = doc_path.resolve()
        cwd = Path.cwd().resolve()
        if doc_path.is_absolute():
            echo(f"  Error creating document {prefix}: path '{path}' must be relative, not absolute")
            return "error"
        if not resolved.is_relative_to(cwd):
            echo(f"  Error creating document {prefix}: path '{path}' traverses outside project directory")
            return "error"
    except OSError as e:
        echo(f"  Error creating document {prefix}: cannot resolve path '{path}': {e}")
        return "error"
    except ValueError as e:
        echo(f"  Error creating document {prefix}: invalid path '{path}': {e}")
        return "error"
    try:
        save_document_config(config, doc_path)
    except (OSError, ValueError) as e:
        echo(f"  Error creating document {prefix}: {e}")
        return "error"

    if verbose:
        echo(f"  Created document: {prefix}")
    return "created"


def _create_item(
    spec: dict[str, Any],
    dry_run: bool,
    update: bool,
    verbose: bool,
    echo: Callable[[str], object],
    dag: DocumentDAG | None = None,
) -> str:
    """Create or update an item.

    Args:
        spec: A dict containing item specification with required keys
            'uid' and 'text', and optional keys 'header' (str) and
            'links' (list of linked item UIDs).
        dry_run: If True, report what would happen without making changes.
        update: If True, update existing items instead of skipping them.
        verbose: If True, print detailed output including skip messages.
        echo: Callable for output (e.g., print or click.echo).
        dag: Optional pre-built DAG to avoid repeated discovery.

    Returns:
        A string indicating the result: 'created', 'updated', 'skipped',
        or 'error'.
    """
    uid = spec["uid"]
    text = spec["text"]
    header = spec.get("header", "")
    links = spec.get("links", [])

    # Extract prefix from UID (e.g., SRS001 -> SRS)
    prefix = _extract_prefix(uid, dag=dag)
    if not prefix:
        echo(f"  Error: Cannot determine prefix from UID: {uid}")
        return "error"

    # Get document path
    doc_path = _get_document_path(prefix, dag=dag)
    if not doc_path:
        echo(f"  Error: Cannot find document path for {prefix}")
        return "error"

    item_path = doc_path / f"{uid}.yml"
    existing = item_path.exists()

    # Check if item already exists
    if existing and not update:
        if verbose:
            echo(f"  Skipping item {uid} (already exists)")
        return "skipped"

    if dry_run:
        links_str = f" (links: {', '.join(links)})" if links else ""
        if existing:
            echo(f"  Would update item: {uid}{links_str}")
            return "updated"
        else:
            echo(f"  Would create item: {uid}{links_str}")
            return "created"

    # Update existing item
    if existing:
        return _update_item(item_path, spec, verbose, echo)

    # Write new item YAML file directly
    item_data: dict[str, Any] = {
        "active": True,
        "text": text,
    }
    if header:
        item_data["header"] = header
    if links:
        item_data["links"] = links
    # Preserve type, derived, and testable fields from import spec
    if spec.get("type") and spec["type"] != "requirement":
        item_data["type"] = spec["type"]
    if spec.get("derived"):
        item_data["derived"] = True
    if "testable" in spec and not spec["testable"]:
        item_data["testable"] = False

    with open(item_path, "w", encoding="utf-8") as f:
        _dump_yaml(item_data, f)

    if verbose:
        echo(f"  Created item: {uid}")
    return "created"


def _document_exists(prefix: str, dag: DocumentDAG | None = None) -> bool:
    """Check if a document with the given prefix exists on the filesystem.

    Args:
        prefix: The document prefix to search for (e.g., 'SRS').
        dag: Optional pre-built DAG. If None, calls discover_documents().

    Returns:
        True if a document with the given prefix exists, False otherwise.
    """
    if dag is None:
        from jamb.storage import discover_documents

        dag = discover_documents()
    return prefix in dag.documents


def _extract_prefix(uid: str, dag: DocumentDAG | None = None) -> str | None:
    """Extract document prefix from UID (e.g., SRS001 -> SRS).

    Args:
        uid: The item UID string to extract a prefix from.
        dag: Optional pre-built DAG.  When provided, the UID is matched
            against known prefixes (longest first) so that prefixes
            containing digits or underscores are handled correctly
            (e.g., ``SRS2`` vs ``SRS``).

    Returns:
        The prefix string, or None if no valid prefix is found.
    """
    if dag is not None:
        # Match against known prefixes, longest first, to resolve ambiguity
        # (e.g. both "SRS" and "SRS2" exist — "SRS2001" should match "SRS2").
        for prefix in sorted(dag.documents, key=len, reverse=True):
            config = dag.documents[prefix]
            sep = config.sep
            if uid.startswith(prefix + sep) and uid[len(prefix) + len(sep) :].isdigit():
                return prefix
        # Fall through to regex if no known prefix matched

    match = re.match(r"^([A-Za-z][A-Za-z_]*)", uid)
    return match.group(1) if match else None


def _get_document_path(prefix: str, dag: DocumentDAG | None = None) -> Path | None:
    """Get the filesystem path for a document prefix.

    Args:
        prefix: The document prefix to look up (e.g., 'SRS').
        dag: Optional pre-built DAG. If None, calls discover_documents().

    Returns:
        The Path to the document directory, or None if no document with
        the given prefix is found.
    """
    if dag is None:
        from jamb.storage import discover_documents

        dag = discover_documents()
    return dag.document_paths.get(prefix)


def _update_item(item_path: Path, spec: dict[str, Any], verbose: bool, echo: Callable[[str], object]) -> str:
    """Update an existing item YAML file.

    Preserves existing fields not specified in spec.
    Clears 'reviewed' status to indicate item needs re-review.

    Args:
        item_path: Path to the item YAML file.
        spec: Dict with uid, text, and optional header/links.
        verbose: If True, print verbose output.
        echo: Function for output.

    Returns: 'updated' or 'error'
    """
    uid = spec["uid"]

    # Load existing item data
    with open(item_path, encoding="utf-8") as f:
        existing_data = yaml.safe_load(f) or {}

    if not isinstance(existing_data, dict):
        echo(f"  Error: {uid} contains invalid YAML (expected mapping)")
        return "error"

    # Compute content hash before mutations to detect real changes
    from jamb.storage.items import compute_content_hash

    old_hash = compute_content_hash(existing_data)

    # Update fields from spec (only update what's provided)
    if "text" in spec:
        existing_data["text"] = spec["text"]
    if "header" in spec:
        if spec["header"]:
            existing_data["header"] = spec["header"]
        elif "header" in existing_data:
            del existing_data["header"]
    if "links" in spec:
        if spec["links"]:
            existing_data["links"] = spec["links"]
        elif "links" in existing_data:
            del existing_data["links"]
    # Preserve type, derived, and testable fields from import spec
    if "type" in spec:
        if spec["type"] and spec["type"] != "requirement":
            existing_data["type"] = spec["type"]
        elif "type" in existing_data:
            del existing_data["type"]
    if "derived" in spec:
        if spec["derived"]:
            existing_data["derived"] = True
        elif "derived" in existing_data:
            del existing_data["derived"]
    if "testable" in spec:
        if not spec["testable"]:
            existing_data["testable"] = False
        elif "testable" in existing_data:
            del existing_data["testable"]

    # Only clear reviewed status if content actually changed
    new_hash = compute_content_hash(existing_data)
    if old_hash != new_hash and "reviewed" in existing_data:
        del existing_data["reviewed"]

    # Write updated data
    with open(item_path, "w", encoding="utf-8") as f:
        _dump_yaml(existing_data, f)

    if verbose:
        echo(f"  Updated item: {uid}")
    return "updated"
