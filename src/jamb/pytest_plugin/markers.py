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
    """
    uids: list[str] = []

    for marker in item.iter_markers("requirement"):
        for arg in marker.args:
            if not isinstance(arg, str):
                raise TypeError(
                    f"Requirement marker arguments must be strings, "
                    f"got {type(arg).__name__}: {arg!r}"
                )
            uids.append(arg)

    return uids
