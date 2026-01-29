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

# Valid test outcomes for type validation
VALID_OUTCOMES = {"passed", "failed", "skipped", "error"}


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
        self._links_by_nodeid: dict[str, list[LinkedTest]] = {}
        self.unknown_items: set[str] = set()
        self.execution_timestamp: str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._load_requirements()

    def _load_requirements(self) -> None:
        """Load requirements from the native storage layer.

        Discovers documents and builds the traceability graph. If loading
        fails for any reason, logs an error and initializes an empty
        graph so that the plugin can continue without requirements data.
        The ``_graph_load_failed`` flag is set to indicate that graph
        loading failed.
        """
        self._graph_load_failed = False
        try:
            from jamb.storage import build_traceability_graph, discover_documents

            dag = discover_documents()
            self.graph = build_traceability_graph(dag, exclude_patterns=self.jamb_config.exclude_patterns or None)
        except (ValueError, FileNotFoundError, OSError) as e:
            import logging
            import warnings

            logger = logging.getLogger("jamb")
            logger.error("Could not load requirements: %s", e)
            warnings.warn(f"Could not load requirements: {e}", stacklevel=2)
            self.graph = TraceabilityGraph()
            self._graph_load_failed = True

    @pytest.hookimpl(hookwrapper=True)
    def pytest_collection_modifyitems(self, items: list[pytest.Item]) -> Generator[None, None, None]:
        """Collect requirement markers from all test items.

        Extracts requirement UIDs from markers on each test item and records
        them as ``LinkedTest`` entries. Yields control for collection to
        complete first.

        Args:
            items: The list of pytest test items collected for the session.
        """
        yield  # Let collection complete

        # Fail early if graph loading failed
        if self._graph_load_failed:
            raise pytest.UsageError(
                "Cannot run with --jamb: requirement graph failed to load. Check earlier warnings for details."
            )

        for item in items:
            req_uids = get_requirement_markers(item)
            for uid in req_uids:
                is_unknown = self.graph and not self._graph_load_failed and uid not in self.graph.items
                if is_unknown:
                    self.unknown_items.add(uid)

                link = LinkedTest(
                    test_nodeid=item.nodeid,
                    item_uid=uid,
                )
                self.test_links.append(link)
                self._links_by_nodeid.setdefault(item.nodeid, []).append(link)

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

        links_for_node = self._links_by_nodeid.get(item.nodeid)
        if links_for_node is None:
            links_for_node = [lk for lk in self.test_links if lk.test_nodeid == item.nodeid]

        if report.when == "setup":
            if report.failed:
                for link in links_for_node:
                    link.test_outcome = "error"
                    link.notes = [f"[SETUP FAILURE] {report.longreprtext or ''}"]
            elif report.skipped:
                reason = ""
                if hasattr(report, "wasxfail") and report.wasxfail:
                    reason = report.wasxfail
                elif report.longreprtext:
                    reason = report.longreprtext
                for link in links_for_node:
                    link.test_outcome = "skipped"
                    link.notes = [f"[SKIPPED] {reason}"]
        elif report.when == "call":
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

            # Validate and normalize test outcome
            outcome = report.outcome
            if outcome not in VALID_OUTCOMES:
                import warnings

                warnings.warn(
                    f"Unknown test outcome '{outcome}', using 'error'",
                    stacklevel=2,
                )
                outcome = "error"

            # Update test outcomes and data for all links to this test
            for link in links_for_node:
                link.test_outcome = outcome
                link.notes = list(notes)
                link.test_actions = list(test_actions)
                link.expected_results = list(expected_results)
                link.actual_results = list(actual_results)
                link.execution_timestamp = test_timestamp
        elif report.when == "teardown":
            if report.failed:
                for link in links_for_node:
                    if link.test_outcome not in ("failed", "error"):
                        link.test_outcome = "error"
                        link.notes.append(f"[TEARDOWN FAILURE] {report.longreprtext or ''}")

    def get_coverage(self) -> dict[str, ItemCoverage]:
        """Build coverage report for all items in test documents.

        Returns:
            A dict mapping item UIDs to ``ItemCoverage`` objects for items
            in the configured test documents.
        """
        coverage: dict[str, ItemCoverage] = {}

        if not self.graph:
            return coverage

        # Build index of links by item UID for O(1) lookup
        links_by_uid: dict[str, list[LinkedTest]] = {}
        for link in self.test_links:
            links_by_uid.setdefault(link.item_uid, []).append(link)

        # Get test document prefixes
        test_docs = self._get_test_documents()

        # Build coverage for items in test documents
        for prefix in test_docs:
            for item in self.graph.get_items_by_document(prefix):
                coverage[item.uid] = ItemCoverage(
                    item=item,
                    linked_tests=links_by_uid.get(item.uid, []),
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
            if cov.item.type == "requirement" and cov.item.active and cov.item.testable:
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

        import logging

        logger = logging.getLogger("jamb")

        # Always include pytest version first
        try:
            import pytest as pytest_module

            test_tools["pytest"] = pytest_module.__version__
        except AttributeError as e:
            logger.debug("Could not get pytest version: %s", e)

        # Get all loaded pytest plugins with their versions
        try:
            plugin_info = self.pytest_config.pluginmanager.list_plugin_distinfo()
            for _plugin, dist in plugin_info:
                name = dist.project_name
                version = dist.version
                # Skip pytest itself (already added) and internal plugins
                if name.lower() != "pytest" and not name.startswith("_"):
                    test_tools[name] = version
        except (AttributeError, TypeError, OSError) as e:
            logger.debug("Could not get plugin versions: %s", e)
            # Fallback: at least try to get jamb version
            from importlib.metadata import PackageNotFoundError
            from importlib.metadata import version as get_version

            try:
                test_tools["jamb"] = get_version("jamb")
            except (AttributeError, TypeError, OSError, PackageNotFoundError) as e2:
                logger.debug("Could not get jamb version: %s", e2)

        try:
            hostname = socket.gethostname()
        except OSError:
            hostname = "unknown"

        return TestEnvironment(
            os_name=platform.system(),
            os_version=platform.release(),
            python_version=platform.python_version(),
            platform=platform.machine(),
            processor=platform.processor() or "unknown",
            hostname=hostname,
            cpu_count=os.cpu_count(),
            test_tools=test_tools,
        )

    def _build_matrix_metadata(
        self,
        tester_id: str = "Unknown",
        software_version: str | None = None,
    ) -> MatrixMetadata:
        """Build matrix metadata for IEC 62304 5.7.5 compliance.

        Args:
            tester_id: Identification of the tester or CI system.
            software_version: Software version override (takes precedence over config).

        Returns:
            MatrixMetadata populated with version, tester, timestamp, and environment.
        """
        version = software_version or self.jamb_config.software_version
        return MatrixMetadata(
            software_version=version,
            tester_id=tester_id,
            execution_timestamp=self.execution_timestamp,
            environment=self._build_test_environment(),
        )

    def _build_links_by_uid(self) -> dict[str, list[LinkedTest]]:
        """Build mapping of test links by item UID.

        This allows chain_builder to find tests linked to any item,
        including higher-order items not in coverage.

        Returns:
            Dict mapping item UIDs to lists of LinkedTest objects.
        """
        links_by_uid: dict[str, list[LinkedTest]] = {}
        for link in self.test_links:
            links_by_uid.setdefault(link.item_uid, []).append(link)
        return links_by_uid

    def generate_test_records_matrix(
        self,
        path: str,
        output_format: str,
        tester_id: str = "Unknown",
        software_version: str | None = None,
    ) -> None:
        """Generate test records matrix.

        Args:
            path: The output file path for the generated matrix.
            output_format: The output format (html, markdown, json, csv, or xlsx).
            tester_id: Identification of the tester or CI system.
            software_version: Software version override (takes precedence over config).
        """
        from jamb.matrix.generator import (
            build_test_records,
            generate_test_records_matrix,
        )

        coverage = self.get_coverage()
        records = build_test_records(coverage)
        metadata = self._build_matrix_metadata(tester_id, software_version)

        generate_test_records_matrix(
            records,
            path,
            output_format,
            metadata=metadata,
        )

    def generate_trace_matrix(
        self,
        path: str,
        output_format: str,
        trace_from: str | None = None,
        include_ancestors: bool = False,
    ) -> None:
        """Generate traceability matrix.

        Args:
            path: The output file path for the generated matrix.
            output_format: The output format (html, markdown, json, csv, or xlsx).
            trace_from: Starting document prefix for trace matrix.
                If not provided, auto-detects the root document.
            include_ancestors: Whether to include "Traces To" column.
        """
        from jamb.matrix.generator import generate_full_chain_matrix

        coverage = self.get_coverage()

        if not self.graph:
            raise ValueError("No traceability graph available")

        # Auto-detect root document if not specified
        if trace_from is None:
            root_docs = self.graph.get_root_documents()
            if not root_docs:
                raise ValueError("No root documents found. Use trace_from to specify.")
            trace_from = root_docs[0]

        # Get trace_to_ignore from config
        trace_to_ignore: set[str] | None = None
        if self.jamb_config.trace_to_ignore:
            trace_to_ignore = set(self.jamb_config.trace_to_ignore)

        generate_full_chain_matrix(
            coverage,
            self.graph,
            path,
            output_format,
            trace_from=trace_from,
            include_ancestors=include_ancestors,
            trace_to_ignore=trace_to_ignore,
            all_test_links=self._build_links_by_uid(),
        )

    def save_coverage_file(
        self,
        output_path: str = ".jamb",
        tester_id: str = "Unknown",
        software_version: str | None = None,
    ) -> None:
        """Save coverage data to .jamb file for later matrix generation.

        This allows running tests once and generating multiple matrix views
        without re-running the tests.

        Args:
            output_path: Path to write the coverage file (default: .jamb).
            tester_id: Identification of the tester or CI system.
            software_version: Software version override.
        """
        from jamb.coverage.serializer import save_coverage

        if self.graph is None:
            return

        coverage = self.get_coverage()
        metadata = self._build_matrix_metadata(tester_id, software_version)

        save_coverage(coverage, self.graph, output_path, metadata)
