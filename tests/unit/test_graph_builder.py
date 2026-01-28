"""Tests for jamb.storage.graph_builder module."""

import pytest
import yaml

from jamb.storage.document_config import DocumentConfig
from jamb.storage.document_dag import DocumentDAG
from jamb.storage.graph_builder import build_traceability_graph


@pytest.fixture
def tmp_dag(tmp_path):
    """Create a DocumentDAG with two documents and several items on disk."""
    # Create SRS document
    srs_dir = tmp_path / "srs"
    srs_dir.mkdir()
    for uid, text in [("SRS001", "Req 1"), ("SRS002", "Req 2"), ("SRS003", "Req 3")]:
        (srs_dir / f"{uid}.yml").write_text(
            yaml.dump(
                {
                    "active": True,
                    "type": "requirement",
                    "text": text,
                    "header": "",
                    "links": [],
                    "reviewed": None,
                }
            )
        )

    # Create DRAFT document
    draft_dir = tmp_path / "draft"
    draft_dir.mkdir()
    (draft_dir / "DRAFT001.yml").write_text(
        yaml.dump(
            {
                "active": True,
                "type": "requirement",
                "text": "Draft req",
                "header": "",
                "links": [],
                "reviewed": None,
            }
        )
    )

    dag = DocumentDAG()
    dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=[], digits=3)
    dag.documents["DRAFT"] = DocumentConfig(prefix="DRAFT", parents=[], digits=3)
    dag.document_paths["SRS"] = srs_dir
    dag.document_paths["DRAFT"] = draft_dir

    return dag


class TestExcludePatternsFilterDocuments:
    """Tests for exclude_patterns filtering documents by prefix."""

    def test_exclude_patterns_filters_documents(self, tmp_dag):
        """Pattern 'DRAFT*' excludes document with prefix DRAFT."""
        graph = build_traceability_graph(tmp_dag, exclude_patterns=["DRAFT*"])

        # DRAFT document items should be excluded
        uids = list(graph.items.keys())
        assert "DRAFT001" not in uids
        # SRS items should remain
        assert "SRS001" in uids
        assert "SRS002" in uids
        assert "SRS003" in uids

    def test_exclude_patterns_filters_items(self, tmp_dag):
        """Pattern 'SRS00[23]' excludes SRS002 and SRS003 but keeps SRS001."""
        graph = build_traceability_graph(tmp_dag, exclude_patterns=["SRS00[23]"])

        uids = list(graph.items.keys())
        assert "SRS001" in uids
        assert "SRS002" not in uids
        assert "SRS003" not in uids
        # DRAFT still included
        assert "DRAFT001" in uids

    def test_exclude_patterns_none_includes_all(self, tmp_dag):
        """exclude_patterns=None includes everything (backward compatible)."""
        graph = build_traceability_graph(tmp_dag, exclude_patterns=None)

        uids = list(graph.items.keys())
        assert "SRS001" in uids
        assert "SRS002" in uids
        assert "SRS003" in uids
        assert "DRAFT001" in uids

    def test_exclude_patterns_empty_list_includes_all(self, tmp_dag):
        """Empty list includes everything."""
        graph = build_traceability_graph(tmp_dag, exclude_patterns=[])

        uids = list(graph.items.keys())
        assert "SRS001" in uids
        assert "SRS002" in uids
        assert "SRS003" in uids
        assert "DRAFT001" in uids
