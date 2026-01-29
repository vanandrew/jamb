"""Shared utilities for matrix generation."""

from pathlib import Path

from jamb.core.models import ItemCoverage, LinkedTest

# Supported matrix format extensions
EXTENSION_TO_FORMAT = {
    ".html": "html",
    ".htm": "html",
    ".json": "json",
    ".csv": "csv",
    ".md": "markdown",
    ".xlsx": "xlsx",
}


def infer_format(path: str) -> str:
    """Infer output format from file extension.

    Args:
        path: File path with extension.

    Returns:
        Format string: "html", "json", "csv", "markdown", or "xlsx".

    Raises:
        ValueError: If the file extension is not recognized.
    """
    ext = Path(path).suffix.lower()
    if ext not in EXTENSION_TO_FORMAT:
        supported = ", ".join(sorted(EXTENSION_TO_FORMAT.keys()))
        raise ValueError(f"Unrecognized file extension '{ext}' for '{path}'. Supported extensions: {supported}")
    return EXTENSION_TO_FORMAT[ext]


def group_tests_by_nodeid(
    coverage: dict[str, ItemCoverage],
) -> tuple[list[str], dict[str, list[LinkedTest]], int]:
    """Group linked tests by nodeid and sort for consistent ordering.

    Collects all tests from coverage data, groups them by nodeid, and
    returns them sorted by first requirement UID (alphabetically) with
    nodeid as tiebreaker.

    Args:
        coverage: Coverage data mapping UIDs to ItemCoverage.

    Returns:
        Tuple of:
        - sorted_nodeids: List of test nodeids in sorted order
        - tests_by_nodeid: Dict mapping nodeid to list of LinkedTest
        - width: Minimum width for zero-padded TC IDs (at least 3)
    """
    tests_by_nodeid: dict[str, list[LinkedTest]] = {}
    for cov in coverage.values():
        for link in cov.linked_tests:
            tests_by_nodeid.setdefault(link.test_nodeid, []).append(link)

    if not tests_by_nodeid:
        return [], {}, 3

    def sort_key(nodeid: str) -> tuple[str, str]:
        links = tests_by_nodeid[nodeid]
        reqs = sorted(set(lk.item_uid for lk in links))
        first_req = reqs[0] if reqs else ""
        return (first_req, nodeid)

    sorted_nodeids = sorted(tests_by_nodeid.keys(), key=sort_key)
    width = max(3, len(str(len(sorted_nodeids))))

    return sorted_nodeids, tests_by_nodeid, width
