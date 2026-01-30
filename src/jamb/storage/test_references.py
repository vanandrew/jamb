"""Test reference operations for jamb.

Provides functions to find, update, and remove @pytest.mark.requirement()
references in test files.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RequirementReference:
    """A reference to a requirement UID in a test file.

    Attributes:
        file: Path to the test file containing the reference.
        line: 1-based line number of the UID string.
        column: 0-based column offset where the quoted string starts.
        end_column: 0-based column offset where the quoted string ends.
        uid: The requirement UID string value.
        test_name: Name of the enclosing test function, if determinable.
    """

    file: Path
    line: int
    column: int
    end_column: int
    uid: str
    test_name: str | None = None


def _is_requirement_marker(node: ast.Call) -> bool:
    """Check if an AST Call node is a requirement marker.

    Handles multiple import styles:
    - pytest.mark.requirement(...)
    - mark.requirement(...)
    - requirement(...)

    Args:
        node: An ``ast.Call`` node to inspect.

    Returns:
        ``True`` if the node represents a requirement marker call,
        ``False`` otherwise.
    """
    func = node.func

    # @pytest.mark.requirement(...)
    if isinstance(func, ast.Attribute) and func.attr == "requirement":
        if isinstance(func.value, ast.Attribute) and func.value.attr == "mark":
            if isinstance(func.value.value, ast.Name) and func.value.value.id == "pytest":
                return True
        # @mark.requirement(...)
        if isinstance(func.value, ast.Name) and func.value.id == "mark":
            return True

    # @requirement(...)
    if isinstance(func, ast.Name) and func.id == "requirement":
        return True

    return False


def _find_enclosing_function(tree: ast.AST, target_line: int) -> str | None:
    """Find the name of the function/method enclosing a given line.

    Args:
        tree: The parsed AST of the source file.
        target_line: The 1-based line number to search for.

    Returns:
        The name of the enclosing function, or None if not found.
    """
    enclosing: str | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            # Check if the target line is within this function's decorator range
            # Decorators are applied before the function definition
            start_line = node.lineno
            if node.decorator_list:
                start_line = min(d.lineno for d in node.decorator_list)
            end_line = getattr(node, "end_lineno", node.lineno)
            if start_line <= target_line <= end_line:
                enclosing = node.name
    return enclosing


def _find_uid_positions_in_source(source: str) -> list[tuple[int, int, int, str, str | None]]:
    """Parse source and return positions of all UIDs in requirement markers.

    Args:
        source: Python source code to parse.

    Returns:
        List of tuples (line, column, end_column, uid, test_name).
        Line is 1-based, columns are 0-based.
    """
    tree = ast.parse(source)
    refs: list[tuple[int, int, int, str, str | None]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_requirement_marker(node):
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    test_name = _find_enclosing_function(tree, arg.lineno)
                    refs.append(
                        (
                            arg.lineno,
                            arg.col_offset,
                            arg.end_col_offset or (arg.col_offset + len(repr(arg.value))),
                            arg.value,
                            test_name,
                        )
                    )
            # Also check keyword arguments
            for kw in node.keywords:
                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    test_name = _find_enclosing_function(tree, kw.value.lineno)
                    refs.append(
                        (
                            kw.value.lineno,
                            kw.value.col_offset,
                            kw.value.end_col_offset or (kw.value.col_offset + len(repr(kw.value.value))),
                            kw.value.value,
                            test_name,
                        )
                    )
    return refs


def _get_test_files(test_dir: Path) -> list[Path]:
    """Get all test files in a directory.

    Args:
        test_dir: Directory to search for test files.

    Returns:
        List of paths to test files (test_*.py and *_test.py).
    """
    test_files: list[Path] = []
    for pattern in ("test_*.py", "*_test.py"):
        test_files.extend(test_dir.rglob(pattern))
    return test_files


def find_test_references(
    test_dir: Path,
    uid: str | None = None,
) -> list[RequirementReference]:
    """Find all @pytest.mark.requirement references in test files.

    Args:
        test_dir: Directory to search for test files.
        uid: Optional UID to filter by. If None, returns all references.

    Returns:
        List of RequirementReference objects for found references.
    """
    refs: list[RequirementReference] = []

    for test_file in _get_test_files(test_dir):
        try:
            source = test_file.read_text()
            positions = _find_uid_positions_in_source(source)

            for line, col, end_col, found_uid, test_name in positions:
                if uid is None or found_uid == uid:
                    refs.append(
                        RequirementReference(
                            file=test_file,
                            line=line,
                            column=col,
                            end_column=end_col,
                            uid=found_uid,
                            test_name=test_name,
                        )
                    )
        except (SyntaxError, OSError, UnicodeDecodeError):
            # Skip files that can't be parsed
            continue

    return refs


def update_test_references(
    rename_map: dict[str, str],
    test_dir: Path,
) -> dict[Path, list[str]]:
    """Update UIDs in @pytest.mark.requirement decorators.

    Args:
        rename_map: Mapping of old UIDs to new UIDs.
        test_dir: Directory containing test files.

    Returns:
        Dict mapping file paths to lists of change descriptions (e.g., "SRS003->SRS002").
    """
    changes: dict[Path, list[str]] = {}

    for test_file in _get_test_files(test_dir):
        try:
            source = test_file.read_text()
            positions = _find_uid_positions_in_source(source)

            # Filter to positions that need updating
            refs_to_update = [
                (line, col, end_col, uid) for line, col, end_col, uid, _ in positions if uid in rename_map
            ]

            if not refs_to_update:
                continue

            # Sort by position (reverse) to replace from end to start
            refs_to_update.sort(key=lambda r: (r[0], r[1]), reverse=True)

            lines = source.splitlines(keepends=True)
            file_changes: list[str] = []

            for line_num, col, end_col, old_uid in refs_to_update:
                new_uid = rename_map[old_uid]
                line_idx = line_num - 1
                line = lines[line_idx]

                # Replace the quoted UID at the exact position
                # The AST gives us the position of the string constant (including quotes)
                before = line[:col]
                after = line[end_col:]
                lines[line_idx] = before + f'"{new_uid}"' + after
                file_changes.append(f"{old_uid}->{new_uid}")

            test_file.write_text("".join(lines))
            changes[test_file] = file_changes

        except (SyntaxError, OSError, UnicodeDecodeError):
            # Skip files that can't be parsed
            continue

    return changes


def remove_test_reference(
    uid: str,
    test_dir: Path,
    remove_empty: bool = True,
) -> dict[Path, list[str]]:
    """Remove a UID from @pytest.mark.requirement decorators.

    When remove_empty is True and removing the UID leaves an empty decorator
    (no remaining UIDs), the entire decorator line is removed.

    Args:
        uid: The UID to remove from decorators.
        test_dir: Directory containing test files.
        remove_empty: If True, remove entire decorator line when no UIDs remain.

    Returns:
        Dict mapping file paths to lists of change descriptions.
    """
    changes: dict[Path, list[str]] = {}

    for test_file in _get_test_files(test_dir):
        try:
            source = test_file.read_text()
            tree = ast.parse(source)

            # Find all requirement markers and their UIDs
            markers_to_process: list[tuple[ast.Call, list[str]]] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _is_requirement_marker(node):
                    uids_in_marker: list[str] = []
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            uids_in_marker.append(arg.value)
                    for kw in node.keywords:
                        if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                            uids_in_marker.append(kw.value.value)
                    if uid in uids_in_marker:
                        markers_to_process.append((node, uids_in_marker))

            if not markers_to_process:
                continue

            lines = source.splitlines(keepends=True)
            file_changes: list[str] = []

            # Process markers from end to start to avoid line number shifts
            markers_to_process.sort(key=lambda m: m[0].lineno, reverse=True)

            for marker_node, uids_in_marker in markers_to_process:
                remaining_uids = [u for u in uids_in_marker if u != uid]

                if not remaining_uids and remove_empty:
                    # Remove entire decorator line
                    line_idx = marker_node.lineno - 1
                    # Find the start of the decorator (@ symbol)
                    # Walk backwards from the marker to find @
                    decorator_start_line = line_idx
                    for i in range(line_idx, -1, -1):
                        stripped = lines[i].lstrip()
                        if stripped.startswith("@"):
                            decorator_start_line = i
                            break
                    # Remove the decorator line(s)
                    end_line = getattr(marker_node, "end_lineno", marker_node.lineno)
                    for i in range(end_line - 1, decorator_start_line - 1, -1):
                        if i < len(lines):
                            lines[i] = ""
                    file_changes.append(f"removed decorator with {uid}")
                else:
                    # Find and remove just the UID argument
                    for arg in marker_node.args:
                        if isinstance(arg, ast.Constant) and arg.value == uid:
                            line_idx = arg.lineno - 1
                            line = lines[line_idx]
                            col = arg.col_offset
                            end_col = arg.end_col_offset or (col + len(repr(uid)))

                            # Also remove trailing comma if present
                            after_str = line[end_col:].lstrip()
                            extra_remove = len(line[end_col:]) - len(after_str)
                            if after_str.startswith(","):
                                end_col += extra_remove + 1
                                # Remove any space after comma too
                                rest = line[end_col:]
                                if rest and rest[0] == " ":
                                    end_col += 1
                            else:
                                # Check for leading comma (we're the last arg)
                                before_str = line[:col].rstrip()
                                if before_str.endswith(","):
                                    col = len(before_str) - 1

                            before = line[:col]
                            after = line[end_col:]
                            lines[line_idx] = before + after
                            file_changes.append(f"removed {uid}")
                            break

            # Clean up empty lines from removed decorators
            cleaned_lines = [line for line in lines if line.strip() or line == "\n"]

            test_file.write_text("".join(cleaned_lines))
            changes[test_file] = file_changes

        except (SyntaxError, OSError, UnicodeDecodeError):
            # Skip files that can't be parsed
            continue

    return changes
