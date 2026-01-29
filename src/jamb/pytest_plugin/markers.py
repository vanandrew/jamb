"""Marker utilities for extracting requirement links from tests."""

import pytest


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
