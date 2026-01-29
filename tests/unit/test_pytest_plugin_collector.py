"""Unit tests for the pytest plugin collector module."""

import socket
from unittest.mock import MagicMock, patch

import pytest


class TestLoadRequirementsErrorHandling:
    """Tests for _load_requirements error handling."""

    def test_graph_load_failed_raises_usage_error(self):
        """Test that UsageError is raised when graph loading fails."""
        from jamb.pytest_plugin.collector import RequirementCollector

        # Create a mock pytest.Config
        mock_config = MagicMock()
        mock_config.option = MagicMock()
        mock_config.option.jamb_documents = None

        with (
            patch("jamb.pytest_plugin.collector.load_config") as mock_load_config,
            patch("jamb.storage.discover_documents") as mock_discover,
        ):
            # Set up mock config
            mock_jamb_config = MagicMock()
            mock_jamb_config.exclude_patterns = None
            mock_load_config.return_value = mock_jamb_config

            # Make discovery fail
            mock_discover.side_effect = FileNotFoundError("Config not found")

            # Create collector (which triggers _load_requirements)
            collector = RequirementCollector(mock_config)

            # Verify the graph load failed flag is set
            assert collector._graph_load_failed is True

            # Now simulate pytest_collection_modifyitems hook
            generator = collector.pytest_collection_modifyitems(items=[])
            next(generator)  # Advance to yield

            # Should raise UsageError
            with pytest.raises(pytest.UsageError, match="Cannot run with --jamb"):
                try:
                    next(generator)
                except StopIteration:
                    pass

    def test_malformed_config_raises_value_error(self):
        """Test that malformed config raises appropriate error."""
        from jamb.pytest_plugin.collector import RequirementCollector

        mock_config = MagicMock()
        mock_config.option = MagicMock()
        mock_config.option.jamb_documents = None

        with (
            patch("jamb.pytest_plugin.collector.load_config") as mock_load_config,
            patch("jamb.storage.discover_documents") as mock_discover,
        ):
            mock_jamb_config = MagicMock()
            mock_jamb_config.exclude_patterns = None
            mock_load_config.return_value = mock_jamb_config

            # Make discovery raise ValueError for malformed config
            mock_discover.side_effect = ValueError("Invalid configuration format")

            collector = RequirementCollector(mock_config)

            # Graph load should have failed
            assert collector._graph_load_failed is True


class TestOutcomeHandling:
    """Tests for test outcome handling."""

    def test_setup_phase_failure_sets_error_outcome(self):
        """Test that setup phase failure sets outcome to 'error' with note."""
        from jamb.core.models import LinkedTest, TraceabilityGraph
        from jamb.pytest_plugin.collector import RequirementCollector

        mock_config = MagicMock()
        mock_config.option = MagicMock()
        mock_config.option.jamb_documents = None

        with (
            patch("jamb.pytest_plugin.collector.load_config") as mock_load_config,
            patch("jamb.storage.discover_documents"),
            patch("jamb.storage.build_traceability_graph") as mock_build_graph,
        ):
            mock_jamb_config = MagicMock()
            mock_jamb_config.exclude_patterns = None
            mock_load_config.return_value = mock_jamb_config

            mock_build_graph.return_value = TraceabilityGraph()

            collector = RequirementCollector(mock_config)

            # Add a test link manually
            test_link = LinkedTest(
                test_nodeid="test::setup_fail",
                item_uid="SRS001",
            )
            collector.test_links.append(test_link)
            collector._links_by_nodeid["test::setup_fail"] = [test_link]

            # Create mock item and report with setup failure
            mock_item = MagicMock()
            mock_item.nodeid = "test::setup_fail"
            mock_item.stash = {}

            mock_report = MagicMock()
            mock_report.when = "setup"
            mock_report.failed = True
            mock_report.skipped = False
            mock_report.longreprtext = "Setup failed due to fixture error"

            mock_call = MagicMock()

            mock_outcome = MagicMock()
            mock_outcome.get_result.return_value = mock_report

            # Run the hook wrapper
            generator = collector.pytest_runtest_makereport(mock_item, mock_call)
            next(generator)
            try:
                generator.send(mock_outcome)
            except StopIteration:
                pass

            # Verify outcome is 'error' with setup failure note
            assert test_link.test_outcome == "error"
            assert len(test_link.notes) == 1
            assert "[SETUP FAILURE]" in test_link.notes[0]

    def test_setup_phase_skip_with_wasxfail(self):
        """Test that setup phase skip with wasxfail adds skipped note."""
        from jamb.core.models import LinkedTest, TraceabilityGraph
        from jamb.pytest_plugin.collector import RequirementCollector

        mock_config = MagicMock()
        mock_config.option = MagicMock()
        mock_config.option.jamb_documents = None

        with (
            patch("jamb.pytest_plugin.collector.load_config") as mock_load_config,
            patch("jamb.storage.discover_documents"),
            patch("jamb.storage.build_traceability_graph") as mock_build_graph,
        ):
            mock_jamb_config = MagicMock()
            mock_jamb_config.exclude_patterns = None
            mock_load_config.return_value = mock_jamb_config

            mock_build_graph.return_value = TraceabilityGraph()

            collector = RequirementCollector(mock_config)

            # Add a test link manually
            test_link = LinkedTest(
                test_nodeid="test::setup_skip_xfail",
                item_uid="SRS001",
            )
            collector.test_links.append(test_link)
            collector._links_by_nodeid["test::setup_skip_xfail"] = [test_link]

            # Create mock item and report with setup skip and wasxfail
            mock_item = MagicMock()
            mock_item.nodeid = "test::setup_skip_xfail"
            mock_item.stash = {}

            mock_report = MagicMock()
            mock_report.when = "setup"
            mock_report.failed = False
            mock_report.skipped = True
            mock_report.wasxfail = "Expected to fail due to known issue"
            mock_report.longreprtext = ""

            mock_call = MagicMock()

            mock_outcome = MagicMock()
            mock_outcome.get_result.return_value = mock_report

            # Run the hook wrapper
            generator = collector.pytest_runtest_makereport(mock_item, mock_call)
            next(generator)
            try:
                generator.send(mock_outcome)
            except StopIteration:
                pass

            # Verify outcome is 'skipped' with xfail reason
            assert test_link.test_outcome == "skipped"
            assert len(test_link.notes) == 1
            assert "[SKIPPED]" in test_link.notes[0]
            assert "Expected to fail" in test_link.notes[0]

    def test_teardown_failure_sets_error_for_passed_test(self):
        """Test that teardown failure changes outcome to 'error' for passed test."""
        from jamb.core.models import LinkedTest, TraceabilityGraph
        from jamb.pytest_plugin.collector import RequirementCollector

        mock_config = MagicMock()
        mock_config.option = MagicMock()
        mock_config.option.jamb_documents = None

        with (
            patch("jamb.pytest_plugin.collector.load_config") as mock_load_config,
            patch("jamb.storage.discover_documents"),
            patch("jamb.storage.build_traceability_graph") as mock_build_graph,
        ):
            mock_jamb_config = MagicMock()
            mock_jamb_config.exclude_patterns = None
            mock_load_config.return_value = mock_jamb_config

            mock_build_graph.return_value = TraceabilityGraph()

            collector = RequirementCollector(mock_config)

            # Add a test link manually (simulating a passed test)
            test_link = LinkedTest(
                test_nodeid="test::teardown_fail",
                item_uid="SRS001",
                test_outcome="passed",
            )
            test_link.notes = []
            collector.test_links.append(test_link)
            collector._links_by_nodeid["test::teardown_fail"] = [test_link]

            # Create mock item and report with teardown failure
            mock_item = MagicMock()
            mock_item.nodeid = "test::teardown_fail"
            mock_item.stash = {}

            mock_report = MagicMock()
            mock_report.when = "teardown"
            mock_report.failed = True
            mock_report.skipped = False
            mock_report.longreprtext = "Teardown failed: cleanup error"

            mock_call = MagicMock()

            mock_outcome = MagicMock()
            mock_outcome.get_result.return_value = mock_report

            # Run the hook wrapper
            generator = collector.pytest_runtest_makereport(mock_item, mock_call)
            next(generator)
            try:
                generator.send(mock_outcome)
            except StopIteration:
                pass

            # Verify outcome changed to 'error' with teardown failure note
            assert test_link.test_outcome == "error"
            assert len(test_link.notes) == 1
            assert "[TEARDOWN FAILURE]" in test_link.notes[0]

    def test_unknown_outcome_defaults_to_error(self):
        """Test that unknown test outcome is warned and defaults to 'error'."""
        from jamb.core.models import LinkedTest, TraceabilityGraph
        from jamb.pytest_plugin.collector import RequirementCollector

        mock_config = MagicMock()
        mock_config.option = MagicMock()
        mock_config.option.jamb_documents = None

        with (
            patch("jamb.pytest_plugin.collector.load_config") as mock_load_config,
            patch("jamb.storage.discover_documents"),
            patch("jamb.storage.build_traceability_graph") as mock_build_graph,
        ):
            mock_jamb_config = MagicMock()
            mock_jamb_config.exclude_patterns = None
            mock_load_config.return_value = mock_jamb_config

            # Create empty graph
            mock_build_graph.return_value = TraceabilityGraph()

            collector = RequirementCollector(mock_config)

            # Add a test link manually
            test_link = LinkedTest(
                test_nodeid="test::unknown_outcome",
                item_uid="SRS001",
            )
            collector.test_links.append(test_link)
            collector._links_by_nodeid["test::unknown_outcome"] = [test_link]

            # Create mock item and report with unknown outcome
            mock_item = MagicMock()
            mock_item.nodeid = "test::unknown_outcome"
            mock_item.stash = {}

            mock_report = MagicMock()
            mock_report.when = "call"
            mock_report.outcome = "weird_unknown_outcome"  # Invalid outcome
            mock_report.failed = False
            mock_report.skipped = False

            mock_call = MagicMock()

            # Create outcome mock
            mock_outcome = MagicMock()
            mock_outcome.get_result.return_value = mock_report

            # Run the hook wrapper
            generator = collector.pytest_runtest_makereport(mock_item, mock_call)
            next(generator)  # Advance to yield

            # Should warn about unknown outcome
            with pytest.warns(UserWarning, match="Unknown test outcome"):
                try:
                    generator.send(mock_outcome)
                except StopIteration:
                    pass

            # Outcome should default to "error"
            assert test_link.test_outcome == "error"


class TestFailureMessageTruncation:
    """Tests for failure message truncation."""

    def test_long_failure_message_truncated(self):
        """Test that failure messages longer than 500 chars are truncated."""
        from jamb.core.models import LinkedTest, TraceabilityGraph
        from jamb.pytest_plugin.collector import RequirementCollector

        mock_config = MagicMock()
        mock_config.option = MagicMock()
        mock_config.option.jamb_documents = None

        with (
            patch("jamb.pytest_plugin.collector.load_config") as mock_load_config,
            patch("jamb.storage.discover_documents"),
            patch("jamb.storage.build_traceability_graph") as mock_build_graph,
        ):
            mock_jamb_config = MagicMock()
            mock_jamb_config.exclude_patterns = None
            mock_load_config.return_value = mock_jamb_config

            mock_build_graph.return_value = TraceabilityGraph()

            collector = RequirementCollector(mock_config)

            # Add a test link
            test_link = LinkedTest(
                test_nodeid="test::long_failure",
                item_uid="SRS001",
            )
            collector.test_links.append(test_link)
            collector._links_by_nodeid["test::long_failure"] = [test_link]

            # Create mock item and report with very long failure message
            mock_item = MagicMock()
            mock_item.nodeid = "test::long_failure"
            mock_item.stash = {}

            long_message = "A" * 600  # 600 chars, longer than 500 limit
            mock_report = MagicMock()
            mock_report.when = "call"
            mock_report.outcome = "failed"
            mock_report.failed = True
            mock_report.skipped = False
            mock_report.longreprtext = long_message

            mock_call = MagicMock()

            mock_outcome = MagicMock()
            mock_outcome.get_result.return_value = mock_report

            # Run the hook wrapper
            generator = collector.pytest_runtest_makereport(mock_item, mock_call)
            next(generator)
            try:
                generator.send(mock_outcome)
            except StopIteration:
                pass

            # Check that failure message was truncated
            assert len(test_link.notes) == 1
            note = test_link.notes[0]
            assert "... (truncated)" in note
            # The total length should be limited
            assert len(note) < 600


class TestBuildTestEnvironmentExceptions:
    """Tests for _build_test_environment exception handling."""

    def test_pytest_version_attribute_error_handled(self):
        """Test that AttributeError on pytest.__version__ is handled gracefully."""
        from jamb.core.models import TraceabilityGraph
        from jamb.pytest_plugin.collector import RequirementCollector

        mock_config = MagicMock()
        mock_config.option = MagicMock()
        mock_config.option.jamb_documents = None
        mock_config.pluginmanager = MagicMock()
        mock_config.pluginmanager.list_plugin_distinfo.return_value = []

        with (
            patch("jamb.pytest_plugin.collector.load_config") as mock_load_config,
            patch("jamb.storage.discover_documents"),
            patch("jamb.storage.build_traceability_graph") as mock_build_graph,
        ):
            mock_jamb_config = MagicMock()
            mock_jamb_config.exclude_patterns = None
            mock_load_config.return_value = mock_jamb_config

            mock_build_graph.return_value = TraceabilityGraph()

            collector = RequirementCollector(mock_config)

            # Patch pytest module to raise AttributeError
            with patch.dict("sys.modules", {"pytest": MagicMock(spec=[])}):
                env = collector._build_test_environment()

            # Should still return a valid environment
            assert env is not None
            assert env.python_version is not None

    def test_plugin_distinfo_exception_handled(self):
        """Test that TypeError from list_plugin_distinfo is handled gracefully."""
        from jamb.core.models import TraceabilityGraph
        from jamb.pytest_plugin.collector import RequirementCollector

        mock_config = MagicMock()
        mock_config.option = MagicMock()
        mock_config.option.jamb_documents = None
        mock_config.pluginmanager = MagicMock()
        # Make list_plugin_distinfo raise TypeError
        mock_config.pluginmanager.list_plugin_distinfo.side_effect = TypeError("Plugin error")

        with (
            patch("jamb.pytest_plugin.collector.load_config") as mock_load_config,
            patch("jamb.storage.discover_documents"),
            patch("jamb.storage.build_traceability_graph") as mock_build_graph,
        ):
            mock_jamb_config = MagicMock()
            mock_jamb_config.exclude_patterns = None
            mock_load_config.return_value = mock_jamb_config

            mock_build_graph.return_value = TraceabilityGraph()

            collector = RequirementCollector(mock_config)

            # Should not raise, should return valid environment
            env = collector._build_test_environment()

            assert env is not None
            assert env.python_version is not None
            # test_tools should still have pytest at minimum
            assert "pytest" in env.test_tools


class TestBuildTestEnvironment:
    """Tests for _build_test_environment."""

    def test_hostname_failure_returns_unknown(self):
        """Test that socket.gethostname() failure returns 'unknown'."""
        from jamb.core.models import TraceabilityGraph
        from jamb.pytest_plugin.collector import RequirementCollector

        mock_config = MagicMock()
        mock_config.option = MagicMock()
        mock_config.option.jamb_documents = None
        mock_config.pluginmanager = MagicMock()
        mock_config.pluginmanager.list_plugin_distinfo.return_value = []

        with (
            patch("jamb.pytest_plugin.collector.load_config") as mock_load_config,
            patch("jamb.storage.discover_documents"),
            patch("jamb.storage.build_traceability_graph") as mock_build_graph,
            patch.object(socket, "gethostname", side_effect=OSError("No hostname")),
        ):
            mock_jamb_config = MagicMock()
            mock_jamb_config.exclude_patterns = None
            mock_load_config.return_value = mock_jamb_config

            mock_build_graph.return_value = TraceabilityGraph()

            collector = RequirementCollector(mock_config)

            # Build environment
            env = collector._build_test_environment()

            # Hostname should be "unknown" due to OSError
            assert env.hostname == "unknown"


class TestBuildMatrixMetadata:
    """Tests for _build_matrix_metadata."""

    def test_build_matrix_metadata_uses_software_version_param(self):
        """Test metadata uses software_version parameter over config."""
        from jamb.core.models import TraceabilityGraph
        from jamb.pytest_plugin.collector import RequirementCollector

        mock_config = MagicMock()
        mock_config.option = MagicMock()
        mock_config.option.jamb_documents = None
        mock_config.pluginmanager = MagicMock()
        mock_config.pluginmanager.list_plugin_distinfo.return_value = []

        with (
            patch("jamb.pytest_plugin.collector.load_config") as mock_load_config,
            patch("jamb.storage.discover_documents"),
            patch("jamb.storage.build_traceability_graph") as mock_build_graph,
        ):
            mock_jamb_config = MagicMock()
            mock_jamb_config.exclude_patterns = None
            mock_jamb_config.software_version = "1.0.0"
            mock_load_config.return_value = mock_jamb_config

            mock_build_graph.return_value = TraceabilityGraph()

            collector = RequirementCollector(mock_config)

            # Call with explicit software_version parameter
            metadata = collector._build_matrix_metadata(
                tester_id="Test CI",
                software_version="2.0.0",  # Should override config
            )

            assert metadata.software_version == "2.0.0"
            assert metadata.tester_id == "Test CI"

    def test_build_matrix_metadata_uses_config_version_fallback(self):
        """Test metadata falls back to config software_version."""
        from jamb.core.models import TraceabilityGraph
        from jamb.pytest_plugin.collector import RequirementCollector

        mock_config = MagicMock()
        mock_config.option = MagicMock()
        mock_config.option.jamb_documents = None
        mock_config.pluginmanager = MagicMock()
        mock_config.pluginmanager.list_plugin_distinfo.return_value = []

        with (
            patch("jamb.pytest_plugin.collector.load_config") as mock_load_config,
            patch("jamb.storage.discover_documents"),
            patch("jamb.storage.build_traceability_graph") as mock_build_graph,
        ):
            mock_jamb_config = MagicMock()
            mock_jamb_config.exclude_patterns = None
            mock_jamb_config.software_version = "3.5.0"
            mock_load_config.return_value = mock_jamb_config

            mock_build_graph.return_value = TraceabilityGraph()

            collector = RequirementCollector(mock_config)

            # Call without software_version parameter
            metadata = collector._build_matrix_metadata(tester_id="Tester")

            assert metadata.software_version == "3.5.0"
            assert metadata.tester_id == "Tester"


class TestBuildLinksByUid:
    """Tests for _build_links_by_uid."""

    def test_build_links_by_uid_maps_test_links(self):
        """Test that test links are correctly indexed by UID."""
        from jamb.core.models import LinkedTest, TraceabilityGraph
        from jamb.pytest_plugin.collector import RequirementCollector

        mock_config = MagicMock()
        mock_config.option = MagicMock()
        mock_config.option.jamb_documents = None

        with (
            patch("jamb.pytest_plugin.collector.load_config") as mock_load_config,
            patch("jamb.storage.discover_documents"),
            patch("jamb.storage.build_traceability_graph") as mock_build_graph,
        ):
            mock_jamb_config = MagicMock()
            mock_jamb_config.exclude_patterns = None
            mock_load_config.return_value = mock_jamb_config

            mock_build_graph.return_value = TraceabilityGraph()

            collector = RequirementCollector(mock_config)

            # Add test links
            link1 = LinkedTest(test_nodeid="test::a", item_uid="SRS001")
            link2 = LinkedTest(test_nodeid="test::b", item_uid="SRS002")
            collector.test_links = [link1, link2]

            result = collector._build_links_by_uid()

            assert "SRS001" in result
            assert "SRS002" in result
            assert result["SRS001"] == [link1]
            assert result["SRS002"] == [link2]

    def test_build_links_by_uid_multiple_tests_per_item(self):
        """Test handling multiple tests linked to same item."""
        from jamb.core.models import LinkedTest, TraceabilityGraph
        from jamb.pytest_plugin.collector import RequirementCollector

        mock_config = MagicMock()
        mock_config.option = MagicMock()
        mock_config.option.jamb_documents = None

        with (
            patch("jamb.pytest_plugin.collector.load_config") as mock_load_config,
            patch("jamb.storage.discover_documents"),
            patch("jamb.storage.build_traceability_graph") as mock_build_graph,
        ):
            mock_jamb_config = MagicMock()
            mock_jamb_config.exclude_patterns = None
            mock_load_config.return_value = mock_jamb_config

            mock_build_graph.return_value = TraceabilityGraph()

            collector = RequirementCollector(mock_config)

            # Multiple tests for same item
            link1 = LinkedTest(test_nodeid="test::a", item_uid="SRS001")
            link2 = LinkedTest(test_nodeid="test::b", item_uid="SRS001")
            link3 = LinkedTest(test_nodeid="test::c", item_uid="SRS001")
            collector.test_links = [link1, link2, link3]

            result = collector._build_links_by_uid()

            assert len(result["SRS001"]) == 3
            assert link1 in result["SRS001"]
            assert link2 in result["SRS001"]
            assert link3 in result["SRS001"]


class TestSaveCoverageFile:
    """Tests for save_coverage_file."""

    def test_save_coverage_file_returns_early_when_no_graph(self):
        """Test save_coverage_file returns early if graph is None."""
        from jamb.core.models import TraceabilityGraph
        from jamb.pytest_plugin.collector import RequirementCollector

        mock_config = MagicMock()
        mock_config.option = MagicMock()
        mock_config.option.jamb_documents = None

        with (
            patch("jamb.pytest_plugin.collector.load_config") as mock_load_config,
            patch("jamb.storage.discover_documents"),
            patch("jamb.storage.build_traceability_graph") as mock_build_graph,
            patch("jamb.coverage.serializer.save_coverage") as mock_save_coverage,
        ):
            mock_jamb_config = MagicMock()
            mock_jamb_config.exclude_patterns = None
            mock_load_config.return_value = mock_jamb_config

            mock_build_graph.return_value = TraceabilityGraph()

            collector = RequirementCollector(mock_config)
            # Set graph to None
            collector.graph = None

            collector.save_coverage_file()

            # save_coverage should not be called
            mock_save_coverage.assert_not_called()

    def test_save_coverage_file_calls_serializer(self):
        """Test save_coverage_file delegates to save_coverage."""
        from jamb.core.models import TraceabilityGraph
        from jamb.pytest_plugin.collector import RequirementCollector

        mock_config = MagicMock()
        mock_config.option = MagicMock()
        mock_config.option.jamb_documents = None
        mock_config.pluginmanager = MagicMock()
        mock_config.pluginmanager.list_plugin_distinfo.return_value = []

        with (
            patch("jamb.pytest_plugin.collector.load_config") as mock_load_config,
            patch("jamb.storage.discover_documents"),
            patch("jamb.storage.build_traceability_graph") as mock_build_graph,
            patch("jamb.coverage.serializer.save_coverage") as mock_save_coverage,
        ):
            mock_jamb_config = MagicMock()
            mock_jamb_config.exclude_patterns = None
            mock_jamb_config.software_version = "1.0.0"
            mock_load_config.return_value = mock_jamb_config

            graph = TraceabilityGraph()
            mock_build_graph.return_value = graph

            collector = RequirementCollector(mock_config)

            collector.save_coverage_file(
                output_path="custom.jamb",
                tester_id="CI",
                software_version="2.0.0",
            )

            # save_coverage should be called
            mock_save_coverage.assert_called_once()
            call_args = mock_save_coverage.call_args
            assert call_args[0][2] == "custom.jamb"
