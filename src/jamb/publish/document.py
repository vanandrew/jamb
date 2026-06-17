"""The in-memory document model handed to the Quarto renderer.

This module turns the requirement :class:`~jamb.core.models.Item` objects and
their traceability graph into a flat, ordered, render-agnostic structure. It
holds no formatting logic and never touches the filesystem or the Quarto
binary, which makes it fully deterministic and unit-testable on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from jamb.core.models import Item, TraceabilityGraph

ItemType = Literal["requirement", "info", "heading"]


@dataclass(frozen=True)
class RenderItem:
    """A single requirement item prepared for rendering.

    Attributes:
        uid: The item identifier, used verbatim as its anchor.
        type: The item type, which selects how the body is rendered.
        heading_text: The text shown on the item's heading line.
        body: The item body text (empty string when the item has none).
        level: Heading depth for ``heading`` items; ``None`` otherwise.
        parent_links: UIDs this item traces up to.
        child_links: UIDs that trace down to this item, restricted to the
            items present in the rendered set.
    """

    uid: str
    type: ItemType
    heading_text: str
    body: str
    level: int | None
    parent_links: tuple[str, ...]
    child_links: tuple[str, ...]


@dataclass(frozen=True)
class RenderSection:
    """A group of items sharing a document prefix."""

    prefix: str
    items: tuple[RenderItem, ...]


@dataclass(frozen=True)
class PublishDocument:
    """A complete document ready to be rendered to any output format.

    Attributes:
        title: The document title shown on the title block.
        subtitle: Optional metadata line shown under the title (e.g. document
            id, version, date, status), or ``None`` to omit.
        sections: Document sections in hierarchy order.
        total_items: The number of items across all sections.
        include_links: Whether parent and child link references render.
        known_uids: Every UID in the document, used to decide whether a
            parent link renders as an anchor or as plain text.
    """

    title: str
    subtitle: str | None
    sections: tuple[RenderSection, ...]
    total_items: int
    include_links: bool
    known_uids: frozenset[str]


def build_publish_document(
    items: list[Item],
    title: str,
    *,
    subtitle: str | None = None,
    include_links: bool = True,
    document_order: list[str] | None = None,
    graph: TraceabilityGraph | None = None,
) -> PublishDocument:
    """Assemble a :class:`PublishDocument` from requirement items.

    Items are ordered by document hierarchy, then document prefix, then UID,
    and grouped into one section per prefix.

    Args:
        items: The items to publish.
        title: The document title.
        subtitle: Optional metadata line shown under the title.
        include_links: Whether to carry parent and child link references.
        document_order: Document prefixes in hierarchy order; used to sort
            sections. Prefixes outside the list sort last, alphabetically.
        graph: The traceability graph, used to resolve child (reverse) links.

    Returns:
        The assembled document.
    """
    known_uids = frozenset(item.uid for item in items)

    if document_order:
        order_index = {prefix: i for i, prefix in enumerate(document_order)}
        fallback = len(document_order)
    else:
        order_index = {}
        fallback = 0

    def sort_key(item: Item) -> tuple[int, str, str]:
        return (order_index.get(item.document_prefix, fallback), item.document_prefix, item.uid)

    sections: list[RenderSection] = []
    current_prefix: str | None = None
    current_items: list[RenderItem] = []

    for item in sorted(items, key=sort_key):
        if item.document_prefix != current_prefix:
            if current_prefix is not None:
                sections.append(RenderSection(current_prefix, tuple(current_items)))
            current_prefix = item.document_prefix
            current_items = []

        heading_text = f"{item.uid}: {item.header}" if item.header else item.uid

        if graph is not None:
            child_links = tuple(c for c in graph.item_children.get(item.uid, []) if c in known_uids)
        else:
            child_links = ()

        current_items.append(
            RenderItem(
                uid=item.uid,
                type=item.type,
                heading_text=heading_text,
                body=item.text or "",
                level=item.level,
                parent_links=tuple(item.links),
                child_links=child_links,
            )
        )

    if current_prefix is not None:
        sections.append(RenderSection(current_prefix, tuple(current_items)))

    return PublishDocument(
        title=title,
        subtitle=subtitle,
        sections=tuple(sections),
        total_items=len(items),
        include_links=include_links,
        known_uids=known_uids,
    )
