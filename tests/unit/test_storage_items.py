"""Tests for jamb.storage.items module."""

import pytest
import yaml

from jamb.storage.items import (
    compute_content_hash,
    next_uid,
    read_document_items,
    read_item,
    write_item,
)


class TestReadItemErrorHandling:
    """Tests for read_item error handling."""

    def test_read_item_os_error(self, tmp_path):
        """Test read_item handles OSError appropriately."""
        from unittest.mock import patch

        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("text: test")

        # Mock open to raise OSError on the second call (after file exists check)
        original_open = open

        def mock_open_wrapper(*args, **kwargs):
            if str(item_path) in str(args[0]) and "r" in str(kwargs.get("mode", "r")):
                raise OSError("Permission denied")
            return original_open(*args, **kwargs)

        with patch("builtins.open", side_effect=mock_open_wrapper):
            with pytest.raises(OSError, match="Permission denied"):
                read_item(item_path, "SRS")

    def test_read_item_yaml_error(self, tmp_path):
        """Test read_item raises ValueError on YAML syntax error."""
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("invalid: yaml: [unclosed")

        with pytest.raises(ValueError, match="Invalid YAML"):
            read_item(item_path, "SRS")


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
        item_path.write_text("active: true\ntext: Test\nlinks:\n  - SYS001\n  - SYS002\n")
        data = read_item(item_path, "SRS")
        assert data["links"] == ["SYS001", "SYS002"]

    def test_reads_links_with_hash(self, tmp_path):
        # Hash must be >= 20 chars and contain only URL-safe base64 chars
        valid_hash = "abcdefghijklmnopqrstuvwxyz"
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text(f"active: true\ntext: Test\nlinks:\n  - SYS001: {valid_hash}\n")
        data = read_item(item_path, "SRS")
        assert data["links"] == ["SYS001"]
        assert data["link_hashes"] == {"SYS001": valid_hash}

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

    def test_reads_mixed_link_formats(self, tmp_path):
        """Links list with both dict and string entries."""
        # Hash must be >= 20 chars and contain only URL-safe base64 chars
        valid_hash = "abcdefghijklmnopqrstuvwxyz"
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text(f"active: true\ntext: Test\nlinks:\n  - SYS001: {valid_hash}\n  - SYS002\n")
        data = read_item(item_path, "SRS")
        assert data["links"] == ["SYS001", "SYS002"]
        assert data["link_hashes"] == {"SYS001": valid_hash}

    def test_reads_empty_header_as_none(self, tmp_path):
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\ntext: Test\nheader:\n")
        data = read_item(item_path, "SRS")
        assert data["header"] is None

    def test_reads_derived_flag(self, tmp_path):
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\ntext: Test\nderived: true\n")
        data = read_item(item_path, "SRS")
        assert data["derived"] is True

    def test_reads_empty_file(self, tmp_path):
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("")
        data = read_item(item_path, "SRS")
        assert data["uid"] == "SRS001"
        assert data["text"] == ""
        assert data["active"] is True

    def test_reads_numeric_link_rejected_with_warning(self, tmp_path):
        """A link that YAML parses as int is rejected with warning."""
        import warnings

        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\ntext: Test\nlinks:\n  - 123\n")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            data = read_item(item_path, "SRS")
        # Non-string links are rejected
        assert data["links"] == []

    def test_null_hash_excluded_from_link_hashes(self, tmp_path):
        """1a: {UID: null} link hash should be excluded from link_hashes."""
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\ntext: Test\nlinks:\n  - SYS001:\n")
        data = read_item(item_path, "SRS")
        assert data["links"] == ["SYS001"]
        assert data["link_hashes"] == {}

    def test_scalar_links_ignored(self, tmp_path):
        """1b: links as scalar string (not list) produces empty links."""
        import warnings

        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\ntext: Test\nlinks: SYS001\n")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            data = read_item(item_path, "SRS")
        assert data["links"] == []

    def test_warns_on_scalar_links(self, tmp_path):
        """Scalar links value produces warning."""
        import warnings

        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\ntext: Test\nlinks: SYS001\n")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            data = read_item(item_path, "SRS")
            assert data["links"] == []  # Still returns empty list
            assert len(w) == 1
            assert "not a list" in str(w[0].message)
            assert "SRS001" in str(w[0].message)

    def test_non_string_text_coerced(self, tmp_path):
        """1c: YAML `text: 42` (int) is coerced to string '42'."""
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\ntext: 42\n")
        data = read_item(item_path, "SRS")
        assert data["text"] == "42"

    def test_empty_yaml_file(self, tmp_path):
        """1g: Completely empty YAML file returns sensible defaults."""
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("")
        data = read_item(item_path, "SRS")
        assert data["uid"] == "SRS001"
        assert data["text"] == ""
        assert data["active"] is True
        assert data["links"] == []
        assert data["link_hashes"] == {}
        assert data["type"] == "requirement"
        assert data["header"] is None

    def test_raises_on_yaml_syntax_error(self, tmp_path):
        """Malformed YAML content raises ValueError with context."""
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text(": bad: {{")
        with pytest.raises(ValueError, match="Invalid YAML in file"):
            read_item(item_path, "SRS")

    def test_reads_empty_dict_in_links(self, tmp_path):
        """Empty dict {} in links list is skipped without error."""
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\ntext: Test\nlinks:\n  - {}\n  - SYS001\n")
        data = read_item(item_path, "SRS")
        assert data["links"] == ["SYS001"]
        assert data["link_hashes"] == {}

    def test_reads_empty_string_link_with_warning(self, tmp_path):
        """Empty string in links list produces warning."""
        import warnings

        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\ntext: Test\nlinks:\n  - ''\n  - SYS001\n")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            data = read_item(item_path, "SRS")
            # Should skip empty string but keep valid link
            assert data["links"] == ["SYS001"]
            # Should warn about empty link
            assert any("Empty link UID" in str(warning.message) for warning in w)

    def test_reads_short_hash_with_warning(self, tmp_path):
        """Link hash shorter than 20 chars produces warning."""
        import warnings

        short_hash = "abc123"  # Only 6 chars, should be rejected
        item_path = tmp_path / "SRS001.yml"
        item_path.write_text(f"active: true\ntext: Test\nlinks:\n  - SYS001: {short_hash}\n")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            data = read_item(item_path, "SRS")
            # Link UID should still be added
            assert data["links"] == ["SYS001"]
            # But hash should not be stored due to invalid format
            assert data["link_hashes"] == {}
            # Should warn about invalid hash format
            assert any("Invalid hash format" in str(warning.message) for warning in w)

    def test_reads_non_string_reviewed_with_warning(self, tmp_path):
        """Non-string reviewed field produces warning and is treated as None."""
        import warnings

        item_path = tmp_path / "SRS001.yml"
        item_path.write_text("active: true\ntext: Test\nreviewed: 123\n")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            data = read_item(item_path, "SRS")
            # Should be treated as not reviewed
            assert data["reviewed"] is None
            # Should warn about non-string reviewed
            assert any("non-string 'reviewed'" in str(warning.message) for warning in w)


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

    def test_writes_extra_fields(self, tmp_path):
        item_path = tmp_path / "SRS001.yml"
        write_item(
            {"active": True, "text": "Test", "type": "requirement"},
            item_path,
            extra_fields={"custom_field": "custom_value"},
        )
        data = yaml.safe_load(item_path.read_text())
        assert data["custom_field"] == "custom_value"

    def test_writes_multiline_text_as_block_scalar(self, tmp_path):
        item_path = tmp_path / "SRS001.yml"
        write_item({"active": True, "text": "line1\nline2\nline3"}, item_path)
        raw_text = item_path.read_text()
        # Block scalar should use | style
        assert "|" in raw_text

    def test_writes_links_with_hashes(self, tmp_path):
        item_path = tmp_path / "SRS001.yml"
        write_item(
            {
                "active": True,
                "text": "Test",
                "links": ["SYS001"],
                "link_hashes": {"SYS001": "abc123"},
            },
            item_path,
        )
        data = yaml.safe_load(item_path.read_text())
        assert isinstance(data["links"][0], dict)
        assert data["links"][0]["SYS001"] == "abc123"

    def test_writes_derived_flag(self, tmp_path):
        item_path = tmp_path / "SRS001.yml"
        write_item({"active": True, "text": "Test", "derived": True}, item_path)
        data = yaml.safe_load(item_path.read_text())
        assert data["derived"] is True

    def test_omits_derived_when_false(self, tmp_path):
        """1d: write_item omits 'derived' key when derived is False."""
        item_path = tmp_path / "SRS001.yml"
        write_item({"active": True, "text": "Test", "derived": False}, item_path)
        data = yaml.safe_load(item_path.read_text())
        assert "derived" not in data

    def test_creates_parent_directory(self, tmp_path):
        item_path = tmp_path / "subdir" / "SRS001.yml"
        write_item({"active": True, "text": "Test"}, item_path)
        assert item_path.exists()

    def test_cleans_temp_on_write_failure(self, tmp_path):
        """Temp file is cleaned up if write fails."""
        from unittest.mock import patch

        item_path = tmp_path / "SRS001.yml"

        # Mock dump_yaml to raise an error during write
        with patch("jamb.storage.items.dump_yaml") as mock_dump:
            mock_dump.side_effect = ValueError("Simulated write failure")
            with pytest.raises(ValueError, match="Simulated write failure"):
                write_item({"active": True, "text": "Test"}, item_path)

        # No temp files should remain
        temp_files = list(tmp_path.glob(".tmp_*.yml"))
        assert temp_files == []


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

    def test_reads_items_with_separator(self, tmp_path):
        (tmp_path / ".jamb.yml").write_text("settings:\n  prefix: API\n  sep: '-'\n")
        (tmp_path / "API-0001.yml").write_text("active: true\ntext: First\n")
        (tmp_path / "API-0002.yml").write_text("active: true\ntext: Second\n")
        items = read_document_items(tmp_path, "API", sep="-")
        assert len(items) == 2
        assert items[0]["uid"] == "API-0001"

    def test_raises_on_yaml_syntax_error(self, tmp_path):
        """A malformed YAML item file raises ValueError with context."""
        (tmp_path / "SRS001.yml").write_text("active: true\ntext: Valid\n")
        (tmp_path / "SRS002.yml").write_text(": bad: {{")
        with pytest.raises(ValueError, match="Invalid YAML in file"):
            read_document_items(tmp_path, "SRS")


class TestNextUid:
    def test_first_uid(self):
        assert next_uid("SRS", 3, []) == "SRS001"

    def test_increments(self):
        assert next_uid("SRS", 3, ["SRS001", "SRS002"]) == "SRS003"

    def test_with_separator(self):
        assert next_uid("SRS", 3, [], sep="-") == "SRS-001"

    def test_respects_digits(self):
        assert next_uid("SRS", 4, []) == "SRS0001"

    def test_gap_in_existing_uids(self):
        """Should use max+1, not fill gaps."""
        assert next_uid("SRS", 3, ["SRS001", "SRS003"]) == "SRS004"

    def test_ignores_non_matching_uids(self):
        """UIDs from other prefixes are ignored."""
        assert next_uid("SRS", 3, ["OTHER001", "SRS001"]) == "SRS002"

    def test_mixed_case_uids(self):
        """1f: next_uid with mixed-case existing UIDs (IGNORECASE)."""
        assert next_uid("SRS", 3, ["srs001", "SRS002"]) == "SRS003"


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

    def test_link_order_invariance(self):
        """Hash should be the same regardless of link order (links are sorted)."""
        data1 = {"text": "test", "links": ["SYS002", "SYS001"], "type": "requirement"}
        data2 = {"text": "test", "links": ["SYS001", "SYS002"], "type": "requirement"}
        assert compute_content_hash(data1) == compute_content_hash(data2)

    def test_empty_vs_missing_links(self):
        """Empty links list and missing links should produce same hash."""
        data1 = {"text": "test", "links": [], "type": "requirement"}
        data2 = {"text": "test", "type": "requirement"}
        assert compute_content_hash(data1) == compute_content_hash(data2)

    def test_header_none_vs_empty_string(self):
        """1e: header=None and header='' produce the same hash."""
        data_none = {"text": "test", "header": None, "type": "requirement"}
        data_empty = {"text": "test", "header": "", "type": "requirement"}
        assert compute_content_hash(data_none) == compute_content_hash(data_empty)


class TestRoundTrip:
    """Tests for write_item -> read_item round-trip consistency."""

    def test_block_scalar_multiline(self, tmp_path):
        """Write multiline text, read back, assert exact match and | in raw file."""
        item_path = tmp_path / "SRS001.yml"
        multiline_text = "line1\nline2\nline3"
        write_item({"active": True, "text": multiline_text, "type": "requirement"}, item_path)
        raw = item_path.read_text()
        assert "|" in raw
        data = read_item(item_path, "SRS")
        assert data["text"] == multiline_text

    def test_preserves_all_fields(self, tmp_path):
        """Write item with every field populated, read back, assert all match."""
        # Hash must be >= 20 chars and contain only URL-safe base64 chars
        link_hash = "abcdefghijklmnopqrstuvwxyz"
        reviewed_hash = "reviewhash_0123456789abcdef"
        item_path = tmp_path / "SRS001.yml"
        item_data = {
            "active": True,
            "text": "Full item text",
            "type": "heading",
            "header": "Section A",
            "links": ["SYS001", "SYS002"],
            "link_hashes": {"SYS001": link_hash},
            "reviewed": reviewed_hash,
            "derived": True,
        }
        write_item(item_data, item_path)
        data = read_item(item_path, "SRS")
        assert data["uid"] == "SRS001"
        assert data["text"] == "Full item text"
        assert data["type"] == "heading"
        assert data["header"] == "Section A"
        assert data["active"] is True
        assert "SYS001" in data["links"]
        assert "SYS002" in data["links"]
        assert data["link_hashes"]["SYS001"] == link_hash
        assert data["reviewed"] == reviewed_hash
        assert data["derived"] is True

    def test_empty_links_and_no_header(self, tmp_path):
        """Round-trip with links=[] and header=''."""
        item_path = tmp_path / "SRS001.yml"
        write_item({"active": True, "text": "Simple", "links": [], "header": ""}, item_path)
        data = read_item(item_path, "SRS")
        assert data["text"] == "Simple"
        assert data["links"] == []
        assert data["header"] is None
