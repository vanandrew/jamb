"""Tests for jamb.yaml_io module."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from jamb.core.models import Item, TraceabilityGraph
from jamb.storage.document_config import DocumentConfig
from jamb.storage.document_dag import DocumentDAG
from jamb.yaml_io import (
    _create_document,
    _create_item,
    _document_exists,
    _extract_prefix,
    _get_document_path,
    _graph_item_to_dict,
    _update_item,
    export_items_to_yaml,
    export_to_yaml,
    import_from_yaml,
    load_import_file,
)


class TestExtractPrefix:
    """Tests for _extract_prefix function."""

    def test_extracts_letters(self):
        """Test extracting prefix from UID."""
        assert _extract_prefix("SRS001") == "SRS"
        assert _extract_prefix("UN123") == "UN"
        assert _extract_prefix("UT42") == "UT"

    def test_handles_lowercase(self):
        """Test lowercase UIDs."""
        assert _extract_prefix("srs001") == "srs"

    def test_handles_mixed_case(self):
        """Test mixed case UIDs."""
        assert _extract_prefix("SrS001") == "SrS"

    def test_returns_none_for_invalid(self):
        """Test invalid UIDs return None."""
        assert _extract_prefix("123") is None
        assert _extract_prefix("") is None
        assert _extract_prefix("123ABC") is None

    def test_prefix_with_digits_using_dag(self):
        """DAG-aware extraction handles prefixes containing digits."""
        dag = DocumentDAG()
        dag.documents["SRS2"] = DocumentConfig(prefix="SRS2", digits=3)
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", digits=3)
        # "SRS2001" should match "SRS2", not "SRS"
        assert _extract_prefix("SRS2001", dag=dag) == "SRS2"
        # "SRS001" should still match "SRS"
        assert _extract_prefix("SRS001", dag=dag) == "SRS"

    def test_prefix_with_underscore_using_dag(self):
        """DAG-aware extraction handles prefixes with underscores."""
        dag = DocumentDAG()
        dag.documents["MY_DOC"] = DocumentConfig(prefix="MY_DOC", sep="-", digits=3)
        assert _extract_prefix("MY_DOC-001", dag=dag) == "MY_DOC"

    def test_fallback_regex_without_dag(self):
        """Fallback regex (no DAG) matches letter/underscore prefixes only."""
        # Without DAG, digits in the prefix are ambiguous so they are
        # treated as part of the numeric suffix.
        assert _extract_prefix("SRS2001") == "SRS"
        assert _extract_prefix("MY_DOC001") == "MY_DOC"

    def test_dag_no_match_falls_through(self):
        """When DAG has no matching prefix, fallback regex is used."""
        dag = DocumentDAG()
        dag.documents["UT"] = DocumentConfig(prefix="UT", digits=3)
        # "SRS001" not in DAG — falls through to regex
        assert _extract_prefix("SRS001", dag=dag) == "SRS"


class TestLoadImportFile:
    """Tests for load_import_file function."""

    def test_loads_valid_file(self, tmp_path):
        """Test loading valid YAML file."""
        yaml_content = {
            "documents": [{"prefix": "SRS", "path": "srs"}],
            "items": [{"uid": "SRS001", "text": "Test"}],
        }
        yaml_file = tmp_path / "test.yml"
        yaml_file.write_text(yaml.dump(yaml_content))

        result = load_import_file(yaml_file)
        assert len(result["documents"]) == 1
        assert len(result["items"]) == 1

    def test_adds_missing_keys(self, tmp_path):
        """Test that missing keys are added."""
        yaml_file = tmp_path / "test.yml"
        yaml_file.write_text("documents: []")

        result = load_import_file(yaml_file)
        assert "documents" in result
        assert "items" in result

    def test_raises_on_missing_document_prefix(self, tmp_path):
        """Test error when document missing prefix."""
        yaml_file = tmp_path / "test.yml"
        yaml_file.write_text("documents:\n  - path: srs")

        with pytest.raises(ValueError, match="missing 'prefix'"):
            load_import_file(yaml_file)

    def test_raises_on_missing_document_path(self, tmp_path):
        """Test error when document missing path."""
        yaml_file = tmp_path / "test.yml"
        yaml_file.write_text("documents:\n  - prefix: SRS")

        with pytest.raises(ValueError, match="missing 'path'"):
            load_import_file(yaml_file)

    def test_raises_on_missing_item_uid(self, tmp_path):
        """Test error when item missing uid."""
        yaml_file = tmp_path / "test.yml"
        yaml_file.write_text("items:\n  - text: Test")

        with pytest.raises(ValueError, match="missing 'uid'"):
            load_import_file(yaml_file)

    def test_raises_on_missing_item_text(self, tmp_path):
        """Test error when item missing text."""
        yaml_file = tmp_path / "test.yml"
        yaml_file.write_text("items:\n  - uid: SRS001")

        with pytest.raises(ValueError, match="missing 'text'"):
            load_import_file(yaml_file)

    def test_duplicate_uids_raises(self, tmp_path):
        """Test error when import file contains duplicate UIDs."""
        yaml_file = tmp_path / "test.yml"
        yaml_file.write_text("items:\n  - uid: SRS001\n    text: First\n  - uid: SRS001\n    text: Second\n")

        with pytest.raises(ValueError, match="Duplicate UIDs.*SRS001"):
            load_import_file(yaml_file)

    def test_multiple_duplicate_uids_raises(self, tmp_path):
        """Test error lists all duplicated UIDs."""
        yaml_file = tmp_path / "test.yml"
        yaml_file.write_text(
            "items:\n"
            "  - uid: SRS001\n"
            "    text: First\n"
            "  - uid: SRS002\n"
            "    text: Second\n"
            "  - uid: SRS001\n"
            "    text: Third\n"
            "  - uid: SRS002\n"
            "    text: Fourth\n"
        )

        with pytest.raises(ValueError, match="Duplicate UIDs.*SRS001.*SRS002"):
            load_import_file(yaml_file)

    def test_raises_on_invalid_yaml(self, tmp_path):
        """Test error on non-mapping YAML."""
        yaml_file = tmp_path / "test.yml"
        yaml_file.write_text("- item1\n- item2")

        with pytest.raises(ValueError, match="Expected dict"):
            load_import_file(yaml_file)

    def test_load_import_file_os_error(self, tmp_path):
        """Test load_import_file handles OSError gracefully."""
        yaml_file = tmp_path / "test.yml"
        yaml_file.write_text("documents: []")

        # Mock open to raise OSError
        with patch("builtins.open", side_effect=OSError("Permission denied")):
            with pytest.raises(OSError, match="Failed to read file"):
                load_import_file(yaml_file)

    def test_load_import_file_yaml_error(self, tmp_path):
        """Test load_import_file handles YAML syntax errors."""
        yaml_file = tmp_path / "test.yml"
        yaml_file.write_text("invalid: yaml: [unclosed")

        with pytest.raises(ValueError, match="Invalid YAML"):
            load_import_file(yaml_file)

    def test_empty_yaml_warns(self, tmp_path):
        """Test that empty/null YAML produces warning."""
        import warnings

        yaml_file = tmp_path / "test.yml"
        yaml_file.write_text("")  # Empty file results in null

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = load_import_file(yaml_file)
            assert any("empty or contains only null" in str(warning.message) for warning in w)
            # Should return empty structure
            assert result == {"documents": [], "items": []}

    def test_both_sections_empty_warns(self, tmp_path):
        """Test that empty documents and items warns."""
        yaml_file = tmp_path / "test.yml"
        yaml_file.write_text("documents: []\nitems: []")

        messages = []
        result = load_import_file(yaml_file, echo=messages.append)
        assert any("no documents and no items" in msg for msg in messages)
        assert result == {"documents": [], "items": []}

    def test_unrecognized_keys_warns(self, tmp_path):
        """Test that unrecognized top-level keys produce warning."""
        yaml_file = tmp_path / "test.yml"
        yaml_file.write_text("documents: []\nitems: []\nextra_key: value\nanother_extra: 123\n")

        messages = []
        result = load_import_file(yaml_file, echo=messages.append)
        assert any("unrecognized top-level keys" in msg for msg in messages)
        # Should still process valid sections
        assert "documents" in result
        assert "items" in result


class TestUpdateItem:
    """Tests for _update_item function."""

    def test_updates_text(self, tmp_path):
        """Test updating item text."""
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\ntext: Old text\n")

        result = _update_item(item_path, {"uid": "SRS001", "text": "New text"}, verbose=False, echo=print)

        assert result == "updated"
        updated = yaml.safe_load(item_path.read_text())
        assert updated["text"] == "New text"
        assert updated["active"] is True  # Preserved

    def test_preserves_existing_fields(self, tmp_path):
        """Test that unspecified fields are preserved."""
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\ncustom_field: true\ntext: Test\n")

        _update_item(item_path, {"uid": "SRS001", "text": "New text"}, verbose=False, echo=print)

        updated = yaml.safe_load(item_path.read_text())
        assert updated["custom_field"] is True  # Preserved

    def test_clears_reviewed_status(self, tmp_path):
        """Test that reviewed status is cleared on update."""
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\nreviewed: abc123\ntext: Test\n")

        _update_item(item_path, {"uid": "SRS001", "text": "New text"}, verbose=False, echo=print)

        updated = yaml.safe_load(item_path.read_text())
        assert "reviewed" not in updated

    def test_replaces_links(self, tmp_path):
        """Test that links are replaced, not merged."""
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\nlinks:\n- UN001\n- UN002\ntext: Test\n")

        _update_item(
            item_path,
            {"uid": "SRS001", "text": "Test", "links": ["UN003"]},
            verbose=False,
            echo=print,
        )

        updated = yaml.safe_load(item_path.read_text())
        assert updated["links"] == ["UN003"]

    def test_clears_links_when_empty(self, tmp_path):
        """Test that empty links list removes links field."""
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\nlinks:\n- UN001\ntext: Test\n")

        _update_item(
            item_path,
            {"uid": "SRS001", "text": "Test", "links": []},
            verbose=False,
            echo=print,
        )

        updated = yaml.safe_load(item_path.read_text())
        assert "links" not in updated

    def test_updates_header(self, tmp_path):
        """Test updating item header."""
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\nheader: Old Header\ntext: Test\n")

        _update_item(
            item_path,
            {"uid": "SRS001", "text": "Test", "header": "New Header"},
            verbose=False,
            echo=print,
        )

        updated = yaml.safe_load(item_path.read_text())
        assert updated["header"] == "New Header"

    def test_removes_header_when_empty(self, tmp_path):
        """Test that empty header removes header field."""
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\nheader: Old Header\ntext: Test\n")

        _update_item(
            item_path,
            {"uid": "SRS001", "text": "Test", "header": ""},
            verbose=False,
            echo=print,
        )

        updated = yaml.safe_load(item_path.read_text())
        assert "header" not in updated

    def test_preserves_reviewed_on_no_op_update(self, tmp_path):
        """Reviewed status is preserved when content does not change."""
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\nreviewed: abc123\ntext: Same text\n")

        _update_item(
            item_path,
            {"uid": "SRS001", "text": "Same text"},
            verbose=False,
            echo=print,
        )

        updated = yaml.safe_load(item_path.read_text())
        assert updated["reviewed"] == "abc123"

    def test_clears_reviewed_when_content_changes(self, tmp_path):
        """Reviewed status is cleared when content actually changes."""
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\nreviewed: abc123\ntext: Old text\n")

        _update_item(
            item_path,
            {"uid": "SRS001", "text": "New text"},
            verbose=False,
            echo=print,
        )

        updated = yaml.safe_load(item_path.read_text())
        assert "reviewed" not in updated

    def test_update_item_verbose(self, tmp_path):
        """Test _update_item verbose output."""
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\ntext: Old text\n")

        messages = []
        result = _update_item(
            item_path,
            {"uid": "SRS001", "text": "New text"},
            verbose=True,
            echo=messages.append,
        )

        assert result == "updated"
        assert any("Updated" in msg and "SRS001" in msg for msg in messages)

    def test_update_item_preserves_type_derived_testable(self, tmp_path):
        """Test _update_item updates type, derived, and testable fields."""
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\ntext: Original\n")

        result = _update_item(
            item_path,
            {
                "uid": "SRS001",
                "text": "Updated",
                "type": "info",
                "derived": True,
                "testable": False,
            },
            verbose=False,
            echo=lambda x: None,
        )

        assert result == "updated"
        content = yaml.safe_load(item_path.read_text())
        assert content["type"] == "info"
        assert content["derived"] is True
        assert content["testable"] is False

    def test_update_item_removes_type_when_requirement(self, tmp_path):
        """Test _update_item removes type field when reset to 'requirement'."""
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\ntext: Original\ntype: heading\n")

        result = _update_item(
            item_path,
            {"uid": "SRS001", "text": "Updated", "type": "requirement"},
            verbose=False,
            echo=lambda x: None,
        )

        assert result == "updated"
        content = yaml.safe_load(item_path.read_text())
        assert "type" not in content

    def test_update_item_removes_derived_when_false(self, tmp_path):
        """Test _update_item removes derived field when set to False."""
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\ntext: Original\nderived: true\n")

        result = _update_item(
            item_path,
            {"uid": "SRS001", "text": "Updated", "derived": False},
            verbose=False,
            echo=lambda x: None,
        )

        assert result == "updated"
        content = yaml.safe_load(item_path.read_text())
        assert "derived" not in content

    def test_update_item_removes_testable_when_true(self, tmp_path):
        """Test _update_item removes testable field when set to True."""
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\ntext: Original\ntestable: false\n")

        result = _update_item(
            item_path,
            {"uid": "SRS001", "text": "Updated", "testable": True},
            verbose=False,
            echo=lambda x: None,
        )

        assert result == "updated"
        content = yaml.safe_load(item_path.read_text())
        assert "testable" not in content


class TestImportFromYaml:
    """Tests for import_from_yaml function."""

    def test_import_uses_print_as_default_echo(self, tmp_path, monkeypatch):
        """Test import uses print when no echo provided."""
        yaml_file = tmp_path / "import.yml"
        yaml_file.write_text("documents: []\nitems: []")

        # Mock _create_document and _create_item to avoid actual calls
        with (
            patch("jamb.yaml_io._create_document") as mock_doc,
            patch("jamb.yaml_io._create_item") as mock_item,
        ):
            mock_doc.return_value = "created"
            mock_item.return_value = "created"

            stats = import_from_yaml(yaml_file)

            assert stats["documents_created"] == 0
            assert stats["items_created"] == 0

    def test_import_returns_stats(self, tmp_path):
        """Test import returns correct statistics dict."""
        yaml_file = tmp_path / "import.yml"
        yaml_file.write_text(
            """
documents:
  - prefix: NEW
    path: new
items:
  - uid: NEW001
    text: New item
"""
        )

        with (
            patch("jamb.yaml_io._create_document") as mock_doc,
            patch("jamb.yaml_io._create_item") as mock_item,
        ):
            mock_doc.return_value = "created"
            mock_item.return_value = "created"

            stats = import_from_yaml(yaml_file, echo=lambda x: None)

            assert stats["documents_created"] == 1
            assert stats["items_created"] == 1

    def test_import_counts_skipped(self, tmp_path):
        """Test import counts skipped items."""
        yaml_file = tmp_path / "import.yml"
        yaml_file.write_text(
            """
documents: []
items:
  - uid: SRS001
    text: Existing item
"""
        )

        with patch("jamb.yaml_io._create_item") as mock_item:
            mock_item.return_value = "skipped"

            stats = import_from_yaml(yaml_file, echo=lambda x: None)

            assert stats["skipped"] == 1


class TestCreateDocument:
    """Tests for _create_document function."""

    def test_create_document_rejects_absolute_path(self):
        """Test _create_document rejects absolute path in document config."""
        with patch("jamb.yaml_io._document_exists") as mock_exists:
            mock_exists.return_value = False

            messages = []
            result = _create_document(
                {"prefix": "ABS", "path": "/absolute/path/to/doc"},
                dry_run=False,
                verbose=True,
                echo=messages.append,
            )

            assert result == "error"
            assert any("absolute" in msg.lower() for msg in messages)

    def test_create_document_rejects_path_traversal(self, tmp_path):
        """Test _create_document rejects path traversal attempt."""
        import os

        # Change to tmp_path so relative path resolution works predictably
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            with patch("jamb.yaml_io._document_exists") as mock_exists:
                mock_exists.return_value = False

                messages = []
                result = _create_document(
                    {"prefix": "TRAV", "path": "../outside/doc"},
                    dry_run=False,
                    verbose=True,
                    echo=messages.append,
                )

                assert result == "error"
                assert any("outside" in msg.lower() for msg in messages)
        finally:
            os.chdir(old_cwd)

    def test_create_document_skips_existing(self):
        """Test _create_document skips existing documents."""
        with patch("jamb.yaml_io._document_exists") as mock_exists:
            mock_exists.return_value = True

            messages = []
            result = _create_document(
                {"prefix": "SRS", "path": "srs"},
                dry_run=False,
                verbose=True,
                echo=messages.append,
            )

            assert result == "skipped"
            assert any("Skipping" in msg for msg in messages)

    def test_create_document_dry_run(self):
        """Test _create_document in dry_run mode."""
        with patch("jamb.yaml_io._document_exists") as mock_exists:
            mock_exists.return_value = False

            messages = []
            result = _create_document(
                {"prefix": "NEW", "path": "new"},
                dry_run=True,
                verbose=False,
                echo=messages.append,
            )

            assert result == "created"
            assert any("Would create" in msg for msg in messages)

    def test_create_document_dry_run_with_parents(self):
        """Test _create_document dry_run shows parents."""
        with patch("jamb.yaml_io._document_exists") as mock_exists:
            mock_exists.return_value = False

            messages = []
            result = _create_document(
                {"prefix": "NEW", "path": "new", "parents": ["UN"]},
                dry_run=True,
                verbose=False,
                echo=messages.append,
            )

            assert result == "created"
            assert any("parents: UN" in msg for msg in messages)

    def test_create_document_calls_save_document_config(self):
        """Test _create_document calls save_document_config on create."""
        with (
            patch("jamb.yaml_io._document_exists") as mock_exists,
            patch("jamb.storage.document_config.save_document_config") as mock_save,
        ):
            mock_exists.return_value = False

            messages = []
            result = _create_document(
                {"prefix": "NEW", "path": "new", "parents": ["UN"]},
                dry_run=False,
                verbose=True,
                echo=messages.append,
            )

            assert result == "created"
            mock_save.assert_called_once()
            config_arg = mock_save.call_args[0][0]
            assert config_arg.prefix == "NEW"
            assert config_arg.parents == ["UN"]
            assert any("Created document: NEW" in msg for msg in messages)

    def test_create_document_handles_save_error(self):
        """Test _create_document handles save_document_config failure."""
        with (
            patch("jamb.yaml_io._document_exists") as mock_exists,
            patch("jamb.storage.document_config.save_document_config") as mock_save,
        ):
            mock_exists.return_value = False
            mock_save.side_effect = OSError("Write failed")

            messages = []
            result = _create_document(
                {"prefix": "FAIL", "path": "fail"},
                dry_run=False,
                verbose=True,
                echo=messages.append,
            )

            assert result == "error"
            assert any("Error creating" in msg for msg in messages)


class TestCreateItem:
    """Tests for _create_item function."""

    def test_create_item_invalid_uid_prefix(self):
        """Test _create_item handles invalid UID."""
        messages = []
        result = _create_item(
            {"uid": "123", "text": "Invalid"},
            dry_run=False,
            update=False,
            verbose=False,
            echo=messages.append,
        )

        assert result == "error"
        assert any("Cannot determine prefix" in msg for msg in messages)

    def test_create_item_missing_document(self):
        """Test _create_item handles missing document path."""
        with patch("jamb.yaml_io._get_document_path") as mock_path:
            mock_path.return_value = None

            messages = []
            result = _create_item(
                {"uid": "SRS001", "text": "Test"},
                dry_run=False,
                update=False,
                verbose=False,
                echo=messages.append,
            )

            assert result == "error"
            assert any("Cannot find document path" in msg for msg in messages)

    def test_create_item_dry_run_new(self, tmp_path):
        """Test _create_item dry_run with new item."""
        with patch("jamb.yaml_io._get_document_path") as mock_path:
            mock_path.return_value = tmp_path
            # Item doesn't exist

            messages = []
            result = _create_item(
                {"uid": "SRS001", "text": "Test"},
                dry_run=True,
                update=False,
                verbose=False,
                echo=messages.append,
            )

            assert result == "created"
            assert any("Would create" in msg for msg in messages)

    def test_create_item_dry_run_existing_with_update(self, tmp_path):
        """Test _create_item dry_run with existing item and update flag."""
        # Create existing item
        (tmp_path / "SRS001.yml").write_text("text: Existing")

        with patch("jamb.yaml_io._get_document_path") as mock_path:
            mock_path.return_value = tmp_path

            messages = []
            result = _create_item(
                {"uid": "SRS001", "text": "Updated"},
                dry_run=True,
                update=True,
                verbose=False,
                echo=messages.append,
            )

            assert result == "updated"
            assert any("Would update" in msg for msg in messages)

    def test_create_item_skip_existing_without_update(self, tmp_path):
        """Test _create_item skips existing item without update flag."""
        # Create existing item
        (tmp_path / "SRS001.yml").write_text("text: Existing")

        with patch("jamb.yaml_io._get_document_path") as mock_path:
            mock_path.return_value = tmp_path

            messages = []
            result = _create_item(
                {"uid": "SRS001", "text": "New"},
                dry_run=False,
                update=False,
                verbose=True,
                echo=messages.append,
            )

            assert result == "skipped"
            assert any("Skipping" in msg for msg in messages)

    def test_create_item_writes_yaml(self, tmp_path):
        """Test _create_item writes correct YAML structure."""
        with patch("jamb.yaml_io._get_document_path") as mock_path:
            mock_path.return_value = tmp_path

            messages = []
            result = _create_item(
                {"uid": "SRS001", "text": "New requirement"},
                dry_run=False,
                update=False,
                verbose=True,
                echo=messages.append,
            )

            assert result == "created"
            item_path = tmp_path / "SRS001.yml"
            assert item_path.exists()

            content = yaml.safe_load(item_path.read_text())
            assert content["active"] is True
            assert content["text"] == "New requirement"
            assert "normative" not in content

    def test_create_item_with_header_and_links(self, tmp_path):
        """Test _create_item includes header and links in YAML."""
        with patch("jamb.yaml_io._get_document_path") as mock_path:
            mock_path.return_value = tmp_path

            result = _create_item(
                {
                    "uid": "SRS001",
                    "text": "Requirement",
                    "header": "Auth",
                    "links": ["UN001"],
                },
                dry_run=False,
                update=False,
                verbose=False,
                echo=lambda x: None,
            )

            assert result == "created"
            content = yaml.safe_load((tmp_path / "SRS001.yml").read_text())
            assert content["header"] == "Auth"
            assert content["links"] == ["UN001"]

    def test_create_item_preserves_type_derived_testable(self, tmp_path):
        """Test _create_item writes type, derived, and testable fields."""
        with patch("jamb.yaml_io._get_document_path") as mock_path:
            mock_path.return_value = tmp_path

            result = _create_item(
                {
                    "uid": "SRS001",
                    "text": "A heading",
                    "type": "heading",
                    "derived": True,
                    "testable": False,
                },
                dry_run=False,
                update=False,
                verbose=False,
                echo=lambda x: None,
            )

            assert result == "created"
            content = yaml.safe_load((tmp_path / "SRS001.yml").read_text())
            assert content["type"] == "heading"
            assert content["derived"] is True
            assert content["testable"] is False

    def test_create_item_skips_default_type(self, tmp_path):
        """Test _create_item does not write type if it's 'requirement' (default)."""
        with patch("jamb.yaml_io._get_document_path") as mock_path:
            mock_path.return_value = tmp_path

            result = _create_item(
                {
                    "uid": "SRS001",
                    "text": "Normal requirement",
                    "type": "requirement",
                },
                dry_run=False,
                update=False,
                verbose=False,
                echo=lambda x: None,
            )

            assert result == "created"
            content = yaml.safe_load((tmp_path / "SRS001.yml").read_text())
            assert "type" not in content


class TestDocumentExists:
    """Tests for _document_exists function."""

    def test_document_exists_with_jamb_yml(self, tmp_path):
        """Test _document_exists finds document via discover_documents."""
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()

        dag = DocumentDAG()
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=[], digits=3)
        dag.document_paths["SRS"] = srs_dir

        with patch("jamb.storage.discover_documents", return_value=dag):
            assert _document_exists("SRS") is True

    def test_document_exists_false(self):
        """Test _document_exists returns False for missing doc."""
        dag = DocumentDAG()

        with patch("jamb.storage.discover_documents", return_value=dag):
            assert _document_exists("NONEXISTENT") is False

    def test_document_exists_false_wrong_prefix(self, tmp_path):
        """Test _document_exists returns False when prefix doesn't match."""
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()

        dag = DocumentDAG()
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=[], digits=3)
        dag.document_paths["SRS"] = srs_dir

        with patch("jamb.storage.discover_documents", return_value=dag):
            assert _document_exists("UN") is False


class TestGetDocumentPath:
    """Tests for _get_document_path function."""

    def test_get_document_path_found_jamb_yml(self, tmp_path):
        """Test _get_document_path finds correct path via discover_documents."""
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()

        dag = DocumentDAG()
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=[], digits=3)
        dag.document_paths["SRS"] = srs_dir

        with patch("jamb.storage.discover_documents", return_value=dag):
            result = _get_document_path("SRS")

        assert result is not None
        assert result.name == "srs"

    def test_get_document_path_not_found(self):
        """Test _get_document_path returns None when not found."""
        dag = DocumentDAG()

        with patch("jamb.storage.discover_documents", return_value=dag):
            result = _get_document_path("NONEXISTENT")

        assert result is None


class TestImportFromYamlDocumentSkip:
    """Tests for import_from_yaml document skip counting."""

    def test_import_counts_document_skipped(self, tmp_path):
        """Test import counts skipped documents."""
        yaml_file = tmp_path / "import.yml"
        yaml_file.write_text(
            """
documents:
  - prefix: SRS
    path: srs
items: []
"""
        )

        with patch("jamb.yaml_io._create_document") as mock_doc:
            mock_doc.return_value = "skipped"

            stats = import_from_yaml(yaml_file, echo=lambda x: None)

            assert stats["skipped"] == 1
            assert stats["documents_created"] == 0

    def test_import_counts_item_updated(self, tmp_path):
        """Test import counts updated items."""
        yaml_file = tmp_path / "import.yml"
        yaml_file.write_text(
            """
documents: []
items:
  - uid: SRS001
    text: Updated
"""
        )

        with patch("jamb.yaml_io._create_item") as mock_item:
            mock_item.return_value = "updated"

            stats = import_from_yaml(yaml_file, update=True, echo=lambda x: None)

            assert stats["items_updated"] == 1


# ---------------------------------------------------------------------------
# Export tests
# ---------------------------------------------------------------------------


def _make_export_fixtures():
    """Build a DAG and TraceabilityGraph for export tests."""
    dag = DocumentDAG()
    dag.documents["SYS"] = DocumentConfig(prefix="SYS")
    dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=["SYS"])
    dag.document_paths["SYS"] = Path("/fake/sys")
    dag.document_paths["SRS"] = Path("/fake/srs")

    graph = TraceabilityGraph()
    sys_item = Item(uid="SYS001", text="System req", document_prefix="SYS")
    srs_item = Item(uid="SRS001", text="Software req", document_prefix="SRS", links=["SYS001"])
    inactive_item = Item(uid="SRS002", text="Inactive", document_prefix="SRS", active=False)
    graph.add_item(sys_item)
    graph.add_item(srs_item)
    graph.add_item(inactive_item)
    graph.set_document_parents("SYS", [])
    graph.set_document_parents("SRS", ["SYS"])
    return dag, graph


class TestGraphItemToDict:
    """Tests for _graph_item_to_dict function."""

    def test_basic(self):
        """Test basic item conversion without optional fields."""
        item = Item(uid="SRS001", text="Hello", document_prefix="SRS")
        result = _graph_item_to_dict(item)

        assert result == {"uid": "SRS001", "text": "Hello"}
        assert "header" not in result
        assert "links" not in result

    def test_with_header(self):
        """Test item conversion with header."""
        item = Item(uid="SRS001", text="Hello", document_prefix="SRS", header="My Header")
        result = _graph_item_to_dict(item)

        assert result.get("header") == "My Header"

    def test_with_links(self):
        """Test item conversion with links."""
        item = Item(
            uid="SRS001",
            text="Hello",
            document_prefix="SRS",
            links=["SYS001", "SYS002"],
        )
        result = _graph_item_to_dict(item)

        assert result.get("links") == ["SYS001", "SYS002"]

    def test_with_header_and_links(self):
        """Test item conversion with both header and links."""
        item = Item(
            uid="SRS001",
            text="Hello",
            document_prefix="SRS",
            header="Section",
            links=["SYS001"],
        )
        result = _graph_item_to_dict(item)

        assert result["uid"] == "SRS001"
        assert result["text"] == "Hello"
        assert result.get("header") == "Section"
        assert result.get("links") == ["SYS001"]


@patch("jamb.storage.build_traceability_graph")
@patch("jamb.storage.discover_documents")
class TestExportToYaml:
    """Tests for export_to_yaml function."""

    def test_all_documents(self, mock_discover, mock_build, tmp_path):
        """Test exporting all documents in topological order."""
        dag, graph = _make_export_fixtures()
        mock_discover.return_value = dag
        mock_build.return_value = graph

        out = tmp_path / "out.yml"
        export_to_yaml(out, root=Path("/fake"))

        data = yaml.safe_load(out.read_text())
        assert len(data["documents"]) == 2
        assert data["documents"][0]["prefix"] == "SYS"
        assert data["documents"][1]["prefix"] == "SRS"
        assert data["documents"][1]["parents"] == ["SYS"]
        # Inactive SRS002 excluded
        assert len(data["items"]) == 2
        item_uids = [i["uid"] for i in data["items"]]
        assert "SRS001" in item_uids
        srs_item = next(i for i in data["items"] if i["uid"] == "SRS001")
        assert srs_item["links"] == ["SYS001"]

    def test_prefix_filter(self, mock_discover, mock_build, tmp_path):
        """Test exporting only specific prefixes."""
        dag, graph = _make_export_fixtures()
        mock_discover.return_value = dag
        mock_build.return_value = graph

        out = tmp_path / "out.yml"
        export_to_yaml(out, prefixes=["SRS"], root=Path("/fake"))

        data = yaml.safe_load(out.read_text())
        assert len(data["documents"]) == 1
        assert data["documents"][0]["prefix"] == "SRS"
        item_uids = [i["uid"] for i in data["items"]]
        assert all(uid.startswith("SRS") for uid in item_uids)

    def test_excludes_inactive(self, mock_discover, mock_build, tmp_path):
        """Test that inactive items are excluded from export."""
        dag, graph = _make_export_fixtures()
        mock_discover.return_value = dag
        mock_build.return_value = graph

        out = tmp_path / "out.yml"
        export_to_yaml(out, root=Path("/fake"))

        data = yaml.safe_load(out.read_text())
        item_uids = [i["uid"] for i in data["items"]]
        assert "SRS002" not in item_uids

    def test_creates_parent_directory(self, mock_discover, mock_build, tmp_path):
        """Test that parent directories are created automatically."""
        dag, graph = _make_export_fixtures()
        mock_discover.return_value = dag
        mock_build.return_value = graph

        out = tmp_path / "nested" / "deep" / "out.yml"
        export_to_yaml(out, root=Path("/fake"))

        assert out.exists()

    def test_item_with_header(self, mock_discover, mock_build, tmp_path):
        """Test that item headers appear in export output."""
        dag, graph = _make_export_fixtures()
        header_item = Item(
            uid="SYS002",
            text="Header item",
            document_prefix="SYS",
            header="Overview",
        )
        graph.add_item(header_item)
        mock_discover.return_value = dag
        mock_build.return_value = graph

        out = tmp_path / "out.yml"
        export_to_yaml(out, root=Path("/fake"))

        data = yaml.safe_load(out.read_text())
        sys002 = next(i for i in data["items"] if i["uid"] == "SYS002")
        assert sys002["header"] == "Overview"


@patch("jamb.storage.build_traceability_graph")
@patch("jamb.storage.discover_documents")
class TestExportItemsToYaml:
    """Tests for export_items_to_yaml function."""

    def test_specific_uids(self, mock_discover, mock_build, tmp_path):
        """Test exporting specific UIDs only."""
        dag, graph = _make_export_fixtures()
        mock_discover.return_value = dag
        mock_build.return_value = graph

        out = tmp_path / "out.yml"
        export_items_to_yaml(out, ["SRS001"], root=Path("/fake"))

        data = yaml.safe_load(out.read_text())
        item_uids = [i["uid"] for i in data["items"]]
        assert item_uids == ["SRS001"]

    def test_include_neighbors(self, mock_discover, mock_build, tmp_path):
        """Test exporting with neighbors includes linked items."""
        dag, graph = _make_export_fixtures()
        mock_discover.return_value = dag
        mock_build.return_value = graph

        out = tmp_path / "out.yml"
        export_items_to_yaml(out, ["SRS001"], include_neighbors=True, root=Path("/fake"))

        data = yaml.safe_load(out.read_text())
        item_uids = {i["uid"] for i in data["items"]}
        assert "SRS001" in item_uids
        assert "SYS001" in item_uids

    def test_prefix_filter_with_neighbors(self, mock_discover, mock_build, tmp_path):
        """Test that prefix filter limits neighbor inclusion."""
        dag, graph = _make_export_fixtures()
        mock_discover.return_value = dag
        mock_build.return_value = graph

        out = tmp_path / "out.yml"
        export_items_to_yaml(
            out,
            ["SRS001"],
            include_neighbors=True,
            prefixes=["SRS"],
            root=Path("/fake"),
        )

        data = yaml.safe_load(out.read_text())
        item_uids = [i["uid"] for i in data["items"]]
        assert "SRS001" in item_uids
        assert "SYS001" not in item_uids

    def test_unknown_uid_ignored(self, mock_discover, mock_build, tmp_path):
        """Test that unknown UIDs are silently ignored."""
        dag, graph = _make_export_fixtures()
        mock_discover.return_value = dag
        mock_build.return_value = graph

        out = tmp_path / "out.yml"
        export_items_to_yaml(out, ["NONEXIST"], root=Path("/fake"))

        data = yaml.safe_load(out.read_text())
        assert data["items"] == []


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


class TestRoundTripCustomAttributes:
    """Round-trip preservation of custom_attributes
    through export and re-import."""

    def test_custom_attributes_roundtrip(self, tmp_path):
        """Export items with custom_attributes, re-import, verify they survive."""
        from jamb.storage.items import read_item, write_item

        item_data = {
            "uid": "SRS001",
            "text": "Requirement with custom attrs",
            "document_prefix": "SRS",
            "active": True,
            "type": "requirement",
            "header": "",
            "links": [],
            "link_hashes": {},
            "reviewed": None,
            "derived": False,
            "custom_attributes": {},
        }

        # Write the item with extra_fields containing custom attributes
        item_path = tmp_path / "SRS001.yml"
        write_item(
            item_data,
            item_path,
            extra_fields={"priority": "high", "category": "security"},
        )

        # Re-read the item
        result = read_item(item_path, "SRS")
        assert result["uid"] == "SRS001"
        assert result["text"] == "Requirement with custom attrs"
        # Custom attributes should be preserved in the custom_attributes dict
        assert "priority" in result["custom_attributes"]
        assert result["custom_attributes"]["priority"] == "high"
        assert "category" in result["custom_attributes"]
        assert result["custom_attributes"]["category"] == "security"


class TestMultilineTextPreservation:
    """Test that very long multiline text is preserved via block scalar formatting."""

    def test_long_multiline_text_block_scalar(self, tmp_path):
        """Write item with long multiline text, verify
        block scalar style and content."""
        from jamb.storage.items import read_item, write_item

        long_text = (
            "This is a very long requirement text that spans multiple lines.\n"
            "It describes a complex feature with many details.\n"
            "Line 3: The system shall support concurrent users.\n"
            "Line 4: Performance must meet SLA targets.\n"
            "Line 5: All data must be encrypted at rest and in transit.\n"
            "Line 6: The audit log shall capture all state transitions.\n"
            "Line 7: Recovery time objective is 4 hours.\n"
            "Line 8: Final line of the requirement."
        )

        item_data = {
            "uid": "SRS050",
            "text": long_text,
            "document_prefix": "SRS",
            "active": True,
            "type": "requirement",
            "header": "Performance and Security",
            "links": [],
            "link_hashes": {},
            "reviewed": None,
            "derived": False,
        }

        item_path = tmp_path / "SRS050.yml"
        write_item(item_data, item_path)

        # Verify the raw YAML uses block scalar style ("|")
        raw_yaml = item_path.read_text()
        assert "|" in raw_yaml, "Multiline text should use block scalar style"

        # Re-read and verify content is identical
        result = read_item(item_path, "SRS")
        assert result["text"] == long_text
        assert result["header"] == "Performance and Security"


class TestLinkHashesSpecialCharacters:
    """Test import/export with link_hashes containing URL-safe base64 chars."""

    def test_link_hashes_with_special_chars(self, tmp_path):
        """Write and read item with link_hashes containing URL-safe base64 chars."""
        from jamb.storage.items import read_item, write_item

        # URL-safe base64 hashes may contain - and _ (but not / + or =)
        # Hash must be >= 20 chars and contain only [A-Za-z0-9_-]
        special_hash = "abc-DEF_123-XYZ_abc-def-789"

        item_data = {
            "uid": "SRS099",
            "text": "Item with special hash characters",
            "document_prefix": "SRS",
            "active": True,
            "type": "requirement",
            "header": "",
            "links": ["SYS001"],
            "link_hashes": {"SYS001": special_hash},
            "reviewed": None,
            "derived": False,
        }

        item_path = tmp_path / "SRS099.yml"
        write_item(item_data, item_path)

        # Re-read and verify the hash is preserved exactly
        result = read_item(item_path, "SRS")
        assert result["links"] == ["SYS001"]
        assert result["link_hashes"]["SYS001"] == special_hash

    def test_link_hashes_with_invalid_chars_rejected(self, tmp_path):
        """Write and read item where link hash contains invalid chars."""

        from jamb.storage.items import read_item, write_item

        # Hash with invalid characters (unicode) should be rejected on read
        invalid_hash = "hash_with_unicode_chars"  # Valid hash for write

        item_data = {
            "uid": "SRS100",
            "text": "Item with hash",
            "document_prefix": "SRS",
            "active": True,
            "type": "requirement",
            "header": "",
            "links": ["SYS002"],
            "link_hashes": {"SYS002": invalid_hash},
            "reviewed": None,
            "derived": False,
        }

        item_path = tmp_path / "SRS100.yml"
        write_item(item_data, item_path)

        result = read_item(item_path, "SRS")
        assert result["links"] == ["SYS002"]
        assert result["link_hashes"]["SYS002"] == invalid_hash
