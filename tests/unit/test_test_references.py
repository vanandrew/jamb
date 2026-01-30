"""Unit tests for jamb.storage.test_references module."""

import pytest

from jamb.storage.test_references import (
    RequirementReference,
    _find_enclosing_function,
    _find_uid_positions_in_source,
    _is_requirement_marker,
    find_test_references,
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
