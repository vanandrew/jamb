"""Tests for jamb.pytest_plugin.plugin module."""

from unittest.mock import MagicMock, patch


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
        mock_parser.getgroup.assert_called_once_with(
            "jamb", "IEC 62304 requirements traceability"
        )

        # Verify all options were added
        calls = mock_group.addoption.call_args_list
        option_names = [call[0][0] for call in calls]

        assert "--jamb" in option_names
        assert "--jamb-fail-uncovered" in option_names
        assert "--jamb-matrix" in option_names
        assert "--jamb-matrix-format" in option_names
        assert "--jamb-documents" in option_names

    def test_matrix_format_default_is_none(self):
        """Test that --jamb-matrix-format default is None (config takes over)."""
        from jamb.pytest_plugin.plugin import pytest_addoption

        mock_parser = MagicMock()
        mock_group = MagicMock()
        mock_parser.getgroup.return_value = mock_group

        pytest_addoption(mock_parser)

        calls = mock_group.addoption.call_args_list
        for call in calls:
            if call[0][0] == "--jamb-matrix-format":
                assert call[1]["default"] is None
                return
        raise AssertionError("--jamb-matrix-format option not found")


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

    def test_generates_matrix_when_requested(self):
        """Test that matrix is generated when --jamb-matrix is provided."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session = MagicMock()
        mock_session.config.option.jamb = True
        mock_session.config.option.jamb_matrix = "output.html"
        mock_session.config.option.jamb_matrix_format = "html"
        mock_session.config.option.jamb_fail_uncovered = False
        mock_session.config.option.jamb_tester_id = "CI Pipeline"
        mock_session.config.option.jamb_software_version = "1.2.3"

        mock_collector = MagicMock()
        mock_collector.jamb_config.fail_uncovered = False
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        mock_collector.generate_matrix.assert_called_once_with(
            "output.html",
            output_format="html",
            tester_id="CI Pipeline",
            software_version="1.2.3",
        )

    def test_fails_when_uncovered_and_flag_set(self):
        """Test that exit status is 1 when uncovered items and flag is set."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session = MagicMock()
        mock_session.config.option.jamb = True
        mock_session.config.option.jamb_matrix = None
        mock_session.config.option.jamb_fail_uncovered = True
        mock_session.exitstatus = 0

        mock_collector = MagicMock()
        mock_collector.jamb_config.matrix_output = None
        mock_collector.all_test_items_covered.return_value = False
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        assert mock_session.exitstatus == 1

    def test_no_fail_when_all_covered(self):
        """Test that exit status is unchanged when all items covered."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session = MagicMock()
        mock_session.config.option.jamb = True
        mock_session.config.option.jamb_matrix = None
        mock_session.config.option.jamb_fail_uncovered = True
        mock_session.exitstatus = 0

        mock_collector = MagicMock()
        mock_collector.all_test_items_covered.return_value = True
        mock_collector.jamb_config.matrix_output = None
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        assert mock_session.exitstatus == 0

    def test_fail_uncovered_from_config(self):
        """Test fail_uncovered from config when CLI flag is False."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session = MagicMock()
        mock_session.config.option.jamb = True
        mock_session.config.option.jamb_matrix = None
        mock_session.config.option.jamb_fail_uncovered = False
        mock_session.exitstatus = 0

        mock_collector = MagicMock()
        mock_collector.jamb_config.fail_uncovered = True
        mock_collector.jamb_config.matrix_output = None
        mock_collector.all_test_items_covered.return_value = False
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        assert mock_session.exitstatus == 1

    def test_cli_fail_uncovered_overrides_config(self):
        """Test CLI --jamb-fail-uncovered takes effect even if config is False."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session = MagicMock()
        mock_session.config.option.jamb = True
        mock_session.config.option.jamb_matrix = None
        mock_session.config.option.jamb_fail_uncovered = True
        mock_session.exitstatus = 0

        mock_collector = MagicMock()
        mock_collector.jamb_config.fail_uncovered = False
        mock_collector.jamb_config.matrix_output = None
        mock_collector.all_test_items_covered.return_value = False
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        assert mock_session.exitstatus == 1

    def test_matrix_output_from_config(self):
        """Test matrix_output falls back to config when CLI is None."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session = MagicMock()
        mock_session.config.option.jamb = True
        mock_session.config.option.jamb_matrix = None
        mock_session.config.option.jamb_matrix_format = None
        mock_session.config.option.jamb_fail_uncovered = False
        mock_session.config.option.jamb_tester_id = "tester"
        mock_session.config.option.jamb_software_version = None

        mock_collector = MagicMock()
        mock_collector.jamb_config.matrix_output = "out.html"
        mock_collector.jamb_config.matrix_format = "html"
        mock_collector.jamb_config.fail_uncovered = False
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        mock_collector.generate_matrix.assert_called_once_with(
            "out.html",
            output_format="html",
            tester_id="tester",
            software_version=None,
        )

    def test_cli_matrix_overrides_config(self):
        """Test CLI --jamb-matrix takes precedence over config matrix_output."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session = MagicMock()
        mock_session.config.option.jamb = True
        mock_session.config.option.jamb_matrix = "cli.html"
        mock_session.config.option.jamb_matrix_format = "html"
        mock_session.config.option.jamb_fail_uncovered = False
        mock_session.config.option.jamb_tester_id = "tester"
        mock_session.config.option.jamb_software_version = None

        mock_collector = MagicMock()
        mock_collector.jamb_config.matrix_output = "cfg.html"
        mock_collector.jamb_config.fail_uncovered = False
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        mock_collector.generate_matrix.assert_called_once_with(
            "cli.html",
            output_format="html",
            tester_id="tester",
            software_version=None,
        )

    def test_matrix_format_from_config(self):
        """Test matrix_format falls back to config when CLI is None."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session = MagicMock()
        mock_session.config.option.jamb = True
        mock_session.config.option.jamb_matrix = "out.json"
        mock_session.config.option.jamb_matrix_format = None
        mock_session.config.option.jamb_fail_uncovered = False
        mock_session.config.option.jamb_tester_id = "tester"
        mock_session.config.option.jamb_software_version = None

        mock_collector = MagicMock()
        mock_collector.jamb_config.matrix_format = "json"
        mock_collector.jamb_config.fail_uncovered = False
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        mock_collector.generate_matrix.assert_called_once_with(
            "out.json",
            output_format="json",
            tester_id="tester",
            software_version=None,
        )

    def test_cli_matrix_format_overrides_config(self):
        """Test CLI --jamb-matrix-format takes precedence over config."""
        from jamb.pytest_plugin.plugin import pytest_sessionfinish

        mock_session = MagicMock()
        mock_session.config.option.jamb = True
        mock_session.config.option.jamb_matrix = "out.csv"
        mock_session.config.option.jamb_matrix_format = "csv"
        mock_session.config.option.jamb_fail_uncovered = False
        mock_session.config.option.jamb_tester_id = "tester"
        mock_session.config.option.jamb_software_version = None

        mock_collector = MagicMock()
        mock_collector.jamb_config.matrix_format = "json"
        mock_collector.jamb_config.fail_uncovered = False
        mock_session.config.pluginmanager.get_plugin.return_value = mock_collector

        pytest_sessionfinish(mock_session, 0)

        mock_collector.generate_matrix.assert_called_once_with(
            "out.csv",
            output_format="csv",
            tester_id="tester",
            software_version=None,
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
