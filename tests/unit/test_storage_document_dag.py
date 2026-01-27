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
