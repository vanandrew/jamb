"""Build TraceabilityGraph from native storage layer."""

from jamb.core.models import Item, TraceabilityGraph
from jamb.storage.document_dag import DocumentDAG
from jamb.storage.items import read_document_items


def build_traceability_graph(
    dag: DocumentDAG,
    document_prefixes: list[str] | None = None,
    include_inactive: bool = False,
) -> TraceabilityGraph:
    """Build a TraceabilityGraph from the native storage layer.

    Args:
        dag: The document DAG with discovered documents.
        document_prefixes: Optional list of prefixes to include.
            If None, includes all documents.
        include_inactive: Whether to include inactive items.

    Returns:
        TraceabilityGraph populated with items and document relationships.
    """
    graph = TraceabilityGraph()

    if document_prefixes is not None:
        prefixes_to_load = document_prefixes
    else:
        prefixes_to_load = list(dag.documents.keys())

    for prefix in prefixes_to_load:
        if prefix not in dag.documents:
            continue

        config = dag.documents[prefix]
        doc_path = dag.document_paths.get(prefix)

        # Set document parents (DAG: multiple parents)
        graph.set_document_parents(prefix, config.parents)

        if doc_path is None:
            continue

        # Read items from disk
        raw_items = read_document_items(doc_path, prefix, include_inactive)

        for raw in raw_items:
            item = Item(
                uid=raw["uid"],
                text=raw["text"],
                document_prefix=raw["document_prefix"],
                active=raw["active"],
                type=raw["type"],
                header=raw["header"],
                links=raw["links"],
                reviewed=raw["reviewed"],
                derived=raw["derived"],
                custom_attributes=raw.get("custom_attributes", {}),
            )
            graph.add_item(item)

    return graph
