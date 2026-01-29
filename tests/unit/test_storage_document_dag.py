"""Tests for jamb.storage.document_dag module."""

from jamb.storage.document_config import DocumentConfig
from jamb.storage.document_dag import DocumentDAG


class TestDocumentDAG:
    def _make_dag(self):
        dag = DocumentDAG()
        dag.documents["PRJ"] = DocumentConfig(prefix="PRJ")
        dag.documents["UN"] = DocumentConfig(prefix="UN", parents=["PRJ"])
        dag.documents["SYS"] = DocumentConfig(prefix="SYS", parents=["UN"])
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=["SYS"])
        return dag

    def test_get_parents(self):
        dag = self._make_dag()
        assert dag.get_parents("SRS") == ["SYS"]
        assert dag.get_parents("PRJ") == []

    def test_get_parents_missing(self):
        dag = self._make_dag()
        assert dag.get_parents("NONEXISTENT") == []

    def test_get_children(self):
        dag = self._make_dag()
        assert dag.get_children("PRJ") == ["UN"]
        assert dag.get_children("UN") == ["SYS"]
        assert dag.get_children("SRS") == []

    def test_get_root_documents(self):
        dag = self._make_dag()
        assert dag.get_root_documents() == ["PRJ"]

    def test_get_leaf_documents(self):
        dag = self._make_dag()
        assert dag.get_leaf_documents() == ["SRS"]

    def test_topological_sort(self):
        dag = self._make_dag()
        order = dag.topological_sort()
        assert order.index("PRJ") < order.index("UN")
        assert order.index("UN") < order.index("SYS")
        assert order.index("SYS") < order.index("SRS")

    def test_validate_acyclic_no_cycles(self):
        dag = self._make_dag()
        errors = dag.validate_acyclic()
        assert errors == []

    def test_validate_acyclic_with_cycle(self):
        dag = DocumentDAG()
        dag.documents["A"] = DocumentConfig(prefix="A", parents=["B"])
        dag.documents["B"] = DocumentConfig(prefix="B", parents=["A"])
        errors = dag.validate_acyclic()
        assert len(errors) == 1
        assert "Cycle" in errors[0]

    def test_multi_parent_dag(self):
        dag = DocumentDAG()
        dag.documents["PRJ"] = DocumentConfig(prefix="PRJ")
        dag.documents["UN"] = DocumentConfig(prefix="UN", parents=["PRJ"])
        dag.documents["HAZ"] = DocumentConfig(prefix="HAZ", parents=["PRJ"])
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=["UN", "HAZ"])

        assert set(dag.get_children("PRJ")) == {"UN", "HAZ"}
        assert dag.get_parents("SRS") == ["UN", "HAZ"]
        order = dag.topological_sort()
        assert order.index("PRJ") < order.index("UN")
        assert order.index("PRJ") < order.index("HAZ")
        assert order.index("UN") < order.index("SRS")
        assert order.index("HAZ") < order.index("SRS")

    def test_topological_sort_parent_referencing_nonexistent(self):
        """3a: Doc with parent not in documents raises ValueError."""
        import pytest

        dag = DocumentDAG()
        dag.documents["A"] = DocumentConfig(prefix="A", parents=["NONEXIST"])
        with pytest.raises(ValueError, match="missing parents"):
            dag.topological_sort()

    def test_validate_acyclic_self_reference(self):
        """3b: Self-referencing document (A.parents = ['A']) is a cycle."""
        dag = DocumentDAG()
        dag.documents["A"] = DocumentConfig(prefix="A", parents=["A"])
        errors = dag.validate_acyclic()
        assert len(errors) == 1
        assert "A" in errors[0]

    def test_topological_sort_single_isolated_document(self):
        """3c: Single isolated document (no parents, no children) appears in sort."""
        dag = DocumentDAG()
        dag.documents["SOLO"] = DocumentConfig(prefix="SOLO")
        order = dag.topological_sort()
        assert order == ["SOLO"]

    def test_validate_acyclic_three_node_cycle(self):
        """3d: 3-node cycle A→B→C→A is detected."""
        dag = DocumentDAG()
        dag.documents["A"] = DocumentConfig(prefix="A", parents=["C"])
        dag.documents["B"] = DocumentConfig(prefix="B", parents=["A"])
        dag.documents["C"] = DocumentConfig(prefix="C", parents=["B"])
        errors = dag.validate_acyclic()
        assert len(errors) == 1
        assert "Cycle" in errors[0]
        for node in ["A", "B", "C"]:
            assert node in errors[0]

    def test_get_leaf_documents_all_parents(self):
        """Mutual parent cycle means no leaves; assert empty list."""
        dag = DocumentDAG()
        dag.documents["A"] = DocumentConfig(prefix="A", parents=["B"])
        dag.documents["B"] = DocumentConfig(prefix="B", parents=["A"])
        # Both A and B are parents of each other, so neither is a leaf
        leaves = dag.get_leaf_documents()
        assert leaves == []

    def test_topological_sort_2node_cycle_with_acyclic(self):
        """Acyclic node sorted first, cycle participants appended."""
        dag = DocumentDAG()
        dag.documents["ROOT"] = DocumentConfig(prefix="ROOT")
        dag.documents["A"] = DocumentConfig(prefix="A", parents=["B"])
        dag.documents["B"] = DocumentConfig(prefix="B", parents=["A"])
        order = dag.topological_sort()
        # ROOT has no parents, so it should come first
        assert order[0] == "ROOT"
        # A and B are in a cycle, they should both be in the result
        assert "A" in order
        assert "B" in order
        assert order.index("ROOT") < order.index("A")
        assert order.index("ROOT") < order.index("B")
