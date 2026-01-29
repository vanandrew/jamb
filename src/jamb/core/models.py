"""Domain models for requirements traceability."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class Item:
    """Represents a requirements item (requirement, info, heading, etc.).

    Attributes:
        uid (str): Unique identifier for the item (e.g. ``REQ001``).
        text (str): Body text of the requirement.
        document_prefix (str): Prefix of the document this item belongs to.
        active (bool): Whether the item is active. Inactive items are ignored
            during validation and coverage checks.
        type (Literal["requirement", "info", "heading"]): Item type.
        header (str | None): Optional heading text displayed instead of body text.
        links (list[str]): UIDs of parent items this item traces to.
        reviewed (str | None): Content hash recorded when the item was last reviewed,
            or ``None`` if never reviewed.
        derived (bool): Whether the item is derived (intentionally has no
            parent links).
        testable (bool): Whether the item can be verified by testing. If False,
            the item shows "N/A" instead of "NOT COVERED" in the matrix.
        custom_attributes (dict[str, Any]): Arbitrary user-defined key-value pairs.

    Examples:
        Construct an item and access its display text::

            >>> item = Item(
            ...     uid="SRS001",
            ...     text="The system shall log in users.",
            ...     document_prefix="SRS",
            ... )
            >>> item.uid
            'SRS001'
            >>> item.display_text
            'The system shall log in users.'

        An item with a header uses the header as display text::

            >>> item = Item(
            ...     uid="SRS002",
            ...     text="Details...",
            ...     document_prefix="SRS",
            ...     header="Login",
            ... )
            >>> item.display_text
            'Login'
    """

    uid: str
    text: str
    document_prefix: str
    active: bool = True
    type: Literal["requirement", "info", "heading"] = "requirement"
    header: str | None = None
    links: list[str] = field(default_factory=list)
    reviewed: str | None = None
    derived: bool = False
    testable: bool = True
    custom_attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def display_text(self) -> str:
        """Return header if present, otherwise truncated text.

        Truncation is safe for multi-byte UTF-8 characters since Python
        strings are Unicode codepoint sequences, not byte sequences.
        """
        if self.header:
            return self.header
        if len(self.text) > 80:
            # Truncate at word boundary if possible to avoid mid-word cuts
            truncated = self.text[:80]
            last_space = truncated.rfind(" ")
            if last_space > 60:  # Only use word boundary if reasonably close
                truncated = truncated[:last_space]
            return truncated + "..."
        return self.text

    @property
    def full_display_text(self) -> str:
        """Return 'header - text' if header present, otherwise just text.

        Used for full chain matrices where both header and text are desired.
        """
        if self.header:
            return f"{self.header} - {self.text}"
        return self.text


@dataclass
class LinkedTest:
    """Represents a link from a pytest test to a requirements item.

    Attributes:
        test_nodeid (str): The pytest node ID of the test (e.g.
            ``tests/test_foo.py::test_bar``).
        item_uid (str): UID of the requirements item the test covers.
        test_outcome (str | None): Result of the test — ``"passed"``, ``"failed"``,
            ``"skipped"``, or ``"error"``. ``None`` before execution.
        notes (list[str]): Free-form notes captured during test execution.
        test_actions (list[str]): Steps performed by the test.
        expected_results (list[str]): Expected outcomes for each test action.
        actual_results (list[str]): Actual outcomes observed during test execution.
        execution_timestamp (str | None): ISO 8601 UTC timestamp of test execution.
    """

    test_nodeid: str
    item_uid: str
    test_outcome: Literal["passed", "failed", "skipped", "error"] | None = None
    notes: list[str] = field(default_factory=list)
    test_actions: list[str] = field(default_factory=list)
    expected_results: list[str] = field(default_factory=list)
    actual_results: list[str] = field(default_factory=list)
    execution_timestamp: str | None = None


@dataclass
class TestEnvironment:
    """Test environment info per IEC 62304 5.7.5.

    Uses stdlib only for portability.

    Attributes:
        os_name (str): Operating system name (e.g., "Darwin").
        os_version (str): Operating system version (e.g., "25.2.0").
        python_version (str): Python version (e.g., "3.12.0").
        platform (str): Platform architecture (e.g., "arm64").
        processor (str): Processor type (e.g., "arm").
        hostname (str): Machine hostname (e.g., "dev-machine.local").
        cpu_count (int | None): Number of CPUs, or None if unavailable.
        test_tools (dict[str, str]): Mapping of tool name to version
            (e.g., {"pytest": "8.0.0", "jamb": "1.2.0"}).
    """

    os_name: str
    os_version: str
    python_version: str
    platform: str
    processor: str
    hostname: str
    cpu_count: int | None
    test_tools: dict[str, str] = field(default_factory=dict)


@dataclass
class MatrixMetadata:
    """Metadata for the traceability matrix per IEC 62304 5.7.5.

    Attributes:
        software_version (str | None): Version of the software under test.
        tester_id (str): Identification of the tester or CI system.
        execution_timestamp (str | None): ISO 8601 UTC timestamp of test execution.
        environment (TestEnvironment | None): Test environment information.
    """

    software_version: str | None = None
    tester_id: str = "Unknown"
    execution_timestamp: str | None = None
    environment: TestEnvironment | None = None


@dataclass
class TestRecord:
    """A test case record for the test records matrix.

    Attributes:
        test_id (str): Sequential test case ID (e.g., ``TC001``, ``TC002``).
        test_name (str): Function name extracted from the pytest nodeid.
        test_nodeid (str): Full pytest node ID.
        outcome (str): Test result — ``"passed"``, ``"failed"``, ``"skipped"``,
            ``"error"``, or ``"unknown"``.
        requirements (list[str]): UIDs of requirements this test covers.
        test_actions (list[str]): Steps performed by the test.
        expected_results (list[str]): Expected outcomes for each test action.
        actual_results (list[str]): Actual outcomes observed during test execution.
        notes (list[str]): Free-form notes captured during test execution.
        execution_timestamp (str | None): ISO 8601 UTC timestamp of test execution.
    """

    __test__ = False  # Prevent pytest from collecting this as a test class

    test_id: str
    test_name: str
    test_nodeid: str
    outcome: str
    requirements: list[str] = field(default_factory=list)
    test_actions: list[str] = field(default_factory=list)
    expected_results: list[str] = field(default_factory=list)
    actual_results: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    execution_timestamp: str | None = None


@dataclass
class ItemCoverage:
    """Coverage status for a single requirements item.

    Attributes:
        item (Item): The requirements item being tracked.
        linked_tests (list[LinkedTest]): Tests linked to this item
            via requirement markers.
    """

    item: Item
    linked_tests: list[LinkedTest] = field(default_factory=list)

    @property
    def is_covered(self) -> bool:
        """Return True if at least one test links to this item."""
        return len(self.linked_tests) > 0

    @property
    def all_tests_passed(self) -> bool:
        """Return True if all linked tests passed.

        Returns False if there are no linked tests, since an item with
        no tests cannot be considered to have "all tests passing".
        This is intentional - use ``is_covered`` to check if tests exist.
        """
        if not self.linked_tests:
            return False
        return all(t.test_outcome == "passed" for t in self.linked_tests)


@dataclass
class TraceabilityGraph:
    """
    Graph representing the full traceability hierarchy.

    Stores items by UID and tracks parent-child relationships
    based on document hierarchy and item links.

    Attributes:
        items (dict[str, Item]): Mapping of item UID to :class:`Item` instance.
        item_parents (dict[str, list[str]]): Mapping of item UID to
            list of parent item UIDs (derived from each item's
            ``links`` field).
        item_children (dict[str, list[str]]): Reverse index mapping
            item UID to list of child item UIDs that link to it.
        document_parents (dict[str, list[str]]): Mapping of document
            prefix to list of parent document prefixes (the
            document-level DAG).

    Examples:
        Build a graph and add linked items::

            >>> graph = TraceabilityGraph()
            >>> graph.set_document_parents("SRS", ["SYS"])
            >>> graph.set_document_parents("SYS", [])
            >>> sys_item = Item(uid="SYS001", text="System req", document_prefix="SYS")
            >>> srs_item = Item(
            ...     uid="SRS001",
            ...     text="Software req",
            ...     document_prefix="SRS",
            ...     links=["SYS001"],
            ... )
            >>> graph.add_item(sys_item)
            >>> graph.add_item(srs_item)
            >>> graph.item_children["SYS001"]
            ['SRS001']
    """

    items: dict[str, Item] = field(default_factory=dict)
    item_parents: dict[str, list[str]] = field(default_factory=dict)
    item_children: dict[str, list[str]] = field(default_factory=dict)
    document_parents: dict[str, list[str]] = field(default_factory=dict)

    def add_item(self, item: Item) -> None:
        """Add an item to the graph.

        Args:
            item: The Item to add. Its links are used to populate the
                parent and child reverse-index maps.

        Raises:
            ValueError: If the item links to itself (self-loop).
        """
        # Check for self-loop
        if item.uid in item.links:
            raise ValueError(f"Item '{item.uid}' cannot link to itself (self-loop detected)")

        if item.uid in self.items:
            for old_parent in self.item_parents.get(item.uid, []):
                if old_parent in self.item_children:
                    try:
                        self.item_children[old_parent].remove(item.uid)
                    except ValueError:
                        pass
        self.items[item.uid] = item
        self.item_parents[item.uid] = item.links.copy()
        # Initialize children list for this item if not exists
        if item.uid not in self.item_children:
            self.item_children[item.uid] = []
        # Populate reverse index: for each parent, add this item as a child
        for parent_uid in item.links:
            if parent_uid not in self.item_children:
                self.item_children[parent_uid] = []
            if item.uid not in self.item_children[parent_uid]:
                self.item_children[parent_uid].append(item.uid)

    def set_document_parent(self, prefix: str, parent_prefix: str | None) -> None:
        """Set a single parent document, replacing any existing parents.

        Backward-compatible wrapper for single-parent hierarchies.
        For DAG support with multiple parents, use set_document_parents().

        Args:
            prefix: The document prefix to set the parent for.
            parent_prefix: The parent document prefix, or None to clear.
        """
        if parent_prefix is None:
            self.document_parents[prefix] = []
        else:
            self.document_parents[prefix] = [parent_prefix]

    def set_document_parents(self, prefix: str, parents: list[str]) -> None:
        """Replace all parent documents with the given list.

        Use this when you need to set the complete list of parents at once.
        Existing parents are replaced, not merged.

        Args:
            prefix: The document prefix to set parents for.
            parents: List of parent document prefixes.
        """
        self.document_parents[prefix] = list(parents)

    def add_document_parent(self, prefix: str, parent: str) -> None:
        """Add a parent document without removing existing parents.

        Use this when building the graph incrementally.
        No-op if the parent already exists for this prefix.

        Args:
            prefix: The document prefix to add a parent to.
            parent: The parent document prefix to add.
        """
        if prefix not in self.document_parents:
            self.document_parents[prefix] = []
        if parent not in self.document_parents[prefix]:
            self.document_parents[prefix].append(parent)

    def get_ancestors(self, uid: str) -> list[Item]:
        """
        Get all ancestor items by following links upward.

        Returns items in order from immediate parent to root.
        """
        ancestors = []
        visited = set()
        to_visit = deque(self.item_parents.get(uid, []))

        while to_visit:
            parent_uid = to_visit.popleft()
            if parent_uid in visited:
                continue
            visited.add(parent_uid)

            if parent_uid in self.items:
                parent_item = self.items[parent_uid]
                ancestors.append(parent_item)
                to_visit.extend(self.item_parents.get(parent_uid, []))

        return ancestors

    def get_descendants(self, uid: str) -> list[Item]:
        """
        Get all descendant items by following children downward.

        Returns items in BFS order from immediate children to leaves.
        """
        descendants = []
        visited = set()
        to_visit = deque(self.item_children.get(uid, []))

        while to_visit:
            child_uid = to_visit.popleft()
            if child_uid in visited:
                continue
            visited.add(child_uid)

            if child_uid in self.items:
                child_item = self.items[child_uid]
                descendants.append(child_item)
                to_visit.extend(self.item_children.get(child_uid, []))

        return descendants

    def get_neighbors(self, uid: str) -> list[Item]:
        """
        Get all neighbor items: ancestors + descendants + self.

        Returns the item itself plus all items connected to it
        through the traceability hierarchy.
        """
        neighbors = []
        seen_uids = set()

        # Add self if exists
        if uid in self.items:
            neighbors.append(self.items[uid])
            seen_uids.add(uid)

        # Add ancestors
        for ancestor in self.get_ancestors(uid):
            if ancestor.uid not in seen_uids:
                neighbors.append(ancestor)
                seen_uids.add(ancestor.uid)

        # Add descendants
        for descendant in self.get_descendants(uid):
            if descendant.uid not in seen_uids:
                neighbors.append(descendant)
                seen_uids.add(descendant.uid)

        return neighbors

    def get_children_from_document(self, uid: str, prefix: str) -> list[Item]:
        """Get children of uid that belong to the given document.

        Args:
            uid: The parent item UID.
            prefix: The document prefix to filter children by.

        Returns:
            List of child Item objects in the specified document.
        """
        return [
            self.items[child_uid]
            for child_uid in self.item_children.get(uid, [])
            if child_uid in self.items and self.items[child_uid].document_prefix == prefix
        ]

    def get_parents_from_document(self, uid: str, prefix: str) -> list[Item]:
        """Get parents of uid that belong to the given document.

        Args:
            uid: The child item UID.
            prefix: The document prefix to filter parents by.

        Returns:
            List of parent Item objects in the specified document.
        """
        return [
            self.items[parent_uid]
            for parent_uid in self.item_parents.get(uid, [])
            if parent_uid in self.items and self.items[parent_uid].document_prefix == prefix
        ]

    def get_items_by_document(self, prefix: str) -> list[Item]:
        """Get all items belonging to a specific document.

        Args:
            prefix: The document prefix to filter by.

        Returns:
            List of Item objects with the given document prefix.
        """
        return [item for item in self.items.values() if item.document_prefix == prefix]

    def get_root_documents(self) -> list[str]:
        """Get document prefixes that have no parents.

        Returns:
            List of document prefix strings with no parent documents.
        """
        return [prefix for prefix, parents in self.document_parents.items() if not parents]

    def get_leaf_documents(self) -> list[str]:
        """Get document prefixes that are not parents of any other document.

        Returns:
            List of document prefix strings that have no child documents.
        """
        all_parents: set[str] = set()
        for parents in self.document_parents.values():
            all_parents.update(parents)
        return [prefix for prefix in self.document_parents.keys() if prefix not in all_parents]

    def get_document_children(self, prefix: str) -> list[str]:
        """Get child document prefixes for a document.

        Args:
            prefix: The document prefix to find children for.

        Returns:
            List of document prefix strings that have this document as a parent.
        """
        return [child_prefix for child_prefix, parents in self.document_parents.items() if prefix in parents]


@dataclass
class ChainRow:
    """A row in the full chain trace matrix.

    Represents a single trace chain from a starting document through
    the hierarchy to leaf items and their tests.

    Attributes:
        chain (dict[str, Item | None]): Mapping of document prefix to
            the Item at each level in the chain. None if no item exists
            at that level in this particular trace path.
        leaf_coverage (ItemCoverage | None): Coverage information for the
            leaf item in this chain, if any.
        rollup_status (str): Aggregated status for this row based on
            descendant test results. One of "Passed", "Failed", "Partial",
            "Not Covered", or "N/A".
        descendant_tests (list[LinkedTest]): All tests linked to descendants
            of items in this chain.
        ancestor_uids (list[str]): UIDs of items that the starting item
            traces to (its ancestors). Only populated when --include-ancestors
            is used.
    """

    chain: dict[str, Item | None] = field(default_factory=dict)
    leaf_coverage: ItemCoverage | None = None
    rollup_status: str = "Not Covered"
    descendant_tests: list[LinkedTest] = field(default_factory=list)
    ancestor_uids: list[str] = field(default_factory=list)


@dataclass
class FullChainMatrix:
    """A single full chain trace matrix for one document path.

    When a starting document has multiple child paths (e.g., PRJ -> UN and
    PRJ -> HAZ), a separate FullChainMatrix is generated for each path.

    Attributes:
        path_name (str): Human-readable name for this path, e.g.,
            "PRJ -> UN -> SYS -> SRS".
        document_hierarchy (list[str]): Ordered list of document prefixes
            from start to leaf, e.g., ["PRJ", "UN", "SYS", "SRS"].
        rows (list[ChainRow]): The data rows for this matrix.
        summary (dict[str, int]): Summary statistics including:
            - total: Total number of leaf items
            - passed: Items with all tests passing
            - failed: Items with any failing tests
            - partial: Items with mixed results
            - not_covered: Items with no tests
            - na: Items that are not testable
        include_ancestors (bool): Whether this matrix includes the
            "Traces To" column showing ancestors.
    """

    path_name: str
    document_hierarchy: list[str]
    rows: list[ChainRow] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)
    include_ancestors: bool = False
