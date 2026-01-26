"""Collector for test-to-requirement mappings."""

from collections.abc import Generator
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from _pytest.terminal import TerminalReporter

from jamb.config.loader import JambConfig, load_config
from jamb.core.models import ItemCoverage, LinkedTest, TraceabilityGraph
from jamb.doorstop.discovery import discover_tree
from jamb.doorstop.reader import build_traceability_graph
from jamb.pytest_plugin.log import JAMB_LOG_KEY
from jamb.pytest_plugin.markers import get_requirement_markers


class RequirementCollector:
    """Collects test-to-requirement mappings during pytest execution."""

    def __init__(self, config: pytest.Config) -> None:
        self.pytest_config = config
        self.jamb_config: JambConfig = load_config()
        self.graph: TraceabilityGraph | None = None
        self.test_links: list[LinkedTest] = []
        self.unknown_items: set[str] = set()
        self._load_doorstop()

    def _load_doorstop(self) -> None:
        """Load requirements from doorstop."""
        try:
            tree = discover_tree()
            self.graph = build_traceability_graph(tree)
        except Exception as e:
            # If doorstop isn't configured, create empty graph
            import warnings

            warnings.warn(f"Could not load doorstop tree: {e}", stacklevel=2)
            self.graph = TraceabilityGraph()

    @pytest.hookimpl(hookwrapper=True)
    def pytest_collection_modifyitems(
        self, items: list[pytest.Item]
    ) -> Generator[None, None, None]:
        """Collect requirement markers from all test items."""
        yield  # Let collection complete

        for item in items:
            req_uids = get_requirement_markers(item)
            for uid in req_uids:
                if self.graph and uid not in self.graph.items:
                    self.unknown_items.add(uid)

                self.test_links.append(
                    LinkedTest(
                        test_nodeid=item.nodeid,
                        item_uid=uid,
                    )
                )

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(
        self,
        item: pytest.Item,
        call: pytest.CallInfo,  # noqa: ARG002
    ) -> Generator[None, Any, None]:
        """Record test outcomes, notes, test actions, and expected results."""
        _ = call  # Required by pytest hook signature
        outcome = yield
        report = outcome.get_result()

        if report.when == "call":
            notes: list[str] = []
            test_actions: list[str] = []
            expected_results: list[str] = []

            # Capture custom data from jamb_log fixture
            if JAMB_LOG_KEY in item.stash:
                jamb_log = item.stash[JAMB_LOG_KEY]
                notes.extend(jamb_log.notes)
                test_actions.extend(jamb_log.test_actions)
                expected_results.extend(jamb_log.expected_results)

            # Capture failure message/traceback
            if report.failed and report.longreprtext:
                failure_msg = report.longreprtext
                if len(failure_msg) > 500:
                    failure_msg = failure_msg[:500] + "\n... (truncated)"
                notes.append(f"[FAILURE] {failure_msg}")

            # Capture skip reason
            if report.skipped:
                if hasattr(report, "wasxfail") and report.wasxfail:
                    notes.append(f"[XFAIL] {report.wasxfail}")
                elif report.longreprtext:
                    notes.append(f"[SKIPPED] {report.longreprtext}")

            # Update test outcomes and data for all links to this test
            for link in self.test_links:
                if link.test_nodeid == item.nodeid:
                    link.test_outcome = report.outcome
                    link.notes = notes
                    link.test_actions = test_actions
                    link.expected_results = expected_results

    def get_coverage(self) -> dict[str, ItemCoverage]:
        """Build coverage report for all items in test documents."""
        coverage: dict[str, ItemCoverage] = {}

        if not self.graph:
            return coverage

        # Get test document prefixes
        test_docs = self._get_test_documents()

        # Build coverage for items in test documents
        for prefix in test_docs:
            for item in self.graph.get_items_by_document(prefix):
                linked_tests = [
                    link for link in self.test_links if link.item_uid == item.uid
                ]
                coverage[item.uid] = ItemCoverage(
                    item=item,
                    linked_tests=linked_tests,
                )

        return coverage

    def _get_test_documents(self) -> list[str]:
        """Get list of test document prefixes to check for coverage."""
        # Command line option takes precedence
        if docs := self.pytest_config.option.jamb_documents:
            return [d.strip() for d in docs.split(",")]

        # Then config file
        if self.jamb_config.test_documents:
            return self.jamb_config.test_documents

        # Default: use leaf documents (documents that aren't parents of others)
        if self.graph:
            return self.graph.get_leaf_documents()

        return []

    def all_test_items_covered(self) -> bool:
        """Check if all normative items in test documents have test coverage."""
        coverage = self.get_coverage()
        for cov in coverage.values():
            if cov.item.normative and cov.item.active and not cov.is_covered:
                return False
        return True

    def generate_matrix(self, path: str, format: str) -> None:
        """Generate traceability matrix."""
        from jamb.matrix.generator import generate_matrix

        coverage = self.get_coverage()
        generate_matrix(
            coverage,
            self.graph,
            path,
            format,
            trace_to_ignore=set(self.jamb_config.trace_to_ignore),
        )


@pytest.hookimpl(trylast=True)
def pytest_report_header(config: pytest.Config) -> list[str] | None:
    """Add jamb info to pytest header."""
    if config.option.jamb:
        collector = config.pluginmanager.get_plugin("jamb_collector")
        if collector and collector.graph:
            return [
                f"jamb: tracking {len(collector.graph.items)} doorstop items",
            ]
    return None


@pytest.hookimpl(trylast=True)
def pytest_terminal_summary(
    terminalreporter: "TerminalReporter",
    exitstatus: int,  # noqa: ARG001
    config: pytest.Config,
) -> None:
    _ = exitstatus  # Required by pytest hook signature
    """Add coverage summary to terminal output."""
    if not config.option.jamb:
        return

    collector = config.pluginmanager.get_plugin("jamb_collector")
    if not collector:
        return

    coverage = collector.get_coverage()
    if not coverage:
        return

    terminalreporter.write_sep("=", "Requirements Coverage Summary")

    # Count statistics
    total = len(coverage)
    covered = sum(1 for c in coverage.values() if c.is_covered)
    passed = sum(1 for c in coverage.values() if c.all_tests_passed)

    terminalreporter.write_line(f"Total test spec items: {total}")
    if total > 0:
        terminalreporter.write_line(
            f"Covered by pytest tests: {covered} ({100 * covered / total:.1f}%)"
        )
        terminalreporter.write_line(f"All tests passing: {passed}")

    # Report uncovered items
    uncovered = [
        uid
        for uid, c in coverage.items()
        if not c.is_covered and c.item.normative and c.item.active
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
        terminalreporter.write_line(
            "Unknown items referenced in tests:", yellow=True, bold=True
        )
        for uid in sorted(collector.unknown_items):
            terminalreporter.write_line(f"  - {uid}", yellow=True)
