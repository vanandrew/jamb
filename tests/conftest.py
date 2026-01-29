"""Shared fixtures for jamb tests."""

import contextlib
import os
import warnings
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from jamb.cli.commands import cli
from jamb.core.models import Item, ItemCoverage, LinkedTest, TraceabilityGraph

# =============================================================================
# Warning Suppression Utilities
# =============================================================================


@contextlib.contextmanager
def expect_user_warning(match: str | None = None):
    """Context manager for code that is expected to emit UserWarning.

    Use this instead of bare `warnings.simplefilter("ignore")` to document
    that warnings are expected and optionally verify the warning message.

    Args:
        match: Optional regex pattern to match against warning message.
              If provided, asserts that at least one warning matches.

    Example:
        with expect_user_warning("deprecated"):
            deprecated_function()
    """
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always", UserWarning)
        yield recorded
        if match is not None:
            import re

            matched = any(re.search(match, str(w.message)) for w in recorded)
            if not matched:
                got = [str(w.message) for w in recorded]
                msg = f"Expected UserWarning matching '{match}', got: {got}"
                raise AssertionError(msg)


@contextlib.contextmanager
def suppress_expected_warnings():
    """Context manager to suppress expected warnings in tests.

    Use this when warnings are a known, documented side effect of the test
    scenario (e.g., testing deprecated paths or error recovery).
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        yield


# =============================================================================
# Shared Test Helpers
# =============================================================================


def _invoke(runner: CliRunner, args: list[str], *, cwd: Path | None = None):
    """Invoke CLI, optionally inside *cwd*.  Returns the Click result."""
    if cwd is not None:
        old = os.getcwd()
        os.chdir(cwd)
        try:
            return runner.invoke(cli, args, catch_exceptions=False)
        finally:
            os.chdir(old)
    return runner.invoke(cli, args, catch_exceptions=False)


def _read_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _write_yaml(path: Path, data: dict) -> None:
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


# =============================================================================
# Item Fixtures
# =============================================================================


@pytest.fixture
def sample_item() -> Item:
    """A basic Item for testing."""
    return Item(
        uid="SRS001",
        text="Software shall validate user credentials",
        document_prefix="SRS",
        active=True,
    )


@pytest.fixture
def item_with_header() -> Item:
    """An Item with a header set."""
    return Item(
        uid="SRS002",
        text="This is a very long requirement text that should be truncated",
        document_prefix="SRS",
        header="User Authentication",
        active=True,
    )


@pytest.fixture
def inactive_item() -> Item:
    """An inactive Item."""
    return Item(
        uid="SRS003",
        text="Deprecated requirement",
        document_prefix="SRS",
        active=False,
    )


@pytest.fixture
def item_with_links() -> Item:
    """An Item with parent links."""
    return Item(
        uid="SRS001",
        text="Software requirement",
        document_prefix="SRS",
        links=["SYS001", "SYS002"],
    )


# =============================================================================
# LinkedTest Fixtures
# =============================================================================


@pytest.fixture
def passed_test_link() -> LinkedTest:
    """A LinkedTest with passed outcome."""
    return LinkedTest(
        test_nodeid="test_auth.py::test_valid_credentials",
        item_uid="SRS001",
        test_outcome="passed",
    )


@pytest.fixture
def failed_test_link() -> LinkedTest:
    """A LinkedTest with failed outcome."""
    return LinkedTest(
        test_nodeid="test_auth.py::test_invalid_credentials",
        item_uid="SRS001",
        test_outcome="failed",
    )


@pytest.fixture
def pending_test_link() -> LinkedTest:
    """A LinkedTest with no outcome yet."""
    return LinkedTest(
        test_nodeid="test_auth.py::test_something",
        item_uid="SRS001",
        test_outcome=None,
    )


@pytest.fixture
def test_link_with_messages() -> LinkedTest:
    """A LinkedTest with custom notes."""
    return LinkedTest(
        test_nodeid="test_auth.py::test_boundary",
        item_uid="SRS001",
        test_outcome="passed",
        notes=["Verified boundary condition", "Tested edge case"],
        test_actions=["Entered boundary value"],
        expected_results=["System accepts value"],
    )


@pytest.fixture
def test_link_with_failure_message() -> LinkedTest:
    """A LinkedTest with a failure message."""
    return LinkedTest(
        test_nodeid="test_auth.py::test_failed",
        item_uid="SRS001",
        test_outcome="failed",
        notes=["[FAILURE] AssertionError: expected True, got False"],
    )


# =============================================================================
# Coverage Fixtures
# =============================================================================


@pytest.fixture
def covered_item_coverage(sample_item, passed_test_link) -> ItemCoverage:
    """ItemCoverage with passing test."""
    return ItemCoverage(item=sample_item, linked_tests=[passed_test_link])


@pytest.fixture
def uncovered_item_coverage(sample_item) -> ItemCoverage:
    """ItemCoverage with no linked tests."""
    return ItemCoverage(item=sample_item, linked_tests=[])


@pytest.fixture
def mixed_coverage(sample_item, passed_test_link, failed_test_link) -> ItemCoverage:
    """ItemCoverage with mixed test outcomes."""
    return ItemCoverage(item=sample_item, linked_tests=[passed_test_link, failed_test_link])


# =============================================================================
# Graph Fixtures
# =============================================================================


@pytest.fixture
def empty_graph() -> TraceabilityGraph:
    """An empty TraceabilityGraph."""
    return TraceabilityGraph()


@pytest.fixture
def simple_graph() -> TraceabilityGraph:
    """A graph with UN -> SYS -> SRS hierarchy."""
    graph = TraceabilityGraph()

    un = Item(uid="UN001", text="User need", document_prefix="UN", links=[])
    sys = Item(uid="SYS001", text="System requirement", document_prefix="SYS", links=["UN001"])
    srs = Item(
        uid="SRS001",
        text="Software requirement",
        document_prefix="SRS",
        links=["SYS001"],
    )

    graph.add_item(un)
    graph.add_item(sys)
    graph.add_item(srs)

    graph.set_document_parent("UN", None)
    graph.set_document_parent("SYS", "UN")
    graph.set_document_parent("SRS", "SYS")

    return graph


# =============================================================================
# Config Fixtures
# =============================================================================


@pytest.fixture
def sample_pyproject(tmp_path) -> Path:
    """Create a sample pyproject.toml with jamb config."""
    content = """
[tool.jamb]
test_documents = ["SRS", "SYS"]
fail_uncovered = true
test_matrix_output = "test-records.html"
trace_matrix_output = "traceability.html"
"""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(content)
    return pyproject


@pytest.fixture
def empty_pyproject(tmp_path) -> Path:
    """Create a pyproject.toml without jamb section."""
    content = """
[project]
name = "test-project"
version = "0.1.0"
"""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(content)
    return pyproject
