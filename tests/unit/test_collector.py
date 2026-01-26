"""Tests for jamb.pytest_plugin.collector module."""

from unittest.mock import MagicMock, patch

import pytest

from jamb.core.models import Item, ItemCoverage, LinkedTest, TraceabilityGraph
from jamb.pytest_plugin.collector import RequirementCollector


@pytest.fixture
def mock_pytest_config():
    """Mock pytest config for RequirementCollector tests."""
    config = MagicMock()
    config.option.jamb = True
    config.option.jamb_documents = None
    config.option.jamb_fail_uncovered = False
    config.option.jamb_matrix = None
    config.option.jamb_matrix_format = "html"
    return config


@pytest.fixture
def mock_graph():
    """Create a mock TraceabilityGraph with test items."""
    graph = TraceabilityGraph()
    item1 = Item(
        uid="SRS001",
        text="Requirement 1",
        document_prefix="SRS",
        active=True,
        normative=True,
    )
    item2 = Item(
        uid="SRS002",
        text="Requirement 2",
        document_prefix="SRS",
        active=True,
        normative=True,
    )
    item3 = Item(
        uid="SRS003",
        text="Inactive requirement",
        document_prefix="SRS",
        active=False,
        normative=True,
    )
    graph.add_item(item1)
    graph.add_item(item2)
    graph.add_item(item3)
    graph.set_document_parent("SRS", None)
    return graph


class TestRequirementCollectorInit:
    """Tests for RequirementCollector initialization."""

    @patch("jamb.pytest_plugin.collector.discover_tree")
    @patch("jamb.pytest_plugin.collector.build_traceability_graph")
    def test_collector_init_loads_doorstop(
        self, mock_build_graph, mock_discover, mock_pytest_config, mock_graph
    ):
        """Test collector initialization loads doorstop tree."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph

        collector = RequirementCollector(mock_pytest_config)

        assert collector.graph is not None
        assert len(collector.graph.items) == 3
        mock_discover.assert_called_once()
        mock_build_graph.assert_called_once()

    @patch("jamb.pytest_plugin.collector.discover_tree")
    def test_collector_init_handles_missing_doorstop(
        self, mock_discover, mock_pytest_config
    ):
        """Test collector handles missing doorstop gracefully."""
        mock_discover.side_effect = Exception("No doorstop tree found")

        with pytest.warns(UserWarning, match="Could not load doorstop tree"):
            collector = RequirementCollector(mock_pytest_config)

        # Should create empty graph on error
        assert collector.graph is not None
        assert len(collector.graph.items) == 0

    @patch("jamb.pytest_plugin.collector.discover_tree")
    @patch("jamb.pytest_plugin.collector.build_traceability_graph")
    def test_collector_init_empty_test_links(
        self, mock_build_graph, mock_discover, mock_pytest_config
    ):
        """Test collector initializes with empty test links."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = TraceabilityGraph()

        collector = RequirementCollector(mock_pytest_config)

        assert collector.test_links == []
        assert collector.unknown_items == set()


class TestGetTestDocuments:
    """Tests for _get_test_documents method."""

    @patch("jamb.pytest_plugin.collector.discover_tree")
    @patch("jamb.pytest_plugin.collector.build_traceability_graph")
    def test_get_test_documents_from_cli_option(
        self, mock_build_graph, mock_discover, mock_graph
    ):
        """Test _get_test_documents uses CLI option first."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = "SRS, SYS"
        config.option.jamb_fail_uncovered = False
        config.option.jamb_matrix = None
        config.option.jamb_matrix_format = "html"

        collector = RequirementCollector(config)
        docs = collector._get_test_documents()

        assert docs == ["SRS", "SYS"]

    @patch("jamb.pytest_plugin.collector.discover_tree")
    @patch("jamb.pytest_plugin.collector.build_traceability_graph")
    @patch("jamb.pytest_plugin.collector.load_config")
    def test_get_test_documents_from_config(
        self, mock_load_config, mock_build_graph, mock_discover, mock_graph
    ):
        """Test _get_test_documents uses config when no CLI option."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph

        mock_config = MagicMock()
        mock_config.test_documents = ["UT", "IT"]
        mock_load_config.return_value = mock_config

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        docs = collector._get_test_documents()

        assert docs == ["UT", "IT"]

    @patch("jamb.pytest_plugin.collector.discover_tree")
    @patch("jamb.pytest_plugin.collector.build_traceability_graph")
    @patch("jamb.pytest_plugin.collector.load_config")
    def test_get_test_documents_defaults_to_leaf_docs(
        self, mock_load_config, mock_build_graph, mock_discover, mock_graph
    ):
        """Test _get_test_documents uses leaf documents as default."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph

        mock_config = MagicMock()
        mock_config.test_documents = []
        mock_load_config.return_value = mock_config

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        docs = collector._get_test_documents()

        # SRS is the only document (leaf)
        assert "SRS" in docs


class TestGetCoverage:
    """Tests for get_coverage method."""

    @patch("jamb.pytest_plugin.collector.discover_tree")
    @patch("jamb.pytest_plugin.collector.build_traceability_graph")
    def test_get_coverage_returns_empty_when_no_graph(
        self, mock_build_graph, mock_discover, mock_pytest_config
    ):
        """Test get_coverage returns empty dict when graph loading failed."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = TraceabilityGraph()

        collector = RequirementCollector(mock_pytest_config)
        collector.graph = None  # Simulate failed graph loading

        coverage = collector.get_coverage()

        assert coverage == {}

    @patch("jamb.pytest_plugin.collector.discover_tree")
    @patch("jamb.pytest_plugin.collector.build_traceability_graph")
    @patch("jamb.pytest_plugin.collector.load_config")
    def test_get_coverage_builds_coverage_for_test_docs(
        self, mock_load_config, mock_build_graph, mock_discover, mock_graph
    ):
        """Test get_coverage builds coverage dict correctly."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph

        mock_config = MagicMock()
        mock_config.test_documents = ["SRS"]
        mock_load_config.return_value = mock_config

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        # Add a test link
        collector.test_links.append(
            LinkedTest(test_nodeid="test.py::test_foo", item_uid="SRS001")
        )

        coverage = collector.get_coverage()

        assert "SRS001" in coverage
        assert coverage["SRS001"].is_covered is True
        assert "SRS002" in coverage
        assert coverage["SRS002"].is_covered is False


class TestAllTestItemsCovered:
    """Tests for all_test_items_covered method."""

    @patch("jamb.pytest_plugin.collector.discover_tree")
    @patch("jamb.pytest_plugin.collector.build_traceability_graph")
    @patch("jamb.pytest_plugin.collector.load_config")
    def test_all_test_items_covered_true_when_all_covered(
        self, mock_load_config, mock_build_graph, mock_discover
    ):
        """Test all_test_items_covered returns True when all covered."""
        graph = TraceabilityGraph()
        item = Item(
            uid="SRS001",
            text="Requirement",
            document_prefix="SRS",
            active=True,
            normative=True,
        )
        graph.add_item(item)
        graph.set_document_parent("SRS", None)

        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = graph

        mock_config = MagicMock()
        mock_config.test_documents = ["SRS"]
        mock_load_config.return_value = mock_config

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        collector.test_links.append(
            LinkedTest(test_nodeid="test.py::test_foo", item_uid="SRS001")
        )

        assert collector.all_test_items_covered() is True

    @patch("jamb.pytest_plugin.collector.discover_tree")
    @patch("jamb.pytest_plugin.collector.build_traceability_graph")
    @patch("jamb.pytest_plugin.collector.load_config")
    def test_all_test_items_covered_false_when_uncovered(
        self, mock_load_config, mock_build_graph, mock_discover, mock_graph
    ):
        """Test all_test_items_covered returns False for uncovered items."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph

        mock_config = MagicMock()
        mock_config.test_documents = ["SRS"]
        mock_load_config.return_value = mock_config

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        # No test links added, so SRS001 and SRS002 are uncovered

        assert collector.all_test_items_covered() is False

    @patch("jamb.pytest_plugin.collector.discover_tree")
    @patch("jamb.pytest_plugin.collector.build_traceability_graph")
    @patch("jamb.pytest_plugin.collector.load_config")
    def test_all_test_items_covered_ignores_inactive(
        self, mock_load_config, mock_build_graph, mock_discover, mock_graph
    ):
        """Test all_test_items_covered ignores inactive items."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph

        mock_config = MagicMock()
        mock_config.test_documents = ["SRS"]
        mock_load_config.return_value = mock_config

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        # Cover only active items
        collector.test_links.append(
            LinkedTest(test_nodeid="test.py::test_1", item_uid="SRS001")
        )
        collector.test_links.append(
            LinkedTest(test_nodeid="test.py::test_2", item_uid="SRS002")
        )
        # SRS003 is inactive, should be ignored

        assert collector.all_test_items_covered() is True

    @patch("jamb.pytest_plugin.collector.discover_tree")
    @patch("jamb.pytest_plugin.collector.build_traceability_graph")
    @patch("jamb.pytest_plugin.collector.load_config")
    def test_all_test_items_covered_ignores_non_normative(
        self, mock_load_config, mock_build_graph, mock_discover
    ):
        """Test all_test_items_covered ignores non-normative items."""
        graph = TraceabilityGraph()
        normative_item = Item(
            uid="SRS001",
            text="Normative requirement",
            document_prefix="SRS",
            active=True,
            normative=True,
        )
        informative_item = Item(
            uid="SRS002",
            text="Informative note",
            document_prefix="SRS",
            active=True,
            normative=False,
        )
        graph.add_item(normative_item)
        graph.add_item(informative_item)
        graph.set_document_parent("SRS", None)

        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = graph

        mock_config = MagicMock()
        mock_config.test_documents = ["SRS"]
        mock_load_config.return_value = mock_config

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        # Only cover normative item
        collector.test_links.append(
            LinkedTest(test_nodeid="test.py::test_1", item_uid="SRS001")
        )
        # SRS002 is non-normative, should be ignored

        assert collector.all_test_items_covered() is True


class TestGenerateMatrix:
    """Tests for generate_matrix method."""

    @patch("jamb.pytest_plugin.collector.discover_tree")
    @patch("jamb.pytest_plugin.collector.build_traceability_graph")
    @patch("jamb.pytest_plugin.collector.load_config")
    @patch("jamb.matrix.generator.generate_matrix")
    def test_generate_matrix_calls_generator(
        self,
        mock_generate,
        mock_load_config,
        mock_build_graph,
        mock_discover,
        mock_graph,
    ):
        """Test generate_matrix calls the matrix generator."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph

        mock_config = MagicMock()
        mock_config.test_documents = ["SRS"]
        mock_load_config.return_value = mock_config

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        collector.generate_matrix("output.html", "html")

        mock_generate.assert_called_once()
        call_args = mock_generate.call_args
        assert call_args[0][2] == "output.html"
        assert call_args[0][3] == "html"
        assert "trace_to_ignore" in call_args[1]

    @patch("jamb.pytest_plugin.collector.discover_tree")
    @patch("jamb.pytest_plugin.collector.build_traceability_graph")
    @patch("jamb.pytest_plugin.collector.load_config")
    @patch("jamb.matrix.generator.generate_matrix")
    def test_generate_matrix_passes_trace_to_ignore(
        self,
        mock_generate,
        mock_load_config,
        mock_build_graph,
        mock_discover,
        mock_graph,
    ):
        """Test generate_matrix passes trace_to_ignore from config."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph

        mock_config = MagicMock()
        mock_config.test_documents = ["SRS"]
        mock_config.trace_to_ignore = ["PRJ", "UN"]
        mock_load_config.return_value = mock_config

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        collector.generate_matrix("output.html", "html")

        mock_generate.assert_called_once()
        call_args = mock_generate.call_args
        assert call_args[1]["trace_to_ignore"] == {"PRJ", "UN"}


class TestPytestCollectionModifyItems:
    """Tests for pytest_collection_modifyitems hook."""

    @patch("jamb.pytest_plugin.collector.discover_tree")
    @patch("jamb.pytest_plugin.collector.build_traceability_graph")
    @patch("jamb.pytest_plugin.collector.get_requirement_markers")
    def test_collection_adds_test_links(
        self, mock_get_markers, mock_build_graph, mock_discover, mock_graph
    ):
        """Test collection hook adds test links for requirement markers."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph

        # Mock a pytest item
        mock_item = MagicMock()
        mock_item.nodeid = "test_example.py::test_something"
        mock_get_markers.return_value = ["SRS001", "SRS002"]

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)

        # Execute the hook
        gen = collector.pytest_collection_modifyitems([mock_item])
        next(gen)  # Resume after yield
        try:
            next(gen)
        except StopIteration:
            pass

        assert len(collector.test_links) == 2
        assert collector.test_links[0].item_uid == "SRS001"
        assert collector.test_links[1].item_uid == "SRS002"

    @patch("jamb.pytest_plugin.collector.discover_tree")
    @patch("jamb.pytest_plugin.collector.build_traceability_graph")
    @patch("jamb.pytest_plugin.collector.get_requirement_markers")
    def test_collection_tracks_unknown_items(
        self, mock_get_markers, mock_build_graph, mock_discover, mock_graph
    ):
        """Test collection hook tracks unknown requirement UIDs."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph

        mock_item = MagicMock()
        mock_item.nodeid = "test.py::test_unknown"
        mock_get_markers.return_value = ["UNKNOWN001"]  # Not in graph

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)

        gen = collector.pytest_collection_modifyitems([mock_item])
        next(gen)
        try:
            next(gen)
        except StopIteration:
            pass

        assert "UNKNOWN001" in collector.unknown_items


class TestPytestRunTestMakeReport:
    """Tests for pytest_runtest_makereport hook."""

    @patch("jamb.pytest_plugin.collector.discover_tree")
    @patch("jamb.pytest_plugin.collector.build_traceability_graph")
    def test_makereport_updates_outcome_on_pass(
        self, mock_build_graph, mock_discover, mock_graph
    ):
        """Test makereport hook updates test outcome on pass."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        collector.test_links.append(
            LinkedTest(test_nodeid="test.py::test_pass", item_uid="SRS001")
        )

        # Mock pytest item and call
        mock_item = MagicMock()
        mock_item.nodeid = "test.py::test_pass"
        mock_item.stash = {}

        mock_call = MagicMock()

        # Mock report
        mock_report = MagicMock()
        mock_report.when = "call"
        mock_report.outcome = "passed"
        mock_report.failed = False
        mock_report.skipped = False

        mock_outcome = MagicMock()
        mock_outcome.get_result.return_value = mock_report

        # Execute hook
        gen = collector.pytest_runtest_makereport(mock_item, mock_call)
        next(gen)
        try:
            gen.send(mock_outcome)
        except StopIteration:
            pass

        assert collector.test_links[0].test_outcome == "passed"

    @patch("jamb.pytest_plugin.collector.discover_tree")
    @patch("jamb.pytest_plugin.collector.build_traceability_graph")
    def test_makereport_captures_failure_message(
        self, mock_build_graph, mock_discover, mock_graph
    ):
        """Test makereport hook captures failure messages."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        collector.test_links.append(
            LinkedTest(test_nodeid="test.py::test_fail", item_uid="SRS001")
        )

        mock_item = MagicMock()
        mock_item.nodeid = "test.py::test_fail"
        mock_item.stash = {}

        mock_call = MagicMock()

        mock_report = MagicMock()
        mock_report.when = "call"
        mock_report.outcome = "failed"
        mock_report.failed = True
        mock_report.skipped = False
        mock_report.longreprtext = "AssertionError: expected True"

        mock_outcome = MagicMock()
        mock_outcome.get_result.return_value = mock_report

        gen = collector.pytest_runtest_makereport(mock_item, mock_call)
        next(gen)
        try:
            gen.send(mock_outcome)
        except StopIteration:
            pass

        assert collector.test_links[0].test_outcome == "failed"
        assert any("[FAILURE]" in msg for msg in collector.test_links[0].notes)

    @patch("jamb.pytest_plugin.collector.discover_tree")
    @patch("jamb.pytest_plugin.collector.build_traceability_graph")
    def test_makereport_truncates_long_failure(
        self, mock_build_graph, mock_discover, mock_graph
    ):
        """Test makereport hook truncates long failure messages."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        collector.test_links.append(
            LinkedTest(test_nodeid="test.py::test_fail", item_uid="SRS001")
        )

        mock_item = MagicMock()
        mock_item.nodeid = "test.py::test_fail"
        mock_item.stash = {}

        mock_call = MagicMock()

        mock_report = MagicMock()
        mock_report.when = "call"
        mock_report.outcome = "failed"
        mock_report.failed = True
        mock_report.skipped = False
        mock_report.longreprtext = "X" * 1000  # Very long message

        mock_outcome = MagicMock()
        mock_outcome.get_result.return_value = mock_report

        gen = collector.pytest_runtest_makereport(mock_item, mock_call)
        next(gen)
        try:
            gen.send(mock_outcome)
        except StopIteration:
            pass

        # Message should be truncated
        failure_msg = [m for m in collector.test_links[0].notes if "[FAILURE]" in m][0]
        assert "(truncated)" in failure_msg

    @patch("jamb.pytest_plugin.collector.discover_tree")
    @patch("jamb.pytest_plugin.collector.build_traceability_graph")
    def test_makereport_captures_skip_reason(
        self, mock_build_graph, mock_discover, mock_graph
    ):
        """Test makereport hook captures skip reasons."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        collector.test_links.append(
            LinkedTest(test_nodeid="test.py::test_skip", item_uid="SRS001")
        )

        mock_item = MagicMock()
        mock_item.nodeid = "test.py::test_skip"
        mock_item.stash = {}

        mock_call = MagicMock()

        mock_report = MagicMock()
        mock_report.when = "call"
        mock_report.outcome = "skipped"
        mock_report.failed = False
        mock_report.skipped = True
        mock_report.longreprtext = "Skipped: not implemented yet"
        mock_report.wasxfail = None

        mock_outcome = MagicMock()
        mock_outcome.get_result.return_value = mock_report

        gen = collector.pytest_runtest_makereport(mock_item, mock_call)
        next(gen)
        try:
            gen.send(mock_outcome)
        except StopIteration:
            pass

        assert any("[SKIPPED]" in msg for msg in collector.test_links[0].notes)

    @patch("jamb.pytest_plugin.collector.discover_tree")
    @patch("jamb.pytest_plugin.collector.build_traceability_graph")
    def test_makereport_captures_xfail(
        self, mock_build_graph, mock_discover, mock_graph
    ):
        """Test makereport hook captures xfail reasons."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        collector.test_links.append(
            LinkedTest(test_nodeid="test.py::test_xfail", item_uid="SRS001")
        )

        mock_item = MagicMock()
        mock_item.nodeid = "test.py::test_xfail"
        mock_item.stash = {}

        mock_call = MagicMock()

        mock_report = MagicMock()
        mock_report.when = "call"
        mock_report.outcome = "skipped"
        mock_report.failed = False
        mock_report.skipped = True
        mock_report.wasxfail = "expected to fail: known bug"

        mock_outcome = MagicMock()
        mock_outcome.get_result.return_value = mock_report

        gen = collector.pytest_runtest_makereport(mock_item, mock_call)
        next(gen)
        try:
            gen.send(mock_outcome)
        except StopIteration:
            pass

        assert any("[XFAIL]" in msg for msg in collector.test_links[0].notes)

    @patch("jamb.pytest_plugin.collector.discover_tree")
    @patch("jamb.pytest_plugin.collector.build_traceability_graph")
    def test_makereport_captures_jamb_log_messages(
        self, mock_build_graph, mock_discover, mock_graph
    ):
        """Test makereport hook captures jamb_log fixture messages."""
        from jamb.pytest_plugin.log import JAMB_LOG_KEY, JambLog

        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        collector.test_links.append(
            LinkedTest(test_nodeid="test.py::test_with_log", item_uid="SRS001")
        )

        mock_item = MagicMock()
        mock_item.nodeid = "test.py::test_with_log"

        # Add jamb_log to stash
        jamb_log = JambLog()
        jamb_log.note("Custom verification message")
        mock_item.stash = {JAMB_LOG_KEY: jamb_log}

        mock_call = MagicMock()

        mock_report = MagicMock()
        mock_report.when = "call"
        mock_report.outcome = "passed"
        mock_report.failed = False
        mock_report.skipped = False

        mock_outcome = MagicMock()
        mock_outcome.get_result.return_value = mock_report

        gen = collector.pytest_runtest_makereport(mock_item, mock_call)
        next(gen)
        try:
            gen.send(mock_outcome)
        except StopIteration:
            pass

        assert "Custom verification message" in collector.test_links[0].notes


class TestPytestReportHeader:
    """Tests for pytest_report_header hook."""

    def test_report_header_with_jamb_enabled(self):
        """Test report header shows item count when jamb is enabled."""
        from jamb.pytest_plugin.collector import pytest_report_header

        config = MagicMock()
        config.option.jamb = True

        collector = MagicMock()
        collector.graph.items = {"SRS001": MagicMock(), "SRS002": MagicMock()}

        config.pluginmanager.get_plugin.return_value = collector

        result = pytest_report_header(config)

        assert result is not None
        assert "jamb: tracking 2 doorstop items" in result[0]

    def test_report_header_disabled_when_no_jamb(self):
        """Test report header returns None when jamb is disabled."""
        from jamb.pytest_plugin.collector import pytest_report_header

        config = MagicMock()
        config.option.jamb = False

        result = pytest_report_header(config)

        assert result is None

    def test_report_header_no_collector(self):
        """Test report header returns None when no collector."""
        from jamb.pytest_plugin.collector import pytest_report_header

        config = MagicMock()
        config.option.jamb = True
        config.pluginmanager.get_plugin.return_value = None

        result = pytest_report_header(config)

        assert result is None

    def test_report_header_no_graph(self):
        """Test report header returns None when no graph."""
        from jamb.pytest_plugin.collector import pytest_report_header

        config = MagicMock()
        config.option.jamb = True

        collector = MagicMock()
        collector.graph = None
        config.pluginmanager.get_plugin.return_value = collector

        result = pytest_report_header(config)

        assert result is None


class TestPytestTerminalSummary:
    """Tests for pytest_terminal_summary hook."""

    def test_terminal_summary_disabled_when_no_jamb(self):
        """Test terminal summary does nothing when jamb is disabled."""
        from jamb.pytest_plugin.collector import pytest_terminal_summary

        config = MagicMock()
        config.option.jamb = False

        terminal = MagicMock()

        pytest_terminal_summary(terminal, 0, config)

        terminal.write_sep.assert_not_called()

    def test_terminal_summary_no_collector(self):
        """Test terminal summary does nothing when no collector."""
        from jamb.pytest_plugin.collector import pytest_terminal_summary

        config = MagicMock()
        config.option.jamb = True
        config.pluginmanager.get_plugin.return_value = None

        terminal = MagicMock()

        pytest_terminal_summary(terminal, 0, config)

        terminal.write_sep.assert_not_called()

    def test_terminal_summary_empty_coverage(self):
        """Test terminal summary does nothing when no coverage."""
        from jamb.pytest_plugin.collector import pytest_terminal_summary

        config = MagicMock()
        config.option.jamb = True

        collector = MagicMock()
        collector.get_coverage.return_value = {}
        config.pluginmanager.get_plugin.return_value = collector

        terminal = MagicMock()

        pytest_terminal_summary(terminal, 0, config)

        terminal.write_sep.assert_not_called()

    def test_terminal_summary_shows_statistics(self):
        """Test terminal summary shows coverage statistics."""
        from jamb.pytest_plugin.collector import pytest_terminal_summary

        config = MagicMock()
        config.option.jamb = True

        # Create mock coverage
        item1 = Item(
            uid="SRS001",
            text="Covered requirement",
            document_prefix="SRS",
            active=True,
            normative=True,
        )
        item2 = Item(
            uid="SRS002",
            text="Uncovered requirement",
            document_prefix="SRS",
            active=True,
            normative=True,
        )
        cov1 = ItemCoverage(
            item=item1,
            linked_tests=[
                LinkedTest(
                    test_nodeid="test.py::test_1",
                    item_uid="SRS001",
                    test_outcome="passed",
                )
            ],
        )
        cov2 = ItemCoverage(item=item2, linked_tests=[])

        collector = MagicMock()
        collector.get_coverage.return_value = {"SRS001": cov1, "SRS002": cov2}
        collector.unknown_items = set()
        config.pluginmanager.get_plugin.return_value = collector

        terminal = MagicMock()

        pytest_terminal_summary(terminal, 0, config)

        terminal.write_sep.assert_called_once_with("=", "Requirements Coverage Summary")
        # Check statistics were written
        calls = [str(c) for c in terminal.write_line.call_args_list]
        assert any("Total test spec items: 2" in c for c in calls)

    def test_terminal_summary_shows_uncovered_items(self):
        """Test terminal summary shows uncovered items in red."""
        from jamb.pytest_plugin.collector import pytest_terminal_summary

        config = MagicMock()
        config.option.jamb = True

        item = Item(
            uid="SRS001",
            text="Uncovered requirement",
            document_prefix="SRS",
            active=True,
            normative=True,
        )
        cov = ItemCoverage(item=item, linked_tests=[])

        collector = MagicMock()
        collector.get_coverage.return_value = {"SRS001": cov}
        collector.unknown_items = set()
        config.pluginmanager.get_plugin.return_value = collector

        terminal = MagicMock()

        pytest_terminal_summary(terminal, 0, config)

        # Check uncovered items header was written
        calls = terminal.write_line.call_args_list
        assert any(
            "Uncovered test spec items:" in str(c) and "red=True" in str(c)
            for c in calls
        )

    def test_terminal_summary_shows_unknown_items(self):
        """Test terminal summary shows unknown items in yellow."""
        from jamb.pytest_plugin.collector import pytest_terminal_summary

        config = MagicMock()
        config.option.jamb = True

        item = Item(
            uid="SRS001",
            text="Requirement",
            document_prefix="SRS",
            active=True,
            normative=True,
        )
        cov = ItemCoverage(
            item=item,
            linked_tests=[LinkedTest(test_nodeid="test.py::test", item_uid="SRS001")],
        )

        collector = MagicMock()
        collector.get_coverage.return_value = {"SRS001": cov}
        collector.unknown_items = {"UNKNOWN001", "UNKNOWN002"}
        config.pluginmanager.get_plugin.return_value = collector

        terminal = MagicMock()

        pytest_terminal_summary(terminal, 0, config)

        # Check unknown items header was written
        calls = terminal.write_line.call_args_list
        assert any(
            "Unknown items referenced in tests:" in str(c) and "yellow=True" in str(c)
            for c in calls
        )
