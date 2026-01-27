"""HTML document output for publishing."""

from __future__ import annotations

import html

from jamb.core.models import Item, TraceabilityGraph

_CSS = """\
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
    max-width: 960px;
    margin: 0 auto;
    padding: 2rem;
    color: #333;
    line-height: 1.6;
}
h1 { border-bottom: 2px solid #2c3e50; padding-bottom: 0.5rem; color: #2c3e50; }
h2 { border-bottom: 1px solid #bdc3c7; padding-bottom: 0.3rem;
  color: #2c3e50; margin-top: 2rem; }
h3, h4, h5, h6 { color: #34495e; }
p { margin: 0.5rem 0; }
a { color: #2980b9; text-decoration: none; }
a:hover { text-decoration: underline; }
.summary { color: #7f8c8d; font-style: italic; margin-bottom: 1.5rem; }
.item { margin-bottom: 1.5rem; padding-left: 0.5rem; }
.item-heading h2 { border-bottom: 2px solid #2c3e50;
  font-weight: 700; margin-top: 2.5rem; }
.item-info { color: #7f8c8d; font-style: italic; }
.links, .child-links { font-size: 0.9rem; color: #555; margin-top: 0.3rem; }
.links strong, .child-links strong { color: #333; }
"""


def render_html(
    items: list[Item],
    title: str,
    include_links: bool = True,
    document_order: list[str] | None = None,
    graph: TraceabilityGraph | None = None,
) -> str:
    """Render items as a standalone HTML document.

    Args:
        items: List of Item objects to include.
        title: The document title.
        include_links: Whether to include parent and child link sections.
        document_order: Optional list of document prefixes in hierarchy order.
        graph: Optional traceability graph for child link lookup.

    Returns:
        HTML string.
    """
    all_uids = {item.uid for item in items}

    # Build document order index for sorting
    if document_order:
        doc_order_index = {prefix: i for i, prefix in enumerate(document_order)}
    else:
        doc_order_index = {}

    def get_doc_order(item: Item) -> int:
        return doc_order_index.get(item.document_prefix, 999)

    sorted_items = sorted(
        items, key=lambda x: (get_doc_order(x), x.document_prefix, x.uid)
    )

    parts: list[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="en">')
    parts.append("<head>")
    parts.append('<meta charset="utf-8">')
    parts.append(f"<title>{_esc(title)}</title>")
    parts.append(f"<style>{_CSS}</style>")
    parts.append("</head>")
    parts.append("<body>")
    parts.append(f"<h1>{_esc(title)}</h1>")
    parts.append(f'<p class="summary">Total items: {len(items)}</p>')

    current_doc: str | None = None

    for item in sorted_items:
        if item.document_prefix != current_doc:
            current_doc = item.document_prefix
            parts.append(f'<h2 id="doc-{_esc(current_doc)}">{_esc(current_doc)}</h2>')

        heading_text = f"{item.uid}: {item.header}" if item.header else item.uid

        item_type = getattr(item, "type", "requirement")
        if item_type == "heading":
            css_class = "item item-heading"
        elif item_type == "info":
            css_class = "item item-info"
        else:
            css_class = "item item-requirement"

        parts.append(f'<div class="{css_class}">')
        if item_type == "heading":
            heading_display = item.header if item.header else item.uid
            parts.append(f'<h2 id="{_esc(item.uid)}">{_esc(heading_display)}</h2>')
        else:
            parts.append(f'<h3 id="{_esc(item.uid)}">{_esc(heading_text)}</h3>')

        if item.text:
            parts.append(f"<p>{_esc(item.text)}</p>")

        if include_links and item.links:
            link_parts = []
            for link_uid in item.links:
                if link_uid in all_uids:
                    link_parts.append(
                        f'<a href="#{_esc(link_uid)}">{_esc(link_uid)}</a>'
                    )
                else:
                    link_parts.append(_esc(link_uid))
            parts.append(
                f'<p class="links"><strong>Links:</strong> {", ".join(link_parts)}</p>'
            )

        if include_links and graph is not None:
            children = graph.item_children.get(item.uid, [])
            # Only show children that are in the rendered set
            visible_children = [c for c in children if c in all_uids]
            if visible_children:
                child_parts = []
                for child_uid in visible_children:
                    child_parts.append(
                        f'<a href="#{_esc(child_uid)}">{_esc(child_uid)}</a>'
                    )
                parts.append(
                    f'<p class="child-links"><strong>Linked from:</strong> '
                    f"{', '.join(child_parts)}</p>"
                )

        parts.append("</div>")

    parts.append("</body>")
    parts.append("</html>")

    return "\n".join(parts)


def _esc(text: str) -> str:
    """Escape text for safe inclusion in HTML.

    Args:
        text: The plain text to escape.

    Returns:
        The HTML-escaped string.
    """
    return html.escape(str(text))
