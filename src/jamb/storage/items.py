"""Item reading and writing for jamb's native storage layer."""

import base64
import hashlib
import re
from pathlib import Path

import yaml


def read_item(path: Path, document_prefix: str) -> dict:
    """Read an item YAML file and return a normalized dict.

    Args:
        path: Path to the item YAML file.
        document_prefix: The document prefix this item belongs to.

    Returns:
        Dict with keys: uid, text, document_prefix, active, type, level,
        header, links, link_hashes, reviewed, custom_attributes.
    """
    with open(path) as f:
        data = yaml.safe_load(f) or {}

    uid = path.stem

    # Parse links - supports both "- UID" and "- UID: hash" formats
    raw_links = data.get("links", [])
    links: list[str] = []
    link_hashes: dict[str, str] = {}

    if isinstance(raw_links, list):
        for entry in raw_links:
            if isinstance(entry, dict):
                for link_uid, link_hash in entry.items():
                    links.append(str(link_uid))
                    if link_hash is not None:
                        link_hashes[str(link_uid)] = str(link_hash)
            elif isinstance(entry, str):
                links.append(entry)
            else:
                links.append(str(entry))

    # Determine type (default to "requirement" if not specified)
    item_type = data.get("type", "requirement")

    # Standard fields to exclude from custom_attributes
    standard_fields = {
        "active",
        "type",
        "level",
        "text",
        "header",
        "links",
        "reviewed",
    }
    custom_attributes = {k: v for k, v in data.items() if k not in standard_fields}

    return {
        "uid": uid,
        "text": str(data.get("text", "")),
        "document_prefix": document_prefix,
        "active": data.get("active", True),
        "type": item_type,
        "level": _parse_level(data.get("level", 1)),
        "header": str(data.get("header", "") or ""),
        "links": links,
        "link_hashes": link_hashes,
        "reviewed": data.get("reviewed"),
        "custom_attributes": custom_attributes,
    }


def write_item(item_data: dict, path: Path, extra_fields: dict | None = None) -> None:
    """Write an item as a YAML file.

    Args:
        item_data: Dict with item fields (uid, text, etc.).
        path: Path to write the YAML file.
        extra_fields: Additional fields to include in the YAML output.
    """
    output: dict = {}
    output["active"] = item_data.get("active", True)

    item_type = item_data.get("type", "requirement")
    if item_type != "requirement":
        output["type"] = item_type

    level = item_data.get("level")
    if level is not None:
        output["level"] = str(level)

    header = item_data.get("header", "")
    if header:
        output["header"] = header

    output["text"] = item_data.get("text", "")

    links = item_data.get("links", [])
    link_hashes = item_data.get("link_hashes", {})
    if links:
        formatted_links = []
        for link in links:
            if link in link_hashes:
                formatted_links.append({link: link_hashes[link]})
            else:
                formatted_links.append(link)
        output["links"] = formatted_links

    reviewed = item_data.get("reviewed")
    if reviewed:
        output["reviewed"] = reviewed

    if extra_fields:
        output.update(extra_fields)

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(
            output, f, default_flow_style=False, sort_keys=False, allow_unicode=True
        )


def read_document_items(
    doc_path: Path, prefix: str, include_inactive: bool = False
) -> list[dict]:
    """Read all item YAML files from a document directory.

    Args:
        doc_path: Path to the document directory.
        prefix: The document prefix.
        include_inactive: Whether to include inactive items.

    Returns:
        List of item dicts, sorted by UID.
    """
    items = []
    pattern = re.compile(rf"^{re.escape(prefix)}\d+\.yml$", re.IGNORECASE)

    for path in sorted(doc_path.iterdir()):
        if path.is_file() and pattern.match(path.name):
            item = read_item(path, prefix)
            if include_inactive or item["active"]:
                items.append(item)

    return items


def next_uid(prefix: str, digits: int, existing_uids: list[str], sep: str = "") -> str:
    """Generate the next available UID for a document.

    Args:
        prefix: Document prefix (e.g. "SRS").
        digits: Number of digits in the UID.
        existing_uids: List of existing UIDs.
        sep: Separator between prefix and number.

    Returns:
        Next available UID string.
    """
    max_num = 0
    pattern = re.compile(rf"^{re.escape(prefix)}{re.escape(sep)}(\d+)$", re.IGNORECASE)

    for uid in existing_uids:
        match = pattern.match(uid)
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num

    next_num = max_num + 1
    return f"{prefix}{sep}{next_num:0{digits}d}"


def compute_content_hash(item_data: dict) -> str:
    """Compute a SHA-256 hash of item content for review/suspect detection.

    Hashes: text, header, links, type, level.

    Args:
        item_data: Dict with item fields.

    Returns:
        URL-safe base64-encoded SHA-256 hash.
    """
    content_parts = [
        str(item_data.get("text", "")),
        str(item_data.get("header", "")),
        str(sorted(item_data.get("links", []))),
        str(item_data.get("type", "requirement")),
        str(item_data.get("level", 1)),
    ]
    content_str = "|".join(content_parts)
    hash_bytes = hashlib.sha256(content_str.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(hash_bytes).decode("ascii").rstrip("=")


def _parse_level(value) -> float:
    """Parse a level value to float."""
    if value is None:
        return 1.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 1.0
