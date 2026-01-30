"""Unit tests for jamb.storage.reorder module."""

import yaml

from jamb.storage.reorder import _update_links_in_file, insert_items, reorder_document


def _write_item(doc_path, uid, text="req", links=None):
    """Write a minimal item YAML file."""
    data = {"active": True, "type": "requirement", "text": text}
    if links:
        data["links"] = links
    path = doc_path / f"{uid}.yml"
    with open(path, "w") as f:
        yaml.safe_dump(data, f)


def _make_doc(tmp_path, name="srs"):
    """Create a document directory with .jamb.yml."""
    doc_path = tmp_path / name
    doc_path.mkdir()
    (doc_path / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n")
    return doc_path


class TestReorderDocument:
    """Tests for reorder_document function."""

    def test_no_items(self, tmp_path):
        doc_path = _make_doc(tmp_path)
        stats = reorder_document(doc_path, "SRS", 3, "", {"SRS": doc_path})
        assert stats["renamed"] == 0
        assert stats["unchanged"] == 0
        assert stats["rename_map"] == {}

    def test_already_sequential(self, tmp_path):
        doc_path = _make_doc(tmp_path)
        _write_item(doc_path, "SRS001")
        _write_item(doc_path, "SRS002")
        _write_item(doc_path, "SRS003")

        stats = reorder_document(doc_path, "SRS", 3, "", {"SRS": doc_path})
        assert stats["renamed"] == 0
        assert stats["unchanged"] == 3
        assert stats["rename_map"] == {}
        assert (doc_path / "SRS001.yml").exists()
        assert (doc_path / "SRS002.yml").exists()
        assert (doc_path / "SRS003.yml").exists()

    def test_fills_gap(self, tmp_path):
        doc_path = _make_doc(tmp_path)
        _write_item(doc_path, "SRS001", text="first")
        _write_item(doc_path, "SRS003", text="third")

        stats = reorder_document(doc_path, "SRS", 3, "", {"SRS": doc_path})
        assert stats["renamed"] == 1  # SRS003 -> SRS002
        assert stats["unchanged"] == 1  # SRS001 stays
        assert (doc_path / "SRS001.yml").exists()
        assert (doc_path / "SRS002.yml").exists()
        assert not (doc_path / "SRS003.yml").exists()

        # Content is preserved
        data = yaml.safe_load((doc_path / "SRS002.yml").read_text())
        assert data["text"] == "third"

    def test_fills_multiple_gaps(self, tmp_path):
        doc_path = _make_doc(tmp_path)
        _write_item(doc_path, "SRS002")
        _write_item(doc_path, "SRS005")
        _write_item(doc_path, "SRS009")

        stats = reorder_document(doc_path, "SRS", 3, "", {"SRS": doc_path})
        assert stats["renamed"] == 3
        assert (doc_path / "SRS001.yml").exists()
        assert (doc_path / "SRS002.yml").exists()
        assert (doc_path / "SRS003.yml").exists()

    def test_updates_links_in_same_document(self, tmp_path):
        doc_path = _make_doc(tmp_path)
        _write_item(doc_path, "SRS001", links=["SRS003"])
        _write_item(doc_path, "SRS003")

        stats = reorder_document(doc_path, "SRS", 3, "", {"SRS": doc_path})
        assert stats["renamed"] == 1  # SRS003 -> SRS002

        # Check the link in SRS001 was updated
        data = yaml.safe_load((doc_path / "SRS001.yml").read_text())
        assert data["links"] == ["SRS002"]

    def test_updates_links_in_other_documents(self, tmp_path):
        srs_path = _make_doc(tmp_path, "srs")
        other_path = _make_doc(tmp_path, "other")
        (other_path / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: OTH\n  sep: ''\n")

        _write_item(srs_path, "SRS001")
        _write_item(srs_path, "SRS003")
        _write_item(other_path, "OTH001", links=["SRS003"])

        all_docs = {"SRS": srs_path, "OTH": other_path}
        reorder_document(srs_path, "SRS", 3, "", all_docs)

        # OTH001's link should be updated
        data = yaml.safe_load((other_path / "OTH001.yml").read_text())
        assert data["links"] == ["SRS002"]

    def test_updates_hash_links(self, tmp_path):
        doc_path = _make_doc(tmp_path)
        # Write item with hash-style link
        (doc_path / "SRS001.yml").write_text("active: true\ntext: req\nlinks:\n- SRS003: abc123\n")
        _write_item(doc_path, "SRS003")

        reorder_document(doc_path, "SRS", 3, "", {"SRS": doc_path})

        data = yaml.safe_load((doc_path / "SRS001.yml").read_text())
        link_entry = data["links"][0]
        assert isinstance(link_entry, dict)
        assert "SRS002" in link_entry
        assert link_entry["SRS002"] == "abc123"

    def test_separator_in_uid(self, tmp_path):
        doc_path = tmp_path / "doc"
        doc_path.mkdir()
        (doc_path / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: '-'\n")
        _write_item(doc_path, "SRS-002")
        _write_item(doc_path, "SRS-005")

        stats = reorder_document(doc_path, "SRS", 3, "-", {"SRS": doc_path})
        assert stats["renamed"] == 2
        assert (doc_path / "SRS-001.yml").exists()
        assert (doc_path / "SRS-002.yml").exists()

    def test_rejects_broken_links(self, tmp_path):
        """Abort with ValueError when an item links to a non-existent UID."""
        doc_path = _make_doc(tmp_path)
        _write_item(doc_path, "SRS001", links=["NONEXIST"])
        _write_item(doc_path, "SRS002")

        import pytest

        with pytest.raises(ValueError, match="Broken links found.*SRS001 -> NONEXIST"):
            reorder_document(doc_path, "SRS", 3, "", {"SRS": doc_path})

        # No files should have been renamed (aborted before any rename)
        assert (doc_path / "SRS001.yml").exists()
        assert (doc_path / "SRS002.yml").exists()

    def test_swap_positions(self, tmp_path):
        """Two items that swap positions shouldn't collide due to temp files."""
        doc_path = _make_doc(tmp_path)
        _write_item(doc_path, "SRS002", text="was-second")
        _write_item(doc_path, "SRS003", text="was-third")

        reorder_document(doc_path, "SRS", 3, "", {"SRS": doc_path})

        # SRS002 -> SRS001, SRS003 -> SRS002
        data1 = yaml.safe_load((doc_path / "SRS001.yml").read_text())
        data2 = yaml.safe_load((doc_path / "SRS002.yml").read_text())
        assert data1["text"] == "was-second"
        assert data2["text"] == "was-third"

    def test_preserves_custom_attributes(self, tmp_path):
        """Custom attributes in items are preserved after reorder."""
        doc_path = _make_doc(tmp_path)
        # Write item with custom attribute
        (doc_path / "SRS002.yml").write_text("active: true\ntype: requirement\ntext: req\npriority: high\n")
        _write_item(doc_path, "SRS003")

        reorder_document(doc_path, "SRS", 3, "", {"SRS": doc_path})

        data = yaml.safe_load((doc_path / "SRS001.yml").read_text())
        assert data["priority"] == "high"

    def test_single_item_non_sequential(self, tmp_path):
        """5a: Single item at non-sequential UID (SRS005 -> SRS001)."""
        doc_path = _make_doc(tmp_path)
        _write_item(doc_path, "SRS005", text="only item")

        stats = reorder_document(doc_path, "SRS", 3, "", {"SRS": doc_path})
        assert stats["renamed"] == 1
        assert stats["unchanged"] == 0
        assert stats["rename_map"] == {"SRS005": "SRS001"}
        assert (doc_path / "SRS001.yml").exists()
        assert not (doc_path / "SRS005.yml").exists()
        data = yaml.safe_load((doc_path / "SRS001.yml").read_text())
        assert data["text"] == "only item"


class TestUpdateLinksInFile:
    """Tests for _update_links_in_file helper."""

    def test_no_links_key(self, tmp_path):
        """5c: File with no 'links' key — no crash, file unchanged."""
        f = tmp_path / "SRS001.yml"
        f.write_text("active: true\ntext: req\n")
        original = f.read_text()
        _update_links_in_file(f, {"SRS002": "SRS003"})
        assert f.read_text() == original

    def test_empty_links_list(self, tmp_path):
        """5d: File with empty links list — no crash, file unchanged."""
        f = tmp_path / "SRS001.yml"
        f.write_text("active: true\ntext: req\nlinks: []\n")
        original = f.read_text()
        _update_links_in_file(f, {"SRS002": "SRS003"})
        assert f.read_text() == original


class TestInsertItems:
    """Tests for insert_items function."""

    def test_insert_after(self, tmp_path):
        """Insert after SRS002 in [SRS001..SRS003], verify shift."""
        doc_path = _make_doc(tmp_path)
        _write_item(doc_path, "SRS001", text="first")
        _write_item(doc_path, "SRS002", text="second")
        _write_item(doc_path, "SRS003", text="third")

        new_uids = insert_items(doc_path, "SRS", 3, "", position=3, count=1, all_doc_paths={"SRS": doc_path})

        assert new_uids == ["SRS003"]
        # Old SRS003 shifted to SRS004
        assert (doc_path / "SRS004.yml").exists()
        data = yaml.safe_load((doc_path / "SRS004.yml").read_text())
        assert data["text"] == "third"
        # SRS001 and SRS002 unchanged
        assert yaml.safe_load((doc_path / "SRS001.yml").read_text())["text"] == "first"
        assert yaml.safe_load((doc_path / "SRS002.yml").read_text())["text"] == "second"

    def test_insert_before(self, tmp_path):
        """Insert before SRS002, verify SRS002+ shifted."""
        doc_path = _make_doc(tmp_path)
        _write_item(doc_path, "SRS001", text="first")
        _write_item(doc_path, "SRS002", text="second")
        _write_item(doc_path, "SRS003", text="third")

        new_uids = insert_items(doc_path, "SRS", 3, "", position=2, count=1, all_doc_paths={"SRS": doc_path})

        assert new_uids == ["SRS002"]
        # Old SRS002 -> SRS003, old SRS003 -> SRS004
        assert yaml.safe_load((doc_path / "SRS003.yml").read_text())["text"] == "second"
        assert yaml.safe_load((doc_path / "SRS004.yml").read_text())["text"] == "third"
        # SRS001 unchanged
        assert yaml.safe_load((doc_path / "SRS001.yml").read_text())["text"] == "first"

    def test_insert_updates_links(self, tmp_path):
        """Verify cross-document links to shifted UIDs are updated."""
        srs_path = _make_doc(tmp_path, "srs")
        other_path = _make_doc(tmp_path, "other")
        (other_path / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: OTH\n  sep: ''\n")

        _write_item(srs_path, "SRS001", text="first")
        _write_item(srs_path, "SRS002", text="second")
        _write_item(other_path, "OTH001", links=["SRS002"])

        all_docs = {"SRS": srs_path, "OTH": other_path}
        insert_items(srs_path, "SRS", 3, "", position=2, count=1, all_doc_paths=all_docs)

        # OTH001's link to SRS002 should now point to SRS003
        data = yaml.safe_load((other_path / "OTH001.yml").read_text())
        assert data["links"] == ["SRS003"]

    def test_insert_multiple(self, tmp_path):
        """Insert count=2, verify two positions freed and items shifted by 2."""
        doc_path = _make_doc(tmp_path)
        _write_item(doc_path, "SRS001", text="first")
        _write_item(doc_path, "SRS002", text="second")
        _write_item(doc_path, "SRS003", text="third")

        new_uids = insert_items(doc_path, "SRS", 3, "", position=2, count=2, all_doc_paths={"SRS": doc_path})

        assert new_uids == ["SRS002", "SRS003"]
        # Old SRS002 -> SRS004, old SRS003 -> SRS005
        assert yaml.safe_load((doc_path / "SRS004.yml").read_text())["text"] == "second"
        assert yaml.safe_load((doc_path / "SRS005.yml").read_text())["text"] == "third"
        # SRS001 unchanged
        assert yaml.safe_load((doc_path / "SRS001.yml").read_text())["text"] == "first"

    def test_insert_at_position_beyond_count(self, tmp_path):
        """Insert at position > item count: warns and adjusts to max position."""
        import warnings

        doc_path = _make_doc(tmp_path)
        _write_item(doc_path, "SRS001", text="first")
        _write_item(doc_path, "SRS002", text="second")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            new_uids = insert_items(
                doc_path,
                "SRS",
                3,
                "",
                position=10,
                count=1,
                all_doc_paths={"SRS": doc_path},
            )

            # Should emit warning about position adjustment
            assert len(w) == 1
            assert "exceeds item count" in str(w[0].message)

        # Position adjusted to max (len + 1 = 3), so new UID is SRS003
        assert new_uids == ["SRS003"]
        # Existing items unchanged
        assert yaml.safe_load((doc_path / "SRS001.yml").read_text())["text"] == "first"
        assert yaml.safe_load((doc_path / "SRS002.yml").read_text())["text"] == "second"

    def test_insert_at_position_1(self, tmp_path):
        """Insert at position 1 shifts all items."""
        doc_path = _make_doc(tmp_path)
        _write_item(doc_path, "SRS001", text="first")
        _write_item(doc_path, "SRS002", text="second")

        new_uids = insert_items(doc_path, "SRS", 3, "", position=1, count=1, all_doc_paths={"SRS": doc_path})

        assert new_uids == ["SRS001"]
        # Old SRS001 -> SRS002, old SRS002 -> SRS003
        assert yaml.safe_load((doc_path / "SRS002.yml").read_text())["text"] == "first"
        assert yaml.safe_load((doc_path / "SRS003.yml").read_text())["text"] == "second"

    def test_insert_rejects_broken_links(self, tmp_path):
        """Document has a broken link, insert_items raises ValueError."""
        import pytest

        doc_path = _make_doc(tmp_path)
        _write_item(doc_path, "SRS001", links=["NONEXIST"])
        _write_item(doc_path, "SRS002")

        with pytest.raises(ValueError, match="Broken links found.*SRS001 -> NONEXIST"):
            insert_items(
                doc_path,
                "SRS",
                3,
                "",
                position=2,
                count=1,
                all_doc_paths={"SRS": doc_path},
            )

        # No files should have been renamed
        assert (doc_path / "SRS001.yml").exists()
        assert (doc_path / "SRS002.yml").exists()

    def test_insert_items_position_zero_rejected(self, tmp_path):
        """Position 0 raises ValueError."""
        import pytest

        doc_path = _make_doc(tmp_path)
        _write_item(doc_path, "SRS001")

        with pytest.raises(ValueError, match="Position must be >= 1"):
            insert_items(
                doc_path,
                "SRS",
                3,
                "",
                position=0,
                count=1,
                all_doc_paths={"SRS": doc_path},
            )

    def test_insert_items_count_zero_rejected(self, tmp_path):
        """Count 0 raises ValueError."""
        import pytest

        doc_path = _make_doc(tmp_path)
        _write_item(doc_path, "SRS001")

        with pytest.raises(ValueError, match="Count must be >= 1"):
            insert_items(
                doc_path,
                "SRS",
                3,
                "",
                position=1,
                count=0,
                all_doc_paths={"SRS": doc_path},
            )


class TestReorderDigitsValidation:
    """Tests for reorder_document digits validation."""

    def test_digits_less_than_one_raises_value_error(self, tmp_path):
        """Test that digits < 1 raises ValueError."""
        import pytest

        doc_path = _make_doc(tmp_path)
        _write_item(doc_path, "SRS001")

        with pytest.raises(ValueError, match="digits must be >= 1"):
            reorder_document(doc_path, "SRS", 0, "", {"SRS": doc_path})

    def test_digits_negative_raises_value_error(self, tmp_path):
        """Test that negative digits raises ValueError."""
        import pytest

        doc_path = _make_doc(tmp_path)
        _write_item(doc_path, "SRS001")

        with pytest.raises(ValueError, match="digits must be >= 1"):
            reorder_document(doc_path, "SRS", -1, "", {"SRS": doc_path})


class TestCheckBrokenLinksEdgeCases:
    """Edge case tests for _check_broken_links."""

    def test_yaml_parse_error_in_item(self, tmp_path):
        """Test that YAML parsing error is raised with context."""
        import pytest

        doc_path = _make_doc(tmp_path)
        _write_item(doc_path, "SRS001")
        # Write invalid YAML to item file
        (doc_path / "SRS002.yml").write_text("invalid: yaml: [unclosed")

        with pytest.raises(ValueError, match="Failed to parse YAML"):
            reorder_document(doc_path, "SRS", 3, "", {"SRS": doc_path})


class TestReorderEdgeCases:
    """Edge case tests for reorder_document."""

    def test_prefix_with_separator_in_prefix(self, tmp_path):
        """Prefix 'A-B' with sep '-' — separator appears within the prefix itself."""
        doc_path = tmp_path / "doc"
        doc_path.mkdir()
        (doc_path / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: A-B\n  sep: '-'\n")
        # Write items using the composite prefix
        _write_item(doc_path, "A-B-003")
        _write_item(doc_path, "A-B-007")

        stats = reorder_document(doc_path, "A-B", 3, "-", {"A-B": doc_path})
        assert stats["renamed"] == 2
        assert (doc_path / "A-B-001.yml").exists()
        assert (doc_path / "A-B-002.yml").exists()
        assert not (doc_path / "A-B-003.yml").exists()
        assert not (doc_path / "A-B-007.yml").exists()

    def test_reorder_preserves_link_hashes(self, tmp_path):
        """Reorder with items that have link_hashes
        (dict-form links) — hashes preserved."""
        doc_path = _make_doc(tmp_path)
        other_path = _make_doc(tmp_path, "other")
        (other_path / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: OTH\n  sep: ''\n")
        # OTH001 links to SRS003 with a hash
        (other_path / "OTH001.yml").write_text("active: true\ntext: req\nlinks:\n- SRS003: abc123hash\n")
        _write_item(doc_path, "SRS001")
        _write_item(doc_path, "SRS003", text="target")

        all_docs = {"SRS": doc_path, "OTH": other_path}
        reorder_document(doc_path, "SRS", 3, "", all_docs)

        # SRS003 should have become SRS002
        assert (doc_path / "SRS002.yml").exists()
        assert not (doc_path / "SRS003.yml").exists()

        # OTH001's link should now reference SRS002 with hash preserved
        data = yaml.safe_load((other_path / "OTH001.yml").read_text())
        link_entry = data["links"][0]
        assert isinstance(link_entry, dict)
        assert "SRS002" in link_entry
        assert link_entry["SRS002"] == "abc123hash"

    # NOTE: _check_broken_links does NOT perform cycle detection.
    # It only verifies that link targets exist as files on disk.
    # Cycle detection is handled by the validation module
    # (_check_item_link_cycles). Therefore, a "circular link cycle"
    # test is not applicable to the reorder module.

    def test_cleans_temp_on_rename_failure(self, tmp_path):
        """Temp files are cleaned up if rename fails."""
        from unittest.mock import patch

        import pytest

        doc_path = _make_doc(tmp_path)
        _write_item(doc_path, "SRS002", text="first")
        _write_item(doc_path, "SRS003", text="second")

        # Patch rename to fail during the second stage
        original_rename = type(doc_path / "x").rename
        call_count = 0

        def failing_rename(self, target):
            nonlocal call_count
            call_count += 1
            # Fail on the third rename (during temp -> final stage)
            if call_count >= 3:
                raise OSError("Simulated rename failure")
            return original_rename(self, target)

        with patch.object(type(doc_path / "x"), "rename", failing_rename):
            with pytest.raises(OSError, match="Simulated rename failure"):
                reorder_document(doc_path, "SRS", 3, "", {"SRS": doc_path})

        # Temp files should be cleaned up
        temp_files = list(doc_path.glob(".tmp_*.yml"))
        assert temp_files == []

    def test_multiple_broken_links(self, tmp_path):
        """Multiple broken links are reported together."""
        import pytest

        doc_path = _make_doc(tmp_path)
        _write_item(doc_path, "SRS001", links=["MISSING1", "MISSING2"])
        _write_item(doc_path, "SRS002")

        with pytest.raises(ValueError) as exc_info:
            reorder_document(doc_path, "SRS", 3, "", {"SRS": doc_path})

        error_msg = str(exc_info.value)
        assert "MISSING1" in error_msg
        assert "MISSING2" in error_msg
