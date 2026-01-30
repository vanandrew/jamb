"""Marker utilities for extracting requirement links from tests."""

import pytest


def get_tc_id_marker(item: pytest.Item) -> str | None:
    """Extract manual test case ID from a test item's marker.

    Supports @pytest.mark.tc_id('TC-AUTH-001').

    Args:
        item: A pytest test item.

    Returns:
        The TC ID string if present, None otherwise.

    Raises:
        TypeError: If the marker argument is not a string.
        ValueError: If the marker argument is empty or whitespace-only,
            or if multiple tc_id markers or arguments are provided.
    """
    tc_ids: list[str] = []

    for marker in item.iter_markers("tc_id"):
        if len(marker.args) != 1:
            raise ValueError(
                f"tc_id marker must have exactly one argument, got {len(marker.args)} in test {item.nodeid}"
            )
        arg = marker.args[0]
        if not isinstance(arg, str):
            raise TypeError(f"tc_id marker argument must be a string, got {type(arg).__name__}: {arg!r}")
        tc_id = arg.strip()
        if not tc_id:
            raise ValueError(f"Empty tc_id in test {item.nodeid}")
        tc_ids.append(tc_id)

    if len(tc_ids) > 1:
        raise ValueError(f"Multiple tc_id markers found on test {item.nodeid}: {tc_ids}")

    return tc_ids[0] if tc_ids else None


def get_requirement_markers(item: pytest.Item) -> list[str]:
    """
    Extract requirement item UIDs from a test item's markers.

    Supports @pytest.mark.requirement('UT001', 'UT002', ...).

    Args:
        item: A pytest test item.

    Returns:
        List of requirement item UIDs found in requirement markers.
        Duplicates within the same test are removed while preserving order.

    Raises:
        TypeError: If a marker argument is not a string.
        ValueError: If a marker argument is empty or whitespace-only.
    """
    uids: list[str] = []
    seen: set[str] = set()

    for marker in item.iter_markers("requirement"):
        for arg in marker.args:
            if not isinstance(arg, str):
                raise TypeError(f"Requirement marker arguments must be strings, got {type(arg).__name__}: {arg!r}")
            uid = arg.strip()
            if not uid:
                raise ValueError(f"Empty requirement UID in test {item.nodeid}")
            if uid not in seen:
                seen.add(uid)
                uids.append(uid)

    return uids
