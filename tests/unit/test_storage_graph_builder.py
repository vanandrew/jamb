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
        (sys_dir / ".jamb.yml").write_text(yaml.dump({"settings": {"prefix": "SYS", "digits": 3}}))
        (sys_dir / "SYS001.yml").write_text("active: true\ntext: System requirement\n")
        dag.documents["SYS"] = DocumentConfig(prefix="SYS")
        dag.document_paths["SYS"] = sys_dir

        # Create SRS document
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text(yaml.dump({"settings": {"prefix": "SRS", "parents": ["SYS"], "digits": 3}}))
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: Software requirement\nlinks:\n  - SYS001\n")
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

    def test_empty_document_directory(self, tmp_path):
        """Document directory with no item files produces empty items."""
        dag = DocumentDAG()
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        dag.documents["SRS"] = DocumentConfig(prefix="SRS")
        dag.document_paths["SRS"] = srs_dir

        graph = build_traceability_graph(dag)
        assert graph.get_items_by_document("SRS") == []
        assert graph.document_parents["SRS"] == []

    def test_derived_flag_preserved(self, tmp_path):
        """Derived flag on items is passed through to the graph."""
        dag = DocumentDAG()
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: Derived\nderived: true\n")
        dag.documents["SRS"] = DocumentConfig(prefix="SRS")
        dag.document_paths["SRS"] = srs_dir

        graph = build_traceability_graph(dag)
        assert graph.items["SRS001"].derived is True

    def test_nonexistent_prefix_filter_ignored(self, tmp_path):
        """Filtering by a prefix that doesn't exist just returns no items for it."""
        dag = self._setup_docs(tmp_path)
        graph = build_traceability_graph(dag, document_prefixes=["NONEXIST"])
        assert len(graph.items) == 0

    def test_document_with_no_path(self):
        """Document registered in DAG but with no path on disk."""
        dag = DocumentDAG()
        dag.documents["SRS"] = DocumentConfig(prefix="SRS")
        # No path set: dag.document_paths["SRS"] is absent

        graph = build_traceability_graph(dag)
        # Document parents are set, but no items loaded
        assert graph.document_parents["SRS"] == []
        assert graph.get_items_by_document("SRS") == []

    def test_separator_based_document(self, tmp_path):
        """7a: Document with sep='-' loads items correctly."""
        dag = DocumentDAG()
        api_dir = tmp_path / "api"
        api_dir.mkdir()
        (api_dir / "API-001.yml").write_text("active: true\ntext: API endpoint\n")
        (api_dir / "API-002.yml").write_text("active: true\ntext: API auth\n")
        dag.documents["API"] = DocumentConfig(prefix="API", sep="-")
        dag.document_paths["API"] = api_dir

        graph = build_traceability_graph(dag)
        assert "API-001" in graph.items
        assert "API-002" in graph.items
        assert graph.items["API-001"].text == "API endpoint"

    def test_mixed_valid_invalid_prefix_filter(self, tmp_path):
        """Valid prefix loaded, invalid prefixes silently skipped, no error."""
        dag = self._setup_docs(tmp_path)
        graph = build_traceability_graph(dag, document_prefixes=["SYS", "INVALID1", "INVALID2"])
        # Only SYS items should be loaded (INVALID prefixes skipped)
        assert "SYS001" in graph.items
        assert "SRS001" not in graph.items
        # Document parents for SYS should be set
        assert "SYS" in graph.document_parents
