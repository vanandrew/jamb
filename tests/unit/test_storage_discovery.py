"""Tests for jamb.storage.discovery module."""

from pathlib import Path

import pytest
import yaml

from jamb.storage.discovery import discover_documents


class TestDiscoverDocuments:
    def _make_doc(self, base: Path, name: str, prefix: str, parents=None):
        doc_dir = base / name
        doc_dir.mkdir(parents=True, exist_ok=True)
        settings = {"prefix": prefix, "digits": 3, "sep": ""}
        if parents:
            settings["parents"] = parents
        (doc_dir / ".jamb.yml").write_text(yaml.dump({"settings": settings}))
        return doc_dir

    def test_discovers_documents(self, tmp_path):
        self._make_doc(tmp_path, "prj", "PRJ")
        self._make_doc(tmp_path, "srs", "SRS", parents=["PRJ"])

        dag = discover_documents(tmp_path)
        assert "PRJ" in dag.documents
        assert "SRS" in dag.documents
        assert dag.documents["SRS"].parents == ["PRJ"]

    def test_empty_directory(self, tmp_path):
        dag = discover_documents(tmp_path)
        assert len(dag.documents) == 0

    def test_stores_paths(self, tmp_path):
        doc_dir = self._make_doc(tmp_path, "srs", "SRS")
        dag = discover_documents(tmp_path)
        assert dag.document_paths["SRS"] == doc_dir

    def test_skips_invalid_yaml(self, tmp_path):
        """Invalid .jamb.yml file is silently skipped."""
        bad_dir = tmp_path / "bad"
        bad_dir.mkdir()
        (bad_dir / ".jamb.yml").write_text(": invalid: yaml: {{}")
        dag = discover_documents(tmp_path)
        assert len(dag.documents) == 0

    def test_skips_config_missing_prefix(self, tmp_path):
        """Config file without prefix is silently skipped."""
        bad_dir = tmp_path / "no_prefix"
        bad_dir.mkdir()
        (bad_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n")
        dag = discover_documents(tmp_path)
        assert len(dag.documents) == 0

    def test_nested_directories(self, tmp_path):
        """Discovers documents nested several levels deep."""
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        settings = {"prefix": "DEEP", "digits": 3, "sep": ""}
        (nested / ".jamb.yml").write_text(yaml.dump({"settings": settings}))

        dag = discover_documents(tmp_path)
        assert "DEEP" in dag.documents
        assert dag.document_paths["DEEP"] == nested

    def test_raises_on_nonexistent_root(self, tmp_path):
        """Non-existent root directory raises FileNotFoundError."""
        import pytest

        with pytest.raises(FileNotFoundError):
            discover_documents(tmp_path / "nonexistent")

    def test_multiple_documents_at_same_level(self, tmp_path):
        """Multiple documents at the same directory level."""
        self._make_doc(tmp_path, "srs", "SRS")
        self._make_doc(tmp_path, "sys", "SYS")
        self._make_doc(tmp_path, "un", "UN")

        dag = discover_documents(tmp_path)
        assert len(dag.documents) == 3
        assert all(p in dag.documents for p in ["SRS", "SYS", "UN"])

    def test_duplicate_prefix_raises_error(self, tmp_path):
        """8a: Duplicate prefix in two dirs raises ValueError."""
        self._make_doc(tmp_path, "aaa_srs", "SRS")
        self._make_doc(tmp_path, "zzz_srs", "SRS")

        with pytest.raises(ValueError, match="Duplicate document prefix 'SRS'"):
            discover_documents(tmp_path)

    def test_symlink_to_document_directory(self, tmp_path):
        """Symlinked directory with .jamb.yml is discovered."""
        real_dir = tmp_path / "real_srs"
        self._make_doc(tmp_path, "real_srs", "SRS")
        link_dir = tmp_path / "linked_srs"
        link_dir.symlink_to(real_dir)

        dag = discover_documents(tmp_path)
        assert "SRS" in dag.documents

    def test_deeply_nested_five_levels(self, tmp_path):
        """Document at a/b/c/d/e/.jamb.yml is found."""
        deep = tmp_path / "a" / "b" / "c" / "d" / "e"
        deep.mkdir(parents=True)
        settings = {"prefix": "DEEP5", "digits": 3, "sep": ""}
        (deep / ".jamb.yml").write_text(yaml.dump({"settings": settings}))

        dag = discover_documents(tmp_path)
        assert "DEEP5" in dag.documents
        assert dag.document_paths["DEEP5"] == deep

    def test_root_is_file_raises(self, tmp_path):
        """Passing a file path as root raises FileNotFoundError."""
        import pytest

        f = tmp_path / "somefile.txt"
        f.write_text("hello")

        with pytest.raises(FileNotFoundError):
            discover_documents(f)

    def test_config_load_raises_unexpected_exception_propagates(self, tmp_path, monkeypatch):
        """Unexpected exceptions (e.g. RuntimeError) propagate instead of
        being silently swallowed."""
        doc_dir = tmp_path / "bad"
        doc_dir.mkdir()
        (doc_dir / ".jamb.yml").write_text(yaml.dump({"settings": {"prefix": "BAD", "digits": 3}}))

        from jamb.storage import discovery

        def _explode(path):
            raise RuntimeError("unexpected failure")

        monkeypatch.setattr(discovery, "load_document_config", _explode)

        with pytest.raises(RuntimeError, match="unexpected failure"):
            discover_documents(tmp_path)

    def test_empty_jamb_yml_skipped(self, tmp_path):
        """Empty .jamb.yml file is silently skipped."""
        doc_dir = tmp_path / "empty"
        doc_dir.mkdir()
        (doc_dir / ".jamb.yml").write_text("")

        dag = discover_documents(tmp_path)
        assert len(dag.documents) == 0

    def test_unreadable_root_raises_permission_error(self, tmp_path):
        """Unreadable root directory raises PermissionError."""
        import os

        from jamb.storage.discovery import _find_config_files

        # Create a directory and make it unreadable
        unreadable_dir = tmp_path / "unreadable"
        unreadable_dir.mkdir()

        # Remove read permission
        original_mode = unreadable_dir.stat().st_mode
        try:
            os.chmod(unreadable_dir, 0o000)

            # _find_config_files should raise PermissionError
            with pytest.raises(PermissionError, match="Cannot read directory"):
                _find_config_files(unreadable_dir)
        finally:
            # Restore permissions for cleanup
            os.chmod(unreadable_dir, original_mode)
