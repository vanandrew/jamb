"""Item reading and writing for jamb's native storage layer."""

import base64
import hashlib
import os
import re
import tempfile
import unicodedata
import warnings
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

    Raises:
        OSError: If the file cannot be read.
        ValueError: If the file contains invalid YAML or has an empty UID.
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except OSError as e:
        raise OSError(f"Failed to read file {path}: {e}") from e
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in file {path}: {e}") from e

    if not isinstance(data, dict):
        data = {}

    uid = path.stem.strip()
    if not uid:
        raise ValueError(f"Invalid item file with empty UID: {path}")

    # Parse links - supports both "- UID" and "- UID: hash" formats
    raw_links = data.get("links", [])
    links: list[str] = []
    link_hashes: dict[str, str] = {}

    if raw_links and not isinstance(raw_links, list):
        warnings.warn(
            f"Item '{path.stem}' has 'links' field that is not a list. "
            f"Links should be formatted as a YAML list. "
            f"Got: {type(raw_links).__name__}",
            stacklevel=2,
        )

    if isinstance(raw_links, list):
        for entry in raw_links:
            if isinstance(entry, dict):
                for link_uid, link_hash in entry.items():
                    link_str = str(link_uid).strip()
                    if not link_str:
                        warnings.warn(
                            f"Empty link UID in item '{uid}', skipping",
                            stacklevel=2,
                        )
                        continue
                    links.append(link_str)
                    if link_hash is not None:
                        hash_str = str(link_hash)
                        # Validate hash is non-empty and looks like a valid base64
                        if hash_str and hash_str.strip():
                            # SHA-256 base64 is ~43 chars; require >= 20 chars
                            # and URL-safe base64 characters
                            is_valid = len(hash_str) >= 20 and re.match(r"^[A-Za-z0-9_-]+$", hash_str)
                            if is_valid:
                                link_hashes[link_str] = hash_str
                            else:
                                warnings.warn(
                                    f"Invalid hash format for link '{link_str}' in item '{uid}'",
                                    stacklevel=2,
                                )
            elif isinstance(entry, str):
                link_str = entry.strip()
                if not link_str:
                    warnings.warn(
                        f"Empty link UID in item '{uid}', skipping",
                        stacklevel=2,
                    )
                    continue
                links.append(link_str)
            else:
                # Non-string entry (bool, int, etc.) - reject with warning
                warnings.warn(
                    f"Link entry in item '{uid}' is not a string: {entry!r} "
                    f"(type: {type(entry).__name__}). Skipping invalid link.",
                    stacklevel=2,
                )
                continue

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

    # Validate reviewed field type
    reviewed = data.get("reviewed")
    if reviewed is not None and not isinstance(reviewed, str):
        warnings.warn(
            f"Item '{uid}' has non-string 'reviewed' field: {reviewed!r}. Expected hash string or null.",
            stacklevel=2,
        )
        reviewed = None  # Treat as not reviewed

    return {
        "uid": uid,
        "text": str(data.get("text", "")),
        "document_prefix": document_prefix,
        "active": data.get("active", True),
        "type": item_type,
        "header": data.get("header") or None,
        "links": links,
        "link_hashes": link_hashes,
        "reviewed": reviewed,
        "derived": data.get("derived", False),
        "testable": data.get("testable", True),
        "custom_attributes": custom_attributes,
    }


def write_item(item_data: dict[str, Any], path: Path, extra_fields: dict[str, Any] | None = None) -> None:
    """Write an item as a YAML file.

    Args:
        item_data: Dict with item fields (uid, text, etc.).
        path: Path to write the YAML file.
        extra_fields: Additional fields to include in the YAML output.
    """
    output: dict[str, Any] = {}
    # Consistent with read_item behavior - only include header if non-empty
    header = item_data.get("header")
    if header:
        output["header"] = header
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

    if not item_data.get("testable", True):
        output["testable"] = False

    if extra_fields:
        output.update(extra_fields)

    path.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write: write to temp file, then rename
    fd, tmp_path = tempfile.mkstemp(suffix=".yml", prefix=".tmp_", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            dump_yaml(output, f)
        Path(tmp_path).replace(path)  # Atomic on POSIX
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise


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

    Raises:
        ValueError: If the prefix pattern is invalid.
    """
    items = []
    try:
        pattern = re.compile(rf"^{re.escape(prefix)}{re.escape(sep)}\d+\.yml$", re.IGNORECASE)
    except re.error as e:
        raise ValueError(f"Invalid prefix pattern '{prefix}': {e}") from e

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
        digits: Number of digits in the UID (must be >= 1).
        existing_uids: List of existing UIDs.
        sep: Separator between prefix and number.

    Returns:
        Next available UID string.

    Raises:
        ValueError: If digits < 1 or if the prefix pattern is invalid.
    """
    if digits < 1:
        raise ValueError(f"digits must be >= 1, got {digits}")

    try:
        pattern = re.compile(rf"^{re.escape(prefix)}{re.escape(sep)}(\d+)$", re.IGNORECASE)
    except re.error as e:
        raise ValueError(f"Invalid prefix pattern '{prefix}': {e}") from e

    max_num = 0
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

    Hashes: text, header, links, type. All strings are normalized to NFC
    Unicode form for consistent hashing across platforms.

    Args:
        item_data: Dict with item fields.

    Returns:
        URL-safe base64-encoded SHA-256 hash.
    """

    def normalize(s: str) -> str:
        return unicodedata.normalize("NFC", s)

    content_parts = [
        normalize(str(item_data.get("text", ""))),
        normalize(str(item_data.get("header") or "")),
        str(sorted(item_data.get("links") or [])),
        str(item_data.get("type", "requirement")),
    ]
    content_str = "|".join(content_parts)
    hash_bytes = hashlib.sha256(content_str.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(hash_bytes).decode("ascii").rstrip("=")
