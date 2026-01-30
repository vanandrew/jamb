"""Unit tests for jamb.storage.test_references module."""

import pytest

from jamb.storage.test_references import (
    RequirementReference,
    _find_enclosing_function,
    _find_uid_positions_in_source,
    _is_requirement_marker,
    detect_reference_collisions,
    find_orphaned_references,
    find_test_references,
    insert_tc_id_markers,
    remove_test_reference,
    update_test_references,
)


class TestIsRequirementMarker:
    """Tests for _is_requirement_marker function."""

    def test_fully_qualified_pytest_mark_requirement(self):
        """@pytest.mark.requirement(...) is recognized."""
        import ast

        source = '@pytest.mark.requirement("SRS001")\ndef test_foo(): pass'
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                assert _is_requirement_marker(node) is True
                return
        pytest.fail("No Call node found")

    def test_mark_requirement(self):
        """@mark.requirement(...) is recognized."""
        import ast

        source = '@mark.requirement("SRS001")\ndef test_foo(): pass'
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                assert _is_requirement_marker(node) is True
                return
        pytest.fail("No Call node found")

    def test_bare_requirement(self):
        """@requirement(...) is recognized."""
        import ast

        source = '@requirement("SRS001")\ndef test_foo(): pass'
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                assert _is_requirement_marker(node) is True
                return
        pytest.fail("No Call node found")

    def test_other_decorator_not_recognized(self):
        """Other decorators like @pytest.mark.skip are not recognized."""
        import ast

        source = '@pytest.mark.skip("reason")\ndef test_foo(): pass'
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                assert _is_requirement_marker(node) is False

    def test_parametrize_not_recognized(self):
        """@pytest.mark.parametrize is not recognized."""
        import ast

        source = '@pytest.mark.parametrize("x", [1, 2, 3])\ndef test_foo(x): pass'
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                assert _is_requirement_marker(node) is False


class TestFindEnclosingFunction:
    """Tests for _find_enclosing_function."""

    def test_finds_enclosing_function(self):
        """Finds the function that contains a given line."""
        import ast

        source = """
def test_one():
    pass

def test_two():
    x = 1
    pass
"""
        tree = ast.parse(source)
        # Line 6 is inside test_two
        assert _find_enclosing_function(tree, 6) == "test_two"

    def test_finds_function_from_decorator_line(self):
        """Finds function when line is on the decorator."""
        import ast

        source = """
@decorator
def test_one():
    pass
"""
        tree = ast.parse(source)
        # Line 2 is the decorator for test_one
        assert _find_enclosing_function(tree, 2) == "test_one"

    def test_returns_none_for_module_level(self):
        """Returns None for module-level code."""
        import ast

        source = """
x = 1

def test_one():
    pass
"""
        tree = ast.parse(source)
        # Line 2 is module-level
        assert _find_enclosing_function(tree, 2) is None


class TestFindUidPositionsInSource:
    """Tests for _find_uid_positions_in_source."""

    def test_single_uid(self):
        """Finds a single UID in requirement marker."""
        source = '@pytest.mark.requirement("SRS001")\ndef test_foo(): pass'
        positions = _find_uid_positions_in_source(source)
        assert len(positions) == 1
        assert positions[0][3] == "SRS001"
        assert positions[0][4] == "test_foo"  # test_name

    def test_multiple_uids_in_one_decorator(self):
        """Finds multiple UIDs in a single decorator."""
        source = '@pytest.mark.requirement("SRS001", "SRS002")\ndef test_foo(): pass'
        positions = _find_uid_positions_in_source(source)
        assert len(positions) == 2
        uids = {p[3] for p in positions}
        assert uids == {"SRS001", "SRS002"}

    def test_multiple_decorators(self):
        """Finds UIDs across multiple tests."""
        source = """
@pytest.mark.requirement("SRS001")
def test_one():
    pass

@pytest.mark.requirement("SRS002")
def test_two():
    pass
"""
        positions = _find_uid_positions_in_source(source)
        assert len(positions) == 2
        uids = {p[3] for p in positions}
        assert uids == {"SRS001", "SRS002"}

    def test_all_import_styles(self):
        """All import styles are detected."""
        source = """
@pytest.mark.requirement("SRS001")
def test_fully_qualified(): pass

@mark.requirement("SRS002")
def test_mark_style(): pass

@requirement("SRS003")
def test_bare_style(): pass
"""
        positions = _find_uid_positions_in_source(source)
        uids = {p[3] for p in positions}
        assert uids == {"SRS001", "SRS002", "SRS003"}


class TestFindRequirementReferences:
    """Tests for find_test_references function."""

    def test_finds_references_in_test_file(self, tmp_path):
        """Finds references in test_*.py files."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""
import pytest

@pytest.mark.requirement("SRS001")
def test_feature():
    pass
""")
        refs = find_test_references(tmp_path)
        assert len(refs) == 1
        assert refs[0].uid == "SRS001"
        assert refs[0].test_name == "test_feature"
        assert refs[0].file == test_file

    def test_finds_references_in_test_suffix_file(self, tmp_path):
        """Finds references in *_test.py files."""
        test_file = tmp_path / "feature_test.py"
        test_file.write_text("""
import pytest

@pytest.mark.requirement("SRS002")
def test_it():
    pass
""")
        refs = find_test_references(tmp_path)
        assert len(refs) == 1
        assert refs[0].uid == "SRS002"

    def test_filter_by_uid(self, tmp_path):
        """Filters references by specific UID."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""
@pytest.mark.requirement("SRS001")
def test_one(): pass

@pytest.mark.requirement("SRS002")
def test_two(): pass
""")
        refs = find_test_references(tmp_path, uid="SRS001")
        assert len(refs) == 1
        assert refs[0].uid == "SRS001"

    def test_ignores_non_test_files(self, tmp_path):
        """Non-test files are not scanned."""
        non_test_file = tmp_path / "utils.py"
        non_test_file.write_text("""
@pytest.mark.requirement("SRS001")
def helper(): pass
""")
        refs = find_test_references(tmp_path)
        assert len(refs) == 0

    def test_skips_invalid_syntax(self, tmp_path):
        """Files with syntax errors are skipped."""
        test_file = tmp_path / "test_broken.py"
        test_file.write_text("def test_foo(: pass")  # Invalid syntax
        refs = find_test_references(tmp_path)
        assert len(refs) == 0

    def test_nested_test_directory(self, tmp_path):
        """Finds references in nested directories."""
        nested = tmp_path / "tests" / "integration"
        nested.mkdir(parents=True)
        test_file = nested / "test_integration.py"
        test_file.write_text("""
@pytest.mark.requirement("SRS003")
def test_integration(): pass
""")
        refs = find_test_references(tmp_path)
        assert len(refs) == 1
        assert refs[0].uid == "SRS003"


class TestUpdateRequirementReferences:
    """Tests for update_test_references function."""

    def test_updates_single_reference(self, tmp_path):
        """Updates a single UID reference."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""
@pytest.mark.requirement("SRS003")
def test_feature():
    pass
""")
        changes = update_test_references({"SRS003": "SRS002"}, tmp_path)
        assert test_file in changes
        assert "SRS003->SRS002" in changes[test_file]

        # Verify file was updated
        content = test_file.read_text()
        assert '"SRS002"' in content
        assert '"SRS003"' not in content

    def test_updates_multiple_references_in_file(self, tmp_path):
        """Updates multiple UIDs in the same file."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""
@pytest.mark.requirement("SRS003")
def test_one(): pass

@pytest.mark.requirement("SRS005")
def test_two(): pass
""")
        changes = update_test_references({"SRS003": "SRS002", "SRS005": "SRS004"}, tmp_path)
        assert test_file in changes
        assert len(changes[test_file]) == 2

        content = test_file.read_text()
        assert '"SRS002"' in content
        assert '"SRS004"' in content
        assert '"SRS003"' not in content
        assert '"SRS005"' not in content

    def test_preserves_unmarked_uids(self, tmp_path):
        """UIDs not in rename_map are preserved."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""
@pytest.mark.requirement("SRS001")
def test_one(): pass

@pytest.mark.requirement("SRS003")
def test_two(): pass
""")
        update_test_references({"SRS003": "SRS002"}, tmp_path)
        content = test_file.read_text()
        assert '"SRS001"' in content  # Preserved
        assert '"SRS002"' in content  # Updated
        assert '"SRS003"' not in content  # Renamed

    def test_returns_empty_when_no_changes(self, tmp_path):
        """Returns empty dict when no changes needed."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""
@pytest.mark.requirement("SRS001")
def test_feature(): pass
""")
        changes = update_test_references({"SRS999": "SRS000"}, tmp_path)
        assert changes == {}

    def test_updates_multiple_uids_in_single_decorator(self, tmp_path):
        """Updates when multiple UIDs are in one decorator."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""
@pytest.mark.requirement("SRS003", "SRS005")
def test_feature(): pass
""")
        update_test_references({"SRS003": "SRS002", "SRS005": "SRS004"}, tmp_path)
        content = test_file.read_text()
        assert '"SRS002"' in content
        assert '"SRS004"' in content


class TestRemoveRequirementReference:
    """Tests for remove_test_reference function."""

    def test_removes_single_uid_decorator(self, tmp_path):
        """Removes entire decorator when only UID is removed."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""import pytest

@pytest.mark.requirement("SRS001")
def test_feature():
    pass
""")
        changes = remove_test_reference("SRS001", tmp_path, remove_empty=True)
        assert test_file in changes

        content = test_file.read_text()
        assert "@pytest.mark.requirement" not in content
        assert "def test_feature" in content

    def test_removes_uid_from_multiple(self, tmp_path):
        """Removes just the UID when decorator has multiple."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""import pytest

@pytest.mark.requirement("SRS001", "SRS002")
def test_feature():
    pass
""")
        changes = remove_test_reference("SRS001", tmp_path, remove_empty=True)
        assert test_file in changes

        content = test_file.read_text()
        assert "@pytest.mark.requirement" in content
        assert '"SRS002"' in content
        assert '"SRS001"' not in content

    def test_returns_empty_when_no_matches(self, tmp_path):
        """Returns empty dict when UID not found."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""
@pytest.mark.requirement("SRS001")
def test_feature(): pass
""")
        changes = remove_test_reference("SRS999", tmp_path)
        assert changes == {}


class TestRequirementReferenceClass:
    """Tests for RequirementReference dataclass."""

    def test_dataclass_fields(self, tmp_path):
        """RequirementReference has expected fields."""
        ref = RequirementReference(
            file=tmp_path / "test_file.py",
            line=10,
            column=5,
            end_column=15,
            uid="SRS001",
            test_name="test_foo",
        )
        assert ref.file == tmp_path / "test_file.py"
        assert ref.line == 10
        assert ref.column == 5
        assert ref.end_column == 15
        assert ref.uid == "SRS001"
        assert ref.test_name == "test_foo"

    def test_test_name_optional(self, tmp_path):
        """test_name defaults to None."""
        ref = RequirementReference(
            file=tmp_path / "test_file.py",
            line=1,
            column=0,
            end_column=10,
            uid="SRS001",
        )
        assert ref.test_name is None


class TestFindUidPositionsKeywordArgs:
    """Tests for keyword arguments in _find_uid_positions_in_source."""

    def test_keyword_argument_uid(self):
        """UIDs passed as keyword arguments are detected."""
        source = '@pytest.mark.requirement(uid="SRS001")\ndef test_foo(): pass'
        positions = _find_uid_positions_in_source(source)
        assert len(positions) == 1
        assert positions[0][3] == "SRS001"
        assert positions[0][4] == "test_foo"

    def test_multiple_keyword_arguments(self):
        """Multiple keyword UIDs in a single decorator."""
        source = '@pytest.mark.requirement(uid1="SRS001", uid2="SRS002")\ndef test_foo(): pass'
        positions = _find_uid_positions_in_source(source)
        assert len(positions) == 2
        uids = {p[3] for p in positions}
        assert uids == {"SRS001", "SRS002"}

    def test_mixed_positional_and_keyword(self):
        """Mix of positional and keyword arguments."""
        source = '@pytest.mark.requirement("SRS001", uid="SRS002")\ndef test_foo(): pass'
        positions = _find_uid_positions_in_source(source)
        assert len(positions) == 2
        uids = {p[3] for p in positions}
        assert uids == {"SRS001", "SRS002"}


class TestUpdateTestReferencesExceptionHandling:
    """Tests for exception handling in update_test_references."""

    def test_skips_file_with_syntax_error(self, tmp_path):
        """Files with syntax errors are skipped."""
        bad_file = tmp_path / "test_bad.py"
        bad_file.write_text("def broken(\n")  # Invalid syntax
        good_file = tmp_path / "test_good.py"
        good_file.write_text('@pytest.mark.requirement("SRS003")\ndef test_ok(): pass')

        changes = update_test_references({"SRS003": "SRS002"}, tmp_path)
        # Should update good file, skip bad file
        assert good_file in changes
        assert bad_file not in changes

    def test_skips_file_with_encoding_error(self, tmp_path):
        """Files with encoding errors are skipped."""
        bad_file = tmp_path / "test_bad_encoding.py"
        bad_file.write_bytes(b"\x80\x81\x82")  # Invalid UTF-8
        good_file = tmp_path / "test_good.py"
        good_file.write_text('@pytest.mark.requirement("SRS003")\ndef test_ok(): pass')

        changes = update_test_references({"SRS003": "SRS002"}, tmp_path)
        assert good_file in changes
        assert bad_file not in changes

    def test_skips_file_with_os_error(self, tmp_path):
        """Files with OS errors (e.g., permission denied) are skipped."""
        import os

        bad_file = tmp_path / "test_no_read.py"
        bad_file.write_text('@pytest.mark.requirement("SRS001")\ndef test_a(): pass')
        good_file = tmp_path / "test_good.py"
        good_file.write_text('@pytest.mark.requirement("SRS003")\ndef test_ok(): pass')

        # Make file unreadable
        original_mode = bad_file.stat().st_mode
        try:
            os.chmod(bad_file, 0o000)
            changes = update_test_references({"SRS003": "SRS002"}, tmp_path)
            assert good_file in changes
            assert bad_file not in changes
        finally:
            os.chmod(bad_file, original_mode)


class TestRemoveTestReferenceExceptionHandling:
    """Tests for exception handling in remove_test_reference."""

    def test_skips_file_with_syntax_error(self, tmp_path):
        """Files with syntax errors are skipped during remove."""
        bad_file = tmp_path / "test_bad.py"
        bad_file.write_text("def broken(\n")  # Invalid syntax
        good_file = tmp_path / "test_good.py"
        good_file.write_text('@pytest.mark.requirement("SRS001")\ndef test_ok(): pass')

        changes = remove_test_reference("SRS001", tmp_path)
        # Should process good file, skip bad file
        assert good_file in changes
        assert bad_file not in changes

    def test_skips_file_with_encoding_error(self, tmp_path):
        """Files with encoding errors are skipped during remove."""
        bad_file = tmp_path / "test_bad_encoding.py"
        bad_file.write_bytes(b"\x80\x81\x82")  # Invalid UTF-8
        good_file = tmp_path / "test_good.py"
        good_file.write_text('@pytest.mark.requirement("SRS001")\ndef test_ok(): pass')

        changes = remove_test_reference("SRS001", tmp_path)
        assert good_file in changes
        assert bad_file not in changes


class TestRemoveTestReferenceLeadingComma:
    """Tests for leading comma handling in remove_test_reference."""

    def test_removes_trailing_uid_with_leading_comma(self, tmp_path):
        """Removes UID at end of decorator, handling leading comma."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""import pytest

@pytest.mark.requirement("SRS001", "SRS002")
def test_feature():
    pass
""")
        changes = remove_test_reference("SRS002", tmp_path, remove_empty=True)
        assert test_file in changes

        content = test_file.read_text()
        assert '"SRS001"' in content
        assert '"SRS002"' not in content

    def test_removes_middle_uid_preserves_others(self, tmp_path):
        """Removes middle UID from decorator with multiple args."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""import pytest

@pytest.mark.requirement("SRS001", "SRS002", "SRS003")
def test_feature():
    pass
""")
        changes = remove_test_reference("SRS002", tmp_path, remove_empty=True)
        assert test_file in changes

        content = test_file.read_text()
        assert '"SRS001"' in content
        assert '"SRS002"' not in content
        assert '"SRS003"' in content


class TestRemoveTestReferenceKeywordArgs:
    """Tests for keyword argument handling in remove_test_reference."""

    def test_removes_single_keyword_uid(self, tmp_path):
        """Removes entire decorator when keyword UID is the only arg."""
        test_file = tmp_path / "test_kw.py"
        test_file.write_text("""import pytest

@pytest.mark.requirement(uid="SRS001")
def test_feature():
    pass
""")
        changes = remove_test_reference("SRS001", tmp_path, remove_empty=True)
        assert test_file in changes

        content = test_file.read_text()
        # Entire decorator should be removed since it's the only UID
        assert "@pytest.mark.requirement" not in content

    def test_detects_keyword_uid_in_mixed_marker(self, tmp_path):
        """Keyword UIDs are detected but only positional args are removed.

        Note: The implementation detects keyword UIDs to find matching markers,
        but only handles removal of positional arguments. This test verifies
        the keyword detection code path is exercised (lines 278-280).
        """
        test_file = tmp_path / "test_mixed.py"
        test_file.write_text("""import pytest

@pytest.mark.requirement("SRS001", uid="SRS002")
def test_feature():
    pass
""")
        # Remove the positional arg - this should work
        changes = remove_test_reference("SRS001", tmp_path, remove_empty=True)
        assert test_file in changes

        content = test_file.read_text()
        # Positional arg should be removed
        assert '"SRS001"' not in content
        # Keyword arg remains (removal not implemented for kwargs)
        assert '"SRS002"' in content


class TestFindTestReferencesExceptionHandling:
    """Tests for exception handling in find_test_references."""

    def test_skips_file_with_encoding_error(self, tmp_path):
        """Files with encoding errors are skipped during find."""
        bad_file = tmp_path / "test_bad_encoding.py"
        bad_file.write_bytes(b"\x80\x81\x82")  # Invalid UTF-8
        good_file = tmp_path / "test_good.py"
        good_file.write_text('@pytest.mark.requirement("SRS001")\ndef test_ok(): pass')

        refs = find_test_references(tmp_path, uid="SRS001")
        # Should find reference in good file only
        assert len(refs) == 1
        assert refs[0].file == good_file

    def test_skips_file_with_os_error(self, tmp_path):
        """Files with OS errors are skipped during find."""
        import os

        bad_file = tmp_path / "test_no_read.py"
        bad_file.write_text('@pytest.mark.requirement("SRS001")\ndef test_a(): pass')
        good_file = tmp_path / "test_good.py"
        good_file.write_text('@pytest.mark.requirement("SRS001")\ndef test_ok(): pass')

        # Make file unreadable
        original_mode = bad_file.stat().st_mode
        try:
            os.chmod(bad_file, 0o000)
            refs = find_test_references(tmp_path, uid="SRS001")
            # Should only find reference in good file
            assert len(refs) == 1
            assert refs[0].file == good_file
        finally:
            os.chmod(bad_file, original_mode)


class TestFindOrphanedReferences:
    """Tests for find_orphaned_references function."""

    def test_finds_orphaned_reference(self, tmp_path):
        """Finds references to UIDs that don't exist in valid_uids."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""
@pytest.mark.requirement("SRS001")
def test_one(): pass

@pytest.mark.requirement("SRS002")
def test_two(): pass

@pytest.mark.requirement("SRS003")
def test_three(): pass
""")
        # Only SRS001 and SRS003 exist - SRS002 is orphaned
        valid_uids = {"SRS001", "SRS003"}
        orphans = find_orphaned_references(tmp_path, valid_uids)
        assert len(orphans) == 1
        assert orphans[0].uid == "SRS002"

    def test_no_orphans_when_all_valid(self, tmp_path):
        """Returns empty list when all references are valid."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""
@pytest.mark.requirement("SRS001")
def test_one(): pass

@pytest.mark.requirement("SRS002")
def test_two(): pass
""")
        valid_uids = {"SRS001", "SRS002", "SRS003"}
        orphans = find_orphaned_references(tmp_path, valid_uids)
        assert len(orphans) == 0

    def test_all_orphans_when_none_valid(self, tmp_path):
        """Returns all references when none are valid."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""
@pytest.mark.requirement("SRS001")
def test_one(): pass

@pytest.mark.requirement("SRS002")
def test_two(): pass
""")
        valid_uids: set[str] = set()  # No valid UIDs
        orphans = find_orphaned_references(tmp_path, valid_uids)
        assert len(orphans) == 2
        orphan_uids = {o.uid for o in orphans}
        assert orphan_uids == {"SRS001", "SRS002"}

    def test_multiple_orphans_in_multiple_files(self, tmp_path):
        """Finds orphans across multiple test files."""
        test_file1 = tmp_path / "test_one.py"
        test_file1.write_text('@pytest.mark.requirement("SRS001")\ndef test_a(): pass')
        test_file2 = tmp_path / "test_two.py"
        test_file2.write_text('@pytest.mark.requirement("SRS002")\ndef test_b(): pass')

        valid_uids = {"SRS003"}  # Neither SRS001 nor SRS002 exist
        orphans = find_orphaned_references(tmp_path, valid_uids)
        assert len(orphans) == 2
        orphan_uids = {o.uid for o in orphans}
        assert orphan_uids == {"SRS001", "SRS002"}


class TestDetectReferenceCollisions:
    """Tests for detect_reference_collisions function."""

    def test_detects_collision(self, tmp_path):
        """Detects when orphan UID matches a rename target."""
        test_file = tmp_path / "test_feature.py"
        # SRS002 is an orphan (deleted item), but reorder wants to rename SRS003 -> SRS002
        test_file.write_text("""
@pytest.mark.requirement("SRS002")
def test_orphaned(): pass
""")
        rename_map = {"SRS003": "SRS002"}  # SRS003 will become SRS002
        valid_uids = {"SRS001", "SRS003"}  # SRS002 doesn't exist (orphan)

        collisions = detect_reference_collisions(rename_map, tmp_path, valid_uids)
        assert len(collisions) == 1
        target_uid, ref = collisions[0]
        assert target_uid == "SRS002"
        assert ref.uid == "SRS002"

    def test_no_collision_when_orphan_not_target(self, tmp_path):
        """No collision when orphan UID doesn't match any rename target."""
        test_file = tmp_path / "test_feature.py"
        # SRS099 is an orphan but not a target of any rename
        test_file.write_text("""
@pytest.mark.requirement("SRS099")
def test_orphaned(): pass
""")
        rename_map = {"SRS003": "SRS002"}  # SRS003 will become SRS002
        valid_uids = {"SRS001", "SRS002", "SRS003"}  # SRS099 is orphan

        collisions = detect_reference_collisions(rename_map, tmp_path, valid_uids)
        assert len(collisions) == 0

    def test_no_collision_when_no_orphans(self, tmp_path):
        """No collision when there are no orphaned references."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""
@pytest.mark.requirement("SRS001")
def test_valid(): pass
""")
        rename_map = {"SRS003": "SRS002"}
        valid_uids = {"SRS001", "SRS002", "SRS003"}

        collisions = detect_reference_collisions(rename_map, tmp_path, valid_uids)
        assert len(collisions) == 0

    def test_multiple_collisions(self, tmp_path):
        """Detects multiple collisions when multiple orphans match targets."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""
@pytest.mark.requirement("SRS002")
def test_orphan_one(): pass

@pytest.mark.requirement("SRS003")
def test_orphan_two(): pass
""")
        # Both SRS002 and SRS003 are orphans and both are rename targets
        rename_map = {"SRS004": "SRS002", "SRS005": "SRS003"}
        valid_uids = {"SRS001", "SRS004", "SRS005"}  # SRS002, SRS003 are orphans

        collisions = detect_reference_collisions(rename_map, tmp_path, valid_uids)
        assert len(collisions) == 2
        collision_uids = {ref.uid for _, ref in collisions}
        assert collision_uids == {"SRS002", "SRS003"}

    def test_empty_rename_map(self, tmp_path):
        """No collisions when rename_map is empty."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""
@pytest.mark.requirement("SRS002")
def test_orphaned(): pass
""")
        rename_map: dict[str, str] = {}
        valid_uids = {"SRS001"}

        collisions = detect_reference_collisions(rename_map, tmp_path, valid_uids)
        assert len(collisions) == 0


class TestInsertTcIdMarkers:
    """Tests for insert_tc_id_markers function."""

    def test_inserts_marker_no_existing_decorators(self, tmp_path):
        """Inserts tc_id marker when function has no decorators."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""import pytest

def test_feature():
    pass
""")
        tc_mapping = {"test_feature.py::test_feature": "TC001"}
        changes = insert_tc_id_markers(tc_mapping, tmp_path)

        assert test_file in changes
        content = test_file.read_text()
        assert '@pytest.mark.tc_id("TC001")' in content
        # Verify indentation - should have no leading spaces
        lines = content.split("\n")
        tc_id_line = [line for line in lines if "tc_id" in line][0]
        assert tc_id_line == '@pytest.mark.tc_id("TC001")'

    def test_inserts_marker_with_existing_decorator_no_indent(self, tmp_path):
        """Inserts tc_id marker before existing decorator at column 0."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""import pytest

@pytest.mark.requirement("SRS001")
def test_feature():
    pass
""")
        tc_mapping = {"test_feature.py::test_feature": "TC001"}
        changes = insert_tc_id_markers(tc_mapping, tmp_path)

        assert test_file in changes
        content = test_file.read_text()
        assert '@pytest.mark.tc_id("TC001")' in content
        # tc_id should come before requirement
        tc_id_idx = content.index("tc_id")
        req_idx = content.index("requirement")
        assert tc_id_idx < req_idx
        # Verify no extra indentation
        lines = content.split("\n")
        tc_id_line = [line for line in lines if "tc_id" in line][0]
        assert tc_id_line == '@pytest.mark.tc_id("TC001")'

    def test_inserts_marker_with_4_space_indent(self, tmp_path):
        """Inserts tc_id marker with correct 4-space indentation in class."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""import pytest

class TestFeature:
    @pytest.mark.requirement("SRS001")
    def test_method(self):
        pass
""")
        tc_mapping = {"test_feature.py::TestFeature::test_method": "TC001"}
        changes = insert_tc_id_markers(tc_mapping, tmp_path)

        assert test_file in changes
        content = test_file.read_text()
        assert '@pytest.mark.tc_id("TC001")' in content
        # Verify 4-space indentation matches existing decorator
        lines = content.split("\n")
        tc_id_line = [line for line in lines if "tc_id" in line][0]
        assert tc_id_line == '    @pytest.mark.tc_id("TC001")'

    def test_inserts_marker_with_8_space_indent(self, tmp_path):
        """Inserts tc_id marker with correct 8-space indentation in nested class."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""import pytest

class TestOuter:
    class TestInner:
        @pytest.mark.requirement("SRS001")
        def test_nested(self):
            pass
""")
        tc_mapping = {"test_feature.py::TestOuter::TestInner::test_nested": "TC001"}
        changes = insert_tc_id_markers(tc_mapping, tmp_path)

        assert test_file in changes
        content = test_file.read_text()
        lines = content.split("\n")
        tc_id_line = [line for line in lines if "tc_id" in line][0]
        assert tc_id_line == '        @pytest.mark.tc_id("TC001")'

    def test_inserts_marker_class_method_no_existing_decorator(self, tmp_path):
        """Inserts tc_id marker for class method without existing decorators."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""import pytest

class TestFeature:
    def test_method(self):
        pass
""")
        tc_mapping = {"test_feature.py::TestFeature::test_method": "TC001"}
        changes = insert_tc_id_markers(tc_mapping, tmp_path)

        assert test_file in changes
        content = test_file.read_text()
        lines = content.split("\n")
        tc_id_line = [line for line in lines if "tc_id" in line][0]
        # Should match the def indentation
        assert tc_id_line == '    @pytest.mark.tc_id("TC001")'

    def test_inserts_marker_with_multiple_existing_decorators(self, tmp_path):
        """Inserts tc_id marker before multiple existing decorators."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""import pytest

@pytest.mark.slow
@pytest.mark.requirement("SRS001")
def test_feature():
    pass
""")
        tc_mapping = {"test_feature.py::test_feature": "TC001"}
        changes = insert_tc_id_markers(tc_mapping, tmp_path)

        assert test_file in changes
        content = test_file.read_text()
        # tc_id should come first
        lines = content.split("\n")
        decorator_lines = [line for line in lines if line.strip().startswith("@")]
        assert decorator_lines[0] == '@pytest.mark.tc_id("TC001")'
        assert "@pytest.mark.slow" in decorator_lines[1]

    def test_skips_function_with_existing_tc_id(self, tmp_path):
        """Does not insert tc_id if function already has one."""
        test_file = tmp_path / "test_feature.py"
        original = """import pytest

@pytest.mark.tc_id("TC-EXISTING")
@pytest.mark.requirement("SRS001")
def test_feature():
    pass
"""
        test_file.write_text(original)
        tc_mapping = {"test_feature.py::test_feature": "TC001"}
        changes = insert_tc_id_markers(tc_mapping, tmp_path)

        # No changes should be made
        assert test_file not in changes
        assert test_file.read_text() == original

    def test_dry_run_does_not_modify_file(self, tmp_path):
        """Dry run reports changes without modifying files."""
        test_file = tmp_path / "test_feature.py"
        original = """import pytest

@pytest.mark.requirement("SRS001")
def test_feature():
    pass
"""
        test_file.write_text(original)
        tc_mapping = {"test_feature.py::test_feature": "TC001"}
        changes = insert_tc_id_markers(tc_mapping, tmp_path, dry_run=True)

        assert test_file in changes
        assert "would add" in changes[test_file][0]
        # File should be unchanged
        assert test_file.read_text() == original

    def test_handles_parameterized_tests(self, tmp_path):
        """Parameterized tests get base TC ID without suffix."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""import pytest

@pytest.mark.parametrize("x", [1, 2, 3])
def test_param(x):
    pass
""")
        # Parameterized nodeids have suffixes
        tc_mapping = {
            "test_feature.py::test_param[1]": "TC001a",
            "test_feature.py::test_param[2]": "TC001b",
            "test_feature.py::test_param[3]": "TC001c",
        }
        changes = insert_tc_id_markers(tc_mapping, tmp_path)

        assert test_file in changes
        content = test_file.read_text()
        # Should insert base TC ID (without suffix)
        assert '@pytest.mark.tc_id("TC001")' in content
        # Only one tc_id marker should be inserted
        assert content.count("tc_id") == 1

    def test_inserts_multiple_markers_in_file(self, tmp_path):
        """Inserts tc_id markers for multiple functions in same file."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""import pytest

@pytest.mark.requirement("SRS001")
def test_one():
    pass

@pytest.mark.requirement("SRS002")
def test_two():
    pass
""")
        tc_mapping = {
            "test_feature.py::test_one": "TC001",
            "test_feature.py::test_two": "TC002",
        }
        changes = insert_tc_id_markers(tc_mapping, tmp_path)

        assert test_file in changes
        assert len(changes[test_file]) == 2
        content = test_file.read_text()
        assert '@pytest.mark.tc_id("TC001")' in content
        assert '@pytest.mark.tc_id("TC002")' in content

    def test_handles_async_functions(self, tmp_path):
        """Inserts tc_id marker for async test functions."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""import pytest

@pytest.mark.requirement("SRS001")
async def test_async():
    pass
""")
        tc_mapping = {"test_feature.py::test_async": "TC001"}
        changes = insert_tc_id_markers(tc_mapping, tmp_path)

        assert test_file in changes
        content = test_file.read_text()
        assert '@pytest.mark.tc_id("TC001")' in content

    def test_returns_empty_when_no_matching_functions(self, tmp_path):
        """Returns empty dict when no functions match tc_mapping."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""import pytest

def test_feature():
    pass
""")
        tc_mapping = {"test_other.py::test_other": "TC001"}
        changes = insert_tc_id_markers(tc_mapping, tmp_path)

        assert changes == {}

    def test_skips_file_with_syntax_error(self, tmp_path):
        """Files with syntax errors are skipped."""
        bad_file = tmp_path / "test_bad.py"
        bad_file.write_text("def broken(\n")
        good_file = tmp_path / "test_good.py"
        good_file.write_text("""import pytest

def test_good():
    pass
""")
        tc_mapping = {
            "test_bad.py::test_bad": "TC001",
            "test_good.py::test_good": "TC002",
        }
        changes = insert_tc_id_markers(tc_mapping, tmp_path)

        assert good_file in changes
        assert bad_file not in changes

    def test_2_space_indent(self, tmp_path):
        """Handles 2-space indentation correctly."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""import pytest

class TestFeature:
  @pytest.mark.requirement("SRS001")
  def test_method(self):
    pass
""")
        tc_mapping = {"test_feature.py::TestFeature::test_method": "TC001"}
        changes = insert_tc_id_markers(tc_mapping, tmp_path)

        assert test_file in changes
        content = test_file.read_text()
        lines = content.split("\n")
        tc_id_line = [line for line in lines if "tc_id" in line][0]
        assert tc_id_line == '  @pytest.mark.tc_id("TC001")'

    def test_handles_mark_style_decorator(self, tmp_path):
        """Handles @mark.requirement style decorators."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""from pytest import mark

@mark.requirement("SRS001")
def test_feature():
    pass
""")
        tc_mapping = {"test_feature.py::test_feature": "TC001"}
        changes = insert_tc_id_markers(tc_mapping, tmp_path)

        assert test_file in changes
        content = test_file.read_text()
        lines = content.split("\n")
        tc_id_line = [line for line in lines if "tc_id" in line][0]
        assert tc_id_line == '@pytest.mark.tc_id("TC001")'

    def test_skips_nodeid_without_function_name(self, tmp_path):
        """Skips nodeids that don't have a function name component."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""import pytest

def test_feature():
    pass
""")
        # This nodeid has no function component (malformed)
        tc_mapping = {"test_feature.py": "TC001"}
        changes = insert_tc_id_markers(tc_mapping, tmp_path)

        # Should return empty since the nodeid doesn't have a function
        assert changes == {}

    def test_skips_nonexistent_file(self, tmp_path):
        """Skips files that don't exist."""
        tc_mapping = {"nonexistent_file.py::test_foo": "TC001"}
        changes = insert_tc_id_markers(tc_mapping, tmp_path)

        assert changes == {}

    def test_handles_parameterized_tc_id_suffix_stripping(self, tmp_path):
        """Strips alphabetic suffix from parameterized test TC IDs."""
        test_file = tmp_path / "test_feature.py"
        test_file.write_text("""import pytest

@pytest.mark.parametrize("val", [1, 2, 3])
def test_parameterized(val):
    pass
""")
        # TC IDs with suffixes should strip to base TC ID
        tc_mapping = {
            "test_feature.py::test_parameterized[1]": "TC001a",
            "test_feature.py::test_parameterized[2]": "TC001b",
            "test_feature.py::test_parameterized[3]": "TC001c",
        }
        changes = insert_tc_id_markers(tc_mapping, tmp_path)

        assert test_file in changes
        content = test_file.read_text()
        # Should insert TC001 (base ID, not TC001a)
        assert '@pytest.mark.tc_id("TC001")' in content
        # Should only have one tc_id marker
        assert content.count("tc_id") == 1

    def test_skips_file_with_unicode_error(self, tmp_path):
        """Files with unicode decode errors are skipped."""
        bad_file = tmp_path / "test_bad.py"
        # Write invalid UTF-8 bytes
        bad_file.write_bytes(b"\xff\xfe invalid utf-8")

        tc_mapping = {"test_bad.py::test_bad": "TC001"}
        changes = insert_tc_id_markers(tc_mapping, tmp_path)

        assert bad_file not in changes
