"""Domain models for requirements traceability."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Item:
    """Represents a requirements item (requirement, info, heading, etc.).

    Attributes:
        uid: Unique identifier for the item (e.g. ``REQ001``).
        text: Body text of the requirement.
        document_prefix: Prefix of the document this item belongs to.
        active: Whether the item is active. Inactive items are ignored
            during validation and coverage checks.
        type: Item type — ``"requirement"``, ``"info"``, or ``"heading"``.
        header: Optional heading text displayed instead of body text.
        links: UIDs of parent items this item traces to.
        reviewed: Content hash recorded when the item was last reviewed,
            or ``None`` if never reviewed.
        derived: Whether the item is derived (intentionally has no
            parent links).
        custom_attributes: Arbitrary user-defined key-value pairs.
    """

    uid: str
    text: str
    document_prefix: str
    active: bool = True
    type: str = "requirement"  # "requirement", "info", "heading"
    header: str | None = None
    links: list[str] = field(default_factory=list)
    reviewed: str | None = None
    derived: bool = False
    custom_attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def display_text(self) -> str:
        """Return header if present, otherwise truncated text."""
        if self.header:
            return self.header
        return self.text[:80] + "..." if len(self.text) > 80 else self.text


@dataclass
class LinkedTest:
    """Represents a link from a pytest test to a requirements item.

    Attributes:
        test_nodeid: The pytest node ID of the test (e.g.
            ``tests/test_foo.py::test_bar``).
        item_uid: UID of the requirements item the test covers.
        test_outcome: Result of the test — ``"passed"``, ``"failed"``,
            ``"skipped"``, or ``"error"``. ``None`` before execution.
        notes: Free-form notes captured during test execution.
        test_actions: Steps performed by the test.
        expected_results: Expected outcomes for each test action.
    """

    test_nodeid: str
    item_uid: str
    test_outcome: str | None = None  # "passed", "failed", "skipped", "error"
    notes: list[str] = field(default_factory=list)
    test_actions: list[str] = field(default_factory=list)
    expected_results: list[str] = field(default_factory=list)


@dataclass
class ItemCoverage:
    """Coverage status for a single requirements item.

    Attributes:
        item: The requirements item being tracked.
        linked_tests: Tests linked to this item via requirement markers.
    """

    item: Item
    linked_tests: list[LinkedTest] = field(default_factory=list)

    @property
    def is_covered(self) -> bool:
        """Return True if at least one test links to this item."""
        return len(self.linked_tests) > 0

    @property
    def all_tests_passed(self) -> bool:
        """Return True if all linked tests passed."""
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
        items: Mapping of item UID to :class:`Item` instance.
        item_parents: Mapping of item UID to list of parent item UIDs
            (derived from each item's ``links`` field).
        item_children: Reverse index mapping item UID to list of child
            item UIDs that link to it.
        document_parents: Mapping of document prefix to list of parent
            document prefixes (the document-level DAG).
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
        """
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
        """Set a single parent document (backward-compat wrapper).

        For DAG support, use set_document_parents() instead.

        Args:
            prefix: The document prefix to set the parent for.
            parent_prefix: The parent document prefix, or None to clear.
        """
        if parent_prefix is None:
            self.document_parents[prefix] = []
        else:
            self.document_parents[prefix] = [parent_prefix]

    def set_document_parents(self, prefix: str, parents: list[str]) -> None:
        """Set the parent documents for a document prefix (DAG).

        Args:
            prefix: The document prefix to set parents for.
            parents: List of parent document prefixes.
        """
        self.document_parents[prefix] = list(parents)

    def add_document_parent(self, prefix: str, parent: str) -> None:
        """Add a parent document to a document prefix.

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
        to_visit = list(self.item_parents.get(uid, []))

        while to_visit:
            parent_uid = to_visit.pop(0)
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
        to_visit = list(self.item_children.get(uid, []))

        while to_visit:
            child_uid = to_visit.pop(0)
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
            if child_uid in self.items
            and self.items[child_uid].document_prefix == prefix
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
            if parent_uid in self.items
            and self.items[parent_uid].document_prefix == prefix
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
        return [
            prefix for prefix, parents in self.document_parents.items() if not parents
        ]

    def get_leaf_documents(self) -> list[str]:
        """Get document prefixes that are not parents of any other document.

        Returns:
            List of document prefix strings that have no child documents.
        """
        all_parents: set[str] = set()
        for parents in self.document_parents.values():
            all_parents.update(parents)
        return [
            prefix
            for prefix in self.document_parents.keys()
            if prefix not in all_parents
        ]
