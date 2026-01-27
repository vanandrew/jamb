"""YAML import/export for requirements."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TypedDict

import yaml


class _ItemDictOptional(TypedDict, total=False):
    """Optional fields for ItemDict."""

    header: str
    links: list[str]


class ItemDict(_ItemDictOptional):
    """TypedDict for item export structure."""

    uid: str
    text: str


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
            uid
            for uid in uids_to_export
            if uid in graph.items and graph.items[uid].document_prefix in prefixes
        }

    # Determine which documents contain these items
    doc_prefixes_needed: set[str] = set()
    for uid in uids_to_export:
        if uid in graph.items:
            doc_prefixes_needed.add(graph.items[uid].document_prefix)

    data: dict = {"documents": [], "items": []}

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
            doc_dict: dict = {
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
    with open(output_path, "w") as f:
        yaml.safe_dump(
            data, f, default_flow_style=False, sort_keys=False, allow_unicode=True
        )


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

    data: dict = {"documents": [], "items": []}

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
        doc_dict: dict = {
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
    with open(output_path, "w") as f:
        yaml.safe_dump(
            data, f, default_flow_style=False, sort_keys=False, allow_unicode=True
        )


def _graph_item_to_dict(item) -> ItemDict:
    """Convert a graph Item to dict with plain Python types."""
    d: ItemDict = {
        "uid": str(item.uid),
        "text": str(item.text),
    }
    if item.header:
        d["header"] = str(item.header)
    if item.links:
        d["links"] = [str(link) for link in item.links]
    return d


def load_import_file(path: Path) -> dict:
    """Load and validate YAML import file.

    Args:
        path: Path to YAML file.

    Returns:
        Dict with 'documents' and 'items' keys.

    Raises:
        ValueError: If file is invalid.
    """
    with open(path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("YAML file must contain a mapping")

    # Normalize: ensure both keys exist
    data.setdefault("documents", [])
    data.setdefault("items", [])

    # Validate documents
    for doc in data["documents"]:
        if "prefix" not in doc:
            raise ValueError(f"Document missing 'prefix': {doc}")
        if "path" not in doc:
            raise ValueError(f"Document missing 'path': {doc}")

    # Validate items
    for item in data["items"]:
        if "uid" not in item:
            raise ValueError(f"Item missing 'uid': {item}")
        if "text" not in item:
            raise ValueError(f"Item missing 'text': {item}")

    return data


def import_from_yaml(
    path: Path,
    dry_run: bool = False,
    update: bool = False,
    verbose: bool = False,
    echo=None,
) -> dict:
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

    data = load_import_file(path)
    stats = {
        "documents_created": 0,
        "items_created": 0,
        "items_updated": 0,
        "skipped": 0,
    }

    # Import documents first (in order - parents before children)
    for doc_spec in data["documents"]:
        result = _create_document(doc_spec, dry_run, verbose, echo)
        if result == "created":
            stats["documents_created"] += 1
        elif result == "skipped":
            stats["skipped"] += 1

    # Import items
    for item_spec in data["items"]:
        result = _create_item(item_spec, dry_run, update, verbose, echo)
        if result == "created":
            stats["items_created"] += 1
        elif result == "updated":
            stats["items_updated"] += 1
        elif result == "skipped":
            stats["skipped"] += 1

    return stats


def _create_document(spec: dict, dry_run: bool, verbose: bool, echo) -> str:
    """Create a document from spec.

    Returns: 'created', 'skipped', or 'error'
    """
    from jamb.storage.document_config import DocumentConfig, save_document_config

    prefix = spec["prefix"]
    path = spec["path"]
    parents: list[str] = []
    if "parents" in spec:
        parents = spec["parents"]
    digits = spec.get("digits", 3)

    # Check if document already exists
    if _document_exists(prefix):
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
    try:
        save_document_config(config, doc_path)
    except Exception as e:
        echo(f"  Error creating document {prefix}: {e}")
        return "error"

    if verbose:
        echo(f"  Created document: {prefix}")
    return "created"


def _create_item(spec: dict, dry_run: bool, update: bool, verbose: bool, echo) -> str:
    """Create or update an item.

    Returns: 'created', 'updated', 'skipped', or 'error'
    """
    uid = spec["uid"]
    text = spec["text"]
    header = spec.get("header", "")
    links = spec.get("links", [])

    # Extract prefix from UID (e.g., SRS001 -> SRS)
    prefix = _extract_prefix(uid)
    if not prefix:
        echo(f"  Error: Cannot determine prefix from UID: {uid}")
        return "error"

    # Get document path
    doc_path = _get_document_path(prefix)
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
    item_data: dict = {
        "active": True,
        "text": text,
    }
    if header:
        item_data["header"] = header
    if links:
        item_data["links"] = links

    with open(item_path, "w") as f:
        yaml.dump(item_data, f, default_flow_style=False, sort_keys=False)

    if verbose:
        echo(f"  Created item: {uid}")
    return "created"


def _document_exists(prefix: str) -> bool:
    """Check if a document with the given prefix exists on the filesystem."""
    import os

    for root_dir, _, files in os.walk("."):
        if ".jamb.yml" in files:
            config_path = Path(root_dir) / ".jamb.yml"
            with open(config_path) as f:
                config = yaml.safe_load(f)
            if config.get("settings", {}).get("prefix") == prefix:
                return True
    return False


def _extract_prefix(uid: str) -> str | None:
    """Extract document prefix from UID (e.g., SRS001 -> SRS)."""
    match = re.match(r"^([A-Za-z]+)", uid)
    return match.group(1) if match else None


def _get_document_path(prefix: str) -> Path | None:
    """Get the filesystem path for a document prefix."""
    import os

    for root_dir, _, files in os.walk("."):
        if ".jamb.yml" in files:
            config_path = Path(root_dir) / ".jamb.yml"
            with open(config_path) as f:
                config = yaml.safe_load(f)
            if config.get("settings", {}).get("prefix") == prefix:
                return Path(root_dir)
    return None


def _update_item(item_path: Path, spec: dict, verbose: bool, echo) -> str:
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
    with open(item_path) as f:
        existing_data = yaml.safe_load(f) or {}

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

    # Clear reviewed status - item needs re-review after update
    if "reviewed" in existing_data:
        del existing_data["reviewed"]

    # Write updated data
    with open(item_path, "w") as f:
        yaml.dump(existing_data, f, default_flow_style=False, sort_keys=False)

    if verbose:
        echo(f"  Updated item: {uid}")
    return "updated"
