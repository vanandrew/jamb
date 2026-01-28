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
        yaml_file.write_text(
            "items:\n"
            "  - uid: SRS001\n"
            "    text: First\n"
            "  - uid: SRS001\n"
            "    text: Second\n"
        )

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
        item_path.write_text("active: true\ncustom_field: true\ntext: Test\n")

        _update_item(
            item_path, {"uid": "SRS001", "text": "New text"}, verbose=False, echo=print
        )

        updated = yaml.safe_load(item_path.read_text())
        assert updated["custom_field"] is True  # Preserved

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


class TestDocumentExists:
    """Tests for _document_exists function."""

    def test_document_exists_with_jamb_yml(self, tmp_path, monkeypatch):
        """Test _document_exists finds document via .jamb.yml."""
        monkeypatch.chdir(tmp_path)

        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  prefix: SRS\n  digits: 3\n")

        assert _document_exists("SRS") is True

    def test_document_exists_false(self, tmp_path, monkeypatch):
        """Test _document_exists returns False for missing doc."""
        monkeypatch.chdir(tmp_path)

        assert _document_exists("NONEXISTENT") is False

    def test_document_exists_false_wrong_prefix(self, tmp_path, monkeypatch):
        """Test _document_exists returns False when prefix doesn't match."""
        monkeypatch.chdir(tmp_path)

        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  prefix: SRS\n  digits: 3\n")

        assert _document_exists("UN") is False


class TestGetDocumentPath:
    """Tests for _get_document_path function."""

    def test_get_document_path_found_jamb_yml(self, tmp_path, monkeypatch):
        """Test _get_document_path finds correct path via .jamb.yml."""
        monkeypatch.chdir(tmp_path)

        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  prefix: SRS\n  digits: 3\n")

        result = _get_document_path("SRS")

        assert result is not None
        assert result.name == "srs"

    def test_get_document_path_not_found(self, tmp_path, monkeypatch):
        """Test _get_document_path returns None when not found."""
        monkeypatch.chdir(tmp_path)

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
    srs_item = Item(
        uid="SRS001", text="Software req", document_prefix="SRS", links=["SYS001"]
    )
    inactive_item = Item(
        uid="SRS002", text="Inactive", document_prefix="SRS", active=False
    )
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
        item = Item(
            uid="SRS001", text="Hello", document_prefix="SRS", header="My Header"
        )
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
        export_items_to_yaml(
            out, ["SRS001"], include_neighbors=True, root=Path("/fake")
        )

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
    """Test import/export with link_hashes containing special characters."""

    def test_link_hashes_with_special_chars(self, tmp_path):
        """Write and read item with link_hashes containing URL-safe base64 chars."""
        from jamb.storage.items import read_item, write_item

        # URL-safe base64 hashes may contain - _ and =
        special_hash = "abc-DEF_123/+xyz=="

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

    def test_link_hashes_with_unicode_preserved(self, tmp_path):
        """Write and read item where link hash is a unicode string."""
        from jamb.storage.items import read_item, write_item

        unicode_hash = "hash_\u00e9\u00e8\u00ea_value"

        item_data = {
            "uid": "SRS100",
            "text": "Item with unicode hash",
            "document_prefix": "SRS",
            "active": True,
            "type": "requirement",
            "header": "",
            "links": ["SYS002"],
            "link_hashes": {"SYS002": unicode_hash},
            "reviewed": None,
            "derived": False,
        }

        item_path = tmp_path / "SRS100.yml"
        write_item(item_data, item_path)

        result = read_item(item_path, "SRS")
        assert result["links"] == ["SYS002"]
        assert result["link_hashes"]["SYS002"] == unicode_hash
