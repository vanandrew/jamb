"""Tests for jamb.pytest_plugin.collector module."""

from unittest.mock import MagicMock, patch

import pytest

from jamb.core.models import Item, LinkedTest, TraceabilityGraph
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
    )
    item2 = Item(
        uid="SRS002",
        text="Requirement 2",
        document_prefix="SRS",
        active=True,
    )
    item3 = Item(
        uid="SRS003",
        text="Inactive requirement",
        document_prefix="SRS",
        active=False,
    )
    graph.add_item(item1)
    graph.add_item(item2)
    graph.add_item(item3)
    graph.set_document_parent("SRS", None)
    return graph


class TestRequirementCollectorInit:
    """Tests for RequirementCollector initialization."""

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    def test_collector_init_loads_requirements(self, mock_build_graph, mock_discover, mock_pytest_config, mock_graph):
        """Test collector initialization loads requirements."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph

        collector = RequirementCollector(mock_pytest_config)

        assert collector.graph is not None
        assert len(collector.graph.items) == 3
        mock_discover.assert_called_once()
        mock_build_graph.assert_called_once()

    @patch("jamb.storage.discover_documents")
    def test_collector_init_handles_missing_requirements(self, mock_discover, mock_pytest_config):
        """Test collector handles missing requirements gracefully."""
        mock_discover.side_effect = FileNotFoundError("No requirements found")

        with pytest.warns(UserWarning, match="Could not load requirements"):
            collector = RequirementCollector(mock_pytest_config)

        # Should create empty graph on error
        assert collector.graph is not None
        assert len(collector.graph.items) == 0

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    def test_collector_init_empty_test_links(self, mock_build_graph, mock_discover, mock_pytest_config):
        """Test collector initializes with empty test links."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = TraceabilityGraph()

        collector = RequirementCollector(mock_pytest_config)

        assert collector.test_links == []
        assert collector.unknown_items == set()


class TestGetTestDocuments:
    """Tests for _get_test_documents method."""

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    def test_get_test_documents_from_cli_option(self, mock_build_graph, mock_discover, mock_graph):
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

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    @patch("jamb.pytest_plugin.collector.load_config")
    def test_get_test_documents_from_config(self, mock_load_config, mock_build_graph, mock_discover, mock_graph):
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

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
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

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    def test_get_coverage_returns_empty_when_no_graph(self, mock_build_graph, mock_discover, mock_pytest_config):
        """Test get_coverage returns empty dict when graph loading failed."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = TraceabilityGraph()

        collector = RequirementCollector(mock_pytest_config)
        collector.graph = None  # Simulate failed graph loading

        coverage = collector.get_coverage()

        assert coverage == {}

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
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
        collector.test_links.append(LinkedTest(test_nodeid="test.py::test_foo", item_uid="SRS001"))

        coverage = collector.get_coverage()

        assert "SRS001" in coverage
        assert coverage["SRS001"].is_covered is True
        assert "SRS002" in coverage
        assert coverage["SRS002"].is_covered is False


class TestAllTestItemsCovered:
    """Tests for all_test_items_covered method."""

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    @patch("jamb.pytest_plugin.collector.load_config")
    def test_all_test_items_covered_true_when_all_covered(self, mock_load_config, mock_build_graph, mock_discover):
        """Test all_test_items_covered returns True when all covered."""
        graph = TraceabilityGraph()
        item = Item(
            uid="SRS001",
            text="Requirement",
            document_prefix="SRS",
            active=True,
        )
        graph.add_item(item)
        graph.set_document_parent("SRS", None)

        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = graph

        mock_config = MagicMock()
        mock_config.test_documents = ["SRS"]
        mock_config.require_all_pass = True
        mock_config.exclude_patterns = []
        mock_load_config.return_value = mock_config

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        collector.test_links.append(
            LinkedTest(
                test_nodeid="test.py::test_foo",
                item_uid="SRS001",
                test_outcome="passed",
            )
        )

        assert collector.all_test_items_covered() is True

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
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

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    @patch("jamb.pytest_plugin.collector.load_config")
    def test_all_test_items_covered_ignores_inactive(
        self, mock_load_config, mock_build_graph, mock_discover, mock_graph
    ):
        """Test all_test_items_covered ignores inactive items."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph

        mock_config = MagicMock()
        mock_config.test_documents = ["SRS"]
        mock_config.require_all_pass = True
        mock_config.exclude_patterns = []
        mock_load_config.return_value = mock_config

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        # Cover only active items
        collector.test_links.append(
            LinkedTest(
                test_nodeid="test.py::test_1",
                item_uid="SRS001",
                test_outcome="passed",
            )
        )
        collector.test_links.append(
            LinkedTest(
                test_nodeid="test.py::test_2",
                item_uid="SRS002",
                test_outcome="passed",
            )
        )
        # SRS003 is inactive, should be ignored

        assert collector.all_test_items_covered() is True

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    @patch("jamb.pytest_plugin.collector.load_config")
    def test_all_test_items_covered_ignores_non_normative(self, mock_load_config, mock_build_graph, mock_discover):
        """Test all_test_items_covered ignores non-normative items."""
        graph = TraceabilityGraph()
        normative_item = Item(
            uid="SRS001",
            text="Normative requirement",
            document_prefix="SRS",
            active=True,
        )
        informative_item = Item(
            uid="SRS002",
            text="Informative note",
            document_prefix="SRS",
            active=True,
            type="info",
        )
        graph.add_item(normative_item)
        graph.add_item(informative_item)
        graph.set_document_parent("SRS", None)

        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = graph

        mock_config = MagicMock()
        mock_config.test_documents = ["SRS"]
        mock_config.require_all_pass = True
        mock_config.exclude_patterns = []
        mock_load_config.return_value = mock_config

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        # Only cover normative item
        collector.test_links.append(
            LinkedTest(
                test_nodeid="test.py::test_1",
                item_uid="SRS001",
                test_outcome="passed",
            )
        )
        # SRS002 is non-normative, should be ignored

        assert collector.all_test_items_covered() is True

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    @patch("jamb.pytest_plugin.collector.load_config")
    def test_all_test_items_covered_ignores_non_testable(self, mock_load_config, mock_build_graph, mock_discover):
        """Test all_test_items_covered ignores items with testable=False."""
        graph = TraceabilityGraph()
        testable_item = Item(
            uid="SRS001",
            text="Testable requirement",
            document_prefix="SRS",
            active=True,
            testable=True,
        )
        non_testable_item = Item(
            uid="SRS002",
            text="Non-testable requirement",
            document_prefix="SRS",
            active=True,
            testable=False,
        )
        graph.add_item(testable_item)
        graph.add_item(non_testable_item)
        graph.set_document_parent("SRS", None)

        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = graph

        mock_config = MagicMock()
        mock_config.test_documents = ["SRS"]
        mock_config.require_all_pass = True
        mock_config.exclude_patterns = []
        mock_load_config.return_value = mock_config

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        # Only cover the testable item
        collector.test_links.append(
            LinkedTest(
                test_nodeid="test.py::test_1",
                item_uid="SRS001",
                test_outcome="passed",
            )
        )
        # SRS002 is non-testable, should be ignored even with no test link

        assert collector.all_test_items_covered() is True


class TestAllTestItemsCoveredRequireAllPass:
    """Tests for require_all_pass behavior in all_test_items_covered."""

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    @patch("jamb.pytest_plugin.collector.load_config")
    def test_require_all_pass_true_fails_when_test_failed(self, mock_load_config, mock_build_graph, mock_discover):
        """require_all_pass=True: items with linked but failed tests → False."""
        graph = TraceabilityGraph()
        item = Item(
            uid="SRS001",
            text="Requirement",
            document_prefix="SRS",
            active=True,
        )
        graph.add_item(item)
        graph.set_document_parent("SRS", None)

        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = graph

        mock_config = MagicMock()
        mock_config.test_documents = ["SRS"]
        mock_config.require_all_pass = True
        mock_config.exclude_patterns = []
        mock_load_config.return_value = mock_config

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        collector.test_links.append(
            LinkedTest(
                test_nodeid="test.py::test_foo",
                item_uid="SRS001",
                test_outcome="failed",
            )
        )

        assert collector.all_test_items_covered() is False

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    @patch("jamb.pytest_plugin.collector.load_config")
    def test_require_all_pass_false_passes_when_test_failed(self, mock_load_config, mock_build_graph, mock_discover):
        """require_all_pass=False: items with linked but failed tests → True."""
        graph = TraceabilityGraph()
        item = Item(
            uid="SRS001",
            text="Requirement",
            document_prefix="SRS",
            active=True,
        )
        graph.add_item(item)
        graph.set_document_parent("SRS", None)

        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = graph

        mock_config = MagicMock()
        mock_config.test_documents = ["SRS"]
        mock_config.require_all_pass = False
        mock_config.exclude_patterns = []
        mock_load_config.return_value = mock_config

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        collector.test_links.append(
            LinkedTest(
                test_nodeid="test.py::test_foo",
                item_uid="SRS001",
                test_outcome="failed",
            )
        )

        assert collector.all_test_items_covered() is True

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    @patch("jamb.pytest_plugin.collector.load_config")
    def test_require_all_pass_default_is_true(self, mock_load_config, mock_build_graph, mock_discover):
        """Default require_all_pass is True, so failed tests → False."""
        from jamb.config.loader import JambConfig

        graph = TraceabilityGraph()
        item = Item(
            uid="SRS001",
            text="Requirement",
            document_prefix="SRS",
            active=True,
        )
        graph.add_item(item)
        graph.set_document_parent("SRS", None)

        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = graph

        # Use real JambConfig with default values
        real_config = JambConfig(test_documents=["SRS"])
        mock_load_config.return_value = real_config

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        collector.test_links.append(
            LinkedTest(
                test_nodeid="test.py::test_foo",
                item_uid="SRS001",
                test_outcome="failed",
            )
        )

        assert collector.all_test_items_covered() is False


class TestGenerateTestRecordsMatrix:
    """Tests for generate_test_records_matrix method."""

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    @patch("jamb.pytest_plugin.collector.load_config")
    @patch("jamb.matrix.generator.generate_test_records_matrix")
    @patch("jamb.matrix.generator.build_test_records")
    def test_generate_test_records_matrix_calls_generator(
        self,
        mock_build_records,
        mock_generate,
        mock_load_config,
        mock_build_graph,
        mock_discover,
        mock_graph,
    ):
        """Test generate_test_records_matrix calls the matrix generator."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph
        mock_build_records.return_value = []

        mock_config = MagicMock()
        mock_config.test_documents = ["SRS"]
        mock_load_config.return_value = mock_config

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        collector.generate_test_records_matrix("output.html", "html")

        mock_build_records.assert_called_once()
        mock_generate.assert_called_once()
        call_args = mock_generate.call_args
        assert call_args[0][1] == "output.html"
        assert call_args[0][2] == "html"


class TestGenerateTraceMatrix:
    """Tests for generate_trace_matrix method."""

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    @patch("jamb.pytest_plugin.collector.load_config")
    @patch("jamb.matrix.generator.generate_full_chain_matrix")
    def test_generate_trace_matrix_calls_generator(
        self,
        mock_generate,
        mock_load_config,
        mock_build_graph,
        mock_discover,
        mock_graph,
    ):
        """Test generate_trace_matrix calls the matrix generator."""
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
        collector.generate_trace_matrix("output.html", "html", trace_from="SRS")

        mock_generate.assert_called_once()
        call_args = mock_generate.call_args
        assert call_args[0][2] == "output.html"
        assert call_args[0][3] == "html"
        assert call_args[1]["trace_from"] == "SRS"

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    @patch("jamb.pytest_plugin.collector.load_config")
    @patch("jamb.matrix.generator.generate_full_chain_matrix")
    def test_generate_trace_matrix_auto_detects_root(
        self,
        mock_generate,
        mock_load_config,
        mock_build_graph,
        mock_discover,
    ):
        """Test generate_trace_matrix auto-detects root document."""
        # Create a graph with a root document
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", [])
        item = Item(uid="SRS001", text="req", document_prefix="SRS")
        graph.add_item(item)

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
        collector.generate_trace_matrix("output.html", "html")

        mock_generate.assert_called_once()
        call_args = mock_generate.call_args
        assert call_args[1]["trace_from"] == "SRS"


class TestPytestCollectionModifyItems:
    """Tests for pytest_collection_modifyitems hook."""

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    @patch("jamb.pytest_plugin.collector.get_requirement_markers")
    def test_collection_adds_test_links(self, mock_get_markers, mock_build_graph, mock_discover, mock_graph):
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

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    @patch("jamb.pytest_plugin.collector.get_requirement_markers")
    def test_collection_tracks_unknown_items(self, mock_get_markers, mock_build_graph, mock_discover, mock_graph):
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

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    def test_makereport_updates_outcome_on_pass(self, mock_build_graph, mock_discover, mock_graph):
        """Test makereport hook updates test outcome on pass."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        collector.test_links.append(LinkedTest(test_nodeid="test.py::test_pass", item_uid="SRS001"))

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

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    def test_makereport_captures_failure_message(self, mock_build_graph, mock_discover, mock_graph):
        """Test makereport hook captures failure messages."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        collector.test_links.append(LinkedTest(test_nodeid="test.py::test_fail", item_uid="SRS001"))

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

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    def test_makereport_truncates_long_failure(self, mock_build_graph, mock_discover, mock_graph):
        """Test makereport hook truncates long failure messages."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        collector.test_links.append(LinkedTest(test_nodeid="test.py::test_fail", item_uid="SRS001"))

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

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    def test_makereport_captures_skip_reason(self, mock_build_graph, mock_discover, mock_graph):
        """Test makereport hook captures skip reasons."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        collector.test_links.append(LinkedTest(test_nodeid="test.py::test_skip", item_uid="SRS001"))

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

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    def test_makereport_captures_xfail(self, mock_build_graph, mock_discover, mock_graph):
        """Test makereport hook captures xfail reasons."""
        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        collector.test_links.append(LinkedTest(test_nodeid="test.py::test_xfail", item_uid="SRS001"))

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

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    def test_makereport_captures_jamb_log_messages(self, mock_build_graph, mock_discover, mock_graph):
        """Test makereport hook captures jamb_log fixture messages."""
        from jamb.pytest_plugin.log import JAMB_LOG_KEY, JambLog

        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = mock_graph

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        collector.test_links.append(LinkedTest(test_nodeid="test.py::test_with_log", item_uid="SRS001"))

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


# =========================================================================
# Gap 4 — Failure message truncation precision
# =========================================================================


class TestMakeReportTruncationPrecision:
    """Precision tests for failure message truncation."""

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    def test_makereport_truncation_preserves_first_500_chars(self, mock_build_graph, mock_discover):
        """Truncated note contains first 500 chars and
        '(truncated)' but not chars beyond."""
        graph = TraceabilityGraph()
        item = Item(uid="SRS001", text="req", document_prefix="SRS", active=True)
        graph.add_item(item)
        graph.set_document_parent("SRS", None)

        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = graph

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        collector.test_links.append(LinkedTest(test_nodeid="test.py::test_fail", item_uid="SRS001"))

        mock_item = MagicMock()
        mock_item.nodeid = "test.py::test_fail"
        mock_item.stash = {}

        mock_call = MagicMock()

        mock_report = MagicMock()
        mock_report.when = "call"
        mock_report.outcome = "failed"
        mock_report.failed = True
        mock_report.skipped = False
        mock_report.longreprtext = "A" * 500 + "B" * 500

        mock_outcome = MagicMock()
        mock_outcome.get_result.return_value = mock_report

        gen = collector.pytest_runtest_makereport(mock_item, mock_call)
        next(gen)
        try:
            gen.send(mock_outcome)
        except StopIteration:
            pass

        failure_note = [m for m in collector.test_links[0].notes if "[FAILURE]" in m][0]
        assert "A" * 500 in failure_note
        assert "(truncated)" in failure_note
        assert "B" not in failure_note


# =========================================================================
# Gap 5 — xfail with empty reason
# =========================================================================


class TestMakeReportXfailEmptyReason:
    """Edge case: xfail with empty (falsy) reason."""

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    def test_makereport_xfail_empty_reason_falls_through(self, mock_build_graph, mock_discover):
        """wasxfail='' (falsy) + skipped=True produces [SKIPPED] not [XFAIL]."""
        graph = TraceabilityGraph()
        item = Item(uid="SRS001", text="req", document_prefix="SRS", active=True)
        graph.add_item(item)
        graph.set_document_parent("SRS", None)

        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = graph

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        collector.test_links.append(LinkedTest(test_nodeid="test.py::test_xfail_empty", item_uid="SRS001"))

        mock_item = MagicMock()
        mock_item.nodeid = "test.py::test_xfail_empty"
        mock_item.stash = {}

        mock_call = MagicMock()

        mock_report = MagicMock()
        mock_report.when = "call"
        mock_report.outcome = "skipped"
        mock_report.failed = False
        mock_report.skipped = True
        mock_report.wasxfail = ""  # falsy
        mock_report.longreprtext = "Skipped for reason"

        mock_outcome = MagicMock()
        mock_outcome.get_result.return_value = mock_report

        gen = collector.pytest_runtest_makereport(mock_item, mock_call)
        next(gen)
        try:
            gen.send(mock_outcome)
        except StopIteration:
            pass

        notes = collector.test_links[0].notes
        assert any("[SKIPPED]" in n for n in notes)
        assert not any("[XFAIL]" in n for n in notes)


# =========================================================================
# Setup/teardown phase handling
# =========================================================================


class TestMakeReportSetupTeardown:
    """Tests for setup failure, setup skip, and teardown failure handling."""

    def _make_collector_with_link(self, mock_build_graph, mock_discover):
        """Helper: create a collector with one linked test."""
        graph = TraceabilityGraph()
        item = Item(uid="SRS001", text="req", document_prefix="SRS", active=True)
        graph.add_item(item)
        graph.set_document_parent("SRS", None)

        mock_discover.return_value = MagicMock()
        mock_build_graph.return_value = graph

        config = MagicMock()
        config.option.jamb = True
        config.option.jamb_documents = None
        config.option.jamb_fail_uncovered = False

        collector = RequirementCollector(config)
        collector.test_links.append(LinkedTest(test_nodeid="test.py::test_one", item_uid="SRS001"))
        return collector

    def _send_report(self, collector, mock_report):
        """Drive the hookwrapper generator with a mock report."""
        mock_item = MagicMock()
        mock_item.nodeid = "test.py::test_one"
        mock_item.stash = {}

        mock_call = MagicMock()
        mock_outcome = MagicMock()
        mock_outcome.get_result.return_value = mock_report

        gen = collector.pytest_runtest_makereport(mock_item, mock_call)
        next(gen)
        try:
            gen.send(mock_outcome)
        except StopIteration:
            pass

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    def test_setup_failure_sets_error_outcome(self, mock_build_graph, mock_discover):
        """Setup failure records outcome as 'error' with note."""
        collector = self._make_collector_with_link(mock_build_graph, mock_discover)

        report = MagicMock()
        report.when = "setup"
        report.failed = True
        report.skipped = False
        report.longreprtext = "fixture not found"

        self._send_report(collector, report)

        link = collector.test_links[0]
        assert link.test_outcome == "error"
        assert any("[SETUP FAILURE]" in n for n in link.notes)

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    def test_setup_skip_sets_skipped_outcome(self, mock_build_graph, mock_discover):
        """Setup skip records outcome as 'skipped' with reason."""
        collector = self._make_collector_with_link(mock_build_graph, mock_discover)

        report = MagicMock()
        report.when = "setup"
        report.failed = False
        report.skipped = True
        report.wasxfail = ""
        report.longreprtext = "requires network"

        self._send_report(collector, report)

        link = collector.test_links[0]
        assert link.test_outcome == "skipped"
        assert any("requires network" in n for n in link.notes)

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    def test_teardown_failure_sets_error_when_call_passed(self, mock_build_graph, mock_discover):
        """Teardown failure sets 'error' when call phase passed."""
        collector = self._make_collector_with_link(mock_build_graph, mock_discover)

        # Simulate call phase passing first
        call_report = MagicMock()
        call_report.when = "call"
        call_report.outcome = "passed"
        call_report.failed = False
        call_report.skipped = False
        call_report.longreprtext = ""
        self._send_report(collector, call_report)
        assert collector.test_links[0].test_outcome == "passed"

        # Now teardown fails
        teardown_report = MagicMock()
        teardown_report.when = "teardown"
        teardown_report.failed = True
        teardown_report.longreprtext = "cleanup error"
        self._send_report(collector, teardown_report)

        link = collector.test_links[0]
        assert link.test_outcome == "error"
        assert any("[TEARDOWN FAILURE]" in n for n in link.notes)

    @patch("jamb.storage.discover_documents")
    @patch("jamb.storage.build_traceability_graph")
    def test_teardown_failure_does_not_overwrite_call_failure(self, mock_build_graph, mock_discover):
        """Teardown failure does not overwrite a call-phase failure."""
        collector = self._make_collector_with_link(mock_build_graph, mock_discover)

        # Simulate call phase failing first
        call_report = MagicMock()
        call_report.when = "call"
        call_report.outcome = "failed"
        call_report.failed = True
        call_report.skipped = False
        call_report.longreprtext = "assertion error"
        self._send_report(collector, call_report)
        assert collector.test_links[0].test_outcome == "failed"

        # Now teardown also fails
        teardown_report = MagicMock()
        teardown_report.when = "teardown"
        teardown_report.failed = True
        teardown_report.longreprtext = "cleanup error"
        self._send_report(collector, teardown_report)

        # Should still be "failed" from the call phase, not "error"
        link = collector.test_links[0]
        assert link.test_outcome == "failed"
