"""Unit tests for the chain builder module."""

import warnings

import pytest

from jamb.core.models import (
    Item,
    ItemCoverage,
    LinkedTest,
    TraceabilityGraph,
)
from jamb.matrix.chain_builder import (
    MAX_RECURSION_DEPTH,
    build_full_chain_matrix,
    calculate_rollup_status,
    get_document_paths,
)

# ============================================================================
# Fixtures for common graph configurations
# ============================================================================


@pytest.fixture
def sys_srs_graph() -> TraceabilityGraph:
    """Create a simple SYS -> SRS document hierarchy."""
    graph = TraceabilityGraph()
    graph.set_document_parents("SRS", ["SYS"])
    graph.set_document_parents("SYS", [])
    return graph


@pytest.fixture
def un_sys_srs_graph() -> TraceabilityGraph:
    """Create a UN -> SYS -> SRS document hierarchy."""
    graph = TraceabilityGraph()
    graph.set_document_parents("SRS", ["SYS"])
    graph.set_document_parents("SYS", ["UN"])
    graph.set_document_parents("UN", [])
    return graph


@pytest.fixture
def prj_un_sys_srs_graph() -> TraceabilityGraph:
    """Create a PRJ -> UN -> SYS -> SRS document hierarchy."""
    graph = TraceabilityGraph()
    graph.set_document_parents("SRS", ["SYS"])
    graph.set_document_parents("SYS", ["UN"])
    graph.set_document_parents("UN", ["PRJ"])
    graph.set_document_parents("PRJ", [])
    return graph


def make_linked_test(
    nodeid: str,
    item_uid: str,
    outcome: str | None = "passed",
) -> LinkedTest:
    """Create a LinkedTest with common defaults."""
    return LinkedTest(
        test_nodeid=nodeid,
        item_uid=item_uid,
        test_outcome=outcome,  # type: ignore[arg-type]
    )


class TestGetDocumentPaths:
    """Tests for the get_document_paths function."""

    def test_single_path(self):
        """Test finding a single linear path."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SYS", ["UN"])
        graph.set_document_parents("UN", [])

        paths = get_document_paths(graph, "UN")

        assert len(paths) == 1
        assert paths[0] == ["UN", "SYS", "SRS"]

    def test_starting_from_leaf(self):
        """Test starting from a leaf document."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SYS", [])

        paths = get_document_paths(graph, "SRS")

        assert len(paths) == 1
        assert paths[0] == ["SRS"]

    def test_diverging_paths(self):
        """Test finding multiple diverging paths."""
        graph = TraceabilityGraph()
        # PRJ -> UN -> SYS -> SRS
        # PRJ -> HAZ -> RC -> SRS
        graph.set_document_parents("SRS", ["SYS", "RC"])
        graph.set_document_parents("SYS", ["UN"])
        graph.set_document_parents("RC", ["HAZ"])
        graph.set_document_parents("UN", ["PRJ"])
        graph.set_document_parents("HAZ", ["PRJ"])
        graph.set_document_parents("PRJ", [])

        paths = get_document_paths(graph, "PRJ")

        assert len(paths) == 2
        # Both paths should end at SRS
        path_ends = [p[-1] for p in paths]
        assert "SRS" in path_ends

    def test_invalid_prefix_raises(self):
        """Test that invalid prefix raises ValueError."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", [])

        with pytest.raises(ValueError, match="not found in hierarchy"):
            get_document_paths(graph, "INVALID")


class TestCalculateRollupStatus:
    """Tests for the calculate_rollup_status function."""

    def test_passed_when_all_tests_pass(self):
        """Test that status is Passed when all tests pass."""
        graph = TraceabilityGraph()
        item = Item(uid="SRS001", text="Test", document_prefix="SRS")
        graph.add_item(item)

        coverage = {
            "SRS001": ItemCoverage(
                item=item,
                linked_tests=[
                    LinkedTest(
                        test_nodeid="test::test1",
                        item_uid="SRS001",
                        test_outcome="passed",
                    ),
                ],
            ),
        }

        status, tests = calculate_rollup_status(graph, item, coverage)

        assert status == "Passed"
        assert len(tests) == 1

    def test_failed_when_any_test_fails(self):
        """Test that status is Failed when any test fails."""
        graph = TraceabilityGraph()
        item = Item(uid="SRS001", text="Test", document_prefix="SRS")
        graph.add_item(item)

        coverage = {
            "SRS001": ItemCoverage(
                item=item,
                linked_tests=[
                    LinkedTest(
                        test_nodeid="test::test1",
                        item_uid="SRS001",
                        test_outcome="failed",
                    ),
                ],
            ),
        }

        status, tests = calculate_rollup_status(graph, item, coverage)

        assert status == "Failed"

    def test_partial_with_mixed_results(self):
        """Test that status is Partial with mixed results."""
        graph = TraceabilityGraph()
        item = Item(uid="SRS001", text="Test", document_prefix="SRS")
        graph.add_item(item)

        coverage = {
            "SRS001": ItemCoverage(
                item=item,
                linked_tests=[
                    LinkedTest(
                        test_nodeid="test::test1",
                        item_uid="SRS001",
                        test_outcome="passed",
                    ),
                    LinkedTest(
                        test_nodeid="test::test2",
                        item_uid="SRS001",
                        test_outcome="failed",
                    ),
                ],
            ),
        }

        status, tests = calculate_rollup_status(graph, item, coverage)

        assert status == "Partial"
        assert len(tests) == 2

    def test_not_covered_when_no_tests(self):
        """Test that status is Not Covered when no tests."""
        graph = TraceabilityGraph()
        item = Item(uid="SRS001", text="Test", document_prefix="SRS")
        graph.add_item(item)

        coverage = {
            "SRS001": ItemCoverage(item=item, linked_tests=[]),
        }

        status, tests = calculate_rollup_status(graph, item, coverage)

        assert status == "Not Covered"
        assert len(tests) == 0

    def test_na_when_not_testable(self):
        """Test that status is N/A when item is not testable."""
        graph = TraceabilityGraph()
        item = Item(uid="SRS001", text="Test", document_prefix="SRS", testable=False)
        graph.add_item(item)

        coverage = {
            "SRS001": ItemCoverage(item=item, linked_tests=[]),
        }

        status, tests = calculate_rollup_status(graph, item, coverage)

        assert status == "N/A"


class TestBuildFullChainMatrix:
    """Tests for the build_full_chain_matrix function."""

    def test_basic_chain(self, sys_srs_graph):
        """Test building a basic chain matrix."""
        # Add items with links
        sys_item = Item(uid="SYS001", text="System item", document_prefix="SYS")
        srs_item = Item(uid="SRS001", text="SRS item", document_prefix="SRS", links=["SYS001"])

        sys_srs_graph.add_item(sys_item)
        sys_srs_graph.add_item(srs_item)

        coverage = {
            "SRS001": ItemCoverage(
                item=srs_item,
                linked_tests=[make_linked_test("test::test1", "SRS001")],
            ),
        }

        matrices = build_full_chain_matrix(sys_srs_graph, coverage, "SYS")

        assert len(matrices) == 1
        matrix = matrices[0]
        assert matrix.path_name == "SYS -> SRS"
        assert matrix.document_hierarchy == ["SYS", "SRS"]
        assert len(matrix.rows) > 0

    def test_include_ancestors(self, un_sys_srs_graph):
        """Test that ancestors are included when requested."""
        un_item = Item(uid="UN001", text="UN item", document_prefix="UN")
        sys_item = Item(uid="SYS001", text="System item", document_prefix="SYS", links=["UN001"])
        srs_item = Item(uid="SRS001", text="SRS item", document_prefix="SRS", links=["SYS001"])

        un_sys_srs_graph.add_item(un_item)
        un_sys_srs_graph.add_item(sys_item)
        un_sys_srs_graph.add_item(srs_item)

        coverage = {
            "SRS001": ItemCoverage(item=srs_item, linked_tests=[]),
        }

        matrices = build_full_chain_matrix(un_sys_srs_graph, coverage, "SYS", include_ancestors=True)

        assert len(matrices) == 1
        matrix = matrices[0]
        assert matrix.include_ancestors is True
        # Check that rows have ancestor_uids populated
        if matrix.rows:
            # The first row should have UN001 as an ancestor of SYS001
            first_row = matrix.rows[0]
            assert "UN001" in first_row.ancestor_uids

    def test_summary_calculation(self):
        """Test that summary statistics are calculated correctly."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", [])

        srs_item1 = Item(uid="SRS001", text="Item 1", document_prefix="SRS")
        srs_item2 = Item(uid="SRS002", text="Item 2", document_prefix="SRS")

        graph.add_item(srs_item1)
        graph.add_item(srs_item2)

        coverage = {
            "SRS001": ItemCoverage(
                item=srs_item1,
                linked_tests=[
                    LinkedTest(
                        test_nodeid="test::test1",
                        item_uid="SRS001",
                        test_outcome="passed",
                    ),
                ],
            ),
            "SRS002": ItemCoverage(
                item=srs_item2,
                linked_tests=[],
            ),
        }

        matrices = build_full_chain_matrix(graph, coverage, "SRS")

        assert len(matrices) == 1
        matrix = matrices[0]
        assert matrix.summary["total"] == 2
        assert matrix.summary["passed"] == 1
        assert matrix.summary["not_covered"] == 1

    def test_invalid_prefix_raises(self):
        """Test that invalid prefix raises ValueError."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", [])

        with pytest.raises(ValueError, match="not found in hierarchy"):
            build_full_chain_matrix(graph, {}, "INVALID")

    def test_no_items_at_start_prefix(self):
        """Test that empty list is returned when no items at start prefix."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SYS", [])
        # No items added to graph

        matrices = build_full_chain_matrix(graph, {}, "SYS")

        assert len(matrices) == 1
        assert len(matrices[0].rows) == 0

    def test_missing_children_creates_gap_row(self):
        """Test that rows are created even when children are missing."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SYS", [])

        # Add SYS item with no SRS children
        sys_item = Item(uid="SYS001", text="System item", document_prefix="SYS")
        graph.add_item(sys_item)

        coverage = {
            "SYS001": ItemCoverage(
                item=sys_item,
                linked_tests=[
                    LinkedTest(
                        test_nodeid="test::test1",
                        item_uid="SYS001",
                        test_outcome="passed",
                    ),
                ],
            ),
        }

        matrices = build_full_chain_matrix(graph, coverage, "SYS")

        assert len(matrices) == 1
        matrix = matrices[0]
        # Should have a row for SYS001 with gap at SRS level
        assert len(matrix.rows) == 1
        row = matrix.rows[0]
        assert row.chain["SYS"] is not None
        assert row.chain["SRS"] is None

    def test_rollup_with_all_untestable_descendants(self):
        """Test that rollup returns N/A when all descendants are untestable."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SYS", [])

        sys_item = Item(uid="SYS001", text="System item", document_prefix="SYS", testable=False)
        srs_item = Item(
            uid="SRS001",
            text="SRS item",
            document_prefix="SRS",
            links=["SYS001"],
            testable=False,
        )

        graph.add_item(sys_item)
        graph.add_item(srs_item)

        coverage = {
            "SRS001": ItemCoverage(item=srs_item, linked_tests=[]),
        }

        status, tests = calculate_rollup_status(graph, sys_item, coverage)

        assert status == "N/A"
        assert len(tests) == 0

    def test_summary_calculation_with_mixed_statuses(self):
        """Test that summary correctly counts all status types."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", [])

        # Create items with different statuses
        passed_item = Item(uid="SRS001", text="Passed", document_prefix="SRS")
        failed_item = Item(uid="SRS002", text="Failed", document_prefix="SRS")
        uncovered_item = Item(uid="SRS003", text="Uncovered", document_prefix="SRS")
        na_item = Item(uid="SRS004", text="N/A", document_prefix="SRS", testable=False)

        graph.add_item(passed_item)
        graph.add_item(failed_item)
        graph.add_item(uncovered_item)
        graph.add_item(na_item)

        coverage = {
            "SRS001": ItemCoverage(
                item=passed_item,
                linked_tests=[
                    LinkedTest(
                        test_nodeid="test::pass",
                        item_uid="SRS001",
                        test_outcome="passed",
                    ),
                ],
            ),
            "SRS002": ItemCoverage(
                item=failed_item,
                linked_tests=[
                    LinkedTest(
                        test_nodeid="test::fail",
                        item_uid="SRS002",
                        test_outcome="failed",
                    ),
                ],
            ),
            "SRS003": ItemCoverage(item=uncovered_item, linked_tests=[]),
            "SRS004": ItemCoverage(item=na_item, linked_tests=[]),
        }

        matrices = build_full_chain_matrix(graph, coverage, "SRS")

        assert len(matrices) == 1
        summary = matrices[0].summary
        assert summary["total"] == 4
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["not_covered"] == 1
        assert summary["na"] == 1


class TestTraceToIgnore:
    """Tests for trace_to_ignore filtering in build_full_chain_matrix."""

    def test_trace_to_ignore_filters_document_hierarchy(self, prj_un_sys_srs_graph):
        """Test that trace_to_ignore removes documents from hierarchy."""
        prj_item = Item(uid="PRJ001", text="Project", document_prefix="PRJ")
        un_item = Item(uid="UN001", text="User need", document_prefix="UN", links=["PRJ001"])
        sys_item = Item(uid="SYS001", text="System", document_prefix="SYS", links=["UN001"])
        srs_item = Item(uid="SRS001", text="Software", document_prefix="SRS", links=["SYS001"])

        prj_un_sys_srs_graph.add_item(prj_item)
        prj_un_sys_srs_graph.add_item(un_item)
        prj_un_sys_srs_graph.add_item(sys_item)
        prj_un_sys_srs_graph.add_item(srs_item)

        coverage = {"SRS001": ItemCoverage(item=srs_item, linked_tests=[])}

        # Ignore PRJ document - suppress expected warning about incomplete trace chains
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            matrices = build_full_chain_matrix(prj_un_sys_srs_graph, coverage, "PRJ", trace_to_ignore={"PRJ"})

        assert len(matrices) == 1
        matrix = matrices[0]
        # PRJ should not be in the hierarchy
        assert "PRJ" not in matrix.document_hierarchy
        assert matrix.document_hierarchy == ["UN", "SYS", "SRS"]

    def test_trace_to_ignore_filters_ancestor_uids(self, prj_un_sys_srs_graph):
        """Test that trace_to_ignore removes ancestors from ancestor_uids."""
        prj_item = Item(uid="PRJ001", text="Project", document_prefix="PRJ")
        un_item = Item(uid="UN001", text="User need", document_prefix="UN", links=["PRJ001"])
        sys_item = Item(uid="SYS001", text="System", document_prefix="SYS", links=["UN001"])
        srs_item = Item(uid="SRS001", text="Software", document_prefix="SRS", links=["SYS001"])

        prj_un_sys_srs_graph.add_item(prj_item)
        prj_un_sys_srs_graph.add_item(un_item)
        prj_un_sys_srs_graph.add_item(sys_item)
        prj_un_sys_srs_graph.add_item(srs_item)

        coverage = {"SRS001": ItemCoverage(item=srs_item, linked_tests=[])}

        # Include ancestors but ignore PRJ
        matrices = build_full_chain_matrix(
            prj_un_sys_srs_graph,
            coverage,
            "UN",
            include_ancestors=True,
            trace_to_ignore={"PRJ"},
        )

        assert len(matrices) == 1
        matrix = matrices[0]
        # Check that rows have UN001's ancestors, but PRJ001 is filtered out
        for row in matrix.rows:
            assert "PRJ001" not in row.ancestor_uids

    def test_trace_to_ignore_filters_chain_keys(self):
        """Test that trace_to_ignore removes documents from chain dict."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SYS", ["UN"])
        graph.set_document_parents("UN", [])

        un_item = Item(uid="UN001", text="User need", document_prefix="UN")
        sys_item = Item(uid="SYS001", text="System", document_prefix="SYS", links=["UN001"])
        srs_item = Item(uid="SRS001", text="Software", document_prefix="SRS", links=["SYS001"])

        graph.add_item(un_item)
        graph.add_item(sys_item)
        graph.add_item(srs_item)

        coverage = {"SRS001": ItemCoverage(item=srs_item, linked_tests=[])}

        # Ignore UN document - suppress expected warning about incomplete trace chains
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            matrices = build_full_chain_matrix(graph, coverage, "UN", trace_to_ignore={"UN"})

        assert len(matrices) == 1
        matrix = matrices[0]
        # UN should not be in the chain keys
        for row in matrix.rows:
            assert "UN" not in row.chain

    def test_trace_to_ignore_empty_set_includes_all(self):
        """Test that empty trace_to_ignore includes all documents."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SYS", [])

        sys_item = Item(uid="SYS001", text="System", document_prefix="SYS")
        srs_item = Item(uid="SRS001", text="Software", document_prefix="SRS", links=["SYS001"])

        graph.add_item(sys_item)
        graph.add_item(srs_item)

        coverage = {"SRS001": ItemCoverage(item=srs_item, linked_tests=[])}

        matrices = build_full_chain_matrix(graph, coverage, "SYS", trace_to_ignore=set())

        assert len(matrices) == 1
        matrix = matrices[0]
        assert matrix.document_hierarchy == ["SYS", "SRS"]


class TestHigherOrderDocumentTests:
    """Tests for tests linking directly to higher-order documents."""

    def test_direct_link_creates_gap_row(self):
        """Test that tests linked to higher-order items create gap rows."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SYS", [])

        sys_item = Item(uid="SYS001", text="System", document_prefix="SYS")
        srs_item = Item(uid="SRS001", text="Software", document_prefix="SRS", links=["SYS001"])

        graph.add_item(sys_item)
        graph.add_item(srs_item)

        # Test links directly to SYS001 (skipping SRS)
        direct_test = LinkedTest(
            test_nodeid="test::direct_sys_test",
            item_uid="SYS001",
            test_outcome="passed",
        )

        coverage = {"SRS001": ItemCoverage(item=srs_item, linked_tests=[])}
        all_test_links = {"SYS001": [direct_test]}

        matrices = build_full_chain_matrix(graph, coverage, "SYS", all_test_links=all_test_links)

        assert len(matrices) == 1
        matrix = matrices[0]

        # Should have 2 rows: one for SYS001 direct, one for SRS001
        assert len(matrix.rows) == 2

        # Find the gap row (SRS is None)
        gap_rows = [r for r in matrix.rows if r.chain.get("SRS") is None]
        assert len(gap_rows) == 1
        gap_row = gap_rows[0]

        # Gap row should have the direct test
        assert len(gap_row.descendant_tests) == 1
        assert gap_row.descendant_tests[0].test_nodeid == "test::direct_sys_test"

    def test_direct_link_test_not_in_child_rows(self):
        """Test that tests linked to higher-order items don't appear in child rows."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SYS", [])

        sys_item = Item(uid="SYS001", text="System", document_prefix="SYS")
        srs_item = Item(uid="SRS001", text="Software", document_prefix="SRS", links=["SYS001"])

        graph.add_item(sys_item)
        graph.add_item(srs_item)

        # Test links directly to SYS001 (skipping SRS)
        direct_test = LinkedTest(
            test_nodeid="test::direct_sys_test",
            item_uid="SYS001",
            test_outcome="passed",
        )

        # Test links to SRS001
        srs_test = LinkedTest(
            test_nodeid="test::srs_test",
            item_uid="SRS001",
            test_outcome="passed",
        )

        coverage = {"SRS001": ItemCoverage(item=srs_item, linked_tests=[srs_test])}
        all_test_links = {"SYS001": [direct_test], "SRS001": [srs_test]}

        matrices = build_full_chain_matrix(graph, coverage, "SYS", all_test_links=all_test_links)

        assert len(matrices) == 1
        matrix = matrices[0]

        # Find the SRS001 row
        srs_rows = [r for r in matrix.rows if r.chain.get("SRS") is not None]
        assert len(srs_rows) == 1
        srs_row = srs_rows[0]

        # SRS row should NOT have the direct SYS test
        test_nodeids = [t.test_nodeid for t in srs_row.descendant_tests]
        assert "test::direct_sys_test" not in test_nodeids
        assert "test::srs_test" in test_nodeids

    def test_multiple_direct_links_at_different_levels(self):
        """Test tests linking to multiple higher-order levels."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SYS", ["UN"])
        graph.set_document_parents("UN", [])

        un_item = Item(uid="UN001", text="User need", document_prefix="UN")
        sys_item = Item(uid="SYS001", text="System", document_prefix="SYS", links=["UN001"])
        srs_item = Item(uid="SRS001", text="Software", document_prefix="SRS", links=["SYS001"])

        graph.add_item(un_item)
        graph.add_item(sys_item)
        graph.add_item(srs_item)

        # Tests at each level
        un_test = LinkedTest(test_nodeid="test::un_test", item_uid="UN001", test_outcome="passed")
        sys_test = LinkedTest(test_nodeid="test::sys_test", item_uid="SYS001", test_outcome="passed")
        srs_test = LinkedTest(test_nodeid="test::srs_test", item_uid="SRS001", test_outcome="passed")

        coverage = {"SRS001": ItemCoverage(item=srs_item, linked_tests=[srs_test])}
        all_test_links = {
            "UN001": [un_test],
            "SYS001": [sys_test],
            "SRS001": [srs_test],
        }

        matrices = build_full_chain_matrix(graph, coverage, "UN", all_test_links=all_test_links)

        assert len(matrices) == 1
        matrix = matrices[0]

        # Should have 3 rows: UN gap, SYS gap, SRS full
        assert len(matrix.rows) == 3

        # UN gap row (SYS and SRS are None)
        un_gap_rows = [r for r in matrix.rows if r.chain.get("SYS") is None and r.chain.get("SRS") is None]
        assert len(un_gap_rows) == 1
        assert un_gap_rows[0].descendant_tests[0].test_nodeid == "test::un_test"

        # SYS gap row (SRS is None but SYS is not)
        sys_gap_rows = [r for r in matrix.rows if r.chain.get("SYS") is not None and r.chain.get("SRS") is None]
        assert len(sys_gap_rows) == 1
        assert sys_gap_rows[0].descendant_tests[0].test_nodeid == "test::sys_test"

        # SRS full row
        srs_rows = [r for r in matrix.rows if r.chain.get("SRS") is not None]
        assert len(srs_rows) == 1
        assert srs_rows[0].descendant_tests[0].test_nodeid == "test::srs_test"

    def test_no_direct_link_no_gap_row(self):
        """Test that items without direct tests don't create extra gap rows."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SYS", [])

        sys_item = Item(uid="SYS001", text="System", document_prefix="SYS")
        srs_item = Item(uid="SRS001", text="Software", document_prefix="SRS", links=["SYS001"])

        graph.add_item(sys_item)
        graph.add_item(srs_item)

        # Test only links to SRS001, not SYS001
        srs_test = LinkedTest(
            test_nodeid="test::srs_test",
            item_uid="SRS001",
            test_outcome="passed",
        )

        coverage = {"SRS001": ItemCoverage(item=srs_item, linked_tests=[srs_test])}
        all_test_links = {"SRS001": [srs_test]}  # No SYS001 entry

        matrices = build_full_chain_matrix(graph, coverage, "SYS", all_test_links=all_test_links)

        assert len(matrices) == 1
        matrix = matrices[0]

        # Should only have 1 row for SRS001 (no gap row for SYS001)
        assert len(matrix.rows) == 1
        assert matrix.rows[0].chain.get("SRS") is not None

    def test_direct_link_status_calculated_correctly(self):
        """Test that gap row status is based on direct tests only."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SYS", [])

        sys_item = Item(uid="SYS001", text="System", document_prefix="SYS")
        srs_item = Item(uid="SRS001", text="Software", document_prefix="SRS", links=["SYS001"])

        graph.add_item(sys_item)
        graph.add_item(srs_item)

        # Direct test to SYS001 fails
        direct_test = LinkedTest(
            test_nodeid="test::direct_sys_test",
            item_uid="SYS001",
            test_outcome="failed",
        )

        # SRS test passes
        srs_test = LinkedTest(
            test_nodeid="test::srs_test",
            item_uid="SRS001",
            test_outcome="passed",
        )

        coverage = {"SRS001": ItemCoverage(item=srs_item, linked_tests=[srs_test])}
        all_test_links = {"SYS001": [direct_test], "SRS001": [srs_test]}

        matrices = build_full_chain_matrix(graph, coverage, "SYS", all_test_links=all_test_links)

        assert len(matrices) == 1
        matrix = matrices[0]

        # Gap row should be Failed
        gap_rows = [r for r in matrix.rows if r.chain.get("SRS") is None]
        assert len(gap_rows) == 1
        assert gap_rows[0].rollup_status == "Failed"

        # SRS row should be Passed
        srs_rows = [r for r in matrix.rows if r.chain.get("SRS") is not None]
        assert len(srs_rows) == 1
        assert srs_rows[0].rollup_status == "Passed"


class TestCalculateRollupStatusEdgeCases:
    """Additional edge case tests for calculate_rollup_status."""

    def test_error_outcome_treated_as_failed(self):
        """Test that 'error' outcome is treated as failed."""
        graph = TraceabilityGraph()
        item = Item(uid="SRS001", text="Test", document_prefix="SRS")
        graph.add_item(item)

        coverage = {
            "SRS001": ItemCoverage(
                item=item,
                linked_tests=[
                    LinkedTest(
                        test_nodeid="test::test1",
                        item_uid="SRS001",
                        test_outcome="error",
                    ),
                ],
            ),
        }

        status, _tests = calculate_rollup_status(graph, item, coverage)

        assert status == "Failed"

    def test_skipped_only_returns_skipped(self):
        """Test that only skipped tests returns Skipped status."""
        graph = TraceabilityGraph()
        item = Item(uid="SRS001", text="Test", document_prefix="SRS")
        graph.add_item(item)

        coverage = {
            "SRS001": ItemCoverage(
                item=item,
                linked_tests=[
                    LinkedTest(
                        test_nodeid="test::test1",
                        item_uid="SRS001",
                        test_outcome="skipped",
                    ),
                ],
            ),
        }

        status, _tests = calculate_rollup_status(graph, item, coverage)

        assert status == "Skipped"

    def test_descendant_tests_collected(self):
        """Test that tests from descendants are collected."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SYS", [])

        sys_item = Item(uid="SYS001", text="System", document_prefix="SYS")
        srs_item = Item(uid="SRS001", text="SRS", document_prefix="SRS", links=["SYS001"])

        graph.add_item(sys_item)
        graph.add_item(srs_item)

        coverage = {
            "SRS001": ItemCoverage(
                item=srs_item,
                linked_tests=[
                    LinkedTest(
                        test_nodeid="test::srs_test",
                        item_uid="SRS001",
                        test_outcome="passed",
                    ),
                ],
            ),
        }

        status, tests = calculate_rollup_status(graph, sys_item, coverage)

        assert status == "Passed"
        assert len(tests) == 1
        assert tests[0].test_nodeid == "test::srs_test"

    def test_testable_descendant_with_untestable_parent(self):
        """Test that testable descendant affects untestable parent's status."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SYS", [])

        sys_item = Item(uid="SYS001", text="System", document_prefix="SYS", testable=False)
        srs_item = Item(uid="SRS001", text="SRS", document_prefix="SRS", links=["SYS001"])

        graph.add_item(sys_item)
        graph.add_item(srs_item)

        # No tests linked
        coverage = {
            "SRS001": ItemCoverage(item=srs_item, linked_tests=[]),
        }

        status, _tests = calculate_rollup_status(graph, sys_item, coverage)

        # Should be Not Covered because descendant is testable
        assert status == "Not Covered"


class TestCircularReferenceDetection:
    """Tests for circular reference detection and prevention."""

    def test_self_loop_raises_error(self):
        """Test that adding an item that links to itself raises ValueError."""
        graph = TraceabilityGraph()

        # Item that links to itself
        item = Item(
            uid="SRS001",
            text="Self-referencing",
            document_prefix="SRS",
            links=["SRS001"],
        )

        with pytest.raises(ValueError, match="cannot link to itself"):
            graph.add_item(item)

    def test_max_recursion_depth_constant_exists(self):
        """Test that MAX_RECURSION_DEPTH constant is properly defined."""
        assert MAX_RECURSION_DEPTH == 100

    def test_get_ancestors_handles_cycle_gracefully(self):
        """Test that get_ancestors doesn't infinite loop on manually-created cycle."""
        graph = TraceabilityGraph()

        # Create items without self-loop (which would be caught)
        item_a = Item(uid="A001", text="A", document_prefix="A")
        item_b = Item(uid="B001", text="B", document_prefix="B", links=["A001"])

        graph.add_item(item_a)
        graph.add_item(item_b)

        # Manually create a cycle (bypassing add_item validation)
        graph.item_parents["A001"] = ["B001"]

        # Should not infinite loop due to visited set
        ancestors = graph.get_ancestors("B001")
        # A001 should be in ancestors
        assert any(a.uid == "A001" for a in ancestors)

    def test_get_descendants_handles_cycle_gracefully(self):
        """Test that get_descendants doesn't infinite loop on manually-created cycle."""
        graph = TraceabilityGraph()

        item_a = Item(uid="A001", text="A", document_prefix="A")
        item_b = Item(uid="B001", text="B", document_prefix="B", links=["A001"])

        graph.add_item(item_a)
        graph.add_item(item_b)

        # Manually create a cycle in children (bypassing normal validation)
        graph.item_children["B001"] = ["A001"]

        # Should not infinite loop due to visited set
        descendants = graph.get_descendants("A001")
        # B001 should be in descendants
        assert any(d.uid == "B001" for d in descendants)


class TestEmptyHierarchyAfterFiltering:
    """Tests for empty hierarchy handling when trace_to_ignore filters all docs."""

    def test_all_documents_filtered_emits_warning(self):
        """Test that filtering all documents emits warning and skips path."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", [])

        srs_item = Item(uid="SRS001", text="Software", document_prefix="SRS")
        graph.add_item(srs_item)

        coverage = {"SRS001": ItemCoverage(item=srs_item, linked_tests=[])}

        # Filter all documents
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            matrices = build_full_chain_matrix(graph, coverage, "SRS", trace_to_ignore={"SRS"})

            # Should emit warnings about filtered path, empty result, and incomplete chains
            assert len(w) == 3
            warning_messages = [str(warning.message) for warning in w]
            assert any("All documents filtered" in msg for msg in warning_messages)
            assert any("No traceability matrices generated" in msg for msg in warning_messages)
            assert any("incomplete trace chains" in msg for msg in warning_messages)

        # Should return empty list since all paths are filtered
        assert len(matrices) == 0

    def test_partial_filtering_keeps_remaining_docs(self):
        """Test that partially filtering documents keeps remaining structure."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SYS", [])

        sys_item = Item(uid="SYS001", text="System", document_prefix="SYS")
        srs_item = Item(uid="SRS001", text="Software", document_prefix="SRS", links=["SYS001"])

        graph.add_item(sys_item)
        graph.add_item(srs_item)

        coverage = {"SRS001": ItemCoverage(item=srs_item, linked_tests=[])}

        # Filter only SYS (keep SRS) - suppress expected warning about incomplete trace chains
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            matrices = build_full_chain_matrix(graph, coverage, "SYS", trace_to_ignore={"SYS"})

        assert len(matrices) == 1
        matrix = matrices[0]
        # SYS should not be in hierarchy
        assert "SYS" not in matrix.document_hierarchy
        assert matrix.document_hierarchy == ["SRS"]


class TestDeepHierarchyTraversal:
    """Tests for deep hierarchy traversal."""

    def test_deep_hierarchy_completes_without_error(self):
        """Test that reasonable depth hierarchies complete without error."""
        graph = TraceabilityGraph()

        # Create a chain that's less than MAX_RECURSION_DEPTH
        # A -> B -> C (3 levels, well under 100)
        graph.set_document_parents("C", ["B"])
        graph.set_document_parents("B", ["A"])
        graph.set_document_parents("A", [])

        # Should complete without error
        paths = get_document_paths(graph, "A")
        assert len(paths) == 1
        assert paths[0] == ["A", "B", "C"]

    def test_get_document_paths_max_depth_warning(self):
        """Test that MAX_RECURSION_DEPTH warning is emitted on deep cycles."""
        from unittest.mock import patch

        graph = TraceabilityGraph()

        # Create a simple document hierarchy first
        graph.set_document_parents("B", ["A"])
        graph.set_document_parents("A", [])

        # Mock get_document_children to create a cycle: A -> A (indefinitely)
        # This simulates a graph corruption or invalid state
        def mock_get_children(prefix: str) -> list[str]:
            # Always return a child that points back to itself
            return ["A"] if prefix == "A" else []

        def mock_get_leaf_documents() -> list[str]:
            # Return empty so traverse never terminates early
            return []

        with patch.object(graph, "get_document_children", side_effect=mock_get_children):
            with patch.object(graph, "get_leaf_documents", side_effect=mock_get_leaf_documents):
                # This should trigger the max recursion depth warning
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always")
                    paths = get_document_paths(graph, "A")

                    # Due to the cycle, should emit warning when MAX_RECURSION_DEPTH is hit
                    assert paths is not None  # Should not crash

                    # Check that warning was emitted about max recursion depth
                    depth_warnings = [x for x in w if "Maximum recursion depth" in str(x.message)]
                    assert len(depth_warnings) > 0


class TestStatusUnknownOutcome:
    """Tests for handling unknown test outcomes in status calculation."""

    def test_unknown_outcome_returns_partial(self):
        """Test that tests with unknown outcome return 'Partial' status."""
        from jamb.matrix.chain_builder import _calculate_status_from_tests

        # Create tests with unknown outcomes (not passed, failed, error, or skipped)
        tests = [
            LinkedTest(
                test_nodeid="test::unknown",
                item_uid="SRS001",
                test_outcome=None,  # No outcome set
            ),
        ]

        status = _calculate_status_from_tests(tests)

        # Unknown outcomes should result in "Partial"
        assert status == "Partial"

    def test_mixed_unknown_and_passed_returns_passed(self):
        """Test that passed takes precedence over unknown."""
        from jamb.matrix.chain_builder import _calculate_status_from_tests

        tests = [
            LinkedTest(
                test_nodeid="test::unknown",
                item_uid="SRS001",
                test_outcome=None,
            ),
            LinkedTest(
                test_nodeid="test::passed",
                item_uid="SRS001",
                test_outcome="passed",
            ),
        ]

        status = _calculate_status_from_tests(tests)

        # Passed should take precedence
        assert status == "Passed"


class TestGapRowCreationWithAllTestLinks:
    """Tests for gap row creation with all_test_links parameter."""

    def test_gap_row_only_has_direct_tests(self):
        """Test that gap rows only contain tests directly linked to that item."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SYS", [])

        sys_item = Item(uid="SYS001", text="System", document_prefix="SYS")
        srs_item = Item(uid="SRS001", text="Software", document_prefix="SRS", links=["SYS001"])

        graph.add_item(sys_item)
        graph.add_item(srs_item)

        # Direct test on SYS001
        sys_test = LinkedTest(test_nodeid="test::sys_test", item_uid="SYS001", test_outcome="passed")
        # Test on SRS001
        srs_test = LinkedTest(test_nodeid="test::srs_test", item_uid="SRS001", test_outcome="passed")

        coverage = {"SRS001": ItemCoverage(item=srs_item, linked_tests=[srs_test])}
        all_test_links = {"SYS001": [sys_test], "SRS001": [srs_test]}

        matrices = build_full_chain_matrix(graph, coverage, "SYS", all_test_links=all_test_links)

        assert len(matrices) == 1
        matrix = matrices[0]

        # Find gap row (SRS is None)
        gap_rows = [r for r in matrix.rows if r.chain.get("SRS") is None]
        assert len(gap_rows) == 1

        # Gap row should ONLY have sys_test, not srs_test
        gap_test_nodeids = [t.test_nodeid for t in gap_rows[0].descendant_tests]
        assert "test::sys_test" in gap_test_nodeids
        assert "test::srs_test" not in gap_test_nodeids

    def test_no_gap_row_without_direct_tests(self):
        """Test that no gap row is created when item has no direct tests."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SYS", [])

        sys_item = Item(uid="SYS001", text="System", document_prefix="SYS")
        srs_item = Item(uid="SRS001", text="Software", document_prefix="SRS", links=["SYS001"])

        graph.add_item(sys_item)
        graph.add_item(srs_item)

        # Only test on SRS001, none on SYS001
        srs_test = LinkedTest(test_nodeid="test::srs_test", item_uid="SRS001", test_outcome="passed")

        coverage = {"SRS001": ItemCoverage(item=srs_item, linked_tests=[srs_test])}
        all_test_links = {"SRS001": [srs_test]}  # No SYS001 entry

        matrices = build_full_chain_matrix(graph, coverage, "SYS", all_test_links=all_test_links)

        assert len(matrices) == 1
        matrix = matrices[0]

        # Should only have 1 row (for SRS001), no gap row
        assert len(matrix.rows) == 1
        assert matrix.rows[0].chain.get("SRS") is not None


class TestCollectTestsNoneItem:
    """Tests for _collect_tests with None item."""

    def test_collect_tests_returns_empty_for_none_item(self):
        """Test that _collect_tests returns empty list when item is None."""
        from jamb.matrix.chain_builder import _collect_tests

        graph = TraceabilityGraph()
        coverage: dict[str, ItemCoverage] = {}

        result = _collect_tests(graph, None, coverage)

        assert result == []


class TestCalculateStatusNoGraph:
    """Tests for _calculate_status_from_tests with no graph."""

    def test_na_status_when_not_testable_without_graph(self):
        """Test N/A status when item not testable and no graph provided."""
        from jamb.matrix.chain_builder import _calculate_status_from_tests

        item = Item(uid="SRS001", text="Test", document_prefix="SRS", testable=False)

        # No tests and no graph to check descendants
        status = _calculate_status_from_tests([], item=item, graph=None)

        assert status == "N/A"


class TestSummarySkippedStatus:
    """Tests for summary calculation with skipped status."""

    def test_summary_counts_skipped_status(self):
        """Test that summary correctly counts skipped status."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", [])

        item1 = Item(uid="SRS001", text="Passed item", document_prefix="SRS")
        item2 = Item(uid="SRS002", text="Skipped item", document_prefix="SRS")

        graph.add_item(item1)
        graph.add_item(item2)

        coverage = {
            "SRS001": ItemCoverage(
                item=item1,
                linked_tests=[
                    LinkedTest(
                        test_nodeid="test::pass",
                        item_uid="SRS001",
                        test_outcome="passed",
                    ),
                ],
            ),
            "SRS002": ItemCoverage(
                item=item2,
                linked_tests=[
                    LinkedTest(
                        test_nodeid="test::skip",
                        item_uid="SRS002",
                        test_outcome="skipped",
                    ),
                ],
            ),
        }

        matrices = build_full_chain_matrix(graph, coverage, "SRS")

        assert len(matrices) == 1
        summary = matrices[0].summary
        assert summary["total"] == 2
        assert summary["passed"] == 1
        assert summary["skipped"] == 1


class TestOrphanedItemsWarning:
    """Tests for orphaned items detection and warning."""

    def test_orphaned_items_warning_with_many_items(self):
        """Test orphaned items warning when more than 5 items are orphaned."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SYS", [])

        # Create a SYS item with only one SRS child
        sys_item = Item(uid="SYS001", text="System", document_prefix="SYS")
        srs_linked = Item(uid="SRS001", text="Linked", document_prefix="SRS", links=["SYS001"])

        graph.add_item(sys_item)
        graph.add_item(srs_linked)

        # Create multiple orphaned SRS items (no links to SYS)
        for i in range(2, 10):  # SRS002-SRS009 (8 orphaned items)
            orphan = Item(uid=f"SRS00{i}", text=f"Orphan {i}", document_prefix="SRS")
            graph.add_item(orphan)

        coverage = {
            "SRS001": ItemCoverage(item=srs_linked, linked_tests=[]),
        }

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            build_full_chain_matrix(graph, coverage, "SYS")

            # Should emit warning about orphaned items
            orphan_warnings = [x for x in w if "incomplete trace chains" in str(x.message)]
            assert len(orphan_warnings) == 1
            # Should mention "and X more"
            assert "and" in str(orphan_warnings[0].message) and "more" in str(orphan_warnings[0].message)


class TestBuildChainRowsEmptyPath:
    """Tests for _build_chain_rows with empty document path."""

    def test_empty_doc_path_returns_empty_list(self):
        """Test that _build_chain_rows returns empty list for empty path."""
        from jamb.matrix.chain_builder import _build_chain_rows

        graph = TraceabilityGraph()
        coverage: dict[str, ItemCoverage] = {}

        result = _build_chain_rows(graph, coverage, [], include_ancestors=False)

        assert result == []
