"""DAG-based document hierarchy for jamb."""

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from jamb.storage.document_config import DocumentConfig


@dataclass
class DocumentDAG:
    """Directed acyclic graph of document relationships.

    Supports multiple parents per document (DAG structure).

    Attributes:
        documents (dict[str, DocumentConfig]): Mapping of document prefix to its
            :class:`~jamb.storage.document_config.DocumentConfig`.
        document_paths (dict[str, Path]): Mapping of document prefix to the filesystem
            path of the document directory.
    """

    documents: dict[str, DocumentConfig] = field(default_factory=dict)
    document_paths: dict[str, Path] = field(default_factory=dict)

    def get_parents(self, prefix: str) -> list[str]:
        """Get parent document prefixes for a given document.

        Args:
            prefix: The document prefix to look up.

        Returns:
            List of parent document prefix strings. Empty if the
            document has no parents or is not found.
        """
        config = self.documents.get(prefix)
        if config is None:
            return []
        return list(config.parents)

    def get_children(self, prefix: str) -> list[str]:
        """Get child document prefixes for a given document.

        Args:
            prefix: The document prefix to look up.

        Returns:
            List of child document prefix strings.
        """
        children = []
        for p, config in self.documents.items():
            if prefix in config.parents:
                children.append(p)
        return children

    def get_root_documents(self) -> list[str]:
        """Get documents with no parents.

        Returns:
            List of document prefix strings that have no parent documents.
        """
        return [p for p, config in self.documents.items() if not config.parents]

    def get_leaf_documents(self) -> list[str]:
        """Get documents with no children.

        Returns:
            List of document prefix strings that have no child documents.
        """
        all_parents = set()
        for config in self.documents.values():
            all_parents.update(config.parents)
        return [p for p in self.documents if p not in all_parents]

    def topological_sort(self) -> list[str]:
        """Return prefixes in topological order (parents before children).

        Uses Kahn's algorithm. If there are cycles, remaining nodes
        are appended at the end.

        Raises:
            ValueError: If any document references unknown parent documents.
        """
        # Build in-degree map
        in_degree: dict[str, int] = {p: 0 for p in self.documents}
        children_map: dict[str, list[str]] = {p: [] for p in self.documents}
        missing_parents: list[str] = []

        for prefix, config in self.documents.items():
            for parent in config.parents:
                if parent in self.documents:
                    in_degree[prefix] += 1
                    children_map[parent].append(prefix)
                else:
                    missing_parents.append(f"{prefix} references unknown parent {parent}")

        if missing_parents:
            raise ValueError(f"Document DAG has missing parents: {', '.join(missing_parents)}")

        # Start with nodes that have no parents
        queue: deque[str] = deque()
        for prefix, degree in in_degree.items():
            if degree == 0:
                queue.append(prefix)

        result: list[str] = []
        while queue:
            node = queue.popleft()
            result.append(node)
            for child in children_map[node]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        # Append any remaining (cycle participants)
        for prefix in self.documents:
            if prefix not in result:
                result.append(prefix)

        return result

    def validate_acyclic(self) -> list[str]:
        """Check for cycles in the DAG.

        Returns:
            List of error messages. Empty if no cycles.
        """
        # Build in-degree map and children adjacency (single Kahn's pass)
        in_degree: dict[str, int] = {p: 0 for p in self.documents}
        children_map: dict[str, list[str]] = {p: [] for p in self.documents}

        for prefix, config in self.documents.items():
            for parent in config.parents:
                if parent in self.documents:
                    in_degree[prefix] += 1
                    children_map[parent].append(prefix)

        queue: deque[str] = deque()
        for prefix, degree in in_degree.items():
            if degree == 0:
                queue.append(prefix)

        visited: set[str] = set()
        while queue:
            node = queue.popleft()
            visited.add(node)
            for child in children_map[node]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        errors: list[str] = []
        cycle_nodes = set(self.documents.keys()) - visited
        if cycle_nodes:
            errors.append(f"Cycle detected among documents: {', '.join(sorted(cycle_nodes))}")
        return errors
