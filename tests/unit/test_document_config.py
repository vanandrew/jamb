"""Tests for jamb.storage.document_config module."""

import pytest
import yaml

from jamb.storage.document_config import (
    DocumentConfig,
    load_document_config,
    save_document_config,
)


class TestLoadDocumentConfig:
    def test_loads_basic_config(self, tmp_path):
        config_file = tmp_path / ".jamb.yml"
        config_file.write_text("settings:\n  prefix: SRS\n  digits: 3\n")
        config = load_document_config(config_file)
        assert config.prefix == "SRS"
        assert config.digits == 3
        assert config.parents == []
        assert config.sep == ""

    def test_loads_with_parents_list(self, tmp_path):
        config_file = tmp_path / ".jamb.yml"
        config_file.write_text("settings:\n  prefix: SRS\n  parents:\n    - SYS\n    - UN\n")
        config = load_document_config(config_file)
        assert config.parents == ["SYS", "UN"]

    def test_loads_with_single_parent_string(self, tmp_path):
        config_file = tmp_path / ".jamb.yml"
        config_file.write_text("settings:\n  prefix: SRS\n  parents: SYS\n")
        config = load_document_config(config_file)
        assert config.parents == ["SYS"]

    def test_loads_with_null_parents(self, tmp_path):
        config_file = tmp_path / ".jamb.yml"
        config_file.write_text("settings:\n  prefix: SRS\n  parents: null\n")
        config = load_document_config(config_file)
        assert config.parents == []

    def test_loads_with_separator(self, tmp_path):
        config_file = tmp_path / ".jamb.yml"
        config_file.write_text("settings:\n  prefix: API\n  sep: '-'\n")
        config = load_document_config(config_file)
        assert config.sep == "-"

    def test_raises_on_empty_file(self, tmp_path):
        config_file = tmp_path / ".jamb.yml"
        config_file.write_text("")
        with pytest.raises(ValueError, match="Invalid config file"):
            load_document_config(config_file)

    def test_raises_on_missing_settings(self, tmp_path):
        config_file = tmp_path / ".jamb.yml"
        config_file.write_text("other_key: value\n")
        with pytest.raises(ValueError, match="Invalid config file"):
            load_document_config(config_file)

    def test_raises_on_missing_prefix(self, tmp_path):
        config_file = tmp_path / ".jamb.yml"
        config_file.write_text("settings:\n  digits: 3\n")
        with pytest.raises(ValueError, match="missing 'prefix'"):
            load_document_config(config_file)

    def test_raises_on_empty_prefix(self, tmp_path):
        config_file = tmp_path / ".jamb.yml"
        config_file.write_text("settings:\n  prefix: ''\n")
        with pytest.raises(ValueError, match="missing 'prefix'"):
            load_document_config(config_file)

    def test_defaults_digits_to_3(self, tmp_path):
        config_file = tmp_path / ".jamb.yml"
        config_file.write_text("settings:\n  prefix: SRS\n")
        config = load_document_config(config_file)
        assert config.digits == 3

    def test_defaults_sep_to_empty(self, tmp_path):
        config_file = tmp_path / ".jamb.yml"
        config_file.write_text("settings:\n  prefix: SRS\n")
        config = load_document_config(config_file)
        assert config.sep == ""


class TestSaveDocumentConfig:
    def test_saves_basic_config(self, tmp_path):
        config = DocumentConfig(prefix="SRS")
        save_document_config(config, tmp_path)
        config_file = tmp_path / ".jamb.yml"
        assert config_file.exists()
        data = yaml.safe_load(config_file.read_text())
        assert data["settings"]["prefix"] == "SRS"
        assert data["settings"]["digits"] == 3

    def test_saves_with_parents(self, tmp_path):
        config = DocumentConfig(prefix="SRS", parents=["SYS", "UN"])
        save_document_config(config, tmp_path)
        data = yaml.safe_load((tmp_path / ".jamb.yml").read_text())
        assert data["settings"]["parents"] == ["SYS", "UN"]

    def test_omits_parents_when_empty(self, tmp_path):
        config = DocumentConfig(prefix="SRS")
        save_document_config(config, tmp_path)
        data = yaml.safe_load((tmp_path / ".jamb.yml").read_text())
        assert "parents" not in data["settings"]

    def test_creates_directory(self, tmp_path):
        new_dir = tmp_path / "nested" / "dir"
        config = DocumentConfig(prefix="SRS")
        save_document_config(config, new_dir)
        assert (new_dir / ".jamb.yml").exists()

    def test_round_trip(self, tmp_path):
        original = DocumentConfig(prefix="API", parents=["SYS"], digits=4, sep="-")
        save_document_config(original, tmp_path)
        loaded = load_document_config(tmp_path / ".jamb.yml")
        assert loaded.prefix == original.prefix
        assert loaded.parents == original.parents
        assert loaded.digits == original.digits
        assert loaded.sep == original.sep

    def test_overwrites_existing(self, tmp_path):
        config1 = DocumentConfig(prefix="OLD")
        save_document_config(config1, tmp_path)
        config2 = DocumentConfig(prefix="NEW")
        save_document_config(config2, tmp_path)
        loaded = load_document_config(tmp_path / ".jamb.yml")
        assert loaded.prefix == "NEW"
