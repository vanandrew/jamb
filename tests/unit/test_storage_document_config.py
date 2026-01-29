"""Tests for jamb.storage.document_config module."""

import pytest
import yaml

from jamb.storage.document_config import (
    DocumentConfig,
    load_document_config,
    save_document_config,
)


class TestDocumentConfig:
    def test_default_values(self):
        config = DocumentConfig(prefix="SRS")
        assert config.prefix == "SRS"
        assert config.parents == []
        assert config.digits == 3
        assert config.sep == ""

    def test_with_parents(self):
        config = DocumentConfig(prefix="SRS", parents=["SYS", "RC"])
        assert config.parents == ["SYS", "RC"]


class TestLoadDocumentConfig:
    def test_loads_jamb_config(self, tmp_path):
        config_path = tmp_path / ".jamb.yml"
        config_path.write_text("settings:\n  prefix: SRS\n  parents:\n    - SYS\n  digits: 3\n  sep: ''\n")
        config = load_document_config(config_path)
        assert config.prefix == "SRS"
        assert config.parents == ["SYS"]
        assert config.digits == 3

    def test_loads_root_document(self, tmp_path):
        config_path = tmp_path / ".jamb.yml"
        config_path.write_text("settings:\n  prefix: PRJ\n  digits: 3\n")
        config = load_document_config(config_path)
        assert config.parents == []

    def test_raises_on_missing_settings(self, tmp_path):
        config_path = tmp_path / ".jamb.yml"
        config_path.write_text("foo: bar\n")
        with pytest.raises(ValueError, match="Invalid config"):
            load_document_config(config_path)

    def test_raises_on_missing_prefix(self, tmp_path):
        config_path = tmp_path / ".jamb.yml"
        config_path.write_text("settings:\n  digits: 3\n")
        with pytest.raises(ValueError, match="missing 'prefix'"):
            load_document_config(config_path)


class TestSaveDocumentConfig:
    def test_saves_config(self, tmp_path):
        config = DocumentConfig(prefix="SRS", parents=["SYS"], digits=3, sep="")
        doc_dir = tmp_path / "srs"
        save_document_config(config, doc_dir)
        assert (doc_dir / ".jamb.yml").exists()
        data = yaml.safe_load((doc_dir / ".jamb.yml").read_text())
        assert data["settings"]["prefix"] == "SRS"
        assert data["settings"]["parents"] == ["SYS"]

    def test_saves_root_config(self, tmp_path):
        config = DocumentConfig(prefix="PRJ")
        doc_dir = tmp_path / "prj"
        save_document_config(config, doc_dir)
        data = yaml.safe_load((doc_dir / ".jamb.yml").read_text())
        assert "parents" not in data["settings"]

    def test_creates_directory(self, tmp_path):
        config = DocumentConfig(prefix="SRS")
        doc_dir = tmp_path / "nested" / "srs"
        save_document_config(config, doc_dir)
        assert doc_dir.exists()

    def test_roundtrip(self, tmp_path):
        original = DocumentConfig(prefix="SRS", parents=["SYS", "RC"], digits=4, sep="-")
        doc_dir = tmp_path / "srs"
        save_document_config(original, doc_dir)
        loaded = load_document_config(doc_dir / ".jamb.yml")
        assert loaded.prefix == original.prefix
        assert loaded.parents == original.parents
        assert loaded.digits == original.digits
