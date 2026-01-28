"""Collector for test-to-requirement mappings."""

import os
import platform
import socket
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any

import pytest

from jamb.config.loader import JambConfig, load_config
from jamb.core.models import (
    ItemCoverage,
    LinkedTest,
    MatrixMetadata,
    TestEnvironment,
    TraceabilityGraph,
)
from jamb.pytest_plugin.log import JAMB_LOG_KEY
from jamb.pytest_plugin.markers import get_requirement_markers


class RequirementCollector:
    """Collects test-to-requirement mappings during pytest execution.

    Attributes:
        pytest_config (pytest.Config): The pytest configuration object.
        jamb_config (JambConfig): Loaded jamb configuration
            (:class:`~jamb.config.loader.JambConfig`).
        graph (TraceabilityGraph | None): The traceability graph
            built from stored documents, or ``None`` if loading
            failed.
        test_links (list[LinkedTest]): Accumulated test-to-requirement links recorded
            during collection and execution.
        unknown_items (set[str]): UIDs referenced in test markers that do not
            exist in the traceability graph.
    """

    def __init__(self, config: pytest.Config) -> None:
        """Initialize the requirement collector.

        Loads the jamb configuration and the traceability graph from the
        native storage layer.

        Args:
            config: The pytest configuration object.
        """
        self.pytest_config = config
        self.jamb_config: JambConfig = load_config()
        self.graph: TraceabilityGraph | None = None
        self.test_links: list[LinkedTest] = []
        self.unknown_items: set[str] = set()
        self.execution_timestamp: str = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        self._load_requirements()

    def _load_requirements(self) -> None:
        """Load requirements from the native storage layer.

        Discovers documents and builds the traceability graph. If loading
        fails for any reason, emits a warning and initializes an empty
        graph so that the plugin can continue without requirements data.
        """
        try:
            from jamb.storage import build_traceability_graph, discover_documents

            dag = discover_documents()
            self.graph = build_traceability_graph(
                dag, exclude_patterns=self.jamb_config.exclude_patterns or None
            )
        except (ValueError, FileNotFoundError, OSError) as e:
            import warnings

            warnings.warn(f"Could not load requirements: {e}", stacklevel=2)
            self.graph = TraceabilityGraph()

    @pytest.hookimpl(hookwrapper=True)
    def pytest_collection_modifyitems(
        self, items: list[pytest.Item]
    ) -> Generator[None, None, None]:
        """Collect requirement markers from all test items.

        Extracts requirement UIDs from markers on each test item and records
        them as ``LinkedTest`` entries. Yields control for collection to
        complete first.

        Args:
            items: The list of pytest test items collected for the session.
        """
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
        call: pytest.CallInfo[None],  # noqa: ARG002
    ) -> Generator[None, Any, None]:
        """Record test outcomes, notes, test actions, and expected results.

        Captures the test outcome and data from the ``jamb_log`` fixture,
        including failure messages and skip reasons, and updates all
        ``LinkedTest`` entries for the test.

        Args:
            item: The pytest test item that was executed.
            call: The call information for the test phase.
        """
        _ = call  # Required by pytest hook signature
        outcome = yield
        report = outcome.get_result()

        if report.when == "call":
            notes: list[str] = []
            test_actions: list[str] = []
            expected_results: list[str] = []
            actual_results: list[str] = []

            # Capture custom data from jamb_log fixture
            if JAMB_LOG_KEY in item.stash:
                jamb_log = item.stash[JAMB_LOG_KEY]
                notes.extend(jamb_log.notes)
                test_actions.extend(jamb_log.test_actions)
                expected_results.extend(jamb_log.expected_results)
                actual_results.extend(jamb_log.actual_results)

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

            # Capture execution timestamp for this test
            test_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            # Update test outcomes and data for all links to this test
            for link in self.test_links:
                if link.test_nodeid == item.nodeid:
                    link.test_outcome = report.outcome
                    link.notes = notes
                    link.test_actions = test_actions
                    link.expected_results = expected_results
                    link.actual_results = actual_results
                    link.execution_timestamp = test_timestamp

    def get_coverage(self) -> dict[str, ItemCoverage]:
        """Build coverage report for all items in test documents.

        Returns:
            A dict mapping item UIDs to ``ItemCoverage`` objects for items
            in the configured test documents.
        """
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
        """Get list of test document prefixes to check for coverage.

        Priority order: CLI ``--jamb-documents`` option, then
        ``test_documents`` from the jamb config file, then leaf documents
        from the traceability graph.

        Returns:
            List of document prefix strings.
        """
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
        """Check if all normative items in test documents have test coverage.

        When ``require_all_pass`` is enabled (the default), an item is only
        considered covered if it has linked tests **and** all of those tests
        passed.

        Returns:
            True if every active requirement item meets the coverage
            criteria, False otherwise.
        """
        coverage = self.get_coverage()
        require_all_pass = self.jamb_config.require_all_pass
        for cov in coverage.values():
            if cov.item.type == "requirement" and cov.item.active:
                if not cov.is_covered:
                    return False
                if require_all_pass and not cov.all_tests_passed:
                    return False
        return True

    def _build_test_environment(self) -> TestEnvironment:
        """Build test environment information using stdlib modules.

        Returns:
            A TestEnvironment with current system information.
        """
        # Get test tools from pytest plugin manager
        test_tools: dict[str, str] = {}

        # Always include pytest version first
        try:
            import pytest as pytest_module

            test_tools["pytest"] = pytest_module.__version__
        except (ImportError, AttributeError):
            pass

        # Get all loaded pytest plugins with their versions
        try:
            plugin_info = self.pytest_config.pluginmanager.list_plugin_distinfo()
            for _plugin, dist in plugin_info:
                name = dist.project_name
                version = dist.version
                # Skip pytest itself (already added) and internal plugins
                if name.lower() != "pytest" and not name.startswith("_"):
                    test_tools[name] = version
        except Exception:
            # Fallback: at least try to get jamb version
            try:
                from importlib.metadata import version

                test_tools["jamb"] = version("jamb")
            except Exception:
                pass

        return TestEnvironment(
            os_name=platform.system(),
            os_version=platform.release(),
            python_version=platform.python_version(),
            platform=platform.machine(),
            processor=platform.processor() or "unknown",
            hostname=socket.gethostname(),
            cpu_count=os.cpu_count(),
            test_tools=test_tools,
        )

    def generate_matrix(
        self,
        path: str,
        output_format: str,
        tester_id: str = "Unknown",
        software_version: str | None = None,
    ) -> None:
        """Generate traceability matrix.

        Args:
            path: The output file path for the generated matrix.
            output_format: The output format (html, markdown, json, csv, or xlsx).
            tester_id: Identification of the tester or CI system.
            software_version: Software version override (takes precedence over config).
        """
        from jamb.matrix.generator import generate_matrix

        coverage = self.get_coverage()

        # Build metadata for IEC 62304 5.7.5 compliance
        # CLI flag takes precedence over config file / pyproject.toml
        version = software_version or self.jamb_config.software_version
        metadata = MatrixMetadata(
            software_version=version,
            tester_id=tester_id,
            execution_timestamp=self.execution_timestamp,
            environment=self._build_test_environment(),
        )

        generate_matrix(
            coverage,
            self.graph,
            path,
            output_format,
            trace_to_ignore=set(self.jamb_config.trace_to_ignore),
            metadata=metadata,
        )
