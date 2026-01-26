"""Marker utilities for extracting requirement links from tests."""

import pytest


def get_requirement_markers(item: pytest.Item) -> list[str]:
    """
    Extract doorstop item UIDs from a test item's markers.

    Supports @pytest.mark.requirement('UT001', 'UT002', ...).

    Args:
        item: A pytest test item.

    Returns:
        List of doorstop item UIDs found in requirement markers.
    """
    uids: list[str] = []

    for marker in item.iter_markers("requirement"):
        uids.extend(marker.args)

    return uids
