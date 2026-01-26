"""Discover doorstop document trees."""

from pathlib import Path

import doorstop


def discover_tree(root: Path | None = None) -> doorstop.Tree:
    """
    Discover and build the doorstop document tree.

    Uses doorstop.build() which searches for .doorstop.yml files
    starting from the current directory or specified root.

    Args:
        root: Optional root directory to search from. If None, uses cwd.

    Returns:
        The doorstop Tree object containing all discovered documents.
    """
    if root:
        import os

        original_cwd = os.getcwd()
        os.chdir(root)
        try:
            return doorstop.build()
        finally:
            os.chdir(original_cwd)
    return doorstop.build()
