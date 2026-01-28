"""Item reading and writing for jamb's native storage layer."""

import base64
import hashlib
import re
from pathlib import Path
from typing import IO, Any

import yaml


class _BlockScalarDumper(yaml.SafeDumper):
    """YAML dumper that uses literal block scalar style for multiline strings."""


def _str_representer(dumper: _BlockScalarDumper, data: str) -> yaml.ScalarNode:
    """Represent strings using literal block scalar style for multiline values.

    Args:
        dumper: The YAML dumper instance.
        data: The string value to represent.

    Returns:
        A YAML scalar node, using literal block style if the string
        contains newlines.
    """
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_BlockScalarDumper.add_representer(str, _str_representer)


def dump_yaml(data: dict[str, Any], stream: IO[str], **kwargs: Any) -> None:
    """Dump YAML using block scalar style for multiline strings.

    Args:
        data: The dictionary to serialize as YAML.
        stream: A writable file-like object for the YAML output.
        **kwargs: Additional keyword arguments passed to ``yaml.dump``.
    """
    kwargs.setdefault("default_flow_style", False)
    kwargs.setdefault("sort_keys", False)
    kwargs.setdefault("allow_unicode", True)
    yaml.dump(data, stream, Dumper=_BlockScalarDumper, **kwargs)


def read_item(path: Path, document_prefix: str) -> dict[str, Any]:
    """Read an item YAML file and return a normalized dict.

    Args:
        path: Path to the item YAML file.
        document_prefix: The document prefix this item belongs to.

    Returns:
        Dict with keys: uid, text, document_prefix, active, type,
        header, links, link_hashes, reviewed, derived, testable,
        custom_attributes.
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
        "text",
        "header",
        "links",
        "reviewed",
        "derived",
        "testable",
    }
    custom_attributes = {k: v for k, v in data.items() if k not in standard_fields}

    return {
        "uid": uid,
        "text": str(data.get("text", "")),
        "document_prefix": document_prefix,
        "active": data.get("active", True),
        "type": item_type,
        "header": str(data.get("header", "") or ""),
        "links": links,
        "link_hashes": link_hashes,
        "reviewed": data.get("reviewed"),
        "derived": data.get("derived", False),
        "testable": data.get("testable", True),
        "custom_attributes": custom_attributes,
    }


def write_item(
    item_data: dict[str, Any], path: Path, extra_fields: dict[str, Any] | None = None
) -> None:
    """Write an item as a YAML file.

    Args:
        item_data: Dict with item fields (uid, text, etc.).
        path: Path to write the YAML file.
        extra_fields: Additional fields to include in the YAML output.
    """
    output: dict[str, Any] = {}
    output["header"] = item_data.get("header", "")
    output["active"] = item_data.get("active", True)
    output["type"] = item_data.get("type", "requirement")

    links = item_data.get("links", [])
    link_hashes = item_data.get("link_hashes", {})
    formatted_links = []
    for link in links:
        if link in link_hashes:
            formatted_links.append({link: link_hashes[link]})
        else:
            formatted_links.append(link)
    output["links"] = formatted_links

    output["text"] = item_data.get("text", "")

    reviewed = item_data.get("reviewed")
    output["reviewed"] = reviewed

    if item_data.get("derived", False):
        output["derived"] = True

    if extra_fields:
        output.update(extra_fields)

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        dump_yaml(output, f)


def read_document_items(
    doc_path: Path, prefix: str, include_inactive: bool = False, sep: str = ""
) -> list[dict[str, Any]]:
    """Read all item YAML files from a document directory.

    Args:
        doc_path: Path to the document directory.
        prefix: The document prefix.
        include_inactive: Whether to include inactive items.
        sep: Separator between prefix and number.

    Returns:
        List of item dicts, sorted by UID.
    """
    items = []
    pattern = re.compile(
        rf"^{re.escape(prefix)}{re.escape(sep)}\d+\.yml$", re.IGNORECASE
    )

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


def compute_content_hash(item_data: dict[str, Any]) -> str:
    """Compute a SHA-256 hash of item content for review/suspect detection.

    Hashes: text, header, links, type.

    Args:
        item_data: Dict with item fields.

    Returns:
        URL-safe base64-encoded SHA-256 hash.
    """
    content_parts = [
        str(item_data.get("text", "")),
        str(item_data.get("header", "")),
        str(sorted(item_data.get("links") or [])),
        str(item_data.get("type", "requirement")),
    ]
    content_str = "|".join(content_parts)
    hash_bytes = hashlib.sha256(content_str.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(hash_bytes).decode("ascii").rstrip("=")
