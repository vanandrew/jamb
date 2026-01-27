"""Tests for jamb.storage.graph_builder module."""

import yaml

from jamb.storage.document_config import DocumentConfig
from jamb.storage.document_dag import DocumentDAG
from jamb.storage.graph_builder import build_traceability_graph


class TestBuildTraceabilityGraph:
    def _setup_docs(self, tmp_path):
        dag = DocumentDAG()

        # Create SYS document
        sys_dir = tmp_path / "sys"
        sys_dir.mkdir()
        (sys_dir / ".jamb.yml").write_text(
            yaml.dump({"settings": {"prefix": "SYS", "digits": 3}})
        )
        (sys_dir / "SYS001.yml").write_text("active: true\ntext: System requirement\n")
        dag.documents["SYS"] = DocumentConfig(prefix="SYS")
        dag.document_paths["SYS"] = sys_dir

        # Create SRS document
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text(
            yaml.dump({"settings": {"prefix": "SRS", "parents": ["SYS"], "digits": 3}})
        )
        (srs_dir / "SRS001.yml").write_text(
            "active: true\ntext: Software requirement\nlinks:\n  - SYS001\n"
        )
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=["SYS"])
        dag.document_paths["SRS"] = srs_dir

        return dag

    def test_builds_graph(self, tmp_path):
        dag = self._setup_docs(tmp_path)
        graph = build_traceability_graph(dag)
        assert "SYS001" in graph.items
        assert "SRS001" in graph.items

    def test_sets_document_parents(self, tmp_path):
        dag = self._setup_docs(tmp_path)
        graph = build_traceability_graph(dag)
        assert graph.document_parents["SRS"] == ["SYS"]
        assert graph.document_parents["SYS"] == []

    def test_filters_by_prefix(self, tmp_path):
        dag = self._setup_docs(tmp_path)
        graph = build_traceability_graph(dag, document_prefixes=["SRS"])
        assert "SRS001" in graph.items
        assert "SYS001" not in graph.items

    def test_excludes_inactive(self, tmp_path):
        dag = DocumentDAG()
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: Active\n")
        (srs_dir / "SRS002.yml").write_text("active: false\ntext: Inactive\n")
        dag.documents["SRS"] = DocumentConfig(prefix="SRS")
        dag.document_paths["SRS"] = srs_dir

        graph = build_traceability_graph(dag)
        assert "SRS001" in graph.items
        assert "SRS002" not in graph.items

    def test_includes_inactive(self, tmp_path):
        dag = DocumentDAG()
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: Active\n")
        (srs_dir / "SRS002.yml").write_text("active: false\ntext: Inactive\n")
        dag.documents["SRS"] = DocumentConfig(prefix="SRS")
        dag.document_paths["SRS"] = srs_dir

        graph = build_traceability_graph(dag, include_inactive=True)
        assert "SRS001" in graph.items
        assert "SRS002" in graph.items
