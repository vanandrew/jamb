"""Main pytest plugin entry point for jamb."""

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from _pytest.terminal import TerminalReporter

from jamb.matrix.utils import infer_format
from jamb.pytest_plugin.collector import RequirementCollector
from jamb.pytest_plugin.log import JAMB_LOG_KEY, JambLog


@pytest.fixture
def jamb_log(request: pytest.FixtureRequest) -> JambLog:
    """
    Fixture to log custom messages for the traceability matrix.

    Example::

        @pytest.mark.requirement("SRS001")
        def test_validation(jamb_log):
            jamb_log.note("Verified input validation with boundary values")
            assert validate_input(-1) is False
    """
    log = JambLog()
    request.node.stash[JAMB_LOG_KEY] = log
    return log


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register jamb command-line options with pytest.

    Registers the following options: ``--jamb``, ``--jamb-fail-uncovered``,
    ``--jamb-test-matrix``, ``--jamb-trace-matrix``, and ``--jamb-documents``.

    Args:
        parser: The pytest argument parser to add options to.
    """
    group = parser.getgroup("jamb", "IEC 62304 requirements traceability")

    group.addoption(
        "--jamb",
        action="store_true",
        default=False,
        help="Enable requirements traceability checking",
    )
    group.addoption(
        "--jamb-fail-uncovered",
        action="store_true",
        default=False,
        help="Fail if any test spec items lack pytest test coverage",
    )
    group.addoption(
        "--jamb-test-matrix",
        metavar="PATH",
        help=("Generate test records matrix at PATH (format inferred from extension: .html, .json, .csv, .md, .xlsx)"),
    )
    group.addoption(
        "--jamb-trace-matrix",
        metavar="PATH",
        help=("Generate traceability matrix at PATH (format inferred from extension: .html, .json, .csv, .md, .xlsx)"),
    )
    group.addoption(
        "--jamb-documents",
        metavar="PREFIXES",
        help="Comma-separated list of test document prefixes to check",
    )
    group.addoption(
        "--jamb-tester-id",
        default="Unknown",
        metavar="ID",
        help="Tester identification for test records matrix (default: Unknown)",
    )
    group.addoption(
        "--jamb-software-version",
        default=None,
        metavar="VERSION",
        help="Software version for test records matrix (overrides pyproject.toml)",
    )
    group.addoption(
        "--trace-from",
        metavar="PREFIX",
        help="Starting document prefix for full chain trace matrix (e.g., UN, SYS)",
    )
    group.addoption(
        "--include-ancestors",
        action="store_true",
        default=False,
        help="Include 'Traces To' column showing ancestors of starting items",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register the requirement marker and initialize the jamb collector plugin.

    Registers the ``requirement`` marker for linking tests to requirement UIDs
    and creates a ``RequirementCollector`` instance when ``--jamb`` is enabled.

    Args:
        config: The pytest configuration object.
    """
    # Register the requirement marker
    config.addinivalue_line(
        "markers",
        "requirement(*uids): Mark test as implementing specified "
        "requirement item UID(s). "
        "Example: @pytest.mark.requirement('UT001', 'UT002')",
    )

    if config.option.jamb:
        # Initialize the collector
        collector = RequirementCollector(config)
        config.pluginmanager.register(collector, "jamb_collector")


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Generate reports and check coverage after the test session completes.

    Generates test records matrix when ``--jamb-test-matrix`` or the
    ``test_matrix_output`` config option is set. Generates traceability matrix
    when ``--jamb-trace-matrix`` or the ``trace_matrix_output`` config option
    is set. Sets the exit status to failure when ``--jamb-fail-uncovered`` or
    ``fail_uncovered`` in the config is enabled and any test spec items lack
    coverage.

    For all options, CLI flags take precedence over ``[tool.jamb]`` config
    values, which take precedence over hardcoded defaults.

    Args:
        session: The pytest session object.
        exitstatus: The exit status of the test run.
    """
    _ = exitstatus  # Preserve for hook signature
    if not session.config.option.jamb:
        return

    collector = session.config.pluginmanager.get_plugin("jamb_collector")
    if not collector:
        return

    tester_id = session.config.option.jamb_tester_id
    software_version = session.config.option.jamb_software_version

    # Generate test records matrix if requested
    test_matrix_path = session.config.option.jamb_test_matrix or collector.jamb_config.test_matrix_output
    if test_matrix_path:
        test_format = infer_format(test_matrix_path)
        collector.generate_test_records_matrix(
            test_matrix_path,
            output_format=test_format,
            tester_id=tester_id,
            software_version=software_version,
        )

    # Generate traceability matrix if requested
    trace_matrix_path = session.config.option.jamb_trace_matrix or collector.jamb_config.trace_matrix_output
    trace_from = getattr(session.config.option, "trace_from", None) or collector.jamb_config.trace_from
    include_ancestors = (
        getattr(session.config.option, "include_ancestors", False) or collector.jamb_config.include_ancestors
    )

    if trace_matrix_path:
        trace_format = infer_format(trace_matrix_path)
        collector.generate_trace_matrix(
            trace_matrix_path,
            output_format=trace_format,
            trace_from=trace_from,
            include_ancestors=include_ancestors,
        )

    # Always save .jamb file for later matrix generation
    collector.save_coverage_file(
        tester_id=tester_id,
        software_version=software_version,
    )

    # Check coverage and potentially modify exit status
    fail_uncovered = session.config.option.jamb_fail_uncovered or collector.jamb_config.fail_uncovered
    if fail_uncovered:
        if not collector.all_test_items_covered():
            if session.exitstatus == 0:
                session.exitstatus = 1


def pytest_report_header(config: pytest.Config) -> list[str] | None:
    """Add jamb info to the pytest header.

    Args:
        config: The pytest configuration object.

    Returns:
        A list of strings with tracking information, or ``None`` if jamb
        is not enabled.
    """
    if config.option.jamb:
        collector = config.pluginmanager.get_plugin("jamb_collector")
        if collector and collector.graph:
            return [
                f"jamb: tracking {len(collector.graph.items)} requirement items",
            ]
    return None


def pytest_terminal_summary(
    terminalreporter: "TerminalReporter",
    exitstatus: int,
    config: pytest.Config,
) -> None:
    """Add coverage summary to terminal output.

    Prints total test spec items, coverage percentage, uncovered items,
    and unknown item references to the terminal.

    Args:
        terminalreporter: The pytest terminal reporter instance.
        exitstatus: The exit status of the test run.
        config: The pytest configuration object.
    """
    if not config.option.jamb:
        return

    collector = config.pluginmanager.get_plugin("jamb_collector")
    if not collector:
        return

    coverage = collector.get_coverage()
    if not coverage:
        return

    terminalreporter.write_sep("=", "Requirements Coverage Summary")

    # Count statistics - separate testable from non-testable
    testable_items = [
        c for c in coverage.values() if c.item.type == "requirement" and c.item.active and c.item.testable
    ]
    non_testable = [c for c in coverage.values() if c not in testable_items]

    total_testable = len(testable_items)
    covered = sum(1 for c in testable_items if c.is_covered)
    passed = sum(1 for c in testable_items if c.all_tests_passed)

    terminalreporter.write_line(f"Total testable items: {total_testable}")
    if total_testable > 0:
        terminalreporter.write_line(f"Covered by pytest tests: {covered} ({100 * covered / total_testable:.1f}%)")
        terminalreporter.write_line(f"All tests passing: {passed}")

    # Report non-testable breakdown if any exist
    if non_testable:
        heading_count = sum(1 for c in non_testable if c.item.type == "heading")
        info_count = sum(1 for c in non_testable if c.item.type == "info")
        inactive_count = sum(1 for c in non_testable if not c.item.active)
        untestable_count = sum(1 for c in non_testable if c.item.type == "requirement" and not c.item.testable)
        parts = []
        if heading_count:
            parts.append(f"heading: {heading_count}")
        if info_count:
            parts.append(f"info: {info_count}")
        if inactive_count:
            parts.append(f"inactive: {inactive_count}")
        if untestable_count:
            parts.append(f"non-testable: {untestable_count}")
        if parts:
            terminalreporter.write_line(f"Non-testable items: {len(non_testable)} ({', '.join(parts)})")

    # Report uncovered items - only testable items
    uncovered = [
        uid
        for uid, c in coverage.items()
        if not c.is_covered and c.item.type == "requirement" and c.item.active and c.item.testable
    ]
    if uncovered:
        terminalreporter.write_line("")
        terminalreporter.write_line("Uncovered test spec items:", red=True, bold=True)
        for uid in uncovered:
            item = coverage[uid].item
            terminalreporter.write_line(f"  - {uid}: {item.display_text}", red=True)

    # Report unknown items referenced in tests
    if collector.unknown_items:
        terminalreporter.write_line("")
        terminalreporter.write_line("Unknown items referenced in tests:", yellow=True, bold=True)
        for uid in sorted(collector.unknown_items):
            terminalreporter.write_line(f"  - {uid}", yellow=True)
