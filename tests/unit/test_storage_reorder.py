"""Unit tests for jamb.storage.reorder module."""

import yaml

from jamb.storage.reorder import reorder_document


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
    (doc_path / ".jamb.yml").write_text(
        "settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n"
    )
    return doc_path


class TestReorderDocument:
    """Tests for reorder_document function."""

    def test_no_items(self, tmp_path):
        doc_path = _make_doc(tmp_path)
        stats = reorder_document(doc_path, "SRS", 3, "", {"SRS": doc_path})
        assert stats == {"renamed": 0, "unchanged": 0}

    def test_already_sequential(self, tmp_path):
        doc_path = _make_doc(tmp_path)
        _write_item(doc_path, "SRS001")
        _write_item(doc_path, "SRS002")
        _write_item(doc_path, "SRS003")

        stats = reorder_document(doc_path, "SRS", 3, "", {"SRS": doc_path})
        assert stats == {"renamed": 0, "unchanged": 3}
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
        (other_path / ".jamb.yml").write_text(
            "settings:\n  digits: 3\n  prefix: OTH\n  sep: ''\n"
        )

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
        (doc_path / "SRS001.yml").write_text(
            "active: true\ntext: req\nlinks:\n- SRS003: abc123\n"
        )
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
        (doc_path / ".jamb.yml").write_text(
            "settings:\n  digits: 3\n  prefix: SRS\n  sep: '-'\n"
        )
        _write_item(doc_path, "SRS-002")
        _write_item(doc_path, "SRS-005")

        stats = reorder_document(doc_path, "SRS", 3, "-", {"SRS": doc_path})
        assert stats["renamed"] == 2
        assert (doc_path / "SRS-001.yml").exists()
        assert (doc_path / "SRS-002.yml").exists()

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
