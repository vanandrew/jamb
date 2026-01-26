"""Tests for jamb.yaml_io module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from jamb.yaml_io import (
    _create_document,
    _create_item,
    _document_exists,
    _document_to_dict,
    _extract_prefix,
    _get_document_path,
    _item_exists,
    _item_to_dict,
    _sort_documents_by_dependency,
    _update_item,
    export_items_to_yaml,
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


class TestSortDocumentsByDependency:
    """Tests for _sort_documents_by_dependency function."""

    def test_sorts_root_first(self):
        """Test that root documents come first."""
        root = MagicMock()
        root.prefix = "UN"
        root.parent = None

        child = MagicMock()
        child.prefix = "SRS"
        child.parent = "UN"

        result = _sort_documents_by_dependency([child, root])
        assert [d.prefix for d in result] == ["UN", "SRS"]

    def test_handles_deep_hierarchy(self):
        """Test three-level hierarchy."""
        cus = MagicMock()
        cus.prefix = "UN"
        cus.parent = None

        sys_doc = MagicMock()
        sys_doc.prefix = "SYS"
        sys_doc.parent = "UN"

        srs = MagicMock()
        srs.prefix = "SRS"
        srs.parent = "SYS"

        result = _sort_documents_by_dependency([srs, cus, sys_doc])
        prefixes = [d.prefix for d in result]
        assert prefixes.index("UN") < prefixes.index("SYS")
        assert prefixes.index("SYS") < prefixes.index("SRS")

    def test_handles_single_document(self):
        """Test single document."""
        doc = MagicMock(prefix="SRS", parent=None)
        result = _sort_documents_by_dependency([doc])
        assert len(result) == 1


class TestDocumentToDict:
    """Tests for _document_to_dict function."""

    def test_basic_conversion(self):
        """Test basic document conversion."""
        doc = MagicMock()
        doc.prefix = "SRS"
        doc.path = Path("/project/srs")
        doc.parent = None
        doc.tree = None

        result = _document_to_dict(doc)
        assert result["prefix"] == "SRS"
        assert "path" in result
        assert "parent" not in result

    def test_includes_parent(self):
        """Test document with parent."""
        doc = MagicMock()
        doc.prefix = "SRS"
        doc.path = Path("/project/srs")
        doc.parent = "SYS"
        doc.tree = None

        result = _document_to_dict(doc)
        assert result["parent"] == "SYS"

    def test_relative_path_from_tree_root(self):
        """Test document path is made relative to tree root."""
        doc = MagicMock()
        doc.prefix = "SRS"
        doc.path = Path("/project/srs")
        doc.parent = None

        mock_tree = MagicMock()
        mock_tree.root = Path("/project")
        doc.tree = mock_tree

        result = _document_to_dict(doc)
        assert result["path"] == "srs"

    def test_includes_digits_from_config(self):
        """Test document includes digits from config."""
        doc = MagicMock()
        doc.prefix = "SRS"
        doc.path = Path("/project/srs")
        doc.parent = None
        doc.tree = None
        doc._data = {"settings": {"digits": 4}}

        result = _document_to_dict(doc)
        assert result["digits"] == 4


class TestItemToDict:
    """Tests for _item_to_dict function."""

    def test_basic_conversion(self):
        """Test basic item conversion."""
        item = MagicMock()
        item.uid = "SRS001"
        item.text = "Test requirement"
        item.header = ""
        item.links = []

        result = _item_to_dict(item)
        assert result["uid"] == "SRS001"
        assert result["text"] == "Test requirement"
        assert "header" not in result
        assert "links" not in result

    def test_includes_header(self):
        """Test item with header."""
        item = MagicMock()
        item.uid = "SRS001"
        item.text = "Test requirement"
        item.header = "Authentication"
        item.links = []

        result = _item_to_dict(item)
        assert result["header"] == "Authentication"

    def test_includes_links(self):
        """Test item with links."""
        item = MagicMock()
        item.uid = "SRS001"
        item.text = "Test requirement"
        item.header = ""
        item.links = ["SYS001", "SYS002"]

        result = _item_to_dict(item)
        assert result["links"] == ["SYS001", "SYS002"]


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

    def test_raises_on_invalid_yaml(self, tmp_path):
        """Test error on non-mapping YAML."""
        yaml_file = tmp_path / "test.yml"
        yaml_file.write_text("- item1\n- item2")

        with pytest.raises(ValueError, match="must contain a mapping"):
            load_import_file(yaml_file)


class TestUpdateItem:
    """Tests for _update_item function."""

    def test_updates_text(self, tmp_path):
        """Test updating item text."""
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\ntext: Old text\n")

        result = _update_item(
            item_path, {"uid": "SRS001", "text": "New text"}, verbose=False, echo=print
        )

        assert result == "updated"
        updated = yaml.safe_load(item_path.read_text())
        assert updated["text"] == "New text"
        assert updated["active"] is True  # Preserved

    def test_preserves_existing_fields(self, tmp_path):
        """Test that unspecified fields are preserved."""
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text(
            "active: true\nnormative: true\nlevel: '1.2'\ntext: Test\n"
        )

        _update_item(
            item_path, {"uid": "SRS001", "text": "New text"}, verbose=False, echo=print
        )

        updated = yaml.safe_load(item_path.read_text())
        assert updated["level"] == "1.2"  # Preserved
        assert updated["normative"] is True  # Preserved

    def test_clears_reviewed_status(self, tmp_path):
        """Test that reviewed status is cleared on update."""
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\nreviewed: abc123\ntext: Test\n")

        _update_item(
            item_path, {"uid": "SRS001", "text": "New text"}, verbose=False, echo=print
        )

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


class TestSortDocumentsByDependencyEdgeCases:
    """Edge case tests for _sort_documents_by_dependency."""

    def test_handles_missing_parent(self):
        """Test handling of document with missing parent."""
        orphan = MagicMock()
        orphan.prefix = "SRS"
        orphan.parent = "NONEXISTENT"  # Parent doesn't exist in list

        root = MagicMock()
        root.prefix = "UN"
        root.parent = None

        result = _sort_documents_by_dependency([orphan, root])
        # Should still return all documents
        assert len(result) == 2
        # Root should come first
        assert result[0].prefix == "UN"

    def test_handles_circular_dependency(self):
        """Test handling of circular document dependencies."""
        doc_a = MagicMock()
        doc_a.prefix = "A"
        doc_a.parent = "B"

        doc_b = MagicMock()
        doc_b.prefix = "B"
        doc_b.parent = "A"

        # Both claim to have the other as parent - no root
        result = _sort_documents_by_dependency([doc_a, doc_b])
        # Should return both documents (added as-is after timeout)
        assert len(result) == 2


class TestImportFromYaml:
    """Tests for import_from_yaml function."""

    def test_import_uses_print_as_default_echo(self, tmp_path, monkeypatch):
        """Test import uses print when no echo provided."""
        yaml_file = tmp_path / "import.yml"
        yaml_file.write_text("documents: []\nitems: []")

        # Mock _create_document and _create_item to avoid actual doorstop calls
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

    def test_create_document_dry_run_with_parent(self):
        """Test _create_document dry_run shows parent."""
        with patch("jamb.yaml_io._document_exists") as mock_exists:
            mock_exists.return_value = False

            messages = []
            result = _create_document(
                {"prefix": "NEW", "path": "new", "parent": "UN"},
                dry_run=True,
                verbose=False,
                echo=messages.append,
            )

            assert result == "created"
            assert any("parent: UN" in msg for msg in messages)


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
            assert content["normative"] is True
            assert content["text"] == "New requirement"

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


class TestDocumentExists:
    """Tests for _document_exists function."""

    def test_document_exists_true(self):
        """Test _document_exists returns True for existing doc."""
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = "SRS: 10 items\nUN: 5 items"
            mock_run.return_value = mock_result

            assert _document_exists("SRS") is True
            assert _document_exists("UN") is True

    def test_document_exists_false(self):
        """Test _document_exists returns False for missing doc."""
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = "SRS: 10 items"
            mock_run.return_value = mock_result

            assert _document_exists("NONEXISTENT") is False


class TestItemExists:
    """Tests for _item_exists function."""

    def test_item_exists_true(self, tmp_path):
        """Test _item_exists returns True for existing item."""
        (tmp_path / "SRS001.yml").write_text("text: Test")

        with patch("jamb.yaml_io._get_document_path") as mock_path:
            mock_path.return_value = tmp_path

            assert _item_exists("SRS001") is True

    def test_item_exists_false(self, tmp_path):
        """Test _item_exists returns False for missing item."""
        with patch("jamb.yaml_io._get_document_path") as mock_path:
            mock_path.return_value = tmp_path

            assert _item_exists("SRS999") is False

    def test_item_exists_invalid_prefix(self):
        """Test _item_exists handles invalid UID."""
        assert _item_exists("123") is False

    def test_item_exists_missing_document(self):
        """Test _item_exists handles missing document."""
        with patch("jamb.yaml_io._get_document_path") as mock_path:
            mock_path.return_value = None

            assert _item_exists("SRS001") is False


class TestGetDocumentPath:
    """Tests for _get_document_path function."""

    def test_get_document_path_found(self, tmp_path, monkeypatch):
        """Test _get_document_path finds correct path."""
        monkeypatch.chdir(tmp_path)

        # Create doorstop config
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".doorstop.yml").write_text(
            "settings:\n  prefix: SRS\n  digits: 3\n"
        )

        result = _get_document_path("SRS")

        assert result is not None
        assert result.name == "srs"

    def test_get_document_path_not_found(self, tmp_path, monkeypatch):
        """Test _get_document_path returns None when not found."""
        monkeypatch.chdir(tmp_path)

        result = _get_document_path("NONEXISTENT")

        assert result is None


class TestExportItemsToYaml:
    """Tests for export_items_to_yaml function."""

    def _create_mock_tree(self):
        """Create a mock doorstop tree with linked items."""
        # Create mock items
        cus001 = MagicMock()
        cus001.uid = "UN001"
        cus001.text = "Customer need"
        cus001.header = ""
        cus001.links = []
        cus001.active = True
        cus001.normative = True
        cus001.level = 1.0
        cus001.data = {}

        sys001 = MagicMock()
        sys001.uid = "SYS001"
        sys001.text = "System requirement"
        sys001.header = ""
        sys001.links = ["UN001"]
        sys001.active = True
        sys001.normative = True
        sys001.level = 1.0
        sys001.data = {}

        srs001 = MagicMock()
        srs001.uid = "SRS001"
        srs001.text = "Software requirement 1"
        srs001.header = ""
        srs001.links = ["SYS001"]
        srs001.active = True
        srs001.normative = True
        srs001.level = 1.0
        srs001.data = {}

        srs002 = MagicMock()
        srs002.uid = "SRS002"
        srs002.text = "Software requirement 2"
        srs002.header = ""
        srs002.links = ["SYS001"]
        srs002.active = True
        srs002.normative = True
        srs002.level = 1.0
        srs002.data = {}

        # Create mock documents
        cus_doc = MagicMock()
        cus_doc.prefix = "UN"
        cus_doc.parent = None
        cus_doc.path = Path("/project/req")
        cus_doc.tree = None
        cus_doc._data = {"settings": {"digits": 3}}
        cus_doc.__iter__ = lambda _: iter([cus001])

        sys_doc = MagicMock()
        sys_doc.prefix = "SYS"
        sys_doc.parent = "UN"
        sys_doc.path = Path("/project/sys")
        sys_doc.tree = None
        sys_doc._data = {"settings": {"digits": 3}}
        sys_doc.__iter__ = lambda _: iter([sys001])

        srs_doc = MagicMock()
        srs_doc.prefix = "SRS"
        srs_doc.parent = "SYS"
        srs_doc.path = Path("/project/srs")
        srs_doc.tree = None
        srs_doc._data = {"settings": {"digits": 3}}
        srs_doc.__iter__ = lambda _: iter([srs001, srs002])

        # Create mock tree
        tree = MagicMock()
        tree.documents = [cus_doc, sys_doc, srs_doc]
        tree.find_document = lambda p: {
            "UN": cus_doc,
            "SYS": sys_doc,
            "SRS": srs_doc,
        }.get(p)

        return tree

    def test_export_single_item(self, tmp_path):
        """Test exporting a single item."""
        tree = self._create_mock_tree()
        output_path = tmp_path / "output.yml"

        export_items_to_yaml(tree, output_path, ["SRS001"])

        assert output_path.exists()
        data = yaml.safe_load(output_path.read_text())
        assert len(data["items"]) == 1
        assert data["items"][0]["uid"] == "SRS001"
        assert len(data["documents"]) == 1
        assert data["documents"][0]["prefix"] == "SRS"

    def test_export_multiple_items(self, tmp_path):
        """Test exporting multiple items."""
        tree = self._create_mock_tree()
        output_path = tmp_path / "output.yml"

        export_items_to_yaml(tree, output_path, ["SRS001", "SRS002"])

        data = yaml.safe_load(output_path.read_text())
        assert len(data["items"]) == 2
        uids = [item["uid"] for item in data["items"]]
        assert "SRS001" in uids
        assert "SRS002" in uids

    def test_export_with_neighbors(self, tmp_path):
        """Test exporting items with neighbors includes ancestors and descendants."""
        tree = self._create_mock_tree()
        output_path = tmp_path / "output.yml"

        # Export SYS001 with neighbors should include UN001 (ancestor)
        # and SRS001, SRS002 (descendants)
        export_items_to_yaml(tree, output_path, ["SYS001"], include_neighbors=True)

        data = yaml.safe_load(output_path.read_text())
        uids = [item["uid"] for item in data["items"]]
        assert "SYS001" in uids
        assert "UN001" in uids
        assert "SRS001" in uids
        assert "SRS002" in uids
        # Should have 3 documents
        prefixes = [doc["prefix"] for doc in data["documents"]]
        assert "UN" in prefixes
        assert "SYS" in prefixes
        assert "SRS" in prefixes

    def test_export_with_document_filter(self, tmp_path):
        """Test exporting items with document filter."""
        tree = self._create_mock_tree()
        output_path = tmp_path / "output.yml"

        # Export SYS001 with neighbors but filter to only SYS and SRS
        export_items_to_yaml(
            tree,
            output_path,
            ["SYS001"],
            include_neighbors=True,
            prefixes=["SYS", "SRS"],
        )

        data = yaml.safe_load(output_path.read_text())
        uids = [item["uid"] for item in data["items"]]
        assert "SYS001" in uids
        assert "SRS001" in uids
        assert "SRS002" in uids
        # UN001 should be filtered out
        assert "UN001" not in uids

    def test_export_nonexistent_item_ignored(self, tmp_path):
        """Test that non-existent items are silently ignored."""
        tree = self._create_mock_tree()
        output_path = tmp_path / "output.yml"

        export_items_to_yaml(tree, output_path, ["SRS001", "NONEXISTENT"])

        data = yaml.safe_load(output_path.read_text())
        assert len(data["items"]) == 1
        assert data["items"][0]["uid"] == "SRS001"

    def test_export_creates_parent_directories(self, tmp_path):
        """Test that export creates parent directories if needed."""
        tree = self._create_mock_tree()
        output_path = tmp_path / "subdir" / "nested" / "output.yml"

        export_items_to_yaml(tree, output_path, ["SRS001"])

        assert output_path.exists()

    def test_export_items_in_document_order(self, tmp_path):
        """Test that items are exported in document dependency order."""
        tree = self._create_mock_tree()
        output_path = tmp_path / "output.yml"

        export_items_to_yaml(tree, output_path, ["SRS001"], include_neighbors=True)

        data = yaml.safe_load(output_path.read_text())
        prefixes = [doc["prefix"] for doc in data["documents"]]
        # UN (root) should come before SYS, SYS before SRS
        assert prefixes.index("UN") < prefixes.index("SYS")
        assert prefixes.index("SYS") < prefixes.index("SRS")


class TestDocumentToDictEdgeCases:
    """Edge case tests for _document_to_dict function."""

    def test_document_with_path_not_under_tree_root(self):
        """Test document path outside tree root is handled."""
        doc = MagicMock()
        doc.prefix = "SRS"
        doc.path = Path("/other/location/srs")
        doc.parent = None

        # Tree root is different
        mock_tree = MagicMock()
        mock_tree.root = Path("/project")
        doc.tree = mock_tree

        # path.relative_to() should raise ValueError, handled gracefully
        result = _document_to_dict(doc)
        # Should still have a path
        assert "path" in result
        # Path should remain absolute since it can't be made relative
        assert "/other/location/srs" in result["path"] or "srs" in result["path"]

    def test_document_with_string_path(self):
        """Test document with string path instead of Path object."""
        doc = MagicMock()
        doc.prefix = "SRS"
        doc.path = "/project/srs"  # String instead of Path
        doc.parent = None
        doc.tree = None

        result = _document_to_dict(doc)
        assert result["prefix"] == "SRS"
        assert "path" in result


class TestCreateDocumentErrorHandling:
    """Tests for _create_document error handling."""

    def test_create_document_handles_subprocess_error(self):
        """Test _create_document handles doorstop create failure."""
        with (
            patch("jamb.yaml_io._document_exists") as mock_exists,
            patch("subprocess.run") as mock_run,
        ):
            mock_exists.return_value = False
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "Document creation failed"
            mock_run.return_value = mock_result

            messages = []
            result = _create_document(
                {"prefix": "FAIL", "path": "fail"},
                dry_run=False,
                verbose=True,
                echo=messages.append,
            )

            assert result == "error"
            assert any("Error creating" in msg for msg in messages)

    def test_create_document_verbose_output(self):
        """Test _create_document verbose output on success."""
        with (
            patch("jamb.yaml_io._document_exists") as mock_exists,
            patch("subprocess.run") as mock_run,
        ):
            mock_exists.return_value = False
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            messages = []
            result = _create_document(
                {"prefix": "NEW", "path": "new"},
                dry_run=False,
                verbose=True,
                echo=messages.append,
            )

            assert result == "created"
            assert any("Created document: NEW" in msg for msg in messages)

    def test_create_document_with_parent(self):
        """Test _create_document includes parent in doorstop command."""
        with (
            patch("jamb.yaml_io._document_exists") as mock_exists,
            patch("subprocess.run") as mock_run,
        ):
            mock_exists.return_value = False
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            result = _create_document(
                {"prefix": "SRS", "path": "srs", "parent": "SYS"},
                dry_run=False,
                verbose=False,
                echo=lambda x: None,
            )

            assert result == "created"
            # Verify the command included --parent SYS
            call_args = mock_run.call_args[0][0]
            assert "--parent" in call_args
            assert "SYS" in call_args


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
