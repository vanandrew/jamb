"""Domain models for requirements traceability."""

from dataclasses import dataclass, field


@dataclass
class Item:
    """Represents a requirements item (requirement, info, heading, etc.)."""

    uid: str
    text: str
    document_prefix: str
    active: bool = True
    type: str = "requirement"  # "requirement", "info", "heading"
    header: str | None = None
    links: list[str] = field(default_factory=list)
    reviewed: str | None = None
    derived: bool = False
    custom_attributes: dict = field(default_factory=dict)

    @property
    def display_text(self) -> str:
        """Return header if present, otherwise truncated text."""
        if self.header:
            return self.header
        return self.text[:80] + "..." if len(self.text) > 80 else self.text


@dataclass
class LinkedTest:
    """Represents a link from a pytest test to a requirements item."""

    test_nodeid: str
    item_uid: str
    test_outcome: str | None = None  # "passed", "failed", "skipped", "error"
    notes: list[str] = field(default_factory=list)
    test_actions: list[str] = field(default_factory=list)
    expected_results: list[str] = field(default_factory=list)


@dataclass
class ItemCoverage:
    """Coverage status for a single requirements item."""

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
    """

    items: dict[str, Item] = field(default_factory=dict)
    # Maps item UID -> list of parent item UIDs (from links field)
    item_parents: dict[str, list[str]] = field(default_factory=dict)
    # Maps item UID -> list of child item UIDs (reverse index)
    item_children: dict[str, list[str]] = field(default_factory=dict)
    # Maps document prefix -> list of parent document prefixes (DAG)
    document_parents: dict[str, list[str]] = field(default_factory=dict)

    def add_item(self, item: Item) -> None:
        """Add an item to the graph."""
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
        """
        if parent_prefix is None:
            self.document_parents[prefix] = []
        else:
            self.document_parents[prefix] = [parent_prefix]

    def set_document_parents(self, prefix: str, parents: list[str]) -> None:
        """Set the parent documents for a document prefix (DAG)."""
        self.document_parents[prefix] = list(parents)

    def add_document_parent(self, prefix: str, parent: str) -> None:
        """Add a parent document to a document prefix."""
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
        """Get children of uid that belong to the given document."""
        return [
            self.items[child_uid]
            for child_uid in self.item_children.get(uid, [])
            if child_uid in self.items
            and self.items[child_uid].document_prefix == prefix
        ]

    def get_parents_from_document(self, uid: str, prefix: str) -> list[Item]:
        """Get parents of uid that belong to the given document."""
        return [
            self.items[parent_uid]
            for parent_uid in self.item_parents.get(uid, [])
            if parent_uid in self.items
            and self.items[parent_uid].document_prefix == prefix
        ]

    def get_items_by_document(self, prefix: str) -> list[Item]:
        """Get all items belonging to a specific document."""
        return [item for item in self.items.values() if item.document_prefix == prefix]

    def get_root_documents(self) -> list[str]:
        """Get document prefixes that have no parents."""
        return [
            prefix for prefix, parents in self.document_parents.items() if not parents
        ]

    def get_leaf_documents(self) -> list[str]:
        """Get document prefixes that are not parents of any other document."""
        all_parents: set[str] = set()
        for parents in self.document_parents.values():
            all_parents.update(parents)
        return [
            prefix
            for prefix in self.document_parents.keys()
            if prefix not in all_parents
        ]
