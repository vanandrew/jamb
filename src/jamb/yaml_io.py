"""YAML import/export for doorstop requirements."""

from __future__ import annotations

import re
import subprocess
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
    tree,
    output_path: Path,
    item_uids: list[str],
    include_neighbors: bool = False,
    prefixes: list[str] | None = None,
) -> None:
    """Export specific items (and optionally their neighbors) to YAML file.

    Args:
        tree: Doorstop tree object.
        output_path: Path to write YAML file.
        item_uids: List of item UIDs to export.
        include_neighbors: If True, include ancestors and descendants of
            specified items.
        prefixes: Optional list of document prefixes to filter by.
            If None, no filtering.
    """
    from jamb.doorstop.reader import build_traceability_graph

    # Build traceability graph from tree
    graph = build_traceability_graph(tree)

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

    data = {"documents": [], "items": []}

    # Get documents in dependency order (parents first)
    docs_to_export = []
    for doc in tree.documents:
        if doc.prefix in doc_prefixes_needed:
            docs_to_export.append(doc)

    # Sort by parent dependency
    docs_to_export = _sort_documents_by_dependency(docs_to_export)

    for doc in docs_to_export:
        data["documents"].append(_document_to_dict(doc))

    # Export items in document order
    for doc in docs_to_export:
        for item in doc:
            if item.active and str(item.uid) in uids_to_export:
                data["items"].append(_item_to_dict(item))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        yaml.safe_dump(
            data, f, default_flow_style=False, sort_keys=False, allow_unicode=True
        )


def export_to_yaml(tree, output_path: Path, prefixes: list[str] | None = None) -> None:
    """Export doorstop tree to YAML file.

    Args:
        tree: Doorstop tree object.
        output_path: Path to write YAML file.
        prefixes: Optional list of document prefixes to export. If None, exports all.
    """
    data = {"documents": [], "items": []}

    # Get documents in dependency order (parents first)
    docs_to_export = []
    for doc in tree.documents:
        if prefixes is None or doc.prefix in prefixes:
            docs_to_export.append(doc)

    # Sort by parent dependency
    docs_to_export = _sort_documents_by_dependency(docs_to_export)

    for doc in docs_to_export:
        data["documents"].append(_document_to_dict(doc))

        for item in doc:
            if item.active:
                data["items"].append(_item_to_dict(item))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        yaml.safe_dump(
            data, f, default_flow_style=False, sort_keys=False, allow_unicode=True
        )


def _sort_documents_by_dependency(docs: list) -> list:
    """Sort documents so parents come before children."""
    result = []
    remaining = list(docs)
    prefixes_added = set()

    # First pass: add root documents (no parent)
    for doc in remaining[:]:
        if doc.parent is None:
            result.append(doc)
            prefixes_added.add(doc.prefix)
            remaining.remove(doc)

    # Subsequent passes: add documents whose parent is already added
    while remaining:
        added_this_round = False
        for doc in remaining[:]:
            if doc.parent in prefixes_added:
                result.append(doc)
                prefixes_added.add(doc.prefix)
                remaining.remove(doc)
                added_this_round = True

        if not added_this_round:
            # Circular dependency or missing parent - add remaining as-is
            result.extend(remaining)
            break

    return result


def _document_to_dict(doc) -> dict:
    """Convert doorstop document to dict with plain Python types."""
    # Handle path - might be string or Path
    doc_path = Path(doc.path) if isinstance(doc.path, str) else doc.path
    if doc.tree and hasattr(doc.tree, "root"):
        try:
            doc_path = doc_path.relative_to(doc.tree.root)
        except (ValueError, TypeError):
            pass

    d = {
        "prefix": str(doc.prefix),
        "path": str(doc_path),
    }
    if doc.parent:
        d["parent"] = str(doc.parent)
    # Get digits from config if available
    if hasattr(doc, "_data") and "digits" in doc._data.get("settings", {}):
        d["digits"] = doc._data["settings"]["digits"]
    return d


def _item_to_dict(item) -> ItemDict:
    """Convert doorstop item to dict with plain Python types."""
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
    """Create a doorstop document.

    Returns: 'created', 'skipped', or 'error'
    """
    prefix = spec["prefix"]
    path = spec["path"]
    parent = spec.get("parent")
    digits = spec.get("digits", 3)

    # Check if document already exists
    if _document_exists(prefix):
        if verbose:
            echo(f"  Skipping document {prefix} (already exists)")
        return "skipped"

    if dry_run:
        parent_str = f" (parent: {parent})" if parent else ""
        echo(f"  Would create document: {prefix} at {path}{parent_str}")
        return "created"

    # Build doorstop create command
    args = ["doorstop", "create", prefix, path, "--digits", str(digits)]
    if parent:
        args.extend(["--parent", parent])

    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        echo(f"  Error creating document {prefix}: {result.stderr}")
        return "error"

    if verbose:
        echo(f"  Created document: {prefix}")
    return "created"


def _create_item(spec: dict, dry_run: bool, update: bool, verbose: bool, echo) -> str:
    """Create or update a doorstop item.

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

    # Get document path (needed for both create and update)
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
    item_data = {
        "active": True,
        "normative": True,
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
    """Check if a doorstop document with the given prefix exists."""
    result = subprocess.run(
        ["doorstop", "list"],
        capture_output=True,
        text=True,
    )
    return prefix in result.stdout


def _item_exists(uid: str) -> bool:
    """Check if a doorstop item with the given UID exists."""
    prefix = _extract_prefix(uid)
    if not prefix:
        return False

    doc_path = _get_document_path(prefix)
    if not doc_path:
        return False

    item_path = doc_path / f"{uid}.yml"
    return item_path.exists()


def _extract_prefix(uid: str) -> str | None:
    """Extract document prefix from UID (e.g., SRS001 -> SRS)."""
    match = re.match(r"^([A-Za-z]+)", uid)
    return match.group(1) if match else None


def _get_document_path(prefix: str) -> Path | None:
    """Get the filesystem path for a document prefix."""
    # Find document path by searching for .doorstop.yml files
    import os

    for root, _, files in os.walk("."):
        if ".doorstop.yml" in files:
            config_path = Path(root) / ".doorstop.yml"
            with open(config_path) as f:
                config = yaml.safe_load(f)
            if config.get("settings", {}).get("prefix") == prefix:
                return Path(root)
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
            # Empty header in spec means remove header
            del existing_data["header"]
    if "links" in spec:
        if spec["links"]:
            existing_data["links"] = spec["links"]
        elif "links" in existing_data:
            # Empty links in spec means clear links
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
