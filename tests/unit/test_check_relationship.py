"""Tests for TraceabilityGraph helper methods."""

from jamb.core.models import Item, TraceabilityGraph

# =============================================================================
# TraceabilityGraph helper method tests
# =============================================================================


class TestGetChildrenFromDocument:
    """Tests for TraceabilityGraph.get_children_from_document."""

    def test_returns_children_in_specified_document(self):
        graph = TraceabilityGraph()
        rc = Item(uid="RC001", text="Risk control", document_prefix="RC", links=[])
        srs = Item(
            uid="SRS001",
            text="Implements RC001",
            document_prefix="SRS",
            links=["RC001"],
        )
        graph.add_item(rc)
        graph.add_item(srs)

        children = graph.get_children_from_document("RC001", "SRS")

        assert len(children) == 1
        assert children[0].uid == "SRS001"

    def test_excludes_children_from_other_documents(self):
        graph = TraceabilityGraph()
        rc = Item(uid="RC001", text="Risk control", document_prefix="RC", links=[])
        srs = Item(
            uid="SRS001",
            text="Implements RC001",
            document_prefix="SRS",
            links=["RC001"],
        )
        sys = Item(uid="SYS001", text="System req", document_prefix="SYS", links=["RC001"])
        graph.add_item(rc)
        graph.add_item(srs)
        graph.add_item(sys)

        children = graph.get_children_from_document("RC001", "SRS")

        assert len(children) == 1
        assert children[0].uid == "SRS001"

    def test_returns_empty_when_no_children(self):
        graph = TraceabilityGraph()
        rc = Item(uid="RC001", text="Risk control", document_prefix="RC", links=[])
        graph.add_item(rc)

        children = graph.get_children_from_document("RC001", "SRS")

        assert children == []

    def test_returns_empty_for_unknown_uid(self):
        graph = TraceabilityGraph()

        children = graph.get_children_from_document("NOPE", "SRS")

        assert children == []

    def test_returns_multiple_children(self):
        graph = TraceabilityGraph()
        rc = Item(uid="RC001", text="Risk control", document_prefix="RC", links=[])
        srs1 = Item(uid="SRS001", text="Req 1", document_prefix="SRS", links=["RC001"])
        srs2 = Item(uid="SRS002", text="Req 2", document_prefix="SRS", links=["RC001"])
        graph.add_item(rc)
        graph.add_item(srs1)
        graph.add_item(srs2)

        children = graph.get_children_from_document("RC001", "SRS")

        assert len(children) == 2
        uids = {c.uid for c in children}
        assert uids == {"SRS001", "SRS002"}


class TestGetParentsFromDocument:
    """Tests for TraceabilityGraph.get_parents_from_document."""

    def test_returns_parents_in_specified_document(self):
        graph = TraceabilityGraph()
        rc = Item(uid="RC001", text="Risk control", document_prefix="RC", links=[])
        srs = Item(
            uid="SRS001",
            text="Implements RC001",
            document_prefix="SRS",
            links=["RC001"],
        )
        graph.add_item(rc)
        graph.add_item(srs)

        parents = graph.get_parents_from_document("SRS001", "RC")

        assert len(parents) == 1
        assert parents[0].uid == "RC001"

    def test_excludes_parents_from_other_documents(self):
        graph = TraceabilityGraph()
        rc = Item(uid="RC001", text="Risk control", document_prefix="RC", links=[])
        sys = Item(uid="SYS001", text="System req", document_prefix="SYS", links=[])
        srs = Item(uid="SRS001", text="Req", document_prefix="SRS", links=["RC001", "SYS001"])
        graph.add_item(rc)
        graph.add_item(sys)
        graph.add_item(srs)

        parents = graph.get_parents_from_document("SRS001", "RC")

        assert len(parents) == 1
        assert parents[0].uid == "RC001"

    def test_returns_empty_when_no_parents(self):
        graph = TraceabilityGraph()
        rc = Item(uid="RC001", text="Risk control", document_prefix="RC", links=[])
        graph.add_item(rc)

        parents = graph.get_parents_from_document("RC001", "SRS")

        assert parents == []

    def test_returns_empty_for_unknown_uid(self):
        graph = TraceabilityGraph()

        parents = graph.get_parents_from_document("NOPE", "RC")

        assert parents == []
