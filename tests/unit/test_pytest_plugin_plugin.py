"""Tests for jamb.pytest_plugin.plugin module."""

from unittest.mock import MagicMock, patch

import pytest

# ============================================================================
# Fixtures for common mock configurations
# ============================================================================


@pytest.fixture
def mock_session():
    """Create a mock pytest session with jamb enabled and common defaults."""
    session = MagicMock()
    session.config.option.jamb = True
    session.config.option.jamb_test_matrix = None
    session.config.option.jamb_trace_matrix = None
    session.config.option.jamb_fail_uncovered = False
    session.config.option.jamb_tester_id = "tester"
    session.config.option.jamb_software_version = None
    session.config.option.trace_from = None
    session.config.option.include_ancestors = False
    session.exitstatus = 0
    return session


@pytest.fixture
def mock_collector():
    """Create a mock RequirementCollector with common defaults."""
    collector = MagicMock()
    collector.jamb_config.test_matrix_output = None
    collector.jamb_config.trace_matrix_output = None
    collector.jamb_config.fail_uncovered = False
    collector.jamb_config.trace_from = None
    collector.jamb_config.include_ancestors = False
    collector.all_test_items_covered.return_value = True
    return collector


class TestPytestAddoption:
    """Tests for pytest_addoption hook."""

    def test_registers_jamb_options(self):
        """Test that all jamb options are registered."""
        from jamb.pytest_plugin.plugin import pytest_addoption

        mock_parser = MagicMock()
        mock_group = MagicMock()
        mock_parser.getgroup.return_value = mock_group

        pytest_addoption(mock_parser)

        # Verify group was created
        mock_parser.getgroup.assert_called_once_with("jamb", "IEC 62304 requirements traceability")

        # Verify all options were added
        calls = mock_group.addoption.call_args_list
        option_names = [call[0][0] for call in calls]

        assert "--jamb" in option_names
        assert "--jamb-fail-uncovered" in option_names
        assert "--jamb-test-matrix" in option_names
        assert "--jamb-trace-matrix" in option_names
        assert "--jamb-documents" in option_names

    def test_matrix_options_have_metavar_path(self):
        """Test that matrix options have PATH metavar."""
        from jamb.pytest_plugin.plugin import pytest_addoption

        mock_parser = MagicMock()
        mock_group = MagicMock()
        mock_parser.getgroup.return_value = mock_group

        pytest_addoption(mock_parser)

        calls = mock_group.addoption.call_args_list
        for call in calls:
            if call[0][0] in ("--jamb-test-matrix", "--jamb-trace-matrix"):
                assert call[1]["metavar"] == "PATH"
                return
        raise AssertionError("Matrix options not found")


class TestPytestConfigure:
    """Tests for pytest_configure hook."""

    def test_registers_requirement_marker(self):
        """Test that requirement marker is registered."""
        from jamb.pytest_plugin.plugin import pytest_configure

        mock_config = MagicMock()
        mock_config.option.jamb = False

        pytest_configure(mock_config)

        mock_config.addinivalue_line.assert_called_once()
        call_args = mock_config.addinivalue_line.call_args
        assert call_args[0][0] == "markers"
        assert "requirement" in call_args[0][1]

    @patch("jamb.pytest_plugin.plugin.RequirementCollector")
    def test_creates_collector_when_jamb_enabled(self, mock_collector_class):
        """Test that collector is created when --jamb is enabled."""
        from jamb.pytest_plugin.plugin import pytest_configure

        mock_config = MagicMock()
        mock_config.option.jamb = True

        pytest_configure(mock_config)

        mock_collector_class.assert_called_once_with(mock_config)
        mock_config.pluginmanager.register.assert_called_once()

    def test_no_collector_when_jamb_disabled(self):
        """Test that collector is not created when --jamb is disabled."""
        from jamb.pytest_plugin.plugin import pytest_configure

        mock_config = MagicMock()
        mock_config.option.jamb = False

        pytest_configure(mock_config)

        mock_config.pluginmanager.register.assert_not_called()


class TestPytestSessionfinish:
    """Tests for pytest_sessionfinish hook."""

    def test_does_nothing_when_jamb_disabled(self):
        """Test that nothing happens when --jamb is disabled."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session = MagicMock()
        mock_session.config.option.jamb = False

        pytest_sessionfinish(mock_session, 0)

        mock_session.config.pluginmanager.get_plugin.assert_not_called()

    def test_does_nothing_when_no_collector(self):
        """Test that nothing happens when collector is not found."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session = MagicMock()
        mock_session.config.option.jamb = True
        mock_session.config.pluginmanager.get_plugin.return_value = None

        pytest_sessionfinish(mock_session, 0)

        # Should not raise any errors

    def test_generates_test_matrix_when_requested(self, mock_session, mock_collector):
        """Test that test matrix is generated when --jamb-test-matrix is provided."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session.config.option.jamb_test_matrix = "output.html"
        mock_session.config.option.jamb_tester_id = "CI Pipeline"
        mock_session.config.option.jamb_software_version = "1.2.3"
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        mock_collector.generate_test_records_matrix.assert_called_once_with(
            "output.html",
            output_format="html",
            tester_id="CI Pipeline",
            software_version="1.2.3",
        )
        mock_collector.generate_trace_matrix.assert_not_called()

    def test_fails_when_uncovered_and_flag_set(self, mock_session, mock_collector):
        """Test that exit status is 1 when uncovered items and flag is set."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session.config.option.jamb_fail_uncovered = True
        mock_collector.all_test_items_covered.return_value = False
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        assert mock_session.exitstatus == 1

    def test_no_fail_when_all_covered(self, mock_session, mock_collector):
        """Test that exit status is unchanged when all items covered."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session.config.option.jamb_fail_uncovered = True
        mock_collector.all_test_items_covered.return_value = True
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        assert mock_session.exitstatus == 0

    def test_fail_uncovered_from_config(self):
        """Test fail_uncovered from config when CLI flag is False."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session = MagicMock()
        mock_session.config.option.jamb = True
        mock_session.config.option.jamb_test_matrix = None
        mock_session.config.option.jamb_trace_matrix = None
        mock_session.config.option.jamb_fail_uncovered = False
        mock_session.config.option.jamb_tester_id = "tester"
        mock_session.config.option.jamb_software_version = None
        mock_session.exitstatus = 0

        mock_collector = MagicMock()
        mock_collector.jamb_config.fail_uncovered = True
        mock_collector.jamb_config.test_matrix_output = None
        mock_collector.jamb_config.trace_matrix_output = None
        mock_collector.all_test_items_covered.return_value = False
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        assert mock_session.exitstatus == 1

    def test_cli_fail_uncovered_overrides_config(self):
        """Test CLI --jamb-fail-uncovered takes effect even if config is False."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session = MagicMock()
        mock_session.config.option.jamb = True
        mock_session.config.option.jamb_test_matrix = None
        mock_session.config.option.jamb_trace_matrix = None
        mock_session.config.option.jamb_fail_uncovered = True
        mock_session.config.option.jamb_tester_id = "tester"
        mock_session.config.option.jamb_software_version = None
        mock_session.exitstatus = 0

        mock_collector = MagicMock()
        mock_collector.jamb_config.fail_uncovered = False
        mock_collector.jamb_config.test_matrix_output = None
        mock_collector.jamb_config.trace_matrix_output = None
        mock_collector.all_test_items_covered.return_value = False
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        assert mock_session.exitstatus == 1

    def test_test_matrix_output_from_config(self):
        """Test test_matrix_output falls back to config when CLI is None."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session = MagicMock()
        mock_session.config.option.jamb = True
        mock_session.config.option.jamb_test_matrix = None
        mock_session.config.option.jamb_trace_matrix = None
        mock_session.config.option.jamb_fail_uncovered = False
        mock_session.config.option.jamb_tester_id = "tester"
        mock_session.config.option.jamb_software_version = None

        mock_collector = MagicMock()
        mock_collector.jamb_config.test_matrix_output = "out.html"
        mock_collector.jamb_config.trace_matrix_output = None
        mock_collector.jamb_config.fail_uncovered = False
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        mock_collector.generate_test_records_matrix.assert_called_once_with(
            "out.html",
            output_format="html",
            tester_id="tester",
            software_version=None,
        )

    def test_cli_test_matrix_overrides_config(self):
        """Test CLI --jamb-test-matrix takes precedence over config."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session = MagicMock()
        mock_session.config.option.jamb = True
        mock_session.config.option.jamb_test_matrix = "cli.html"
        mock_session.config.option.jamb_trace_matrix = None
        mock_session.config.option.jamb_fail_uncovered = False
        mock_session.config.option.jamb_tester_id = "tester"
        mock_session.config.option.jamb_software_version = None

        mock_collector = MagicMock()
        mock_collector.jamb_config.test_matrix_output = "cfg.html"
        mock_collector.jamb_config.trace_matrix_output = None
        mock_collector.jamb_config.fail_uncovered = False
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        mock_collector.generate_test_records_matrix.assert_called_once_with(
            "cli.html",
            output_format="html",
            tester_id="tester",
            software_version=None,
        )

    def test_trace_matrix_generated_when_requested(self, mock_session, mock_collector):
        """Test trace matrix is generated when --jamb-trace-matrix is provided."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session.config.option.jamb_trace_matrix = "trace.html"
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        mock_collector.generate_trace_matrix.assert_called_once_with(
            "trace.html",
            output_format="html",
            trace_from=None,
            include_ancestors=False,
        )
        mock_collector.generate_test_records_matrix.assert_not_called()

    def test_both_matrices_generated_when_requested(self, mock_session, mock_collector):
        """Test both matrices are generated when both flags are provided."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session.config.option.jamb_test_matrix = "test.json"
        mock_session.config.option.jamb_trace_matrix = "trace.csv"
        mock_session.config.option.jamb_software_version = "1.0.0"
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        mock_collector.generate_test_records_matrix.assert_called_once_with(
            "test.json",
            output_format="json",
            tester_id="tester",
            software_version="1.0.0",
        )
        mock_collector.generate_trace_matrix.assert_called_once_with(
            "trace.csv",
            output_format="csv",
            trace_from=None,
            include_ancestors=False,
        )

    def test_format_inferred_from_extension(self, mock_session, mock_collector):
        """Test that format is correctly inferred from file extension."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session.config.option.jamb_test_matrix = "output.xlsx"
        mock_session.config.option.jamb_trace_matrix = "trace.md"
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        mock_collector.generate_test_records_matrix.assert_called_once_with(
            "output.xlsx",
            output_format="xlsx",
            tester_id="tester",
            software_version=None,
        )
        mock_collector.generate_trace_matrix.assert_called_once_with(
            "trace.md",
            output_format="markdown",
            trace_from=None,
            include_ancestors=False,
        )


class TestPytestReportHeader:
    """Tests for pytest_report_header hook."""

    def test_returns_none_when_jamb_disabled(self):
        """Test that None is returned when --jamb is disabled."""
        from jamb.pytest_plugin.plugin import pytest_report_header

        mock_config = MagicMock()
        mock_config.option.jamb = False

        result = pytest_report_header(mock_config)

        assert result is None

    def test_returns_none_when_no_collector(self):
        """Test that None is returned when collector is not found."""
        from jamb.pytest_plugin.plugin import pytest_report_header

        mock_config = MagicMock()
        mock_config.option.jamb = True
        mock_config.pluginmanager.get_plugin.return_value = None

        result = pytest_report_header(mock_config)

        assert result is None

    def test_returns_none_when_no_graph(self):
        """Test that None is returned when graph is not loaded."""
        from jamb.pytest_plugin.plugin import pytest_report_header

        mock_config = MagicMock()
        mock_config.option.jamb = True

        mock_collector = MagicMock()
        mock_collector.graph = None
        mock_config.pluginmanager.get_plugin.return_value = mock_collector

        result = pytest_report_header(mock_config)

        assert result is None

    def test_returns_item_count(self):
        """Test that item count is returned when graph is loaded."""
        from jamb.pytest_plugin.plugin import pytest_report_header

        mock_config = MagicMock()
        mock_config.option.jamb = True

        mock_collector = MagicMock()
        mock_collector.graph.items = {"SRS001": MagicMock(), "SRS002": MagicMock()}
        mock_config.pluginmanager.get_plugin.return_value = mock_collector

        result = pytest_report_header(mock_config)

        assert result is not None
        assert "jamb: tracking 2 requirement items" in result[0]


class TestPytestTerminalSummary:
    """Tests for pytest_terminal_summary hook."""

    def test_does_nothing_when_jamb_disabled(self):
        """Test that nothing is written when --jamb is disabled."""
        from jamb.pytest_plugin.plugin import pytest_terminal_summary

        mock_terminal = MagicMock()
        mock_config = MagicMock()
        mock_config.option.jamb = False

        pytest_terminal_summary(mock_terminal, 0, mock_config)

        mock_terminal.write_sep.assert_not_called()

    def test_does_nothing_when_no_collector(self):
        """Test that nothing is written when collector is not found."""
        from jamb.pytest_plugin.plugin import pytest_terminal_summary

        mock_terminal = MagicMock()
        mock_config = MagicMock()
        mock_config.option.jamb = True
        mock_config.pluginmanager.get_plugin.return_value = None

        pytest_terminal_summary(mock_terminal, 0, mock_config)

        mock_terminal.write_sep.assert_not_called()

    def test_does_nothing_when_no_coverage(self):
        """Test that nothing is written when no coverage data."""
        from jamb.pytest_plugin.plugin import pytest_terminal_summary

        mock_terminal = MagicMock()
        mock_config = MagicMock()
        mock_config.option.jamb = True

        mock_collector = MagicMock()
        mock_collector.get_coverage.return_value = {}
        mock_config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_terminal_summary(mock_terminal, 0, mock_config)

        mock_terminal.write_sep.assert_not_called()


class TestJambLogFixture:
    """Tests for jamb_log fixture - tested via integration tests."""

    def test_jamb_log_fixture_is_registered(self):
        """Test that jamb_log fixture function exists in plugin module."""
        from jamb.pytest_plugin import plugin

        # The jamb_log fixture should exist as an attribute
        assert hasattr(plugin, "jamb_log")
        # It should be callable (the underlying function)
        assert callable(plugin.jamb_log)


class TestPytestTerminalSummaryCoverage:
    """Tests for pytest_terminal_summary coverage display."""

    def test_terminal_summary_with_coverage_stats(self):
        """Test terminal summary displays coverage statistics."""
        from jamb.pytest_plugin.plugin import pytest_terminal_summary

        mock_terminal = MagicMock()
        mock_config = MagicMock()
        mock_config.option.jamb = True

        # Create mock coverage data
        item1 = MagicMock()
        item1.type = "requirement"
        item1.active = True
        item1.display_text = "Test item"
        item1.uid = "SRS001"

        cov1 = MagicMock()
        cov1.is_covered = True
        cov1.all_tests_passed = True
        cov1.item = item1

        mock_collector = MagicMock()
        mock_collector.get_coverage.return_value = {"SRS001": cov1}
        mock_collector.unknown_items = set()
        mock_config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_terminal_summary(mock_terminal, 0, mock_config)

        # Verify write_sep was called for header
        mock_terminal.write_sep.assert_called_once_with("=", "Requirements Coverage Summary")
        # Verify write_line was called for stats
        assert mock_terminal.write_line.call_count > 0

    def test_terminal_summary_uncovered_items_formatting(self):
        """Test uncovered items are displayed with red/bold formatting."""
        from jamb.pytest_plugin.plugin import pytest_terminal_summary

        mock_terminal = MagicMock()
        mock_config = MagicMock()
        mock_config.option.jamb = True

        item1 = MagicMock()
        item1.type = "requirement"
        item1.active = True
        item1.display_text = "Uncovered requirement"
        item1.uid = "SRS001"

        cov1 = MagicMock()
        cov1.is_covered = False
        cov1.item = item1

        mock_collector = MagicMock()
        mock_collector.get_coverage.return_value = {"SRS001": cov1}
        mock_collector.unknown_items = set()
        mock_config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_terminal_summary(mock_terminal, 0, mock_config)

        # Check that red/bold was used for uncovered items
        calls = mock_terminal.write_line.call_args_list
        red_bold_call = any(call.kwargs.get("red") and call.kwargs.get("bold") for call in calls if call.kwargs)
        assert red_bold_call, "Expected red/bold formatting for uncovered header"

    def test_terminal_summary_unknown_items_formatting(self):
        """Test unknown items are displayed with yellow/bold formatting."""
        from jamb.pytest_plugin.plugin import pytest_terminal_summary

        mock_terminal = MagicMock()
        mock_config = MagicMock()
        mock_config.option.jamb = True

        item1 = MagicMock()
        item1.type = "requirement"
        item1.active = True
        item1.display_text = "Item"
        item1.uid = "SRS001"

        cov1 = MagicMock()
        cov1.is_covered = True
        cov1.all_tests_passed = True
        cov1.item = item1

        mock_collector = MagicMock()
        mock_collector.get_coverage.return_value = {"SRS001": cov1}
        mock_collector.unknown_items = {"UNKNOWN001", "UNKNOWN002"}
        mock_config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_terminal_summary(mock_terminal, 0, mock_config)

        # Check that yellow/bold was used for unknown items header
        calls = mock_terminal.write_line.call_args_list
        yellow_bold_call = any(call.kwargs.get("yellow") and call.kwargs.get("bold") for call in calls if call.kwargs)
        assert yellow_bold_call, "Expected yellow/bold formatting for unknown header"

    def test_terminal_summary_all_covered(self):
        """Test terminal summary when all items are covered."""
        from jamb.pytest_plugin.plugin import pytest_terminal_summary

        mock_terminal = MagicMock()
        mock_config = MagicMock()
        mock_config.option.jamb = True

        item1 = MagicMock()
        item1.type = "requirement"
        item1.active = True
        item1.display_text = "Covered item"
        item1.uid = "SRS001"

        item2 = MagicMock()
        item2.type = "requirement"
        item2.active = True
        item2.display_text = "Another covered item"
        item2.uid = "SRS002"

        cov1 = MagicMock()
        cov1.is_covered = True
        cov1.all_tests_passed = True
        cov1.item = item1

        cov2 = MagicMock()
        cov2.is_covered = True
        cov2.all_tests_passed = True
        cov2.item = item2

        mock_collector = MagicMock()
        mock_collector.get_coverage.return_value = {"SRS001": cov1, "SRS002": cov2}
        mock_collector.unknown_items = set()
        mock_config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_terminal_summary(mock_terminal, 0, mock_config)

        # Should display stats but no uncovered items
        calls = mock_terminal.write_line.call_args_list
        call_texts = [str(call[0][0]) if call[0] else "" for call in calls]

        # Should show 100% coverage
        assert any("100" in text for text in call_texts)
        # Should not show "Uncovered" in bold/red
        red_bold_calls = [call for call in calls if call.kwargs and call.kwargs.get("red") and call.kwargs.get("bold")]
        assert len(red_bold_calls) == 0


class TestPytestTerminalSummaryNonTestable:
    """Tests for terminal summary with non-testable items."""

    def test_terminal_summary_with_testable_attribute(self):
        """Test terminal summary correctly handles testable attribute."""
        from jamb.pytest_plugin.plugin import pytest_terminal_summary

        mock_terminal = MagicMock()
        mock_config = MagicMock()
        mock_config.option.jamb = True

        # Testable requirement item
        item1 = MagicMock()
        item1.type = "requirement"
        item1.active = True
        item1.testable = True
        item1.display_text = "Testable requirement"
        item1.uid = "SRS001"

        # Non-testable requirement item
        item2 = MagicMock()
        item2.type = "requirement"
        item2.active = True
        item2.testable = False
        item2.display_text = "Non-testable requirement"
        item2.uid = "SRS002"

        cov1 = MagicMock()
        cov1.is_covered = True
        cov1.all_tests_passed = True
        cov1.item = item1

        cov2 = MagicMock()
        cov2.is_covered = False
        cov2.all_tests_passed = False
        cov2.item = item2

        mock_collector = MagicMock()
        mock_collector.get_coverage.return_value = {"SRS001": cov1, "SRS002": cov2}
        mock_collector.unknown_items = set()
        mock_config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_terminal_summary(mock_terminal, 0, mock_config)

        # Verify write_line was called
        assert mock_terminal.write_line.call_count > 0
        calls = mock_terminal.write_line.call_args_list
        call_texts = [str(call[0][0]) if call[0] else "" for call in calls]

        # Should show non-testable in breakdown
        assert any("non-testable" in text.lower() for text in call_texts)

    def test_terminal_summary_with_heading_items(self):
        """Test terminal summary handles heading type items."""
        from jamb.pytest_plugin.plugin import pytest_terminal_summary

        mock_terminal = MagicMock()
        mock_config = MagicMock()
        mock_config.option.jamb = True

        # Heading item
        item1 = MagicMock()
        item1.type = "heading"
        item1.active = True
        item1.testable = True
        item1.display_text = "Section Header"
        item1.uid = "SRS001"

        cov1 = MagicMock()
        cov1.is_covered = False
        cov1.all_tests_passed = False
        cov1.item = item1

        mock_collector = MagicMock()
        mock_collector.get_coverage.return_value = {"SRS001": cov1}
        mock_collector.unknown_items = set()
        mock_config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_terminal_summary(mock_terminal, 0, mock_config)

        calls = mock_terminal.write_line.call_args_list
        call_texts = [str(call[0][0]) if call[0] else "" for call in calls]

        # Should mention heading in breakdown
        assert any("heading" in text.lower() for text in call_texts)

    def test_terminal_summary_with_info_items(self):
        """Test terminal summary handles info type items."""
        from jamb.pytest_plugin.plugin import pytest_terminal_summary

        mock_terminal = MagicMock()
        mock_config = MagicMock()
        mock_config.option.jamb = True

        # Info item
        item1 = MagicMock()
        item1.type = "info"
        item1.active = True
        item1.testable = True
        item1.display_text = "Informational text"
        item1.uid = "SRS001"

        cov1 = MagicMock()
        cov1.is_covered = False
        cov1.all_tests_passed = False
        cov1.item = item1

        mock_collector = MagicMock()
        mock_collector.get_coverage.return_value = {"SRS001": cov1}
        mock_collector.unknown_items = set()
        mock_config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_terminal_summary(mock_terminal, 0, mock_config)

        calls = mock_terminal.write_line.call_args_list
        call_texts = [str(call[0][0]) if call[0] else "" for call in calls]

        # Should mention info in breakdown
        assert any("info" in text.lower() for text in call_texts)

    def test_terminal_summary_with_inactive_items(self):
        """Test terminal summary handles inactive items."""
        from jamb.pytest_plugin.plugin import pytest_terminal_summary

        mock_terminal = MagicMock()
        mock_config = MagicMock()
        mock_config.option.jamb = True

        # Inactive item
        item1 = MagicMock()
        item1.type = "requirement"
        item1.active = False
        item1.testable = True
        item1.display_text = "Inactive requirement"
        item1.uid = "SRS001"

        cov1 = MagicMock()
        cov1.is_covered = False
        cov1.all_tests_passed = False
        cov1.item = item1

        mock_collector = MagicMock()
        mock_collector.get_coverage.return_value = {"SRS001": cov1}
        mock_collector.unknown_items = set()
        mock_config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_terminal_summary(mock_terminal, 0, mock_config)

        calls = mock_terminal.write_line.call_args_list
        call_texts = [str(call[0][0]) if call[0] else "" for call in calls]

        # Should mention inactive in breakdown
        assert any("inactive" in text.lower() for text in call_texts)

    def test_terminal_summary_zero_testable_items(self):
        """Test terminal summary when total_testable is 0."""
        from jamb.pytest_plugin.plugin import pytest_terminal_summary

        mock_terminal = MagicMock()
        mock_config = MagicMock()
        mock_config.option.jamb = True

        # Only heading items (no testable requirement items)
        item1 = MagicMock()
        item1.type = "heading"
        item1.active = True
        item1.testable = True
        item1.display_text = "Header"
        item1.uid = "SRS001"

        cov1 = MagicMock()
        cov1.is_covered = False
        cov1.all_tests_passed = False
        cov1.item = item1

        mock_collector = MagicMock()
        mock_collector.get_coverage.return_value = {"SRS001": cov1}
        mock_collector.unknown_items = set()
        mock_config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_terminal_summary(mock_terminal, 0, mock_config)

        # Should not crash even with 0 testable items
        calls = mock_terminal.write_line.call_args_list
        call_texts = [str(call[0][0]) if call[0] else "" for call in calls]
        # Should show "Total testable items: 0"
        assert any("0" in text for text in call_texts)


class TestSessionFinishTraceMatrixOptions:
    """Tests for trace matrix options in pytest_sessionfinish."""

    def test_trace_from_cli_option(self, mock_session, mock_collector):
        """Test --trace-from CLI option is passed to generate_trace_matrix."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session.config.option.jamb_trace_matrix = "trace.html"
        mock_session.config.option.trace_from = "UN"
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        mock_collector.generate_trace_matrix.assert_called_once_with(
            "trace.html",
            output_format="html",
            trace_from="UN",
            include_ancestors=False,
        )

    def test_trace_from_config_fallback(self):
        """Test trace_from falls back to config when CLI is None."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session = MagicMock()
        mock_session.config.option.jamb = True
        mock_session.config.option.jamb_test_matrix = None
        mock_session.config.option.jamb_trace_matrix = "trace.html"
        mock_session.config.option.jamb_fail_uncovered = False
        mock_session.config.option.jamb_tester_id = "tester"
        mock_session.config.option.jamb_software_version = None
        mock_session.config.option.trace_from = None
        mock_session.config.option.include_ancestors = False

        mock_collector = MagicMock()
        mock_collector.jamb_config.test_matrix_output = None
        mock_collector.jamb_config.trace_matrix_output = None
        mock_collector.jamb_config.fail_uncovered = False
        mock_collector.jamb_config.trace_from = "SYS"
        mock_collector.jamb_config.include_ancestors = False
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        mock_collector.generate_trace_matrix.assert_called_once_with(
            "trace.html",
            output_format="html",
            trace_from="SYS",
            include_ancestors=False,
        )

    def test_include_ancestors_cli_option(self, mock_session, mock_collector):
        """Test --include-ancestors CLI option is passed to generate_trace_matrix."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session.config.option.jamb_trace_matrix = "trace.html"
        mock_session.config.option.include_ancestors = True
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        mock_collector.generate_trace_matrix.assert_called_once_with(
            "trace.html",
            output_format="html",
            trace_from=None,
            include_ancestors=True,
        )

    def test_include_ancestors_config_fallback(self):
        """Test include_ancestors falls back to config when CLI is False."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session = MagicMock()
        mock_session.config.option.jamb = True
        mock_session.config.option.jamb_test_matrix = None
        mock_session.config.option.jamb_trace_matrix = "trace.html"
        mock_session.config.option.jamb_fail_uncovered = False
        mock_session.config.option.jamb_tester_id = "tester"
        mock_session.config.option.jamb_software_version = None
        mock_session.config.option.trace_from = None
        mock_session.config.option.include_ancestors = False

        mock_collector = MagicMock()
        mock_collector.jamb_config.test_matrix_output = None
        mock_collector.jamb_config.trace_matrix_output = None
        mock_collector.jamb_config.fail_uncovered = False
        mock_collector.jamb_config.trace_from = None
        mock_collector.jamb_config.include_ancestors = True
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        mock_collector.generate_trace_matrix.assert_called_once_with(
            "trace.html",
            output_format="html",
            trace_from=None,
            include_ancestors=True,
        )

    def test_trace_matrix_from_config_fallback(self):
        """Test trace_matrix_output falls back to config when CLI is None."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session = MagicMock()
        mock_session.config.option.jamb = True
        mock_session.config.option.jamb_test_matrix = None
        mock_session.config.option.jamb_trace_matrix = None
        mock_session.config.option.jamb_fail_uncovered = False
        mock_session.config.option.jamb_tester_id = "tester"
        mock_session.config.option.jamb_software_version = None
        mock_session.config.option.trace_from = None
        mock_session.config.option.include_ancestors = False

        mock_collector = MagicMock()
        mock_collector.jamb_config.test_matrix_output = None
        mock_collector.jamb_config.trace_matrix_output = "config-trace.json"
        mock_collector.jamb_config.fail_uncovered = False
        mock_collector.jamb_config.trace_from = None
        mock_collector.jamb_config.include_ancestors = False
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        mock_collector.generate_trace_matrix.assert_called_once_with(
            "config-trace.json",
            output_format="json",
            trace_from=None,
            include_ancestors=False,
        )


class TestSessionFinishSavesCoverageFile:
    """Tests for coverage file saving in pytest_sessionfinish."""

    def test_always_saves_coverage_file(self, mock_session, mock_collector):
        """Test that save_coverage_file is always called."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        mock_collector.save_coverage_file.assert_called_once_with(
            tester_id="tester",
            software_version=None,
        )

    def test_coverage_file_with_software_version(self, mock_session, mock_collector):
        """Test that software_version is passed to save_coverage_file."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session.config.option.jamb_software_version = "2.0.0"
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        mock_collector.save_coverage_file.assert_called_once_with(
            tester_id="tester",
            software_version="2.0.0",
        )


class TestSessionFinishExitStatusPreservation:
    """Tests for exit status handling in pytest_sessionfinish."""

    def test_no_change_when_exit_already_nonzero(self, mock_session, mock_collector):
        """Test that exit status is not changed if already non-zero."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session.config.option.jamb_fail_uncovered = True
        mock_session.exitstatus = 2  # Already failed
        mock_collector.all_test_items_covered.return_value = False
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 2)

        # Should remain 2, not change to 1
        assert mock_session.exitstatus == 2
