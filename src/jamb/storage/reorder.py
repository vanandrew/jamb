"""Reorder logic for jamb documents.

Provides sequential UID renumbering with cross-document link updates.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from jamb.storage.items import dump_yaml


def reorder_document(
    doc_path: Path,
    prefix: str,
    digits: int,
    sep: str,
    all_doc_paths: dict[str, Path],
) -> dict[str, int]:
    """Renumber items sequentially and update all cross-document links.

    Items are sorted by current UID and assigned new sequential UIDs
    (e.g. PREFIX001, PREFIX002, ...).  Files are renamed on disk and
    every link reference across *all* documents is updated.

    Returns {"renamed": int, "unchanged": int}.
    """
    # 1. Collect all item files for this document
    item_files = sorted(
        p for p in doc_path.iterdir() if p.suffix == ".yml" and p.name != ".jamb.yml"
    )

    if not item_files:
        return {"renamed": 0, "unchanged": 0}

    # 2. Build rename map: old_uid -> new_uid
    rename_map: dict[str, str] = {}
    for i, item_file in enumerate(item_files, start=1):
        old_uid = item_file.stem
        new_uid = f"{prefix}{sep}{str(i).zfill(digits)}"
        if old_uid != new_uid:
            rename_map[old_uid] = new_uid

    stats = {
        "renamed": len(rename_map),
        "unchanged": len(item_files) - len(rename_map),
    }

    if not rename_map:
        return stats

    # 3. Rename files using temp names to avoid collisions
    temp_map: dict[str, Path] = {}  # old_uid -> temp_path
    for old_uid in rename_map:
        old_path = doc_path / f"{old_uid}.yml"
        tmp_path = doc_path / f".tmp_{old_uid}.yml"
        old_path.rename(tmp_path)
        temp_map[old_uid] = tmp_path

    for old_uid, new_uid in rename_map.items():
        tmp_path = temp_map[old_uid]
        new_path = doc_path / f"{new_uid}.yml"
        tmp_path.rename(new_path)

    # 4. Update links across ALL documents
    for _doc_prefix, dp in all_doc_paths.items():
        for yml_file in dp.iterdir():
            if yml_file.suffix != ".yml" or yml_file.name == ".jamb.yml":
                continue
            _update_links_in_file(yml_file, rename_map)

    return stats


def _update_links_in_file(file_path: Path, rename_map: dict[str, str]) -> None:
    """Rewrite link entries in a single item YAML file."""
    with open(file_path) as f:
        data = yaml.safe_load(f)

    if not data or "links" not in data:
        return

    links = data["links"]
    if not links:
        return

    changed = False
    new_links = []
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
        with open(file_path, "w") as f:
            dump_yaml(data, f)
