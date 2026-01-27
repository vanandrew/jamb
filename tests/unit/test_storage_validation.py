"""Tests for jamb.storage.validation module."""

from pathlib import Path

from jamb.core.models import Item, TraceabilityGraph
from jamb.storage.document_config import DocumentConfig
from jamb.storage.document_dag import DocumentDAG
from jamb.storage.validation import ValidationIssue, validate


class TestValidationIssue:
    def test_str_format(self):
        issue = ValidationIssue("error", "SRS001", "SRS", "links to non-existent item")
        assert "[ERROR]" in str(issue)
        assert "SRS001" in str(issue)

    def test_str_without_uid(self):
        issue = ValidationIssue("warning", None, "SRS", "has issues")
        assert "[WARNING]" in str(issue)
        assert "SRS" in str(issue)


class TestValidate:
    def _make_dag_and_graph(self):
        dag = DocumentDAG()
        dag.documents["SYS"] = DocumentConfig(prefix="SYS")
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=["SYS"])
        dag.document_paths["SYS"] = Path("/tmp/sys")
        dag.document_paths["SRS"] = Path("/tmp/srs")

        graph = TraceabilityGraph()
        sys_item = Item(
            uid="SYS001", text="System req", document_prefix="SYS", reviewed="hash1"
        )
        srs_item = Item(
            uid="SRS001",
            text="Software req",
            document_prefix="SRS",
            links=["SYS001"],
            reviewed="hash2",
        )
        graph.add_item(sys_item)
        graph.add_item(srs_item)
        graph.set_document_parents("SYS", [])
        graph.set_document_parents("SRS", ["SYS"])
        return dag, graph

    def test_valid_tree_passes(self):
        dag, graph = self._make_dag_and_graph()
        issues = validate(dag, graph, check_suspect=False)
        errors = [i for i in issues if i.level == "error"]
        assert len(errors) == 0

    def test_detects_broken_links(self):
        dag, graph = self._make_dag_and_graph()
        # Add item with broken link
        bad_item = Item(
            uid="SRS002",
            text="Bad",
            document_prefix="SRS",
            links=["NONEXIST"],
            reviewed="hash",
        )
        graph.add_item(bad_item)
        issues = validate(
            dag, graph, check_suspect=False, check_review=False, check_children=False
        )
        errors = [i for i in issues if i.level == "error"]
        assert any("non-existent" in str(i) for i in errors)

    def test_detects_cycles(self):
        dag = DocumentDAG()
        dag.documents["A"] = DocumentConfig(prefix="A", parents=["B"])
        dag.documents["B"] = DocumentConfig(prefix="B", parents=["A"])
        graph = TraceabilityGraph()
        issues = validate(
            dag,
            graph,
            check_links=False,
            check_levels=False,
            check_suspect=False,
            check_review=False,
            check_children=False,
        )
        assert any("Cycle" in str(i) for i in issues)

    def test_skip_prefixes(self):
        dag, graph = self._make_dag_and_graph()
        # Add bad item in SRS
        bad_item = Item(
            uid="SRS002", text="Bad", document_prefix="SRS", links=["NONEXIST"]
        )
        graph.add_item(bad_item)
        issues = validate(
            dag,
            graph,
            skip_prefixes=["SRS"],
            check_suspect=False,
            check_review=False,
            check_children=False,
        )
        errors = [i for i in issues if i.level == "error"]
        assert len(errors) == 0

    def test_check_review_status(self):
        dag = DocumentDAG()
        dag.documents["SRS"] = DocumentConfig(prefix="SRS")
        graph = TraceabilityGraph()
        item = Item(uid="SRS001", text="Test", document_prefix="SRS")
        graph.add_item(item)
        graph.set_document_parents("SRS", [])
        issues = validate(
            dag,
            graph,
            check_links=False,
            check_levels=False,
            check_suspect=False,
            check_children=False,
        )
        assert any("not been reviewed" in str(i) for i in issues)

    def test_check_children(self):
        dag = DocumentDAG()
        dag.documents["SYS"] = DocumentConfig(prefix="SYS")
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=["SYS"])
        graph = TraceabilityGraph()
        # SYS item with no children linking to it
        sys_item = Item(
            uid="SYS001", text="System", document_prefix="SYS", reviewed="hash"
        )
        graph.add_item(sys_item)
        graph.set_document_parents("SYS", [])
        graph.set_document_parents("SRS", ["SYS"])
        issues = validate(
            dag,
            graph,
            check_links=False,
            check_levels=False,
            check_suspect=False,
            check_review=False,
        )
        assert any("no children" in str(i) for i in issues)
