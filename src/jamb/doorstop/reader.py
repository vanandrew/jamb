"""Read doorstop items and build traceability graph."""

import doorstop

from jamb.core.models import Item, TraceabilityGraph


def read_tree(
    tree: doorstop.Tree,
    document_prefixes: list[str] | None = None,
    include_inactive: bool = False,
) -> list[Item]:
    """
    Read items from doorstop documents.

    Args:
        tree: The doorstop tree.
        document_prefixes: Optional list of document prefixes to include.
                          If None, includes all documents.
        include_inactive: Whether to include inactive items.

    Returns:
        List of Item objects.
    """
    items = []

    documents = list(tree.documents)
    if document_prefixes:
        documents = [tree.find_document(p) for p in document_prefixes]

    for document in documents:
        for doorstop_item in document:
            if not include_inactive and not doorstop_item.active:
                continue

            # Extract custom attributes (everything not in standard fields)
            standard_fields = {
                "active",
                "normative",
                "derived",
                "text",
                "header",
                "level",
                "links",
                "ref",
                "references",
                "reviewed",
            }
            custom_attrs = {
                k: v for k, v in doorstop_item.data.items() if k not in standard_fields
            }

            # doorstop Level type has .yaml for string representation
            level_obj = doorstop_item.level
            level_float = float(getattr(level_obj, "yaml", level_obj) or 1.0)

            item = Item(
                uid=str(doorstop_item.uid),
                text=doorstop_item.text or "",
                document_prefix=document.prefix,
                active=bool(doorstop_item.active),
                normative=bool(doorstop_item.normative),
                header=doorstop_item.header,
                level=level_float,
                links=[str(link) for link in doorstop_item.links],
                custom_attributes=custom_attrs,
            )
            items.append(item)

    return items


def build_traceability_graph(
    tree: doorstop.Tree,
    document_prefixes: list[str] | None = None,
    include_inactive: bool = False,
) -> TraceabilityGraph:
    """
    Build a complete traceability graph from a doorstop tree.

    Args:
        tree: The doorstop tree.
        document_prefixes: Optional list of document prefixes to include.
                          If None, includes all documents.
        include_inactive: Whether to include inactive items.

    Returns:
        A TraceabilityGraph containing all items and relationships.
    """
    graph = TraceabilityGraph()

    # First, build document hierarchy
    documents = list(tree.documents)
    if document_prefixes:
        documents = [tree.find_document(p) for p in document_prefixes]

    for document in documents:
        parent_prefix = document.parent if document.parent else None
        graph.set_document_parent(document.prefix, parent_prefix)

    # Then add all items
    items = read_tree(tree, document_prefixes, include_inactive)
    for item in items:
        graph.add_item(item)

    return graph
