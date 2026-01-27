"""Tests for jamb.storage.discovery module."""

from pathlib import Path

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
