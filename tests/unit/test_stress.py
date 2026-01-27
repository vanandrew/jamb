"""Stress and scale tests for jamb."""

from pathlib import Path

import yaml

from jamb.core.models import Item, TraceabilityGraph
from jamb.storage.document_config import DocumentConfig
from jamb.storage.document_dag import DocumentDAG
from jamb.storage.items import read_document_items, write_item


class TestStress:
    def test_read_500_items(self, tmp_path):
        """Document with 500 items reads correctly."""
        doc_dir = tmp_path / "srs"
        doc_dir.mkdir()
        settings = {"prefix": "SRS", "digits": 4, "sep": ""}
        (doc_dir / ".jamb.yml").write_text(yaml.dump({"settings": settings}))

        for i in range(1, 501):
            uid = f"SRS{i:04d}"
            item_data = {
                "text": f"Requirement {i}",
                "active": True,
                "type": "requirement",
                "links": [],
                "header": "",
                "reviewed": None,
            }
            write_item(item_data, doc_dir / f"{uid}.yml")

        items = read_document_items(doc_dir, "SRS", sep="")
        assert len(items) == 500

    def test_topological_sort_8_levels(self):
        """8-level deep DAG sorts correctly."""
        dag = DocumentDAG()
        prefixes = [f"L{i}" for i in range(8)]
        for i, p in enumerate(prefixes):
            parents = [prefixes[i - 1]] if i > 0 else []
            dag.documents[p] = DocumentConfig(prefix=p, parents=parents, digits=3)
            dag.document_paths[p] = Path(f"/fake/{p.lower()}")

        result = dag.topological_sort()
        assert len(result) == 8
        # Each level should come after its parent
        for i in range(1, 8):
            assert result.index(prefixes[i]) > result.index(prefixes[i - 1])

    def test_wide_dag_12_siblings(self):
        """DAG with 12 sibling documents handles correctly."""
        dag = DocumentDAG()
        dag.documents["ROOT"] = DocumentConfig(prefix="ROOT", parents=[], digits=3)
        dag.document_paths["ROOT"] = Path("/fake/root")

        for i in range(12):
            p = f"CHILD{i:02d}"
            dag.documents[p] = DocumentConfig(prefix=p, parents=["ROOT"], digits=3)
            dag.document_paths[p] = Path(f"/fake/{p.lower()}")

        result = dag.topological_sort()
        assert len(result) == 13  # ROOT + 12 children
        assert result[0] == "ROOT"
        children = dag.get_children("ROOT")
        assert len(children) == 12

    def test_graph_with_many_items(self):
        """TraceabilityGraph with 500 items across 5 documents."""
        graph = TraceabilityGraph()

        prefixes = ["PRJ", "UN", "SYS", "SRS", "UT"]
        for p in prefixes:
            graph.set_document_parents(p, [])

        for i in range(500):
            prefix = prefixes[i % 5]
            uid = f"{prefix}{i:04d}"
            item = Item(uid=uid, text=f"Item {i}", document_prefix=prefix)
            graph.add_item(item)

        assert len(graph.items) == 500
        for p in prefixes:
            items = graph.get_items_by_document(p)
            assert len(items) == 100
