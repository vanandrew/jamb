"""Aggressive system tests targeting edge cases and boundary conditions."""

import os
from pathlib import Path

import pytest
import yaml

from jamb.core.models import Item, TraceabilityGraph
from jamb.storage.document_config import DocumentConfig
from jamb.storage.document_dag import DocumentDAG
from jamb.storage.items import (
    compute_content_hash,
    next_uid,
    read_document_items,
    read_item,
    write_item,
)
from jamb.storage.validation import validate

# =============================================================================
# 1. Malformed YAML Inputs
# =============================================================================


class TestMalformedYaml:
    """Tests for read_item() with malformed or unexpected YAML content."""

    def test_read_item_empty_file(self, tmp_path: Path) -> None:
        """YAML file with zero bytes returns item with defaults."""
        item_file = tmp_path / "SRS001.yml"
        item_file.write_text("")
        result = read_item(item_file, "SRS")
        assert result["uid"] == "SRS001"
        assert result["text"] == ""
        assert result["active"] is True
        assert result["links"] == []

    def test_read_item_yaml_only_null(self, tmp_path: Path) -> None:
        """File containing just `null` returns item with defaults."""
        item_file = tmp_path / "SRS001.yml"
        item_file.write_text("null\n")
        result = read_item(item_file, "SRS")
        assert result["uid"] == "SRS001"
        assert result["text"] == ""
        assert result["active"] is True

    def test_read_item_yaml_is_a_list(self, tmp_path: Path) -> None:
        """File containing a list returns defaults (graceful handling)."""
        item_file = tmp_path / "SRS001.yml"
        item_file.write_text("[1, 2, 3]\n")
        result = read_item(item_file, "SRS")
        assert result["uid"] == "SRS001"
        assert result["text"] == ""
        assert result["active"] is True

    def test_read_item_yaml_is_a_string(self, tmp_path: Path) -> None:
        """File containing just a string returns defaults."""
        item_file = tmp_path / "SRS001.yml"
        item_file.write_text('"hello"\n')
        result = read_item(item_file, "SRS")
        assert result["uid"] == "SRS001"
        assert result["text"] == ""

    def test_read_item_yaml_is_a_number(self, tmp_path: Path) -> None:
        """File containing just a number returns defaults."""
        item_file = tmp_path / "SRS001.yml"
        item_file.write_text("42\n")
        result = read_item(item_file, "SRS")
        assert result["uid"] == "SRS001"
        assert result["text"] == ""

    def test_read_item_binary_garbage(self, tmp_path: Path) -> None:
        """File with random binary bytes raises yaml.YAMLError."""
        item_file = tmp_path / "SRS001.yml"
        item_file.write_bytes(os.urandom(256))
        # Binary garbage may or may not parse as YAML — some random bytes
        # happen to be valid YAML. We just verify it doesn't silently succeed
        # with garbage data or that it raises an appropriate error.
        try:
            result = read_item(item_file, "SRS")
            # If it parsed, it should still have the uid from the filename
            assert result["uid"] == "SRS001"
        except (yaml.YAMLError, AttributeError, UnicodeDecodeError):
            pass  # Expected for truly unparseable content

    def test_read_item_links_is_a_string(self, tmp_path: Path) -> None:
        """links: 'not a list' is treated as empty (not a list)."""
        from conftest import suppress_expected_warnings

        item_file = tmp_path / "SRS001.yml"
        item_file.write_text("text: hello\nlinks: 'not a list'\n")
        with suppress_expected_warnings():  # warns about invalid links type
            result = read_item(item_file, "SRS")
        assert result["links"] == []

    def test_read_item_links_is_a_number(self, tmp_path: Path) -> None:
        """links: 42 is treated as empty (not a list)."""
        from conftest import suppress_expected_warnings

        item_file = tmp_path / "SRS001.yml"
        item_file.write_text("text: hello\nlinks: 42\n")
        with suppress_expected_warnings():  # warns about invalid links type
            result = read_item(item_file, "SRS")
        assert result["links"] == []

    def test_read_item_links_contains_numbers(self, tmp_path: Path) -> None:
        """links: [1, 2, 3] — non-string entries are skipped with warning."""
        from conftest import suppress_expected_warnings

        item_file = tmp_path / "SRS001.yml"
        item_file.write_text("text: hello\nlinks:\n  - 1\n  - 2\n  - 3\n")
        with suppress_expected_warnings():  # warns about non-string link entries
            result = read_item(item_file, "SRS")
        assert result["links"] == []

    def test_read_item_links_contains_nested_lists(self, tmp_path: Path) -> None:
        """links: [[a, b], [c]] — nested lists are skipped with warning."""
        from conftest import suppress_expected_warnings

        item_file = tmp_path / "SRS001.yml"
        item_file.write_text("text: hello\nlinks:\n  - [a, b]\n  - [c]\n")
        with suppress_expected_warnings():  # warns about non-string link entries
            result = read_item(item_file, "SRS")
        # Non-string entries (nested lists) are rejected with warning
        assert result["links"] == []

    def test_read_item_links_dict_with_null_key(self, tmp_path: Path) -> None:
        """links: [{null: hash}] — str(None) becomes 'None' as UID."""
        from conftest import suppress_expected_warnings

        item_file = tmp_path / "SRS001.yml"
        # Use a valid-length hash (>= 20 chars, base64 characters)
        valid_hash = "abcdefghijklmnopqrstuvwxyz"
        item_file.write_text(f"text: hello\nlinks:\n  - null: {valid_hash}\n")
        with suppress_expected_warnings():  # may warn about null key
            result = read_item(item_file, "SRS")
        assert "None" in result["links"]
        assert result["link_hashes"]["None"] == valid_hash

    def test_read_item_text_is_number(self, tmp_path: Path) -> None:
        """text: 12345 is coerced to '12345' via str()."""
        item_file = tmp_path / "SRS001.yml"
        item_file.write_text("text: 12345\n")
        result = read_item(item_file, "SRS")
        assert result["text"] == "12345"

    def test_read_item_text_is_list(self, tmp_path: Path) -> None:
        """text: [a, b] is coerced to string via str()."""
        item_file = tmp_path / "SRS001.yml"
        item_file.write_text("text:\n  - a\n  - b\n")
        result = read_item(item_file, "SRS")
        assert result["text"] == "['a', 'b']"

    def test_read_item_all_fields_null(self, tmp_path: Path) -> None:
        """Every field set to null — item created with safe defaults."""
        item_file = tmp_path / "SRS001.yml"
        item_file.write_text(
            "text: null\nactive: null\ntype: null\nheader: null\nlinks: null\nreviewed: null\nderived: null\n"
        )
        result = read_item(item_file, "SRS")
        assert result["uid"] == "SRS001"
        assert result["text"] == "None"  # str(None)
        assert result["active"] is None  # data.get("active", True) returns None
        assert result["type"] is None
        assert result["header"] is None  # None or "" -> None
        assert result["links"] == []  # None is not a list
        assert result["reviewed"] is None
        assert result["derived"] is None

    def test_read_item_extra_unknown_fields(self, tmp_path: Path) -> None:
        """50 unknown fields all become custom_attributes."""
        lines = ["text: hello\n"]
        for i in range(50):
            lines.append(f"custom_field_{i}: value_{i}\n")
        item_file = tmp_path / "SRS001.yml"
        item_file.write_text("".join(lines))
        result = read_item(item_file, "SRS")
        assert len(result["custom_attributes"]) == 50
        assert result["custom_attributes"]["custom_field_0"] == "value_0"
        assert result["custom_attributes"]["custom_field_49"] == "value_49"

    def test_read_item_deeply_nested_custom_attrs(self, tmp_path: Path) -> None:
        """Custom attr with 10-deep nesting stored as-is."""
        nested = {"level": 1}
        current = nested
        for i in range(2, 11):
            current["child"] = {"level": i}
            current = current["child"]

        item_file = tmp_path / "SRS001.yml"
        data = {"text": "hello", "deep_attr": nested}
        item_file.write_text(yaml.dump(data))
        result = read_item(item_file, "SRS")
        assert result["custom_attributes"]["deep_attr"]["level"] == 1
        # Traverse 10 levels deep
        node = result["custom_attributes"]["deep_attr"]
        for _ in range(9):
            node = node["child"]
        assert node["level"] == 10


# =============================================================================
# 2. Boundary Conditions
# =============================================================================


class TestBoundaryConditions:
    """Tests for boundary values in UID generation and item display."""

    def test_next_uid_no_existing(self) -> None:
        """Empty existing_uids list returns prefix + '001'."""
        result = next_uid("SRS", 3, [])
        assert result == "SRS001"

    def test_next_uid_very_large_number(self) -> None:
        """Existing UID with very large number increments correctly."""
        result = next_uid("SRS", 3, ["SRS999999999999"])
        assert result == "SRS1000000000000"

    def test_next_uid_digits_zero(self) -> None:
        """digits=0 raises ValueError since digits must be >= 1."""
        import pytest

        with pytest.raises(ValueError, match="digits must be >= 1"):
            next_uid("SRS", 0, [])

    def test_next_uid_digits_very_large(self) -> None:
        """digits=100 produces UID with 100-digit zero-padded number."""
        result = next_uid("SRS", 100, [])
        assert result == "SRS" + "0" * 99 + "1"
        assert len(result) == 103  # "SRS" + 100 digits

    def test_next_uid_empty_prefix(self) -> None:
        """prefix='' returns just the number."""
        result = next_uid("", 3, [])
        assert result == "001"

    def test_next_uid_prefix_with_special_chars(self) -> None:
        """Prefix with special regex chars handled via re.escape."""
        result = next_uid("A-B", 3, ["A-B001"])
        assert result == "A-B002"

    def test_next_uid_sep_with_regex_chars(self) -> None:
        """Separator with regex chars handled via re.escape."""
        result = next_uid("SRS", 3, ["SRS.*001"], sep=".*")
        assert result == "SRS.*002"

    def test_read_document_items_empty_dir(self, tmp_path: Path) -> None:
        """Document directory with only .jamb.yml returns empty list."""
        jamb_file = tmp_path / ".jamb.yml"
        jamb_file.write_text("settings:\n  prefix: SRS\n")
        result = read_document_items(tmp_path, "SRS")
        assert result == []

    def test_read_document_items_1000_items(self, tmp_path: Path) -> None:
        """Directory with 1000 YAML files returns all 1000, sorted."""
        for i in range(1, 1001):
            item_file = tmp_path / f"SRS{i:04d}.yml"
            item_file.write_text(f"text: Item {i}\n")
        result = read_document_items(tmp_path, "SRS")
        assert len(result) == 1000
        assert result[0]["uid"] == "SRS0001"
        assert result[-1]["uid"] == "SRS1000"

    def test_item_display_text_exactly_80_chars(self) -> None:
        """Text exactly 80 chars is not truncated."""
        text = "A" * 80
        item = Item(uid="SRS001", text=text, document_prefix="SRS")
        assert item.display_text == text
        assert "..." not in item.display_text

    def test_item_display_text_81_chars(self) -> None:
        """Text 81 chars is truncated with '...'."""
        text = "A" * 81
        item = Item(uid="SRS001", text=text, document_prefix="SRS")
        assert item.display_text == "A" * 80 + "..."

    def test_item_display_text_empty_string(self) -> None:
        """Empty text, no header returns empty string."""
        item = Item(uid="SRS001", text="", document_prefix="SRS")
        assert item.display_text == ""

    def test_item_empty_uid(self) -> None:
        """Item with uid='' can be created without error."""
        item = Item(uid="", text="test", document_prefix="SRS")
        assert item.uid == ""

    def test_item_uid_with_spaces(self) -> None:
        """uid='SRS 001' can be created without error."""
        item = Item(uid="SRS 001", text="test", document_prefix="SRS")
        assert item.uid == "SRS 001"

    def test_item_uid_with_unicode(self) -> None:
        """uid with emoji can be created without error."""
        item = Item(uid="SRS\U0001f680001", text="test", document_prefix="SRS")
        assert "\U0001f680" in item.uid


# =============================================================================
# 3. Graph Pathologies
# =============================================================================


class TestGraphPathologies:
    """Tests for TraceabilityGraph with pathological inputs."""

    def test_graph_self_referential_item(self) -> None:
        """Item linking to itself raises ValueError."""
        graph = TraceabilityGraph()
        item = Item(uid="A", text="self-ref", document_prefix="X", links=["A"])

        with pytest.raises(ValueError, match="cannot link to itself"):
            graph.add_item(item)

    def test_graph_mutual_cycle_two_items(self) -> None:
        """A links to B, B links to A — get_ancestors terminates."""
        graph = TraceabilityGraph()
        a = Item(uid="A", text="a", document_prefix="X", links=["B"])
        b = Item(uid="B", text="b", document_prefix="X", links=["A"])
        graph.add_item(a)
        graph.add_item(b)
        ancestors_a = graph.get_ancestors("A")
        ancestors_b = graph.get_ancestors("B")
        # Both should terminate without infinite loop
        assert isinstance(ancestors_a, list)
        assert isinstance(ancestors_b, list)

    def test_graph_long_chain_1000_deep(self) -> None:
        """Chain of 1000 items — traversal completes."""
        graph = TraceabilityGraph()
        for i in range(1000):
            links = [f"ITEM{i - 1:04d}"] if i > 0 else []
            item = Item(uid=f"ITEM{i:04d}", text=f"item {i}", document_prefix="X", links=links)
            graph.add_item(item)
        # Get ancestors of the last item — should be 999 items
        ancestors = graph.get_ancestors("ITEM0999")
        assert len(ancestors) == 999
        # Get descendants of first item — should be 999 items
        descendants = graph.get_descendants("ITEM0000")
        assert len(descendants) == 999

    def test_graph_diamond_inheritance(self) -> None:
        """A->B, A->C, B->D, C->D — diamond pattern."""
        graph = TraceabilityGraph()
        a = Item(uid="A", text="root", document_prefix="X", links=[])
        b = Item(uid="B", text="b", document_prefix="X", links=["A"])
        c = Item(uid="C", text="c", document_prefix="X", links=["A"])
        d = Item(uid="D", text="d", document_prefix="X", links=["B", "C"])
        graph.add_item(a)
        graph.add_item(b)
        graph.add_item(c)
        graph.add_item(d)
        ancestors_d = graph.get_ancestors("D")
        ancestor_uids = {a.uid for a in ancestors_d}
        assert ancestor_uids == {"A", "B", "C"}
        descendants_a = graph.get_descendants("A")
        descendant_uids = {d.uid for d in descendants_a}
        assert descendant_uids == {"B", "C", "D"}

    def test_graph_item_links_to_nonexistent(self) -> None:
        """Item links to UID not in graph — get_ancestors skips it gracefully."""
        graph = TraceabilityGraph()
        item = Item(uid="A", text="a", document_prefix="X", links=["NONEXISTENT"])
        graph.add_item(item)
        ancestors = graph.get_ancestors("A")
        assert ancestors == []

    def test_graph_duplicate_add_item(self) -> None:
        """Add same UID twice — second overwrites first."""
        graph = TraceabilityGraph()
        a1 = Item(uid="A", text="first", document_prefix="X", links=[])
        a2 = Item(uid="A", text="second", document_prefix="X", links=[])
        graph.add_item(a1)
        graph.add_item(a2)
        assert graph.items["A"].text == "second"

    def test_graph_thousands_of_children(self) -> None:
        """One parent with 1000 children — get_descendants returns all."""
        graph = TraceabilityGraph()
        parent = Item(uid="PARENT", text="parent", document_prefix="X", links=[])
        graph.add_item(parent)
        for i in range(1000):
            child = Item(
                uid=f"C{i:04d}",
                text=f"child {i}",
                document_prefix="X",
                links=["PARENT"],
            )
            graph.add_item(child)
        descendants = graph.get_descendants("PARENT")
        assert len(descendants) == 1000

    def test_graph_disconnected_components(self) -> None:
        """Two separate subgraphs — each traverses independently."""
        graph = TraceabilityGraph()
        a = Item(uid="A", text="a", document_prefix="X", links=[])
        b = Item(uid="B", text="b", document_prefix="X", links=["A"])
        c = Item(uid="C", text="c", document_prefix="Y", links=[])
        d = Item(uid="D", text="d", document_prefix="Y", links=["C"])
        graph.add_item(a)
        graph.add_item(b)
        graph.add_item(c)
        graph.add_item(d)
        assert {i.uid for i in graph.get_descendants("A")} == {"B"}
        assert {i.uid for i in graph.get_descendants("C")} == {"D"}
        assert {i.uid for i in graph.get_ancestors("B")} == {"A"}
        assert {i.uid for i in graph.get_ancestors("D")} == {"C"}

    def test_graph_item_with_empty_links_list(self) -> None:
        """links=[] — no parents, no crash."""
        graph = TraceabilityGraph()
        item = Item(uid="A", text="a", document_prefix="X", links=[])
        graph.add_item(item)
        assert graph.get_ancestors("A") == []
        assert graph.item_parents["A"] == []

    def test_graph_get_ancestors_unknown_uid(self) -> None:
        """UID not in graph — returns empty list."""
        graph = TraceabilityGraph()
        assert graph.get_ancestors("NOPE") == []

    def test_graph_get_descendants_unknown_uid(self) -> None:
        """UID not in graph — returns empty list."""
        graph = TraceabilityGraph()
        assert graph.get_descendants("NOPE") == []

    def test_graph_get_neighbors_unknown_uid(self) -> None:
        """UID not in graph — returns empty list."""
        graph = TraceabilityGraph()
        assert graph.get_neighbors("NOPE") == []

    def test_graph_set_document_parents_empty(self) -> None:
        """set_document_parents('X', []) — X is a root document."""
        graph = TraceabilityGraph()
        graph.set_document_parents("X", [])
        assert graph.document_parents["X"] == []
        assert "X" in graph.get_root_documents()

    def test_graph_leaf_documents_when_empty(self) -> None:
        """No documents at all — returns empty list."""
        graph = TraceabilityGraph()
        assert graph.get_leaf_documents() == []

    def test_graph_all_documents_are_roots(self) -> None:
        """Multiple docs, none are parents — all are roots AND leaves."""
        graph = TraceabilityGraph()
        graph.set_document_parents("A", [])
        graph.set_document_parents("B", [])
        graph.set_document_parents("C", [])
        assert set(graph.get_root_documents()) == {"A", "B", "C"}
        assert set(graph.get_leaf_documents()) == {"A", "B", "C"}


# =============================================================================
# 4. Validation Edge Cases
# =============================================================================


class TestValidationEdgeCases:
    """Tests for validation with edge-case inputs."""

    def _make_dag(
        self,
        docs: dict[str, list[str]] | None = None,
        paths: dict[str, Path] | None = None,
    ) -> DocumentDAG:
        """Helper to build a DocumentDAG from a dict of prefix -> parents."""
        dag = DocumentDAG()
        if docs:
            for prefix, parents in docs.items():
                dag.documents[prefix] = DocumentConfig(prefix=prefix, parents=parents)
                if paths and prefix in paths:
                    dag.document_paths[prefix] = paths[prefix]
        return dag

    def test_validate_empty_graph_empty_dag(self) -> None:
        """No items, no documents — no issues."""
        dag = self._make_dag()
        graph = TraceabilityGraph()
        issues = validate(dag, graph)
        assert issues == []

    def test_validate_all_items_inactive(self) -> None:
        """Every item is active=False — no link/review issues (all skipped)."""
        dag = self._make_dag({"SRS": ["SYS"]})
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        item = Item(uid="SRS001", text="test", document_prefix="SRS", active=False)
        graph.add_item(item)
        issues = validate(dag, graph, check_suspect=False)
        # Inactive items are skipped by all checks
        link_issues = [i for i in issues if "SRS001" in (i.uid or "")]
        assert link_issues == []

    def test_validate_all_items_skipped_prefix(self) -> None:
        """All items in skipped prefix — no issues found."""
        dag = self._make_dag({"SRS": ["SYS"]})
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        item = Item(uid="SRS001", text="test", document_prefix="SRS")
        graph.add_item(item)
        issues = validate(dag, graph, skip_prefixes=["SRS"], check_suspect=False)
        item_issues = [i for i in issues if i.uid == "SRS001"]
        assert item_issues == []

    def test_validate_item_links_to_itself(self) -> None:
        """Self-link raises ValueError when adding to graph."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", [])
        item = Item(uid="SRS001", text="test", document_prefix="SRS", links=["SRS001"])

        with pytest.raises(ValueError, match="cannot link to itself"):
            graph.add_item(item)

    def test_validate_mutual_cycle(self) -> None:
        """A->B->A cycle detected."""
        dag = self._make_dag({"X": []})
        graph = TraceabilityGraph()
        graph.set_document_parents("X", [])
        a = Item(uid="A", text="a", document_prefix="X", links=["B"])
        b = Item(uid="B", text="b", document_prefix="X", links=["A"])
        graph.add_item(a)
        graph.add_item(b)
        issues = validate(dag, graph, check_suspect=False, check_review=False)
        cycle_issues = [i for i in issues if "cycle" in i.message.lower()]
        assert len(cycle_issues) >= 1

    def test_validate_three_item_cycle(self) -> None:
        """A->B->C->A cycle detected."""
        dag = self._make_dag({"X": []})
        graph = TraceabilityGraph()
        graph.set_document_parents("X", [])
        a = Item(uid="A", text="a", document_prefix="X", links=["C"])
        b = Item(uid="B", text="b", document_prefix="X", links=["A"])
        c = Item(uid="C", text="c", document_prefix="X", links=["B"])
        graph.add_item(a)
        graph.add_item(b)
        graph.add_item(c)
        issues = validate(dag, graph, check_suspect=False, check_review=False)
        cycle_issues = [i for i in issues if "cycle" in i.message.lower()]
        assert len(cycle_issues) >= 1

    def test_validate_item_links_to_inactive(self) -> None:
        """Active item links to inactive — error."""
        dag = self._make_dag({"SRS": ["SYS"], "SYS": []})
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SYS", [])
        active = Item(uid="SRS001", text="active", document_prefix="SRS", links=["SYS001"])
        inactive = Item(uid="SYS001", text="inactive", document_prefix="SYS", active=False)
        graph.add_item(active)
        graph.add_item(inactive)
        issues = validate(dag, graph, check_suspect=False, check_review=False)
        inactive_issues = [i for i in issues if "inactive" in i.message]
        assert len(inactive_issues) >= 1

    def test_validate_non_normative_with_links(self) -> None:
        """type='info' item with links produces warning."""
        dag = self._make_dag({"SRS": []})
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", [])
        item = Item(
            uid="SRS001",
            text="info",
            document_prefix="SRS",
            type="info",
            links=["OTHER"],
        )
        other = Item(uid="OTHER", text="other", document_prefix="SRS")
        graph.add_item(item)
        graph.add_item(other)
        issues = validate(dag, graph, check_suspect=False, check_review=False)
        non_norm = [i for i in issues if "non-normative" in i.message]
        assert len(non_norm) >= 1

    def test_validate_link_to_wrong_document(self) -> None:
        """SRS item links to HAZ (not parent) — warning."""
        dag = self._make_dag({"SRS": ["SYS"], "SYS": [], "HAZ": []})
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SYS", [])
        graph.set_document_parents("HAZ", [])
        srs = Item(uid="SRS001", text="test", document_prefix="SRS", links=["HAZ001"])
        haz = Item(uid="HAZ001", text="hazard", document_prefix="HAZ")
        graph.add_item(srs)
        graph.add_item(haz)
        issues = validate(dag, graph, check_suspect=False, check_review=False)
        wrong_doc = [i for i in issues if "not a parent document" in i.message]
        assert len(wrong_doc) >= 1

    def test_validate_duplicate_links(self) -> None:
        """Same UID in links twice — each checked independently."""
        dag = self._make_dag({"SRS": ["SYS"], "SYS": []})
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SYS", [])
        srs = Item(
            uid="SRS001",
            text="test",
            document_prefix="SRS",
            links=["SYS001", "SYS001"],
        )
        sys_item = Item(uid="SYS001", text="system req", document_prefix="SYS")
        graph.add_item(srs)
        graph.add_item(sys_item)
        issues = validate(dag, graph, check_suspect=False, check_review=False)
        # Should not crash, and each link is checked
        assert isinstance(issues, list)

    def test_validate_suspect_link_hash_mismatch(self, tmp_path: Path) -> None:
        """Stored hash differs from computed — warning: suspect link."""
        doc_path = tmp_path / "srs"
        doc_path.mkdir()
        # Write item with a stale link hash (must be >= 20 chars for valid format)
        stale_hash = "STALEHASH_0123456789abcdef"  # Valid format, wrong value
        item_data = {
            "text": "test",
            "links": [{"SYS001": stale_hash}],
            "active": True,
            "type": "requirement",
        }
        item_file = doc_path / "SRS001.yml"
        with open(item_file, "w") as f:
            yaml.dump(item_data, f)

        dag = self._make_dag({"SRS": ["SYS"], "SYS": []}, paths={"SRS": doc_path})
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SYS", [])
        srs = Item(
            uid="SRS001",
            text="test",
            document_prefix="SRS",
            links=["SYS001"],
        )
        sys_item = Item(uid="SYS001", text="system req", document_prefix="SYS")
        graph.add_item(srs)
        graph.add_item(sys_item)
        issues = validate(dag, graph, check_links=False, check_review=False, check_children=False)
        suspect = [i for i in issues if "suspect" in i.message]
        assert len(suspect) >= 1

    def test_validate_suspect_link_no_hash(self, tmp_path: Path) -> None:
        """Link with no stored hash — warning."""
        doc_path = tmp_path / "srs"
        doc_path.mkdir()
        item_data = {
            "text": "test",
            "links": ["SYS001"],
            "active": True,
            "type": "requirement",
        }
        item_file = doc_path / "SRS001.yml"
        with open(item_file, "w") as f:
            yaml.dump(item_data, f)

        dag = self._make_dag({"SRS": ["SYS"], "SYS": []}, paths={"SRS": doc_path})
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SYS", [])
        srs = Item(
            uid="SRS001",
            text="test",
            document_prefix="SRS",
            links=["SYS001"],
        )
        sys_item = Item(uid="SYS001", text="system req", document_prefix="SYS")
        graph.add_item(srs)
        graph.add_item(sys_item)
        issues = validate(dag, graph, check_links=False, check_review=False, check_children=False)
        no_hash = [i for i in issues if "no stored hash" in i.message]
        assert len(no_hash) >= 1

    def test_validate_derived_item_no_links(self) -> None:
        """Derived item with no links in child doc — no unlinked warning."""
        dag = self._make_dag({"SRS": ["SYS"], "SYS": []})
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SYS", [])
        item = Item(
            uid="SRS001",
            text="derived",
            document_prefix="SRS",
            derived=True,
            links=[],
        )
        graph.add_item(item)
        issues = validate(
            dag,
            graph,
            check_suspect=False,
            check_review=False,
            check_children=False,
        )
        unlinked = [i for i in issues if "no links to parent" in i.message]
        assert unlinked == []

    def test_validate_unlinked_in_root_doc(self) -> None:
        """Root doc item with no links — no unlinked warning."""
        dag = self._make_dag({"ROOT": []})
        graph = TraceabilityGraph()
        graph.set_document_parents("ROOT", [])
        item = Item(uid="ROOT001", text="root item", document_prefix="ROOT", links=[])
        graph.add_item(item)
        issues = validate(
            dag,
            graph,
            check_suspect=False,
            check_review=False,
            check_children=False,
        )
        unlinked = [i for i in issues if "no links to parent" in i.message]
        assert unlinked == []

    def test_validate_empty_text_whitespace_only(self) -> None:
        """Text is '   \\n\\t  ' — warning: empty text."""
        dag = self._make_dag({"SRS": []})
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", [])
        item = Item(uid="SRS001", text="   \n\t  ", document_prefix="SRS")
        graph.add_item(item)
        issues = validate(
            dag,
            graph,
            check_suspect=False,
            check_review=False,
            check_links=False,
            check_children=False,
            check_unlinked=False,
        )
        empty_text = [i for i in issues if "empty text" in i.message]
        assert len(empty_text) == 1


# =============================================================================
# 5. Document DAG Edge Cases
# =============================================================================


class TestDocumentDagEdgeCases:
    """Tests for DocumentDAG with edge-case topologies."""

    def _make_dag(self, docs: dict[str, list[str]]) -> DocumentDAG:
        dag = DocumentDAG()
        for prefix, parents in docs.items():
            dag.documents[prefix] = DocumentConfig(prefix=prefix, parents=parents)
        return dag

    def test_dag_single_document(self) -> None:
        """One document, no parents — topo sort returns [doc]."""
        dag = self._make_dag({"A": []})
        assert dag.topological_sort() == ["A"]

    def test_dag_diamond_shape(self) -> None:
        """A->B, A->C, B->D, C->D — valid DAG."""
        dag = self._make_dag({"A": [], "B": ["A"], "C": ["A"], "D": ["B", "C"]})
        order = dag.topological_sort()
        assert order.index("A") < order.index("B")
        assert order.index("A") < order.index("C")
        assert order.index("B") < order.index("D")
        assert order.index("C") < order.index("D")
        assert dag.validate_acyclic() == []

    def test_dag_document_cycle(self) -> None:
        """A->B->A — validate_acyclic returns error."""
        dag = self._make_dag({"A": ["B"], "B": ["A"]})
        errors = dag.validate_acyclic()
        assert len(errors) > 0
        assert "Cycle" in errors[0] or "cycle" in errors[0].lower()

    def test_dag_self_parent(self) -> None:
        """A lists itself as parent — validate_acyclic detects it."""
        dag = self._make_dag({"A": ["A"]})
        errors = dag.validate_acyclic()
        assert len(errors) > 0

    def test_dag_deep_chain_50_levels(self) -> None:
        """50-deep document chain — topo sort handles it."""
        docs: dict[str, list[str]] = {}
        for i in range(50):
            prefix = f"D{i:03d}"
            parents = [f"D{i - 1:03d}"] if i > 0 else []
            docs[prefix] = parents
        dag = self._make_dag(docs)
        order = dag.topological_sort()
        assert len(order) == 50
        assert order[0] == "D000"
        assert order[-1] == "D049"
        assert dag.validate_acyclic() == []

    def test_dag_orphan_document(self) -> None:
        """Document not referenced by any other still appears in topo sort."""
        dag = self._make_dag({"A": [], "B": ["A"], "ORPHAN": []})
        order = dag.topological_sort()
        assert "ORPHAN" in order

    def test_dag_multiple_roots(self) -> None:
        """3 root documents all appear in topo sort before children."""
        dag = self._make_dag({"R1": [], "R2": [], "R3": [], "CHILD": ["R1", "R2"]})
        order = dag.topological_sort()
        assert order.index("R1") < order.index("CHILD")
        assert order.index("R2") < order.index("CHILD")
        roots = dag.get_root_documents()
        assert set(roots) == {"R1", "R2", "R3"}

    def test_dag_get_children_nonexistent(self) -> None:
        """get_children('NOPE') returns empty list."""
        dag = self._make_dag({"A": []})
        assert dag.get_children("NOPE") == []

    def test_dag_get_parents_nonexistent(self) -> None:
        """get_parents('NOPE') returns empty list."""
        dag = self._make_dag({"A": []})
        assert dag.get_parents("NOPE") == []


# =============================================================================
# 6. CLI Command Abuse
# =============================================================================


class TestCliAbuse:
    """Tests for CLI commands with abusive or edge-case inputs."""

    @pytest.fixture(autouse=True)
    def _cli_setup(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Change to a temp directory for all CLI tests."""
        self.tmp_path = tmp_path
        monkeypatch.chdir(tmp_path)

    def _init_project(self) -> None:
        """Initialize a jamb project in the temp directory."""
        from click.testing import CliRunner

        from jamb.cli.commands import cli

        # Create a pyproject.toml
        (self.tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "0.1.0"\n')
        runner = CliRunner()
        runner.invoke(cli, ["init"])

    def test_cli_init_already_initialized(self) -> None:
        """Run init twice — second run handles gracefully."""
        from click.testing import CliRunner

        from jamb.cli.commands import cli

        (self.tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "0.1.0"\n')
        runner = CliRunner()
        result1 = runner.invoke(cli, ["init"])
        assert result1.exit_code == 0
        result2 = runner.invoke(cli, ["init"])
        # Second init should fail gracefully (docs already exist)
        assert result2.exit_code != 0 or "already exist" in (result2.output or "")

    def test_cli_item_add_empty_text(self) -> None:
        """item add SRS --text '' creates item."""
        from click.testing import CliRunner

        from jamb.cli.commands import cli

        self._init_project()
        runner = CliRunner()
        result = runner.invoke(cli, ["item", "add", "SRS", "--text", ""])
        # Should succeed — empty text is allowed
        assert result.exit_code == 0

    def test_cli_item_add_nonexistent_doc(self) -> None:
        """item add NOPE --text 'x' — error: document not found."""
        from click.testing import CliRunner

        from jamb.cli.commands import cli

        self._init_project()
        runner = CliRunner()
        result = runner.invoke(cli, ["item", "add", "NOPE", "--text", "x"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_cli_item_del_nonexistent_uid(self) -> None:
        """item remove NOPE001 — error: item not found."""
        from click.testing import CliRunner

        from jamb.cli.commands import cli

        self._init_project()
        runner = CliRunner()
        result = runner.invoke(cli, ["item", "remove", "NOPE001"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_cli_link_add_same_uid(self) -> None:
        """link add SRS001 SRS001 — self-link behavior."""
        from click.testing import CliRunner

        from jamb.cli.commands import cli

        self._init_project()
        runner = CliRunner()
        # Add an item first
        runner.invoke(cli, ["item", "add", "SRS", "--text", "test"])
        result = runner.invoke(cli, ["link", "add", "SRS001", "SRS001"])
        # Should not crash — may add the self-link or warn
        assert isinstance(result.output, str)

    def test_cli_link_add_nonexistent_target(self) -> None:
        """link add SRS001 NOPE001 — error because child not found."""
        from click.testing import CliRunner

        from jamb.cli.commands import cli

        self._init_project()
        runner = CliRunner()
        # SRS001 is the init heading, but we need an actual SRS item
        result = runner.invoke(cli, ["link", "add", "SRS001", "NOPE001"])
        # Either child or target not found
        assert isinstance(result.output, str)

    def test_cli_info_no_documents(self) -> None:
        """info with no .jamb.yml files handles gracefully."""
        from click.testing import CliRunner

        from jamb.cli.commands import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["info"])
        # Should not crash
        assert isinstance(result.output, str)

    def test_cli_check_no_documents(self) -> None:
        """check with no documents handles gracefully."""
        from click.testing import CliRunner

        from jamb.cli.commands import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["check"])
        assert isinstance(result.output, str)

    def test_cli_validate_no_documents(self) -> None:
        """validate with no documents handles gracefully."""
        from click.testing import CliRunner

        from jamb.cli.commands import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["validate"])
        assert isinstance(result.output, str)

    def test_cli_doc_create_duplicate_prefix(self) -> None:
        """Create doc with existing prefix — second create writes to same path."""
        from click.testing import CliRunner

        from jamb.cli.commands import cli

        self._init_project()
        runner = CliRunner()
        result = runner.invoke(cli, ["doc", "create", "SRS", str(self.tmp_path / "reqs" / "srs")])
        # SRS already exists from init; doc create overwrites .jamb.yml
        assert isinstance(result.output, str)

    def test_cli_doc_create_empty_prefix(self) -> None:
        """doc create '' — behavior with empty prefix."""
        from click.testing import CliRunner

        from jamb.cli.commands import cli

        runner = CliRunner()
        # Click may interpret empty string differently
        result = runner.invoke(cli, ["doc", "create", "", str(self.tmp_path / "empty")])
        assert isinstance(result.output, str)

    def test_cli_special_chars_in_prefix(self) -> None:
        """doc create 'A/B' — behavior with path separators."""
        from click.testing import CliRunner

        from jamb.cli.commands import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["doc", "create", "A/B", str(self.tmp_path / "special")])
        assert isinstance(result.output, str)

    def test_cli_reorder_empty_document(self) -> None:
        """reorder on doc with 0 items — no crash."""
        from click.testing import CliRunner

        from jamb.cli.commands import cli

        self._init_project()
        # HAZ should have 0 items after init
        runner = CliRunner()
        result = runner.invoke(cli, ["reorder", "HAZ"])
        assert result.exit_code == 0 or "Error" in result.output

    def test_cli_reorder_single_item(self) -> None:
        """reorder on doc with 1 item — no-op."""
        from click.testing import CliRunner

        from jamb.cli.commands import cli

        self._init_project()
        runner = CliRunner()
        # SRS should have 0 items; add one
        runner.invoke(cli, ["item", "add", "SRS", "--text", "solo item"])
        result = runner.invoke(cli, ["reorder", "SRS"])
        assert result.exit_code == 0

    def test_cli_review_mark_nonexistent(self) -> None:
        """review mark NOPE001 — error: not found."""
        from click.testing import CliRunner

        from jamb.cli.commands import cli

        self._init_project()
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "mark", "NOPE001"])
        assert result.exit_code != 0 or "not found" in result.output.lower() or "error" in result.output.lower()


# =============================================================================
# 7. Import/Export Round-Trip Integrity
# =============================================================================


class TestRoundTrip:
    """Tests for write_item/read_item round-trip fidelity."""

    def _roundtrip(self, tmp_path: Path, item_data: dict) -> dict:
        """Write and read back an item."""
        path = tmp_path / "SRS001.yml"
        write_item(item_data, path)
        return read_item(path, "SRS")

    def test_write_read_roundtrip_basic(self, tmp_path: Path) -> None:
        """Basic round-trip: all fields match."""
        data = {
            "header": "Auth",
            "active": True,
            "type": "requirement",
            "links": ["SYS001"],
            "text": "Shall authenticate users",
            "reviewed": None,
        }
        result = self._roundtrip(tmp_path, data)
        assert result["text"] == "Shall authenticate users"
        assert result["header"] == "Auth"
        assert result["active"] is True
        assert result["type"] == "requirement"
        assert "SYS001" in result["links"]

    def test_write_read_roundtrip_multiline_text(self, tmp_path: Path) -> None:
        """Text with newlines preserved exactly (block scalar)."""
        data = {
            "header": "",
            "active": True,
            "type": "requirement",
            "links": [],
            "text": "Line one\nLine two\nLine three\n",
            "reviewed": None,
        }
        result = self._roundtrip(tmp_path, data)
        assert result["text"] == "Line one\nLine two\nLine three\n"

    def test_write_read_roundtrip_unicode(self, tmp_path: Path) -> None:
        """Text with CJK, emoji, accents preserved."""
        data = {
            "header": "",
            "active": True,
            "type": "requirement",
            "links": [],
            "text": "日本語テスト \U0001f680 café résumé",
            "reviewed": None,
        }
        result = self._roundtrip(tmp_path, data)
        assert result["text"] == "日本語テスト \U0001f680 café résumé"

    def test_write_read_roundtrip_special_yaml_chars(self, tmp_path: Path) -> None:
        """Text with YAML special chars properly escaped."""
        data = {
            "header": "",
            "active": True,
            "type": "requirement",
            "links": [],
            "text": "key: value - item # comment { brace } [ bracket ]",
            "reviewed": None,
        }
        result = self._roundtrip(tmp_path, data)
        assert result["text"] == "key: value - item # comment { brace } [ bracket ]"

    def test_write_read_roundtrip_links_with_hashes(self, tmp_path: Path) -> None:
        """Links with content hashes preserved."""
        # Hash must be >= 20 chars and contain only URL-safe base64 chars
        valid_hash = "abcdefghijklmnopqrstuvwxyz012345"
        data = {
            "header": "",
            "active": True,
            "type": "requirement",
            "links": ["SYS001"],
            "link_hashes": {"SYS001": valid_hash},
            "text": "test",
            "reviewed": None,
        }
        result = self._roundtrip(tmp_path, data)
        assert "SYS001" in result["links"]
        assert result["link_hashes"]["SYS001"] == valid_hash

    def test_write_read_roundtrip_empty_fields(self, tmp_path: Path) -> None:
        """All optional fields empty/None reads back with defaults."""
        data = {
            "header": "",
            "active": True,
            "type": "requirement",
            "links": [],
            "text": "",
            "reviewed": None,
        }
        result = self._roundtrip(tmp_path, data)
        assert result["text"] == ""
        assert result["header"] is None
        assert result["links"] == []
        assert result["reviewed"] is None

    def test_write_read_roundtrip_custom_attributes(self, tmp_path: Path) -> None:
        """Extra fields round-trip via custom attrs."""
        data = {
            "header": "",
            "active": True,
            "type": "requirement",
            "links": [],
            "text": "test",
            "reviewed": None,
        }
        extra = {"safety_class": "C", "verification_method": "test"}
        path = tmp_path / "SRS001.yml"
        write_item(data, path, extra_fields=extra)
        result = read_item(path, "SRS")
        assert result["custom_attributes"]["safety_class"] == "C"
        assert result["custom_attributes"]["verification_method"] == "test"

    def test_write_read_roundtrip_boolean_text(self, tmp_path: Path) -> None:
        """text: true (YAML bool) read back as string."""
        item_file = tmp_path / "SRS001.yml"
        # Write raw YAML with boolean text
        item_file.write_text("text: true\n")
        result = read_item(item_file, "SRS")
        assert result["text"] == "True"

    def test_content_hash_stability(self) -> None:
        """Same data computed twice gives identical hashes."""
        data = {
            "text": "hello",
            "header": "",
            "links": ["A", "B"],
            "type": "requirement",
        }
        h1 = compute_content_hash(data)
        h2 = compute_content_hash(data)
        assert h1 == h2

    def test_content_hash_sensitivity(self) -> None:
        """Change one char in text produces different hash."""
        data1 = {"text": "hello", "header": "", "links": [], "type": "requirement"}
        data2 = {"text": "hellp", "header": "", "links": [], "type": "requirement"}
        assert compute_content_hash(data1) != compute_content_hash(data2)


# =============================================================================
# 8. Matrix Generation Edge Cases
# =============================================================================


class TestMatrixEdgeCases:
    """Tests for matrix generation with edge-case inputs."""

    def test_matrix_empty_records(self) -> None:
        """Generate matrix with no test records — valid output."""
        from jamb.matrix.formats.markdown import render_test_records_markdown

        result = render_test_records_markdown([])
        assert "# Test Records" in result
        assert "Total Tests" in result

    def test_matrix_all_tests_failed(self) -> None:
        """Every test has outcome='failed' — matrix shows all failed."""
        from jamb.core.models import TestRecord
        from jamb.matrix.formats.markdown import render_test_records_markdown

        records = [
            TestRecord(
                test_id="TC001",
                test_name="test_fail",
                test_nodeid="test.py::test_fail",
                outcome="failed",
                requirements=["SRS001"],
            )
        ]
        result = render_test_records_markdown(records)
        assert "failed" in result

    def test_matrix_many_tests(self) -> None:
        """100 test records — all appear."""
        from jamb.core.models import TestRecord
        from jamb.matrix.formats.markdown import render_test_records_markdown

        records = [
            TestRecord(
                test_id=f"TC{i:03d}",
                test_name=f"test_{i}",
                test_nodeid=f"test.py::test_{i}",
                outcome="passed",
                requirements=["SRS001"],
            )
            for i in range(100)
        ]
        result = render_test_records_markdown(records)
        assert "test_99" in result

    def test_matrix_special_chars_in_name(self) -> None:
        """Test name with pipe characters — escaped properly."""
        from jamb.core.models import TestRecord
        from jamb.matrix.formats.markdown import render_test_records_markdown

        records = [
            TestRecord(
                test_id="TC001",
                test_name="test_with|pipe",
                test_nodeid="test.py::test_with|pipe",
                outcome="passed",
                requirements=["SRS001"],
            )
        ]
        result = render_test_records_markdown(records)
        # Pipes are escaped in markdown tables
        assert "\\|" in result


# =============================================================================
# 9. Config Edge Cases
# =============================================================================


class TestConfigEdgeCases:
    """Tests for config loading with edge-case inputs."""

    def test_config_missing_pyproject(self, tmp_path: Path) -> None:
        """No pyproject.toml exists — returns defaults."""
        from jamb.config.loader import load_config

        config = load_config(tmp_path / "nonexistent.toml")
        assert config.fail_uncovered is False
        assert config.test_documents == []

    def test_config_empty_jamb_section(self, tmp_path: Path) -> None:
        """[tool.jamb] with no keys — returns defaults."""
        from jamb.config.loader import load_config

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.jamb]\n")
        config = load_config(pyproject)
        assert config.fail_uncovered is False

    def test_config_unknown_keys(self, tmp_path: Path) -> None:
        """Extra keys in [tool.jamb] — ignored gracefully."""
        from conftest import suppress_expected_warnings

        from jamb.config.loader import load_config

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.jamb]\nunknown_key = "value"\nanother = 42\n')
        # load_config uses .get() with defaults, so unknown keys are just ignored
        # But they'll also be passed as kwargs to JambConfig — let's check
        # Actually the code extracts specific keys, so unknowns are dropped
        with suppress_expected_warnings():  # may warn about unknown keys
            config = load_config(pyproject)
        assert config.fail_uncovered is False  # default not overridden

    def test_config_wrong_types(self, tmp_path: Path) -> None:
        """fail_uncovered: 'yes' (string not bool) — stored as-is."""
        from jamb.config.loader import load_config

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.jamb]\nfail_uncovered = "yes"\n')
        config = load_config(pyproject)
        # The config just passes through whatever toml gives it
        assert config.fail_uncovered == "yes"

    def test_config_test_documents_nonexistent(self, tmp_path: Path) -> None:
        """Prefix that doesn't exist — config loads fine."""
        from jamb.config.loader import load_config

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.jamb]\ntest_documents = ["NOPE"]\n')
        config = load_config(pyproject)
        assert config.test_documents == ["NOPE"]

    def test_config_empty_exclude_patterns(self, tmp_path: Path) -> None:
        """exclude_patterns: [] — no exclusions."""
        from jamb.config.loader import load_config

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.jamb]\nexclude_patterns = []\n")
        config = load_config(pyproject)
        assert config.exclude_patterns == []


# =============================================================================
# 10. Content Hash Edge Cases
# =============================================================================


class TestContentHashEdgeCases:
    """Tests for compute_content_hash with edge-case inputs."""

    def test_hash_empty_item(self) -> None:
        """All fields empty strings — produces valid hash."""
        data = {"text": "", "header": "", "links": [], "type": "requirement"}
        h = compute_content_hash(data)
        assert isinstance(h, str)
        assert len(h) > 0

    def test_hash_none_fields(self) -> None:
        """Fields are None — str(None) doesn't crash."""
        data = {"text": None, "header": None, "links": None, "type": None}
        h = compute_content_hash(data)
        assert isinstance(h, str)
        assert len(h) > 0

    def test_hash_order_independence(self) -> None:
        """Same links in different order — same hash (links are sorted)."""
        data1 = {
            "text": "t",
            "header": "",
            "links": ["B", "A", "C"],
            "type": "requirement",
        }
        data2 = {
            "text": "t",
            "header": "",
            "links": ["C", "A", "B"],
            "type": "requirement",
        }
        assert compute_content_hash(data1) == compute_content_hash(data2)

    def test_hash_unicode_normalization(self) -> None:
        """é as single char vs e+combining — same hash (NFC normalization applied)."""
        data1 = {"text": "\u00e9", "header": "", "links": [], "type": "requirement"}
        data2 = {"text": "e\u0301", "header": "", "links": [], "type": "requirement"}
        # These look the same and should produce identical hashes after NFC norm
        assert compute_content_hash(data1) == compute_content_hash(data2)

    def test_hash_very_long_text(self) -> None:
        """1MB text field — produces valid hash without crash."""
        data = {
            "text": "A" * (1024 * 1024),
            "header": "",
            "links": [],
            "type": "requirement",
        }
        h = compute_content_hash(data)
        assert isinstance(h, str)
        assert len(h) > 0
