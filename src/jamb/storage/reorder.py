"""Reorder logic for jamb documents.

Provides sequential UID renumbering with cross-document link updates.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from jamb.storage.items import dump_yaml


def _collect_all_uids(all_doc_paths: dict[str, Path]) -> set[str]:
    """Return the set of all item UIDs across every document directory.

    Args:
        all_doc_paths: A dict mapping document prefixes to their directory
            Paths.

    Returns:
        A set of all UIDs found across every document directory.
    """
    uids: set[str] = set()
    for dp in all_doc_paths.values():
        for p in dp.iterdir():
            if p.suffix == ".yml" and p.name != ".jamb.yml":
                uids.add(p.stem)
    return uids


def _check_broken_links(item_files: list[Path], all_doc_paths: dict[str, Path]) -> None:
    """Raise ValueError if any item links to a non-existent UID.

    Raises:
        ValueError: If broken links are found or YAML parsing fails.
    """
    known_uids = _collect_all_uids(all_doc_paths)
    broken: list[str] = []
    for item_file in item_files:
        try:
            with open(item_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse YAML file '{item_file}': {e}") from e
        if not data or "links" not in data or not data["links"]:
            continue
        src_uid = item_file.stem
        for entry in data["links"]:
            if isinstance(entry, dict):
                for target_uid in entry:
                    if str(target_uid) not in known_uids:
                        broken.append(f"{src_uid} -> {target_uid}")
            else:
                if str(entry) not in known_uids:
                    broken.append(f"{src_uid} -> {entry}")
    if broken:
        raise ValueError(f"Broken links found: {', '.join(broken)}")


def reorder_document(
    doc_path: Path,
    prefix: str,
    digits: int,
    sep: str,
    all_doc_paths: dict[str, Path],
) -> dict[str, int | dict[str, str]]:
    """Renumber items sequentially and update all cross-document links.

    Items are sorted by current UID and assigned new sequential UIDs
    (e.g. PREFIX001, PREFIX002, ...).  Files are renamed on disk and
    every link reference across *all* documents is updated.

    Note: This operation is not atomic. If an error occurs during link
    updates after files have been renamed, the document may be left in
    an inconsistent state. Consider committing to version control before
    reordering.

    Returns {"renamed": int, "unchanged": int, "rename_map": dict[str, str]}.

    Raises:
        ValueError: If digits < 1.
    """
    if digits < 1:
        raise ValueError(f"digits must be >= 1, got {digits}")
    # 1. Collect all item files for this document
    item_files = sorted(p for p in doc_path.iterdir() if p.suffix == ".yml" and p.name != ".jamb.yml")

    if not item_files:
        return {"renamed": 0, "unchanged": 0, "rename_map": {}}

    # 1b. Verify all links resolve to existing UIDs
    _check_broken_links(item_files, all_doc_paths)

    # 2. Build rename map: old_uid -> new_uid
    rename_map: dict[str, str] = {}
    for i, item_file in enumerate(item_files, start=1):
        old_uid = item_file.stem
        new_uid = f"{prefix}{sep}{str(i).zfill(digits)}"
        if old_uid != new_uid:
            rename_map[old_uid] = new_uid

    stats: dict[str, int | dict[str, str]] = {
        "renamed": len(rename_map),
        "unchanged": len(item_files) - len(rename_map),
        "rename_map": rename_map,
    }

    if not rename_map:
        return stats

    # 3. Rename files using temp names to avoid collisions
    # Note: If an error occurs during this phase, temp files may be left behind.
    # Clean up any leftover temp files from previous failed runs first.
    for tmp_file in doc_path.glob(".tmp_*.yml"):
        tmp_file.unlink(missing_ok=True)

    temp_map: dict[str, Path] = {}  # old_uid -> temp_path
    try:
        for old_uid in rename_map:
            old_path = doc_path / f"{old_uid}.yml"
            tmp_path = doc_path / f".tmp_{old_uid}.yml"
            old_path.rename(tmp_path)
            temp_map[old_uid] = tmp_path

        for old_uid, new_uid in rename_map.items():
            tmp_path = temp_map[old_uid]
            new_path = doc_path / f"{new_uid}.yml"
            tmp_path.rename(new_path)
    except Exception:
        # Clean up any remaining temp files on error
        for tmp_path in temp_map.values():
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
        raise

    # 4. Update links across ALL documents
    for _doc_prefix, dp in all_doc_paths.items():
        for yml_file in dp.iterdir():
            if yml_file.suffix != ".yml" or yml_file.name == ".jamb.yml":
                continue
            _update_links_in_file(yml_file, rename_map)

    return stats


def _update_links_in_file(file_path: Path, rename_map: dict[str, str]) -> None:
    """Rewrite link entries in a single item YAML file.

    Handles both plain UID strings and ``{uid: hash}`` dict entries,
    replacing any UIDs found in the rename map.

    Args:
        file_path: Path to the item YAML file.
        rename_map: A dict mapping old UIDs to new UIDs.
    """
    with open(file_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or "links" not in data:
        return

    links = data["links"]
    if not links:
        return

    changed = False
    new_links: list[dict[str, str] | str] = []
    for entry in links:
        if isinstance(entry, dict):
            # {uid: hash} form
            new_entry = {}
            for uid, hash_val in entry.items():
                new_uid = rename_map.get(str(uid), str(uid))
                if new_uid != str(uid):
                    changed = True
                new_entry[new_uid] = hash_val
            new_links.append(new_entry)
        else:
            # plain uid string
            uid_str = str(entry)
            new_uid = rename_map.get(uid_str, uid_str)
            if new_uid != uid_str:
                changed = True
            new_links.append(new_uid)

    if changed:
        data["links"] = new_links
        with open(file_path, "w", encoding="utf-8") as f:
            dump_yaml(data, f)


def insert_items(
    doc_path: Path,
    prefix: str,
    digits: int,
    sep: str,
    position: int,
    count: int,
    all_doc_paths: dict[str, Path],
) -> list[str]:
    """Insert *count* new item slots at *position*, shifting existing items forward.

    Items with number >= *position* are renamed to number + *count*.
    Links across all documents are updated to reflect the new UIDs.

    Args:
        doc_path: Path to the document directory.
        prefix: Document prefix (e.g. "SRS").
        digits: Number of digits in item UIDs.
        sep: Separator between prefix and number.
        position: Position to insert at (must be >= 1).
        count: Number of items to insert.
        all_doc_paths: Mapping of all document prefixes to their paths.

    Returns:
        The list of new UIDs that were freed (e.g. ``["SRS005"]``).
        The caller is responsible for writing the actual item files at those paths.

    Raises:
        ValueError: If position < 1 or count < 1.
    """
    import re
    import warnings

    if position < 1:
        raise ValueError(f"Position must be >= 1, got {position}")
    if count < 1:
        raise ValueError(f"Count must be >= 1, got {count}")

    # 1. Collect item files
    item_files = sorted(p for p in doc_path.iterdir() if p.suffix == ".yml" and p.name != ".jamb.yml")

    # Validate insert position
    max_position = len(item_files) + 1
    if position > max_position:
        warnings.warn(
            f"Insert position {position} exceeds item count ({len(item_files)}). Items will be appended at the end.",
            stacklevel=2,
        )
        position = max_position

    # 2. Broken-link pre-check
    _check_broken_links(item_files, all_doc_paths)

    # 3. Parse numeric part of each UID and build rename map
    pattern = re.compile(rf"^{re.escape(prefix)}{re.escape(sep)}(\d+)$", re.IGNORECASE)
    rename_map: dict[str, str] = {}
    for item_file in item_files:
        uid = item_file.stem
        m = pattern.match(uid)
        if not m:
            continue
        num = int(m.group(1))
        if num >= position:
            new_num = num + count
            new_uid = f"{prefix}{sep}{str(new_num).zfill(digits)}"
            rename_map[uid] = new_uid

    # 4. Two-stage temp-file rename to avoid collisions
    if rename_map:
        temp_map: dict[str, Path] = {}
        try:
            for old_uid in rename_map:
                old_path = doc_path / f"{old_uid}.yml"
                tmp_path = doc_path / f".tmp_{old_uid}.yml"
                old_path.rename(tmp_path)
                temp_map[old_uid] = tmp_path

            for old_uid, new_uid in rename_map.items():
                tmp_path = temp_map[old_uid]
                new_path = doc_path / f"{new_uid}.yml"
                tmp_path.rename(new_path)
        except Exception:
            # Clean up any remaining temp files on error
            for tmp_path in temp_map.values():
                if tmp_path.exists():
                    tmp_path.unlink(missing_ok=True)
            raise

    # 5. Update links across ALL documents
    if rename_map:
        for _doc_prefix, dp in all_doc_paths.items():
            for yml_file in dp.iterdir():
                if yml_file.suffix != ".yml" or yml_file.name == ".jamb.yml":
                    continue
                _update_links_in_file(yml_file, rename_map)

    # 6. Return the freed UIDs
    new_uids = [f"{prefix}{sep}{str(position + i).zfill(digits)}" for i in range(count)]
    return new_uids
