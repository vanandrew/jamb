"""Tests for jamb.storage.validation module."""

from pathlib import Path

import pytest

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
        sys_item = Item(uid="SYS001", text="System req", document_prefix="SYS", reviewed="hash1")
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
        issues = validate(dag, graph, check_suspect=False, check_review=False, check_children=False)
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
        bad_item = Item(uid="SRS002", text="Bad", document_prefix="SRS", links=["NONEXIST"])
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
        sys_item = Item(uid="SYS001", text="System", document_prefix="SYS", reviewed="hash")
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
        sys_item = Item(uid="SYS001", text="System req", document_prefix="SYS", active=False)
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
        sys_item = Item(uid="SYS001", text="System req", document_prefix="SYS", reviewed="hash")
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
        item_file.write_text("uid: SRS001\ntext: Source\nlinks:\n  - SYS001\nlink_hashes:\n  SYS001: stale_hash\n")
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
        target = Item(uid="SYS001", text="Target", document_prefix="SYS", reviewed="hash")
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
        """Self-link raises ValueError when adding to graph."""
        graph = TraceabilityGraph()
        item = Item(
            uid="SRS001",
            text="Self-linker",
            document_prefix="SRS",
            links=["SRS001"],
            reviewed="h",
        )

        with pytest.raises(ValueError, match="cannot link to itself"):
            graph.add_item(item)

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
        sys_item = Item(uid="SYS001", text="System req", document_prefix="SYS", reviewed="h")
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
        srs_item = Item(uid="SRS001", text="No links", document_prefix="SRS", reviewed="h")
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

    def test_three_item_cycle(self):
        """3-item cycle: A -> B -> C -> A."""
        dag = DocumentDAG()
        dag.documents["SRS"] = DocumentConfig(prefix="SRS")
        graph = TraceabilityGraph()
        for uid, link in [
            ("SRS001", "SRS002"),
            ("SRS002", "SRS003"),
            ("SRS003", "SRS001"),
        ]:
            graph.add_item(Item(uid=uid, text=uid, document_prefix="SRS", links=[link], reviewed="h"))
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

    def test_multiple_disjoint_cycles(self):
        """Two separate cycles: (A->B->A) and (C->D->C)."""
        dag = DocumentDAG()
        dag.documents["SRS"] = DocumentConfig(prefix="SRS")
        graph = TraceabilityGraph()
        for uid, link in [
            ("SRS001", "SRS002"),
            ("SRS002", "SRS001"),
            ("SRS003", "SRS004"),
            ("SRS004", "SRS003"),
        ]:
            graph.add_item(Item(uid=uid, text=uid, document_prefix="SRS", links=[link], reviewed="h"))
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
        cycle_issues = [i for i in issues if "cycle in item links" in str(i)]
        assert len(cycle_issues) == 2

    def test_whitespace_tab_text_warning(self):
        """Tab and \\r\\n whitespace-only text triggers empty text warning."""
        dag = DocumentDAG()
        dag.documents["SRS"] = DocumentConfig(prefix="SRS")
        graph = TraceabilityGraph()
        item = Item(uid="SRS001", text="\t\r\n", document_prefix="SRS", reviewed="h")
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

    def test_skip_prefix_on_parent_skips_children_check(self):
        """Skipping a parent prefix does not affect child checks."""
        dag = DocumentDAG()
        dag.documents["SYS"] = DocumentConfig(prefix="SYS")
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=["SYS"])
        graph = TraceabilityGraph()
        srs_item = Item(uid="SRS001", text="No links", document_prefix="SRS", reviewed="h")
        graph.add_item(srs_item)
        graph.set_document_parents("SYS", [])
        graph.set_document_parents("SRS", ["SYS"])
        # Skip SYS, but SRS should still be checked for unlinked
        issues = validate(
            dag,
            graph,
            skip_prefixes=["SYS"],
            check_links=False,
            check_suspect=False,
            check_review=False,
            check_children=False,
            check_empty_docs=False,
            check_empty_text=False,
            check_item_cycles=False,
        )
        assert any("normative non-derived item has no links" in str(i) for i in issues)

    def test_link_conformance_wrong_parent_document(self):
        """Link to non-parent document produces warning."""
        dag = DocumentDAG()
        dag.documents["SYS"] = DocumentConfig(prefix="SYS")
        dag.documents["OTHER"] = DocumentConfig(prefix="OTHER")
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=["SYS"])
        graph = TraceabilityGraph()
        other_item = Item(uid="OTHER001", text="Other", document_prefix="OTHER", reviewed="h")
        srs_item = Item(
            uid="SRS001",
            text="Links to wrong doc",
            document_prefix="SRS",
            links=["OTHER001"],
            reviewed="h",
        )
        graph.add_item(other_item)
        graph.add_item(srs_item)
        graph.set_document_parents("SYS", [])
        graph.set_document_parents("OTHER", [])
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
        assert any("not a parent document" in str(i) for i in issues)

    def test_check_links_prefix_not_in_dag(self):
        """4a: Item whose prefix is not in DAG still runs link checks."""
        dag = DocumentDAG()
        # Only SYS in DAG, not "ORPHAN"
        dag.documents["SYS"] = DocumentConfig(prefix="SYS")
        graph = TraceabilityGraph()
        sys_item = Item(uid="SYS001", text="System", document_prefix="SYS", reviewed="h")
        orphan_item = Item(
            uid="ORPHAN001",
            text="Orphan",
            document_prefix="ORPHAN",
            links=["NONEXIST"],
            reviewed="h",
        )
        graph.add_item(sys_item)
        graph.add_item(orphan_item)
        graph.set_document_parents("SYS", [])
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
        errors = [i for i in issues if i.level == "error"]
        assert any("non-existent" in str(i) for i in errors)

    def test_branching_cycle_detection(self):
        """4b: One branch cycles, other doesn't. A→B, A→C, B→A."""
        dag = DocumentDAG()
        dag.documents["SRS"] = DocumentConfig(prefix="SRS")
        graph = TraceabilityGraph()
        item_a = Item(
            uid="SRS001",
            text="A",
            document_prefix="SRS",
            links=["SRS002", "SRS003"],
            reviewed="h",
        )
        item_b = Item(
            uid="SRS002",
            text="B",
            document_prefix="SRS",
            links=["SRS001"],
            reviewed="h",
        )
        item_c = Item(
            uid="SRS003",
            text="C",
            document_prefix="SRS",
            links=[],
            reviewed="h",
        )
        graph.add_item(item_a)
        graph.add_item(item_b)
        graph.add_item(item_c)
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
        cycle_issues = [i for i in issues if "cycle in item links" in str(i)]
        assert len(cycle_issues) == 1
        # Cycle should mention SRS001 and SRS002
        cycle_msg = str(cycle_issues[0])
        assert "SRS001" in cycle_msg
        assert "SRS002" in cycle_msg

    def test_check_children_all_non_normative(self):
        """4d: Non-normative items in parent doc shouldn't
        trigger no-children warning."""
        dag = DocumentDAG()
        dag.documents["SYS"] = DocumentConfig(prefix="SYS")
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=["SYS"])
        graph = TraceabilityGraph()
        # SYS has only info/heading items — not normative
        info_item = Item(
            uid="SYS001",
            text="Info",
            document_prefix="SYS",
            type="info",
            reviewed="h",
        )
        heading_item = Item(
            uid="SYS002",
            text="Heading",
            document_prefix="SYS",
            type="heading",
            reviewed="h",
        )
        graph.add_item(info_item)
        graph.add_item(heading_item)
        graph.set_document_parents("SYS", [])
        graph.set_document_parents("SRS", ["SYS"])
        issues = validate(
            dag,
            graph,
            check_links=False,
            check_suspect=False,
            check_review=False,
            check_empty_docs=False,
            check_empty_text=False,
            check_item_cycles=False,
            check_unlinked=False,
        )
        children_issues = [i for i in issues if "no children" in str(i)]
        assert len(children_issues) == 0

    def test_suspect_links_matching_hash(self, tmp_path):
        """4f: Link with correct hash produces no suspect warning."""
        dag = DocumentDAG()
        dag.documents["SYS"] = DocumentConfig(prefix="SYS")
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=["SYS"])
        dag.document_paths["SYS"] = tmp_path / "sys"
        dag.document_paths["SRS"] = tmp_path / "srs"
        graph = TraceabilityGraph()
        target = Item(
            uid="SYS001",
            text="Target text",
            document_prefix="SYS",
            reviewed="h",
        )
        # Compute the correct hash for the target
        target_data = {
            "text": target.text,
            "header": target.header,
            "links": target.links,
            "type": target.type,
        }
        correct_hash = compute_content_hash(target_data)
        source = Item(
            uid="SRS001",
            text="Source",
            document_prefix="SRS",
            links=["SYS001"],
            reviewed="h",
        )
        graph.add_item(target)
        graph.add_item(source)
        graph.set_document_parents("SYS", [])
        graph.set_document_parents("SRS", ["SYS"])
        # Write YAML with correct hash
        item_dir = tmp_path / "srs"
        item_dir.mkdir()
        item_file = item_dir / "SRS001.yml"
        item_file.write_text(f"uid: SRS001\ntext: Source\nlinks:\n  - SYS001: {correct_hash}\n")
        issues = validate(
            dag,
            graph,
            check_links=False,
            check_review=False,
            check_children=False,
            check_empty_docs=False,
            check_empty_text=False,
            check_item_cycles=False,
            check_unlinked=False,
        )
        suspect_issues = [i for i in issues if "suspect" in str(i).lower()]
        assert len(suspect_issues) == 0

    def test_full_validate_multiple_checks(self):
        """4g: Full validate with all checks on graph triggering multiple issues."""
        dag = DocumentDAG()
        dag.documents["SYS"] = DocumentConfig(prefix="SYS")
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=["SYS"])
        graph = TraceabilityGraph()
        # SYS item with no children, not reviewed
        sys_item = Item(uid="SYS001", text="System req", document_prefix="SYS")
        # SRS item with broken link, empty text, no review
        srs_item = Item(
            uid="SRS001",
            text="",
            document_prefix="SRS",
            links=["NONEXIST"],
        )
        graph.add_item(sys_item)
        graph.add_item(srs_item)
        graph.set_document_parents("SYS", [])
        graph.set_document_parents("SRS", ["SYS"])
        issues = validate(dag, graph, check_suspect=False)
        # Should have issues from multiple checks
        messages = [str(i) for i in issues]
        assert any("non-existent" in m for m in messages)  # broken link
        assert any("has empty text" in m for m in messages)  # empty text
        assert any("not been reviewed" in m for m in messages)  # review
        assert any("no children" in m for m in messages)  # children check

    def test_isolated_cycle_not_connected_to_root(self):
        """Two items forming a cycle with no external
        references; verify cycle detected."""
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
        cycle_issues = [i for i in issues if "cycle in item links" in str(i)]
        assert len(cycle_issues) >= 1
        # Both items should be mentioned in the cycle
        cycle_msg = str(cycle_issues[0])
        assert "SRS001" in cycle_msg
        assert "SRS002" in cycle_msg

    def test_item_with_reviewed_hash_and_link_hashes(self, tmp_path):
        """Item with both reviewed hash AND link_hashes: both checks fire."""
        # Hashes must be >= 20 chars and contain only URL-safe base64 chars
        stale_link_hash = "stale_link_hash_01234567"
        stale_reviewed_hash = "stale_reviewed_hash_01234567"

        dag = DocumentDAG()
        dag.documents["SYS"] = DocumentConfig(prefix="SYS")
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=["SYS"])
        dag.document_paths["SYS"] = tmp_path / "sys"
        dag.document_paths["SRS"] = tmp_path / "srs"

        graph = TraceabilityGraph()
        target = Item(
            uid="SYS001",
            text="Target",
            document_prefix="SYS",
            reviewed="valid_target_reviewed_hash",
        )
        # Source has a stale reviewed hash AND link_hashes on disk
        source = Item(
            uid="SRS001",
            text="Source text",
            document_prefix="SRS",
            links=["SYS001"],
            reviewed=stale_reviewed_hash,
        )
        graph.add_item(target)
        graph.add_item(source)
        graph.set_document_parents("SYS", [])
        graph.set_document_parents("SRS", ["SYS"])

        # Write YAML with a stale link hash
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / "SRS001.yml").write_text(f"uid: SRS001\ntext: Source text\nlinks:\n  - SYS001: {stale_link_hash}\n")

        issues = validate(
            dag,
            graph,
            check_links=False,
            check_children=False,
            check_empty_docs=False,
            check_empty_text=False,
            check_item_cycles=False,
            check_unlinked=False,
        )
        # Review check should flag SRS001's stale reviewed hash
        review_issues = [i for i in issues if "modified since last review" in str(i) and "SRS001" in str(i)]
        assert len(review_issues) == 1
        # Suspect check should flag the stale link hash on SRS001
        suspect_issues = [i for i in issues if "suspect" in str(i).lower() and "SRS001" in str(i)]
        assert len(suspect_issues) == 1

    def test_multiple_parent_documents_link_to_one(self):
        """Item in child doc links to one of several valid
        parents — no conformance warning."""
        dag = DocumentDAG()
        dag.documents["SYS"] = DocumentConfig(prefix="SYS")
        dag.documents["HW"] = DocumentConfig(prefix="HW")
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=["SYS", "HW"])
        graph = TraceabilityGraph()
        sys_item = Item(uid="SYS001", text="System", document_prefix="SYS", reviewed="h")
        hw_item = Item(uid="HW001", text="Hardware", document_prefix="HW", reviewed="h")
        # SRS item links only to HW001, which is a valid parent
        srs_item = Item(
            uid="SRS001",
            text="Links to HW",
            document_prefix="SRS",
            links=["HW001"],
            reviewed="h",
        )
        graph.add_item(sys_item)
        graph.add_item(hw_item)
        graph.add_item(srs_item)
        graph.set_document_parents("SYS", [])
        graph.set_document_parents("HW", [])
        graph.set_document_parents("SRS", ["SYS", "HW"])
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
        conformance_issues = [i for i in issues if "not a parent document" in str(i)]
        assert len(conformance_issues) == 0

    def test_root_document_items_no_unlinked_warning(self):
        """Root document items with no links should NOT trigger unlinked warning."""
        dag = DocumentDAG()
        dag.documents["SYS"] = DocumentConfig(prefix="SYS")
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=["SYS"])
        graph = TraceabilityGraph()
        # Root doc item with no links — perfectly fine
        sys_item = Item(
            uid="SYS001",
            text="Root item, no links needed",
            document_prefix="SYS",
            reviewed="h",
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
            check_children=False,
            check_empty_docs=False,
            check_empty_text=False,
            check_item_cycles=False,
        )
        unlinked = [i for i in issues if "no links" in str(i)]
        assert len(unlinked) == 0

    def test_non_derived_item_in_child_doc_no_links_warns(self):
        """Non-derived normative item in child doc with no links should warn."""
        dag = DocumentDAG()
        dag.documents["SYS"] = DocumentConfig(prefix="SYS")
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=["SYS"])
        graph = TraceabilityGraph()
        srs_item = Item(
            uid="SRS001",
            text="No links, not derived",
            document_prefix="SRS",
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
        unlinked = [i for i in issues if "normative non-derived item has no links" in str(i)]
        assert len(unlinked) == 1
        assert "SRS001" in str(unlinked[0])
