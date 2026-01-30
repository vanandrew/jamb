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


def find_orphaned_references(
    test_dir: Path,
    valid_uids: set[str],
) -> list[RequirementReference]:
    """Find test references to UIDs that don't exist in requirements.

    Args:
        test_dir: Directory containing test files.
        valid_uids: Set of UIDs that currently exist in requirements.

    Returns:
        List of RequirementReference objects for references to non-existent UIDs.
    """
    all_refs = find_test_references(test_dir)
    return [ref for ref in all_refs if ref.uid not in valid_uids]


def detect_reference_collisions(
    rename_map: dict[str, str],
    test_dir: Path,
    valid_uids: set[str],
) -> list[tuple[str, RequirementReference]]:
    """Detect when renaming would create duplicate test references.

    When reordering items, some UIDs become targets of renames (e.g., SRS003 -> SRS002).
    If there are orphaned test references (refs to deleted items) that already use
    a target UID, the reorder would create ambiguity.

    Args:
        rename_map: Mapping of old UIDs to new UIDs from reorder operation.
        test_dir: Directory containing test files.
        valid_uids: Set of UIDs that currently exist in requirements.

    Returns:
        List of (target_uid, orphan_ref) tuples where an orphaned reference
        already uses a UID that would become the target of a rename.
    """
    target_uids = set(rename_map.values())
    orphans = find_orphaned_references(test_dir, valid_uids)
    return [(ref.uid, ref) for ref in orphans if ref.uid in target_uids]


def _is_tc_id_marker(node: ast.Call) -> bool:
    """Check if an AST Call node is a tc_id marker.

    Handles multiple import styles:
    - pytest.mark.tc_id(...)
    - mark.tc_id(...)

    Args:
        node: An ``ast.Call`` node to inspect.

    Returns:
        ``True`` if the node represents a tc_id marker call.
    """
    func = node.func

    # @pytest.mark.tc_id(...)
    if isinstance(func, ast.Attribute) and func.attr == "tc_id":
        if isinstance(func.value, ast.Attribute) and func.value.attr == "mark":
            if isinstance(func.value.value, ast.Name) and func.value.value.id == "pytest":
                return True
        # @mark.tc_id(...)
        if isinstance(func.value, ast.Name) and func.value.id == "mark":
            return True

    return False


def _has_tc_id_marker(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check if a function has a tc_id marker decorator.

    Args:
        func_node: A function definition AST node.

    Returns:
        True if the function has a tc_id marker.
    """
    for decorator in func_node.decorator_list:
        if isinstance(decorator, ast.Call) and _is_tc_id_marker(decorator):
            return True
    return False


def _nodeid_to_file_and_func(nodeid: str) -> tuple[str, str]:
    """Extract file path and function name from pytest nodeid.

    Args:
        nodeid: Pytest nodeid like "tests/test_foo.py::test_bar[param]".

    Returns:
        Tuple of (file_path, function_name).
    """
    # Remove parameter suffix if present
    base = nodeid.split("[")[0]
    parts = base.split("::")
    file_path = parts[0]
    func_name = parts[-1] if len(parts) > 1 else ""
    return file_path, func_name


def insert_tc_id_markers(
    tc_mapping: dict[str, str],
    test_dir: Path,
    dry_run: bool = False,
) -> dict[Path, list[str]]:
    """Insert @pytest.mark.tc_id() decorators into test files.

    For each test in tc_mapping, adds a tc_id decorator if not already present.
    Parameterized test variations share the same base function, so only one
    decorator is inserted for the base function.

    Args:
        tc_mapping: Dict mapping test nodeid to TC ID.
        test_dir: Root directory containing test files.
        dry_run: If True, don't actually modify files, just report changes.

    Returns:
        Dict mapping file paths to lists of change descriptions.
    """
    changes: dict[Path, list[str]] = {}

    # Group by base nodeid (strip parameter suffix) to avoid duplicate insertions
    base_to_tc_id: dict[str, str] = {}
    for nodeid, tc_id in tc_mapping.items():
        base = nodeid.split("[")[0]
        if base not in base_to_tc_id:
            # For parameterized tests with suffixes, use the base TC ID
            # e.g., TC001a -> TC001
            base_tc_id = tc_id.rstrip("abcdefghijklmnopqrstuvwxyz")
            base_to_tc_id[base] = base_tc_id

    # Group by file
    file_to_funcs: dict[str, dict[str, str]] = {}  # file -> {func_name: tc_id}
    for base_nodeid, tc_id in base_to_tc_id.items():
        file_path, func_name = _nodeid_to_file_and_func(base_nodeid)
        if not func_name:
            continue
        file_to_funcs.setdefault(file_path, {})[func_name] = tc_id

    # Process each file
    for rel_file_path, func_tc_ids in file_to_funcs.items():
        # Find the actual file (could be absolute or relative to test_dir)
        resolved_path = Path(rel_file_path)
        if not resolved_path.is_absolute():
            resolved_path = test_dir / rel_file_path
        if not resolved_path.exists():
            # Try relative to current dir
            resolved_path = Path(rel_file_path)
        if not resolved_path.exists():
            continue

        try:
            source = resolved_path.read_text()
            tree = ast.parse(source)
        except (SyntaxError, OSError, UnicodeDecodeError):
            continue

        # Find test functions that need tc_id markers
        insertions: list[tuple[int, str, str]] = []  # (line, indent, tc_id)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                if node.name in func_tc_ids and not _has_tc_id_marker(node):
                    # Find insertion point (before first decorator or function def)
                    if node.decorator_list:
                        insert_line = min(d.lineno for d in node.decorator_list)
                        # Get indentation from first decorator
                        # col_offset points to the expression after @, so subtract 1
                        first_dec = node.decorator_list[0]
                        indent_col = max(0, first_dec.col_offset - 1)
                    else:
                        insert_line = node.lineno
                        indent_col = node.col_offset

                    tc_id = func_tc_ids[node.name]
                    indent = " " * indent_col
                    insertions.append((insert_line, indent, tc_id))

        if not insertions:
            continue

        # Sort insertions by line number (reverse to insert from bottom up)
        insertions.sort(key=lambda x: x[0], reverse=True)

        if dry_run:
            dry_run_changes = [f"would add @pytest.mark.tc_id('{tc_id}')" for _, _, tc_id in insertions]
            changes[resolved_path] = dry_run_changes
            continue

        # Apply insertions
        lines = source.splitlines(keepends=True)
        applied_changes: list[str] = []

        for line_num, indent, tc_id in insertions:
            # Insert new decorator line
            decorator_line = f'{indent}@pytest.mark.tc_id("{tc_id}")\n'
            # line_num is 1-indexed, list is 0-indexed
            lines.insert(line_num - 1, decorator_line)
            applied_changes.append(f"added @pytest.mark.tc_id('{tc_id}')")

        # Write back
        resolved_path.write_text("".join(lines))
        changes[resolved_path] = applied_changes

    return changes
