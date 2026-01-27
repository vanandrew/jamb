"""Tests for jamb.storage.validation module."""

from pathlib import Path

from jamb.core.models import Item, TraceabilityGraph
from jamb.storage.document_config import DocumentConfig
from jamb.storage.document_dag import DocumentDAG
from jamb.storage.items import compute_content_hash
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
            check_suspect=False,
            check_review=False,
        )
        assert any("no children" in str(i) for i in issues)

    def test_review_detects_content_change(self):
        dag = DocumentDAG()
        dag.documents["SRS"] = DocumentConfig(prefix="SRS")
        graph = TraceabilityGraph()
        item = Item(
            uid="SRS001",
            text="Original text",
            document_prefix="SRS",
            reviewed="stale_hash",
        )
        graph.add_item(item)
        graph.set_document_parents("SRS", [])
        issues = validate(
            dag,
            graph,
            check_links=False,
            check_suspect=False,
            check_children=False,
        )
        assert any("modified since last review" in str(i) for i in issues)

    def test_review_passes_when_hash_matches(self):
        dag = DocumentDAG()
        dag.documents["SRS"] = DocumentConfig(prefix="SRS")
        graph = TraceabilityGraph()
        item_data = {
            "text": "Some text",
            "header": None,
            "links": [],
            "type": "requirement",
        }
        correct_hash = compute_content_hash(item_data)
        item = Item(
            uid="SRS001",
            text="Some text",
            document_prefix="SRS",
            reviewed=correct_hash,
        )
        graph.add_item(item)
        graph.set_document_parents("SRS", [])
        issues = validate(
            dag,
            graph,
            check_links=False,
            check_suspect=False,
            check_children=False,
        )
        review_issues = [i for i in issues if "review" in str(i).lower()]
        assert len(review_issues) == 0

    def test_link_to_inactive_item_is_error(self):
        dag = DocumentDAG()
        dag.documents["SYS"] = DocumentConfig(prefix="SYS")
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=["SYS"])
        graph = TraceabilityGraph()
        sys_item = Item(
            uid="SYS001", text="System req", document_prefix="SYS", active=False
        )
        srs_item = Item(
            uid="SRS001",
            text="Software req",
            document_prefix="SRS",
            links=["SYS001"],
            reviewed="hash",
        )
        graph.add_item(sys_item)
        graph.add_item(srs_item)
        graph.set_document_parents("SYS", [])
        graph.set_document_parents("SRS", ["SYS"])
        issues = validate(
            dag,
            graph,
            check_suspect=False,
            check_review=False,
            check_children=False,
        )
        errors = [i for i in issues if i.level == "error"]
        assert any("inactive" in str(i) for i in errors)

    def test_inactive_children_not_counted(self):
        dag = DocumentDAG()
        dag.documents["SYS"] = DocumentConfig(prefix="SYS")
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=["SYS"])
        graph = TraceabilityGraph()
        sys_item = Item(
            uid="SYS001", text="System req", document_prefix="SYS", reviewed="hash"
        )
        # Inactive child that links to SYS001 — should not count
        srs_item = Item(
            uid="SRS001",
            text="Software req",
            document_prefix="SRS",
            links=["SYS001"],
            active=False,
        )
        graph.add_item(sys_item)
        graph.add_item(srs_item)
        graph.set_document_parents("SYS", [])
        graph.set_document_parents("SRS", ["SYS"])
        issues = validate(
            dag,
            graph,
            check_links=False,
            check_suspect=False,
            check_review=False,
        )
        assert any("no children" in str(i) for i in issues)

    def test_suspect_links_skip_inactive_targets(self, tmp_path):
        dag = DocumentDAG()
        dag.documents["SRS"] = DocumentConfig(prefix="SRS")
        dag.document_paths["SRS"] = tmp_path / "srs"
        graph = TraceabilityGraph()
        # Target is inactive
        target = Item(uid="SYS001", text="Target", document_prefix="SRS", active=False)
        source = Item(
            uid="SRS001",
            text="Source",
            document_prefix="SRS",
            links=["SYS001"],
        )
        graph.add_item(target)
        graph.add_item(source)
        graph.set_document_parents("SRS", [])
        # Write a YAML file with a stale hash so suspect would fire
        # if target were active
        item_dir = tmp_path / "srs"
        item_dir.mkdir()
        item_file = item_dir / "SRS001.yml"
        item_file.write_text(
            "uid: SRS001\ntext: Source\nlinks:\n"
            "  - SYS001\nlink_hashes:\n  SYS001: stale_hash\n"
        )
        issues = validate(
            dag,
            graph,
            check_links=False,
            check_review=False,
            check_children=False,
        )
        suspect_issues = [i for i in issues if "suspect" in str(i).lower()]
        assert len(suspect_issues) == 0

    def test_suspect_links_missing_hash_warning(self, tmp_path):
        dag = DocumentDAG()
        dag.documents["SYS"] = DocumentConfig(prefix="SYS")
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=["SYS"])
        dag.document_paths["SYS"] = tmp_path / "sys"
        dag.document_paths["SRS"] = tmp_path / "srs"
        graph = TraceabilityGraph()
        target = Item(
            uid="SYS001", text="Target", document_prefix="SYS", reviewed="hash"
        )
        source = Item(
            uid="SRS001",
            text="Source",
            document_prefix="SRS",
            links=["SYS001"],
        )
        graph.add_item(target)
        graph.add_item(source)
        graph.set_document_parents("SYS", [])
        graph.set_document_parents("SRS", ["SYS"])
        # Write YAML with link but no link_hashes
        item_dir = tmp_path / "srs"
        item_dir.mkdir()
        item_file = item_dir / "SRS001.yml"
        item_file.write_text("uid: SRS001\ntext: Source\nlinks:\n  - SYS001\n")
        issues = validate(
            dag,
            graph,
            check_links=False,
            check_review=False,
            check_children=False,
        )
        assert any("no stored hash" in str(i) for i in issues)

    def test_empty_document_warning(self):
        dag = DocumentDAG()
        dag.documents["SYS"] = DocumentConfig(prefix="SYS")
        graph = TraceabilityGraph()
        graph.set_document_parents("SYS", [])
        issues = validate(
            dag,
            graph,
            check_links=False,
            check_suspect=False,
            check_review=False,
            check_children=False,
            check_empty_text=False,
            check_item_cycles=False,
            check_unlinked=False,
        )
        assert any("document contains no items" in str(i) for i in issues)

    def test_empty_text_warning(self):
        dag = DocumentDAG()
        dag.documents["SRS"] = DocumentConfig(prefix="SRS")
        graph = TraceabilityGraph()
        item = Item(uid="SRS001", text="", document_prefix="SRS", reviewed="h")
        graph.add_item(item)
        graph.set_document_parents("SRS", [])
        issues = validate(
            dag,
            graph,
            check_links=False,
            check_suspect=False,
            check_review=False,
            check_children=False,
            check_empty_docs=False,
            check_item_cycles=False,
            check_unlinked=False,
        )
        assert any("has empty text" in str(i) for i in issues)

    def test_whitespace_text_warning(self):
        dag = DocumentDAG()
        dag.documents["SRS"] = DocumentConfig(prefix="SRS")
        graph = TraceabilityGraph()
        item = Item(uid="SRS001", text="   \n  ", document_prefix="SRS", reviewed="h")
        graph.add_item(item)
        graph.set_document_parents("SRS", [])
        issues = validate(
            dag,
            graph,
            check_links=False,
            check_suspect=False,
            check_review=False,
            check_children=False,
            check_empty_docs=False,
            check_item_cycles=False,
            check_unlinked=False,
        )
        assert any("has empty text" in str(i) for i in issues)

    def test_self_link_warning(self):
        dag = DocumentDAG()
        dag.documents["SRS"] = DocumentConfig(prefix="SRS")
        graph = TraceabilityGraph()
        item = Item(
            uid="SRS001",
            text="Self-linker",
            document_prefix="SRS",
            links=["SRS001"],
            reviewed="h",
        )
        graph.add_item(item)
        graph.set_document_parents("SRS", [])
        issues = validate(
            dag,
            graph,
            check_suspect=False,
            check_review=False,
            check_children=False,
            check_empty_docs=False,
            check_empty_text=False,
            check_item_cycles=False,
            check_unlinked=False,
        )
        assert any("links to itself" in str(i) for i in issues)

    def test_link_to_non_normative_warning(self):
        dag = DocumentDAG()
        dag.documents["SYS"] = DocumentConfig(prefix="SYS")
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=["SYS"])
        graph = TraceabilityGraph()
        info_item = Item(
            uid="SYS001",
            text="Info item",
            document_prefix="SYS",
            type="info",
            reviewed="h",
        )
        srs_item = Item(
            uid="SRS001",
            text="Links to info",
            document_prefix="SRS",
            links=["SYS001"],
            reviewed="h",
        )
        graph.add_item(info_item)
        graph.add_item(srs_item)
        graph.set_document_parents("SYS", [])
        graph.set_document_parents("SRS", ["SYS"])
        issues = validate(
            dag,
            graph,
            check_suspect=False,
            check_review=False,
            check_children=False,
            check_empty_docs=False,
            check_empty_text=False,
            check_item_cycles=False,
            check_unlinked=False,
        )
        assert any("non-normative item" in str(i) for i in issues)

    def test_non_normative_has_links_warning(self):
        dag = DocumentDAG()
        dag.documents["SYS"] = DocumentConfig(prefix="SYS")
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=["SYS"])
        graph = TraceabilityGraph()
        sys_item = Item(
            uid="SYS001", text="System req", document_prefix="SYS", reviewed="h"
        )
        info_item = Item(
            uid="SRS001",
            text="Info with links",
            document_prefix="SRS",
            type="info",
            links=["SYS001"],
            reviewed="h",
        )
        graph.add_item(sys_item)
        graph.add_item(info_item)
        graph.set_document_parents("SYS", [])
        graph.set_document_parents("SRS", ["SYS"])
        issues = validate(
            dag,
            graph,
            check_suspect=False,
            check_review=False,
            check_children=False,
            check_empty_docs=False,
            check_empty_text=False,
            check_item_cycles=False,
            check_unlinked=False,
        )
        assert any("non-normative item has links" in str(i) for i in issues)

    def test_unlinked_normative_in_child_doc(self):
        dag = DocumentDAG()
        dag.documents["SYS"] = DocumentConfig(prefix="SYS")
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=["SYS"])
        graph = TraceabilityGraph()
        # SRS item with no links in a child document
        srs_item = Item(
            uid="SRS001", text="No links", document_prefix="SRS", reviewed="h"
        )
        graph.add_item(srs_item)
        graph.set_document_parents("SYS", [])
        graph.set_document_parents("SRS", ["SYS"])
        issues = validate(
            dag,
            graph,
            check_links=False,
            check_suspect=False,
            check_review=False,
            check_children=False,
            check_empty_docs=False,
            check_empty_text=False,
            check_item_cycles=False,
        )
        assert any("normative non-derived item has no links" in str(i) for i in issues)

    def test_derived_item_no_link_no_warning(self):
        dag = DocumentDAG()
        dag.documents["SYS"] = DocumentConfig(prefix="SYS")
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=["SYS"])
        graph = TraceabilityGraph()
        # Derived SRS item with no links — should NOT warn
        srs_item = Item(
            uid="SRS001",
            text="Derived item",
            document_prefix="SRS",
            derived=True,
            reviewed="h",
        )
        graph.add_item(srs_item)
        graph.set_document_parents("SYS", [])
        graph.set_document_parents("SRS", ["SYS"])
        issues = validate(
            dag,
            graph,
            check_links=False,
            check_suspect=False,
            check_review=False,
            check_children=False,
            check_empty_docs=False,
            check_empty_text=False,
            check_item_cycles=False,
        )
        unlinked = [i for i in issues if "normative non-derived" in str(i)]
        assert len(unlinked) == 0

    def test_item_link_cycle_warning(self):
        dag = DocumentDAG()
        dag.documents["SRS"] = DocumentConfig(prefix="SRS")
        graph = TraceabilityGraph()
        item_a = Item(
            uid="SRS001",
            text="A",
            document_prefix="SRS",
            links=["SRS002"],
            reviewed="h",
        )
        item_b = Item(
            uid="SRS002",
            text="B",
            document_prefix="SRS",
            links=["SRS001"],
            reviewed="h",
        )
        graph.add_item(item_a)
        graph.add_item(item_b)
        graph.set_document_parents("SRS", [])
        issues = validate(
            dag,
            graph,
            check_links=False,
            check_suspect=False,
            check_review=False,
            check_children=False,
            check_empty_docs=False,
            check_empty_text=False,
            check_unlinked=False,
        )
        assert any("cycle in item links" in str(i) for i in issues)
