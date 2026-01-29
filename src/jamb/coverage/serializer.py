"""Save and load coverage data for decoupled matrix generation."""

import json
import os
import shutil
import tempfile
import warnings
from pathlib import Path
from typing import Any

from jamb.core.models import (
    Item,
    ItemCoverage,
    LinkedTest,
    MatrixMetadata,
    TestEnvironment,
    TraceabilityGraph,
)

COVERAGE_FILE = ".jamb"

# Supported coverage file versions for forward compatibility
CURRENT_VERSION = 1
SUPPORTED_VERSIONS = {1}

# Required top-level fields for file validation
REQUIRED_FIELDS = {"coverage", "graph"}


def save_coverage(
    coverage: dict[str, ItemCoverage],
    graph: TraceabilityGraph,
    output_path: str = COVERAGE_FILE,
    metadata: MatrixMetadata | None = None,
) -> None:
    """Save coverage data to .jamb file for later matrix generation.

    Args:
        coverage: Coverage data mapping UIDs to ItemCoverage.
        graph: The traceability graph with all items and relationships.
        output_path: Path to write the coverage file (default: .jamb).
        metadata: Optional matrix metadata for IEC 62304 compliance.
    """
    data: dict[str, Any] = {
        "version": 1,
        "coverage": {},
        "graph": {
            "items": {},
            "item_parents": graph.item_parents,
            "item_children": graph.item_children,
            "document_parents": graph.document_parents,
        },
    }

    # Serialize coverage
    for uid, cov in coverage.items():
        data["coverage"][uid] = {
            "item": _serialize_item(cov.item),
            "linked_tests": [_serialize_linked_test(lt) for lt in cov.linked_tests],
        }

    # Serialize all graph items (not just coverage items)
    for uid, item in graph.items.items():
        data["graph"]["items"][uid] = _serialize_item(item)

    # Serialize metadata if provided
    if metadata:
        data["metadata"] = _serialize_metadata(metadata)

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Use atomic write pattern: write to temp file, then rename
    # This prevents file corruption if the process is interrupted
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=path.parent,
            delete=False,
            suffix=".tmp",
            encoding="utf-8",
        ) as f:
            f.write(json.dumps(data, indent=2))
            f.flush()
            os.fsync(f.fileno())
            temp_path = f.name
        shutil.move(temp_path, path)  # Atomic on POSIX
    except OSError as atomic_err:
        # Fallback to direct write if atomic write fails
        try:
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError as fallback_err:
            raise OSError(
                f"Failed to write coverage file to {path}. "
                f"Atomic write failed: {atomic_err}. "
                f"Fallback write also failed: {fallback_err}"
            ) from fallback_err


def load_coverage(
    input_path: str = COVERAGE_FILE,
) -> tuple[dict[str, ItemCoverage], TraceabilityGraph, MatrixMetadata | None]:
    """Load coverage data from .jamb file.

    Args:
        input_path: Path to the coverage file (default: .jamb).

    Returns:
        Tuple of (coverage dict, TraceabilityGraph, optional MatrixMetadata).

    Raises:
        FileNotFoundError: If the coverage file does not exist.
        ValueError: If the coverage file is invalid or unsupported version.
    """
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Coverage file not found: {input_path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in coverage file: {e}") from e

    # Validate version with forward compatibility check
    version = data.get("version", 0)
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(
            f"Unsupported .jamb file version {version}. "
            f"Supported versions: {sorted(SUPPORTED_VERSIONS)}. "
            "Regenerate with 'pytest --jamb'."
        )

    # Validate required fields
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        raise ValueError(f"Corrupt .jamb file, missing required fields: {sorted(missing)}")

    # Deserialize graph
    graph = TraceabilityGraph()
    graph_data = data.get("graph", {})

    # Restore document parents first
    for prefix, parents in graph_data.get("document_parents", {}).items():
        graph.set_document_parents(prefix, parents)

    # Restore items
    for _uid, item_data in graph_data.get("items", {}).items():
        item = _deserialize_item(item_data)
        graph.add_item(item)

    # Deserialize coverage
    coverage: dict[str, ItemCoverage] = {}
    orphaned_uids: list[str] = []
    for uid, cov_data in data.get("coverage", {}).items():
        # Validate that coverage item UID exists in graph
        if uid not in graph.items:
            orphaned_uids.append(uid)

        # Validate item data has required field
        if "item" not in cov_data:
            warnings.warn(
                f"Malformed coverage entry for '{uid}': missing 'item' field",
                stacklevel=2,
            )
            continue

        item = _deserialize_item(cov_data["item"])
        linked_tests = [_deserialize_linked_test(lt) for lt in cov_data.get("linked_tests", [])]
        coverage[uid] = ItemCoverage(item=item, linked_tests=linked_tests)

    # Warn about orphaned items (in coverage but not in graph)
    if orphaned_uids:
        preview = orphaned_uids[:5]
        suffix = f" and {len(orphaned_uids) - 5} more" if len(orphaned_uids) > 5 else ""
        warnings.warn(
            f"Orphaned items in coverage not found in graph: {preview}{suffix}",
            stacklevel=2,
        )

    # Deserialize metadata if present
    metadata = None
    if "metadata" in data:
        metadata = _deserialize_metadata(data["metadata"])

    return coverage, graph, metadata


def _serialize_item(item: Item) -> dict[str, Any]:
    """Serialize an Item to a dictionary."""
    return {
        "uid": item.uid,
        "text": item.text,
        "document_prefix": item.document_prefix,
        "active": item.active,
        "type": item.type,
        "header": item.header,
        "links": item.links,
        "reviewed": item.reviewed,
        "derived": item.derived,
        "testable": item.testable,
        "custom_attributes": item.custom_attributes,
    }


VALID_ITEM_TYPES = {"requirement", "info", "heading"}


def _deserialize_item(data: dict[str, Any]) -> Item:
    """Deserialize a dictionary to an Item.

    Args:
        data: Dictionary with item fields.

    Returns:
        Deserialized Item object.

    Raises:
        ValueError: If required fields (uid, text, document_prefix) are missing.

    Note:
        Invalid item types issue a warning and default to 'requirement'.
    """
    # Validate required fields
    for field in ("uid", "text", "document_prefix"):
        if field not in data:
            raise ValueError(f"Missing required field '{field}' in item data")

    # Validate type field
    item_type = data.get("type", "requirement")
    if item_type not in VALID_ITEM_TYPES:
        warnings.warn(
            f"Invalid item type '{item_type}' for item '{data['uid']}', "
            f"expected one of {sorted(VALID_ITEM_TYPES)}. Defaulting to 'requirement'.",
            stacklevel=3,
        )
        item_type = "requirement"

    return Item(
        uid=data["uid"],
        text=data["text"],
        document_prefix=data["document_prefix"],
        active=data.get("active", True),
        type=item_type,
        header=data.get("header"),
        links=data.get("links", []),
        reviewed=data.get("reviewed"),
        derived=data.get("derived", False),
        testable=data.get("testable", True),
        custom_attributes=data.get("custom_attributes", {}),
    )


def _serialize_linked_test(lt: LinkedTest) -> dict[str, Any]:
    """Serialize a LinkedTest to a dictionary."""
    return {
        "test_nodeid": lt.test_nodeid,
        "item_uid": lt.item_uid,
        "test_outcome": lt.test_outcome,
        "notes": lt.notes,
        "test_actions": lt.test_actions,
        "expected_results": lt.expected_results,
        "actual_results": lt.actual_results,
        "execution_timestamp": lt.execution_timestamp,
    }


def _validate_timestamp(ts: str | None) -> str | None:
    """Validate timestamp format (ISO 8601).

    Args:
        ts: Timestamp string to validate, or None.

    Returns:
        The timestamp if valid, or None if invalid.
    """
    if ts is None:
        return None
    try:
        from datetime import datetime

        # Try to parse ISO format (handles both with and without timezone)
        datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return ts
    except (ValueError, AttributeError):
        warnings.warn(f"Invalid timestamp format: {ts}", stacklevel=3)
        return None


def _deserialize_linked_test(data: dict[str, Any]) -> LinkedTest:
    """Deserialize a dictionary to a LinkedTest."""
    return LinkedTest(
        test_nodeid=data["test_nodeid"],
        item_uid=data["item_uid"],
        test_outcome=data.get("test_outcome"),
        notes=data.get("notes", []),
        test_actions=data.get("test_actions", []),
        expected_results=data.get("expected_results", []),
        actual_results=data.get("actual_results", []),
        execution_timestamp=_validate_timestamp(data.get("execution_timestamp")),
    )


def _serialize_metadata(metadata: MatrixMetadata) -> dict[str, Any]:
    """Serialize MatrixMetadata to a dictionary."""
    result: dict[str, Any] = {
        "software_version": metadata.software_version,
        "tester_id": metadata.tester_id,
        "execution_timestamp": metadata.execution_timestamp,
    }
    if metadata.environment:
        env = metadata.environment
        result["environment"] = {
            "os_name": env.os_name,
            "os_version": env.os_version,
            "python_version": env.python_version,
            "platform": env.platform,
            "processor": env.processor,
            "hostname": env.hostname,
            "cpu_count": env.cpu_count,
            "test_tools": env.test_tools,
        }
    return result


def _deserialize_metadata(data: dict[str, Any]) -> MatrixMetadata:
    """Deserialize a dictionary to MatrixMetadata."""
    environment = None
    if "environment" in data and data["environment"]:
        env_data = data["environment"]
        environment = TestEnvironment(
            os_name=env_data.get("os_name", ""),
            os_version=env_data.get("os_version", ""),
            python_version=env_data.get("python_version", ""),
            platform=env_data.get("platform", ""),
            processor=env_data.get("processor", ""),
            hostname=env_data.get("hostname", ""),
            cpu_count=env_data.get("cpu_count"),
            test_tools=env_data.get("test_tools", {}),
        )
    return MatrixMetadata(
        software_version=data.get("software_version"),
        tester_id=data.get("tester_id", "Unknown"),
        execution_timestamp=data.get("execution_timestamp"),
        environment=environment,
    )
