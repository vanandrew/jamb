"""Tests for jamb.core.models module."""

from jamb.core.models import Item, ItemCoverage, LinkedTest, TraceabilityGraph


class TestItem:
    """Tests for Item dataclass."""

    def test_display_text_uses_header(self, item_with_header):
        """Test that display_text returns header when present."""
        assert item_with_header.display_text == "User Authentication"

    def test_display_text_returns_text_when_no_header(self, sample_item):
        """Test that display_text returns text when no header."""
        assert sample_item.display_text == "Software shall validate user credentials"

    def test_display_text_truncates_long_text(self):
        """Test that display_text truncates text longer than 80 chars."""
        long_text = "A" * 100
        item = Item(uid="TEST001", text=long_text, document_prefix="TEST")

        assert len(item.display_text) == 83  # 80 chars + "..."
        assert item.display_text.endswith("...")

    def test_display_text_does_not_truncate_short_text(self):
        """Test that display_text does not truncate text <= 80 chars."""
        short_text = "A" * 80
        item = Item(uid="TEST001", text=short_text, document_prefix="TEST")

        assert item.display_text == short_text
        assert "..." not in item.display_text

    def test_default_values(self):
        """Test Item default values."""
        item = Item(uid="TEST001", text="Test", document_prefix="TEST")

        assert item.active is True
        assert item.header is None
        assert item.links == []
        assert item.custom_attributes == {}


class TestLinkedTestClass:
    """Tests for LinkedTest dataclass."""

    def test_default_outcome_is_none(self):
        """Test that default test_outcome is None."""
        link = LinkedTest(test_nodeid="test.py::test_foo", item_uid="SRS001")

        assert link.test_outcome is None

    def test_default_notes_is_empty(self):
        """Test that default notes is empty list."""
        link = LinkedTest(test_nodeid="test.py::test_foo", item_uid="SRS001")

        assert link.notes == []

    def test_default_test_actions_is_empty(self):
        """Test that default test_actions is empty list."""
        link = LinkedTest(test_nodeid="test.py::test_foo", item_uid="SRS001")

        assert link.test_actions == []

    def test_default_expected_results_is_empty(self):
        """Test that default expected_results is empty list."""
        link = LinkedTest(test_nodeid="test.py::test_foo", item_uid="SRS001")

        assert link.expected_results == []

    def test_with_passed_outcome(self, passed_test_link):
        """Test LinkedTest with passed outcome."""
        assert passed_test_link.test_outcome == "passed"

    def test_with_failed_outcome(self, failed_test_link):
        """Test LinkedTest with failed outcome."""
        assert failed_test_link.test_outcome == "failed"

    def test_with_notes(self, test_link_with_messages):
        """Test LinkedTest with custom notes."""
        assert len(test_link_with_messages.notes) == 2
        assert "Verified boundary condition" in test_link_with_messages.notes
        assert "Tested edge case" in test_link_with_messages.notes

    def test_with_test_actions(self, test_link_with_messages):
        """Test LinkedTest with test actions."""
        assert len(test_link_with_messages.test_actions) == 1
        assert "Entered boundary value" in test_link_with_messages.test_actions

    def test_with_expected_results(self, test_link_with_messages):
        """Test LinkedTest with expected results."""
        assert len(test_link_with_messages.expected_results) == 1
        assert "System accepts value" in test_link_with_messages.expected_results

    def test_with_failure_message(self, test_link_with_failure_message):
        """Test LinkedTest with failure message."""
        assert len(test_link_with_failure_message.notes) == 1
        assert test_link_with_failure_message.notes[0].startswith("[FAILURE]")


class TestItemCoverage:
    """Tests for ItemCoverage dataclass."""

    def test_is_covered_with_tests(self, covered_item_coverage):
        """Test is_covered returns True when tests are linked."""
        assert covered_item_coverage.is_covered is True

    def test_is_covered_without_tests(self, uncovered_item_coverage):
        """Test is_covered returns False when no tests are linked."""
        assert uncovered_item_coverage.is_covered is False

    def test_all_tests_passed_when_all_pass(self, covered_item_coverage):
        """Test all_tests_passed returns True when all tests pass."""
        assert covered_item_coverage.all_tests_passed is True

    def test_all_tests_passed_when_some_fail(self, mixed_coverage):
        """Test all_tests_passed returns False when any test fails."""
        assert mixed_coverage.all_tests_passed is False

    def test_all_tests_passed_when_no_tests(self, uncovered_item_coverage):
        """Test all_tests_passed returns False when no tests."""
        assert uncovered_item_coverage.all_tests_passed is False


class TestTraceabilityGraph:
    """Tests for TraceabilityGraph class."""

    def test_add_item(self, empty_graph, sample_item):
        """Test adding an item to the graph."""
        empty_graph.add_item(sample_item)

        assert "SRS001" in empty_graph.items
        assert empty_graph.items["SRS001"] == sample_item

    def test_add_item_with_links(self, empty_graph, item_with_links):
        """Test adding an item with links stores parent references."""
        empty_graph.add_item(item_with_links)

        assert empty_graph.item_parents["SRS001"] == ["SYS001", "SYS002"]

    def test_get_ancestors(self, simple_graph):
        """Test get_ancestors traverses parent chain."""
        ancestors = simple_graph.get_ancestors("SRS001")

        # SRS001 -> SYS001 -> UN001
        assert len(ancestors) == 2
        uids = [a.uid for a in ancestors]
        assert "SYS001" in uids
        assert "UN001" in uids

    def test_get_ancestors_with_no_parents(self, simple_graph):
        """Test get_ancestors returns empty list for root item."""
        ancestors = simple_graph.get_ancestors("UN001")

        assert ancestors == []

    def test_get_ancestors_handles_missing_item(self, simple_graph):
        """Test get_ancestors handles missing item UID."""
        ancestors = simple_graph.get_ancestors("NONEXISTENT")

        assert ancestors == []

    def test_get_items_by_document(self, simple_graph):
        """Test get_items_by_document filters correctly."""
        srs_items = simple_graph.get_items_by_document("SRS")

        assert len(srs_items) == 1
        assert srs_items[0].uid == "SRS001"

    def test_get_items_by_document_empty(self, simple_graph):
        """Test get_items_by_document returns empty for unknown prefix."""
        items = simple_graph.get_items_by_document("UNKNOWN")

        assert items == []

    def test_get_root_documents(self, simple_graph):
        """Test get_root_documents identifies root."""
        roots = simple_graph.get_root_documents()

        assert roots == ["UN"]

    def test_get_leaf_documents(self, simple_graph):
        """Test get_leaf_documents identifies leaves."""
        leaves = simple_graph.get_leaf_documents()

        assert leaves == ["SRS"]

    def test_set_document_parent(self, empty_graph):
        """Test set_document_parent stores relationship."""
        empty_graph.set_document_parent("SRS", "SYS")

        assert empty_graph.document_parents["SRS"] == ["SYS"]

    def test_set_document_parent_root(self, empty_graph):
        """Test set_document_parent with None for root."""
        empty_graph.set_document_parent("UN", None)

        assert empty_graph.document_parents["UN"] == []

    def test_get_ancestors_circular_reference(self):
        """Test get_ancestors handles circular references without infinite loop."""
        graph = TraceabilityGraph()

        # Create items that could form a cycle if not handled
        item_a = Item(uid="A001", text="Item A", document_prefix="A", links=["B001"])
        item_b = Item(uid="B001", text="Item B", document_prefix="B", links=["A001"])

        graph.add_item(item_a)
        graph.add_item(item_b)

        # Should not infinite loop - BFS traverses the cycle but stops via visited set
        ancestors = graph.get_ancestors("A001")
        # Returns both B001 and A001 (A001 is found as ancestor of B001)
        # but most importantly, it doesn't loop forever
        assert len(ancestors) == 2
        uids = [a.uid for a in ancestors]
        assert "B001" in uids
        assert "A001" in uids

    def test_get_ancestors_diamond_inheritance(self):
        """Test get_ancestors with diamond inheritance pattern."""
        graph = TraceabilityGraph()

        # Diamond pattern: D -> B, C -> A
        #                  B -> A
        #                  C -> A
        item_a = Item(uid="A001", text="Root", document_prefix="A", links=[])
        item_b = Item(uid="B001", text="B", document_prefix="B", links=["A001"])
        item_c = Item(uid="C001", text="C", document_prefix="C", links=["A001"])
        item_d = Item(uid="D001", text="D", document_prefix="D", links=["B001", "C001"])

        graph.add_item(item_a)
        graph.add_item(item_b)
        graph.add_item(item_c)
        graph.add_item(item_d)

        ancestors = graph.get_ancestors("D001")

        # Should include B, C, and A (in BFS order)
        uids = [a.uid for a in ancestors]
        assert "B001" in uids
        assert "C001" in uids
        assert "A001" in uids
        # A should only appear once
        assert uids.count("A001") == 1

    def test_get_root_documents_multiple_roots(self):
        """Test get_root_documents with multiple root documents."""
        graph = TraceabilityGraph()

        graph.set_document_parent("UN", None)
        graph.set_document_parent("REG", None)  # Another root
        graph.set_document_parent("SYS", "UN")
        graph.set_document_parent("SRS", "SYS")

        roots = graph.get_root_documents()

        assert len(roots) == 2
        assert "UN" in roots
        assert "REG" in roots

    def test_get_leaf_documents_multiple_leaves(self):
        """Test get_leaf_documents with multiple leaf documents."""
        graph = TraceabilityGraph()

        graph.set_document_parent("UN", None)
        graph.set_document_parent("SYS", "UN")
        graph.set_document_parent("SRS", "SYS")
        graph.set_document_parent("UT", "SYS")  # Another leaf

        leaves = graph.get_leaf_documents()

        assert len(leaves) == 2
        assert "SRS" in leaves
        assert "UT" in leaves

    def test_get_ancestors_dangling_parent(self):
        """2a: Dangling parent UID (not in items dict) is excluded from ancestors."""
        graph = TraceabilityGraph()
        item = Item(uid="SRS001", text="Req", document_prefix="SRS", links=["NONEXIST"])
        graph.add_item(item)
        ancestors = graph.get_ancestors("SRS001")
        # NONEXIST is not in items, so it should not appear in ancestors
        assert ancestors == []

    def test_get_children_from_document_nonexistent_uid(self):
        """2b: get_children_from_document for UID not in graph returns empty."""
        graph = TraceabilityGraph()
        children = graph.get_children_from_document("NONEXIST", "SRS")
        assert children == []

    def test_get_parents_from_document_nonexistent_uid(self):
        """2b: get_parents_from_document for UID not in graph returns empty."""
        graph = TraceabilityGraph()
        parents = graph.get_parents_from_document("NONEXIST", "SRS")
        assert parents == []

    def test_set_document_parents_overwrites(self):
        """2c: set_document_parents overwrites previous parents, not appends."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SRS", ["UN"])
        assert graph.document_parents["SRS"] == ["UN"]

    def test_get_descendants_dangling_child(self):
        """2e: Child UID not in items dict doesn't crash get_descendants."""
        graph = TraceabilityGraph()
        item = Item(uid="UN001", text="Need", document_prefix="UN", links=[])
        graph.add_item(item)
        # Manually inject a dangling child
        graph.item_children["UN001"] = ["NONEXIST"]
        descendants = graph.get_descendants("UN001")
        # NONEXIST not in items, so not included
        assert descendants == []


class TestTraceabilityGraphDescendantsAndNeighbors:
    """Tests for get_descendants and get_neighbors methods."""

    def test_get_descendants_basic(self):
        """Test get_descendants returns child items."""
        graph = TraceabilityGraph()

        # UN001 <- SYS001 <- SRS001
        cus = Item(uid="UN001", text="Customer", document_prefix="UN", links=[])
        sys = Item(uid="SYS001", text="System", document_prefix="SYS", links=["UN001"])
        srs = Item(uid="SRS001", text="Software", document_prefix="SRS", links=["SYS001"])

        graph.add_item(cus)
        graph.add_item(sys)
        graph.add_item(srs)

        descendants = graph.get_descendants("UN001")

        assert len(descendants) == 2
        uids = [d.uid for d in descendants]
        assert "SYS001" in uids
        assert "SRS001" in uids

    def test_get_descendants_no_children(self):
        """Test get_descendants returns empty for leaf item."""
        graph = TraceabilityGraph()

        cus = Item(uid="UN001", text="Customer", document_prefix="UN", links=[])
        sys = Item(uid="SYS001", text="System", document_prefix="SYS", links=["UN001"])

        graph.add_item(cus)
        graph.add_item(sys)

        descendants = graph.get_descendants("SYS001")

        assert descendants == []

    def test_get_descendants_handles_missing_item(self):
        """Test get_descendants handles missing item UID."""
        graph = TraceabilityGraph()

        descendants = graph.get_descendants("NONEXISTENT")

        assert descendants == []

    def test_get_descendants_multiple_children(self):
        """Test get_descendants with item having multiple children."""
        graph = TraceabilityGraph()

        # UN001 <- SYS001 and UN001 <- SYS002
        cus = Item(uid="UN001", text="Customer", document_prefix="UN", links=[])
        sys1 = Item(uid="SYS001", text="System 1", document_prefix="SYS", links=["UN001"])
        sys2 = Item(uid="SYS002", text="System 2", document_prefix="SYS", links=["UN001"])

        graph.add_item(cus)
        graph.add_item(sys1)
        graph.add_item(sys2)

        descendants = graph.get_descendants("UN001")

        assert len(descendants) == 2
        uids = [d.uid for d in descendants]
        assert "SYS001" in uids
        assert "SYS002" in uids

    def test_get_descendants_circular_reference(self):
        """Test get_descendants handles circular references without infinite loop."""
        graph = TraceabilityGraph()

        item_a = Item(uid="A001", text="Item A", document_prefix="A", links=["B001"])
        item_b = Item(uid="B001", text="Item B", document_prefix="B", links=["A001"])

        graph.add_item(item_a)
        graph.add_item(item_b)

        # Should not infinite loop
        descendants = graph.get_descendants("A001")
        # A001 links to B001, so B001 is a parent of A001
        # B001 links to A001, so A001 is a parent of B001
        # A001 has B001 as a child (reverse of A001 -> B001 link)
        # Wait, the links represent parents, so:
        # A001.links = ["B001"] means B001 is parent of A001
        # B001.links = ["A001"] means A001 is parent of B001
        # So in item_children:
        # B001 has child A001
        # A001 has child B001
        # get_descendants("A001") should find B001, then A001 (circular)
        assert len(descendants) == 2

    def test_get_neighbors_includes_self(self):
        """Test get_neighbors includes the item itself."""
        graph = TraceabilityGraph()

        cus = Item(uid="UN001", text="Customer", document_prefix="UN", links=[])
        graph.add_item(cus)

        neighbors = graph.get_neighbors("UN001")

        uids = [n.uid for n in neighbors]
        assert "UN001" in uids

    def test_get_neighbors_includes_ancestors(self):
        """Test get_neighbors includes ancestor items."""
        graph = TraceabilityGraph()

        cus = Item(uid="UN001", text="Customer", document_prefix="UN", links=[])
        sys = Item(uid="SYS001", text="System", document_prefix="SYS", links=["UN001"])
        srs = Item(uid="SRS001", text="Software", document_prefix="SRS", links=["SYS001"])

        graph.add_item(cus)
        graph.add_item(sys)
        graph.add_item(srs)

        neighbors = graph.get_neighbors("SRS001")

        uids = [n.uid for n in neighbors]
        assert "SRS001" in uids  # self
        assert "SYS001" in uids  # parent
        assert "UN001" in uids  # grandparent

    def test_get_neighbors_includes_descendants(self):
        """Test get_neighbors includes descendant items."""
        graph = TraceabilityGraph()

        cus = Item(uid="UN001", text="Customer", document_prefix="UN", links=[])
        sys = Item(uid="SYS001", text="System", document_prefix="SYS", links=["UN001"])
        srs = Item(uid="SRS001", text="Software", document_prefix="SRS", links=["SYS001"])

        graph.add_item(cus)
        graph.add_item(sys)
        graph.add_item(srs)

        neighbors = graph.get_neighbors("UN001")

        uids = [n.uid for n in neighbors]
        assert "UN001" in uids  # self
        assert "SYS001" in uids  # child
        assert "SRS001" in uids  # grandchild

    def test_get_neighbors_no_duplicates(self):
        """Test get_neighbors returns each item only once."""
        graph = TraceabilityGraph()

        cus = Item(uid="UN001", text="Customer", document_prefix="UN", links=[])
        sys = Item(uid="SYS001", text="System", document_prefix="SYS", links=["UN001"])

        graph.add_item(cus)
        graph.add_item(sys)

        neighbors = graph.get_neighbors("SYS001")

        uids = [n.uid for n in neighbors]
        # Each UID should appear exactly once
        assert uids.count("SYS001") == 1
        assert uids.count("UN001") == 1

    def test_get_neighbors_missing_item(self):
        """Test get_neighbors with non-existent item returns empty."""
        graph = TraceabilityGraph()

        neighbors = graph.get_neighbors("NONEXISTENT")

        assert neighbors == []

    def test_item_children_populated_on_add(self):
        """Test that item_children is populated when items are added."""
        graph = TraceabilityGraph()

        cus = Item(uid="UN001", text="Customer", document_prefix="UN", links=[])
        sys = Item(uid="SYS001", text="System", document_prefix="SYS", links=["UN001"])

        graph.add_item(cus)
        graph.add_item(sys)

        assert "SYS001" in graph.item_children["UN001"]

    def test_item_children_no_duplicates(self):
        """Test that adding same item twice doesn't duplicate children."""
        graph = TraceabilityGraph()

        cus = Item(uid="UN001", text="Customer", document_prefix="UN", links=[])
        sys = Item(uid="SYS001", text="System", document_prefix="SYS", links=["UN001"])

        graph.add_item(cus)
        graph.add_item(sys)
        # Add sys again (simulating duplicate add)
        graph.add_item(sys)

        assert graph.item_children["UN001"].count("SYS001") == 1


class TestTraceabilityGraphDocumentMethods:
    """Tests for get_children_from_document,
    get_parents_from_document, add_document_parent."""

    def test_get_children_from_document(self):
        graph = TraceabilityGraph()
        un = Item(uid="UN001", text="Need", document_prefix="UN", links=[])
        sys1 = Item(uid="SYS001", text="Sys1", document_prefix="SYS", links=["UN001"])
        srs1 = Item(uid="SRS001", text="Srs1", document_prefix="SRS", links=["UN001"])
        graph.add_item(un)
        graph.add_item(sys1)
        graph.add_item(srs1)
        # Only SYS children
        children = graph.get_children_from_document("UN001", "SYS")
        assert len(children) == 1
        assert children[0].uid == "SYS001"

    def test_get_children_from_document_empty(self):
        graph = TraceabilityGraph()
        un = Item(uid="UN001", text="Need", document_prefix="UN", links=[])
        graph.add_item(un)
        children = graph.get_children_from_document("UN001", "SRS")
        assert children == []

    def test_get_parents_from_document(self):
        graph = TraceabilityGraph()
        sys1 = Item(uid="SYS001", text="Sys", document_prefix="SYS", links=[])
        un1 = Item(uid="UN001", text="Need", document_prefix="UN", links=[])
        srs1 = Item(uid="SRS001", text="Srs", document_prefix="SRS", links=["SYS001", "UN001"])
        graph.add_item(sys1)
        graph.add_item(un1)
        graph.add_item(srs1)
        # Only SYS parents
        parents = graph.get_parents_from_document("SRS001", "SYS")
        assert len(parents) == 1
        assert parents[0].uid == "SYS001"

    def test_get_parents_from_document_empty(self):
        graph = TraceabilityGraph()
        item = Item(uid="SRS001", text="Srs", document_prefix="SRS", links=[])
        graph.add_item(item)
        parents = graph.get_parents_from_document("SRS001", "SYS")
        assert parents == []

    def test_add_document_parent_new(self):
        graph = TraceabilityGraph()
        graph.add_document_parent("SRS", "SYS")
        assert graph.document_parents["SRS"] == ["SYS"]

    def test_add_document_parent_duplicate(self):
        graph = TraceabilityGraph()
        graph.add_document_parent("SRS", "SYS")
        graph.add_document_parent("SRS", "SYS")
        assert graph.document_parents["SRS"] == ["SYS"]

    def test_add_document_parent_multiple(self):
        graph = TraceabilityGraph()
        graph.add_document_parent("SRS", "SYS")
        graph.add_document_parent("SRS", "UN")
        assert graph.document_parents["SRS"] == ["SYS", "UN"]

    def test_display_text_empty_string_header(self):
        """Empty string header should fall through to text."""
        item = Item(uid="TEST001", text="Fallback text", document_prefix="TEST", header="")
        assert item.display_text == "Fallback text"


class TestItemAdditionalCases:
    """Additional edge case tests for Item dataclass."""

    def test_item_with_custom_attributes(self):
        """Test Item with custom_attributes populated."""
        item = Item(
            uid="SRS001",
            text="Requirement text",
            document_prefix="SRS",
            custom_attributes={"priority": "high", "component": "auth"},
        )

        assert item.custom_attributes["priority"] == "high"
        assert item.custom_attributes["component"] == "auth"


class TestLinkedTestAdditionalCases:
    """Additional tests for LinkedTest dataclass."""

    def test_linked_test_with_skipped_outcome(self):
        """Test LinkedTest with 'skipped' outcome."""
        link = LinkedTest(
            test_nodeid="test.py::test_skip",
            item_uid="SRS001",
            test_outcome="skipped",
        )

        assert link.test_outcome == "skipped"

    def test_linked_test_with_error_outcome(self):
        """Test LinkedTest with 'error' outcome."""
        link = LinkedTest(
            test_nodeid="test.py::test_error",
            item_uid="SRS001",
            test_outcome="error",
        )

        assert link.test_outcome == "error"


class TestItemCoverageAdditionalCases:
    """Additional tests for ItemCoverage."""

    def test_all_tests_passed_single_passed(self, sample_item):
        """Test all_tests_passed with single passed test."""
        link = LinkedTest(
            test_nodeid="test.py::test_one",
            item_uid="SRS001",
            test_outcome="passed",
        )
        coverage = ItemCoverage(item=sample_item, linked_tests=[link])

        assert coverage.all_tests_passed is True

    def test_all_tests_passed_with_skipped(self, sample_item):
        """Test all_tests_passed returns False with skipped test."""
        link = LinkedTest(
            test_nodeid="test.py::test_skip",
            item_uid="SRS001",
            test_outcome="skipped",
        )
        coverage = ItemCoverage(item=sample_item, linked_tests=[link])

        # Skipped is not "passed", so should be False
        assert coverage.all_tests_passed is False

    def test_is_covered_with_multiple_tests(self, sample_item):
        """Test is_covered with multiple linked tests."""
        links = [
            LinkedTest(test_nodeid="test.py::test_1", item_uid="SRS001"),
            LinkedTest(test_nodeid="test.py::test_2", item_uid="SRS001"),
        ]
        coverage = ItemCoverage(item=sample_item, linked_tests=links)

        assert coverage.is_covered is True
        assert len(coverage.linked_tests) == 2


class TestTraceabilityGraphEdgeCases:
    """Edge case tests for TraceabilityGraph."""

    def test_orphaned_document_is_both_root_and_leaf(self):
        """A document with no parents and no children is both root and leaf."""
        graph = TraceabilityGraph()
        graph.set_document_parent("SOLO", None)

        roots = graph.get_root_documents()
        leaves = graph.get_leaf_documents()

        assert "SOLO" in roots
        assert "SOLO" in leaves

    def test_empty_graph_no_roots_no_leaves(self):
        """An empty graph with no documents has no roots and no leaves."""
        graph = TraceabilityGraph()

        roots = graph.get_root_documents()
        leaves = graph.get_leaf_documents()

        assert roots == []
        assert leaves == []

    def test_all_tests_passed_with_none_outcome(self):
        """all_tests_passed returns False when any linked test has test_outcome=None."""
        item = Item(uid="SRS001", text="Req", document_prefix="SRS")
        passed_link = LinkedTest(
            test_nodeid="test.py::test_pass",
            item_uid="SRS001",
            test_outcome="passed",
        )
        none_link = LinkedTest(
            test_nodeid="test.py::test_pending",
            item_uid="SRS001",
            test_outcome=None,
        )
        coverage = ItemCoverage(item=item, linked_tests=[passed_link, none_link])

        assert coverage.is_covered is True
        assert coverage.all_tests_passed is False
