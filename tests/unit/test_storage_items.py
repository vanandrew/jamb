"""Tests for jamb.storage.items module."""

import yaml

from jamb.storage.items import (
    compute_content_hash,
    next_uid,
    read_document_items,
    read_item,
    write_item,
)


class TestReadItem:
    def test_reads_basic_item(self, tmp_path):
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\ntext: Test requirement\n")
        data = read_item(item_path, "SRS")
        assert data["uid"] == "SRS001"
        assert data["text"] == "Test requirement"
        assert data["active"] is True
        assert data["type"] == "requirement"
        assert data["document_prefix"] == "SRS"

    def test_reads_links_plain(self, tmp_path):
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text(
            "active: true\ntext: Test\nlinks:\n  - SYS001\n  - SYS002\n"
        )
        data = read_item(item_path, "SRS")
        assert data["links"] == ["SYS001", "SYS002"]

    def test_reads_links_with_hash(self, tmp_path):
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\ntext: Test\nlinks:\n  - SYS001: abc123\n")
        data = read_item(item_path, "SRS")
        assert data["links"] == ["SYS001"]
        assert data["link_hashes"] == {"SYS001": "abc123"}

    def test_reads_explicit_type(self, tmp_path):
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\ntype: heading\ntext: Section header\n")
        data = read_item(item_path, "SRS")
        assert data["type"] == "heading"

    def test_reads_custom_attributes(self, tmp_path):
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\ntext: Test\ncustom_field: value\n")
        data = read_item(item_path, "SRS")
        assert data["custom_attributes"]["custom_field"] == "value"


class TestWriteItem:
    def test_writes_basic_item(self, tmp_path):
        item_path = tmp_path / "SRS001.yml"
        write_item(
            {"active": True, "text": "Test requirement", "type": "requirement"},
            item_path,
        )
        assert item_path.exists()
        data = yaml.safe_load(item_path.read_text())
        assert data["active"] is True
        assert data["text"] == "Test requirement"

    def test_writes_links(self, tmp_path):
        item_path = tmp_path / "SRS001.yml"
        write_item({"active": True, "text": "Test", "links": ["SYS001"]}, item_path)
        data = yaml.safe_load(item_path.read_text())
        assert data["links"] == ["SYS001"]


class TestReadDocumentItems:
    def test_reads_items(self, tmp_path):
        (tmp_path / ".jamb.yml").write_text("settings:\n  prefix: SRS\n")
        (tmp_path / "SRS001.yml").write_text("active: true\ntext: First\n")
        (tmp_path / "SRS002.yml").write_text("active: true\ntext: Second\n")
        items = read_document_items(tmp_path, "SRS")
        assert len(items) == 2

    def test_excludes_inactive(self, tmp_path):
        (tmp_path / "SRS001.yml").write_text("active: true\ntext: Active\n")
        (tmp_path / "SRS002.yml").write_text("active: false\ntext: Inactive\n")
        items = read_document_items(tmp_path, "SRS")
        assert len(items) == 1
        assert items[0]["uid"] == "SRS001"

    def test_includes_inactive_when_requested(self, tmp_path):
        (tmp_path / "SRS001.yml").write_text("active: true\ntext: Active\n")
        (tmp_path / "SRS002.yml").write_text("active: false\ntext: Inactive\n")
        items = read_document_items(tmp_path, "SRS", include_inactive=True)
        assert len(items) == 2


class TestNextUid:
    def test_first_uid(self):
        assert next_uid("SRS", 3, []) == "SRS001"

    def test_increments(self):
        assert next_uid("SRS", 3, ["SRS001", "SRS002"]) == "SRS003"

    def test_with_separator(self):
        assert next_uid("SRS", 3, [], sep="-") == "SRS-001"

    def test_respects_digits(self):
        assert next_uid("SRS", 4, []) == "SRS0001"


class TestComputeContentHash:
    def test_returns_string(self):
        result = compute_content_hash({"text": "hello", "type": "requirement"})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_same_content_same_hash(self):
        data = {"text": "hello", "type": "requirement"}
        assert compute_content_hash(data) == compute_content_hash(data)

    def test_different_content_different_hash(self):
        data1 = {"text": "hello", "type": "requirement"}
        data2 = {"text": "world", "type": "requirement"}
        assert compute_content_hash(data1) != compute_content_hash(data2)
