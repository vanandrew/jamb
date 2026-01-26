"""Tests for jamb trace command and TraceabilityGraph helper methods."""

from click.testing import CliRunner

from jamb.cli.commands import cli
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
        sys = Item(
            uid="SYS001", text="System req", document_prefix="SYS", links=["RC001"]
        )
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
        srs = Item(
            uid="SRS001", text="Req", document_prefix="SRS", links=["RC001", "SYS001"]
        )
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


# =============================================================================
# CLI trace command tests (using CliRunner with mocked graph)
# =============================================================================


def _build_test_graph() -> TraceabilityGraph:
    """Build a graph for CLI tests: RC <- SRS, with some gaps."""
    graph = TraceabilityGraph()

    rc1 = Item(
        uid="RC001",
        text="Vital Sign Validation",
        document_prefix="RC",
        header="Vital Sign Validation",
        links=[],
    )
    rc2 = Item(
        uid="RC002",
        text="Redundant Alert Pathways",
        document_prefix="RC",
        header="Redundant Alert Pathways",
        links=[],
    )
    rc3 = Item(
        uid="RC003",
        text="Covered control",
        document_prefix="RC",
        header="Covered Control",
        links=[],
    )

    srs1 = Item(
        uid="SRS001", text="Implements RC003", document_prefix="SRS", links=["RC003"]
    )
    srs2 = Item(uid="SRS002", text="Orphan SRS item", document_prefix="SRS", links=[])

    for item in [rc1, rc2, rc3, srs1, srs2]:
        graph.add_item(item)

    graph.set_document_parent("RC", None)
    graph.set_document_parent("SRS", "RC")

    return graph


def _mock_trace_setup(monkeypatch, graph=None):
    """Monkeypatch discover_tree and build_traceability_graph for CLI tests."""
    if graph is None:
        graph = _build_test_graph()

    monkeypatch.setattr(
        "jamb.doorstop.discovery.discover_tree",
        lambda root=None: None,
    )
    monkeypatch.setattr(
        "jamb.doorstop.reader.build_traceability_graph",
        lambda tree, **kwargs: graph,
    )
    return graph


class TestTraceHasChildren:
    """Tests for `jamb trace has-children`."""

    def test_reports_items_without_children(self, monkeypatch):
        _mock_trace_setup(monkeypatch)
        runner = CliRunner()

        result = runner.invoke(cli, ["trace", "has-children", "RC"])

        assert result.exit_code == 0
        assert "RC001" in result.output
        assert "RC002" in result.output
        assert "2 items failed check" in result.output

    def test_does_not_report_items_with_children(self, monkeypatch):
        _mock_trace_setup(monkeypatch)
        runner = CliRunner()

        result = runner.invoke(cli, ["trace", "has-children", "RC"])

        # RC003 has SRS001 as a child
        assert "RC003" not in result.output

    def test_error_flag_exits_nonzero(self, monkeypatch):
        _mock_trace_setup(monkeypatch)
        runner = CliRunner()

        result = runner.invoke(cli, ["trace", "has-children", "RC", "-e"])

        assert result.exit_code == 1

    def test_all_pass_exits_zero(self, monkeypatch):
        graph = TraceabilityGraph()
        parent = Item(uid="A001", text="A", document_prefix="A", links=[])
        child = Item(uid="B001", text="B", document_prefix="B", links=["A001"])
        graph.add_item(parent)
        graph.add_item(child)
        graph.set_document_parent("A", None)
        graph.set_document_parent("B", "A")
        _mock_trace_setup(monkeypatch, graph)

        runner = CliRunner()
        result = runner.invoke(cli, ["trace", "has-children", "A"])

        assert result.exit_code == 0
        assert "All items passed" in result.output


class TestTraceHasParents:
    """Tests for `jamb trace has-parents`."""

    def test_reports_items_without_parents(self, monkeypatch):
        _mock_trace_setup(monkeypatch)
        runner = CliRunner()

        result = runner.invoke(cli, ["trace", "has-parents", "SRS"])

        assert "SRS002" in result.output
        assert "1 items failed check" in result.output

    def test_does_not_report_items_with_parents(self, monkeypatch):
        _mock_trace_setup(monkeypatch)
        runner = CliRunner()

        result = runner.invoke(cli, ["trace", "has-parents", "SRS"])

        assert "SRS001" not in result.output

    def test_error_flag_exits_nonzero(self, monkeypatch):
        _mock_trace_setup(monkeypatch)
        runner = CliRunner()

        result = runner.invoke(cli, ["trace", "has-parents", "SRS", "-e"])

        assert result.exit_code == 1


class TestTraceLinksTo:
    """Tests for `jamb trace links-to`."""

    def test_reports_items_not_linking_to_target(self, monkeypatch):
        _mock_trace_setup(monkeypatch)
        runner = CliRunner()

        result = runner.invoke(cli, ["trace", "links-to", "SRS", "RC"])

        assert "SRS002" in result.output
        assert "does not link to any item in RC" in result.output

    def test_does_not_report_items_linking_to_target(self, monkeypatch):
        _mock_trace_setup(monkeypatch)
        runner = CliRunner()

        result = runner.invoke(cli, ["trace", "links-to", "SRS", "RC"])

        assert "SRS001" not in result.output

    def test_error_flag_exits_nonzero(self, monkeypatch):
        _mock_trace_setup(monkeypatch)
        runner = CliRunner()

        result = runner.invoke(cli, ["trace", "links-to", "SRS", "RC", "-e"])

        assert result.exit_code == 1


class TestTraceOneToOne:
    """Tests for `jamb trace one-to-one`."""

    def test_reports_failures_both_directions(self, monkeypatch):
        _mock_trace_setup(monkeypatch)
        runner = CliRunner()

        result = runner.invoke(cli, ["trace", "one-to-one", "RC", "SRS"])

        # RC001, RC002 have no children in SRS
        assert "RC001" in result.output
        assert "RC002" in result.output
        # SRS002 doesn't link to any RC item
        assert "SRS002" in result.output
        assert result.exit_code == 0

    def test_perfect_one_to_one(self, monkeypatch):
        graph = TraceabilityGraph()
        a1 = Item(uid="A001", text="A1", document_prefix="A", links=[])
        b1 = Item(uid="B001", text="B1", document_prefix="B", links=["A001"])
        graph.add_item(a1)
        graph.add_item(b1)
        graph.set_document_parent("A", None)
        graph.set_document_parent("B", "A")
        _mock_trace_setup(monkeypatch, graph)

        runner = CliRunner()
        result = runner.invoke(cli, ["trace", "one-to-one", "A", "B"])

        assert result.exit_code == 0
        assert "All items passed" in result.output

    def test_reports_multiple_children(self, monkeypatch):
        graph = TraceabilityGraph()
        a1 = Item(uid="A001", text="A1", document_prefix="A", links=[])
        b1 = Item(uid="B001", text="B1", document_prefix="B", links=["A001"])
        b2 = Item(uid="B002", text="B2", document_prefix="B", links=["A001"])
        graph.add_item(a1)
        graph.add_item(b1)
        graph.add_item(b2)
        graph.set_document_parent("A", None)
        graph.set_document_parent("B", "A")
        _mock_trace_setup(monkeypatch, graph)

        runner = CliRunner()
        result = runner.invoke(cli, ["trace", "one-to-one", "A", "B"])

        assert "A001" in result.output
        assert "2 children" in result.output

    def test_error_flag_exits_nonzero(self, monkeypatch):
        _mock_trace_setup(monkeypatch)
        runner = CliRunner()

        result = runner.invoke(cli, ["trace", "one-to-one", "RC", "SRS", "-e"])

        assert result.exit_code == 1

    def test_skips_inactive_items(self, monkeypatch):
        graph = TraceabilityGraph()
        a1 = Item(uid="A001", text="A1", document_prefix="A", active=False, links=[])
        b1 = Item(uid="B001", text="B1", document_prefix="B", links=[])
        graph.add_item(a1)
        graph.add_item(b1)
        graph.set_document_parent("A", None)
        graph.set_document_parent("B", "A")
        _mock_trace_setup(monkeypatch, graph)

        runner = CliRunner()
        result = runner.invoke(cli, ["trace", "one-to-one", "A", "B"])

        # A001 is inactive, should not be checked
        assert "A001" not in result.output

    def test_skips_non_normative_items(self, monkeypatch):
        graph = TraceabilityGraph()
        a1 = Item(uid="A001", text="A1", document_prefix="A", normative=False, links=[])
        graph.add_item(a1)
        graph.set_document_parent("A", None)
        graph.set_document_parent("B", "A")
        _mock_trace_setup(monkeypatch, graph)

        runner = CliRunner()
        result = runner.invoke(cli, ["trace", "one-to-one", "A", "B"])

        assert "A001" not in result.output
