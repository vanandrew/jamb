"""HTML document output for publishing."""

from __future__ import annotations

import html

from jamb.core.models import Item, TraceabilityGraph

_CSS = """\
:root {
    --color-primary: #1a365d;
    --color-secondary: #2c5282;
    --color-accent: #3182ce;
    --color-text: #1a202c;
    --color-text-muted: #4a5568;
    --color-border: #e2e8f0;
    --color-bg-card: #f7fafc;
    --color-bg-heading: #ebf4ff;
    --color-bg-info: #fefcbf;
    --color-badge-req: #48bb78;
    --color-badge-heading: #805ad5;
    --color-badge-info: #ed8936;
}
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
    max-width: 1000px;
    margin: 0 auto;
    padding: 2.5rem;
    color: var(--color-text);
    line-height: 1.7;
    font-size: 16px;
    background: #fff;
}
h1 {
    border-bottom: 3px solid var(--color-primary);
    padding-bottom: 0.75rem;
    color: var(--color-primary);
    font-size: 2.25rem;
    margin-bottom: 0.5rem;
}
h2 {
    border-bottom: 2px solid var(--color-border);
    padding-bottom: 0.4rem;
    color: var(--color-secondary);
    margin-top: 2.5rem;
    font-size: 1.5rem;
}
h3 {
    color: var(--color-primary);
    font-size: 1.15rem;
    margin-bottom: 0.5rem;
}
h4, h5, h6 { color: var(--color-secondary); }
p { margin: 0.75rem 0; }
a { color: var(--color-accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.summary {
    color: var(--color-text-muted);
    font-size: 0.95rem;
    margin-bottom: 2rem;
    padding: 0.75rem 1rem;
    background: var(--color-bg-card);
    border-radius: 6px;
    border-left: 4px solid var(--color-primary);
}
.item {
    margin-bottom: 1.75rem;
    padding: 1.25rem;
    background: var(--color-bg-card);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    border-left: 4px solid var(--color-badge-req);
}
.item h3 { margin-top: 0; }
.item-heading {
    background: var(--color-bg-heading);
    border-left-color: var(--color-badge-heading);
}
.item-heading h2 {
    border-bottom: none;
    font-weight: 700;
    margin-top: 0;
    margin-bottom: 0.5rem;
    color: var(--color-primary);
}
.item-info {
    background: var(--color-bg-info);
    border-left-color: var(--color-badge-info);
}
.item-info p { color: var(--color-text-muted); }
.item-type-badge {
    display: inline-block;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    margin-left: 0.75rem;
    vertical-align: middle;
}
.badge-requirement {
    background: var(--color-badge-req);
    color: white;
}
.badge-heading {
    background: var(--color-badge-heading);
    color: white;
}
.badge-info {
    background: var(--color-badge-info);
    color: white;
}
.links, .child-links {
    font-size: 0.9rem;
    color: var(--color-text-muted);
    margin-top: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px dashed var(--color-border);
}
.links strong, .child-links strong {
    color: var(--color-text);
    font-weight: 600;
}
/* Document section headers */
h2[id^="doc-"] {
    background: var(--color-primary);
    color: white;
    padding: 0.75rem 1rem;
    border-radius: 6px;
    border-bottom: none;
    font-size: 1.25rem;
    margin-top: 3rem;
}
/* Print styles */
@media print {
    body {
        max-width: none;
        padding: 1rem;
        font-size: 11pt;
    }
    .item {
        break-inside: avoid;
        border: 1px solid #ccc;
        box-shadow: none;
    }
    h1, h2, h3 {
        break-after: avoid;
    }
    h2[id^="doc-"] {
        background: none;
        color: var(--color-primary);
        border-bottom: 2px solid var(--color-primary);
    }
    a { color: var(--color-text); }
    a::after { content: " (" attr(href) ")"; font-size: 0.8em; }
    a[href^="#"]::after { content: ""; }
}
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

    fallback_order = len(document_order) if document_order else 0

    def get_doc_order(item: Item) -> int:
        return doc_order_index.get(item.document_prefix, fallback_order)

    sorted_items = sorted(items, key=lambda x: (get_doc_order(x), x.document_prefix, x.uid))

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

        item_type = item.type
        if item_type == "heading":
            css_class = "item item-heading"
        elif item_type == "info":
            css_class = "item item-info"
        else:
            css_class = "item item-requirement"

        parts.append(f'<div class="{css_class}">')
        if item_type == "heading":
            heading_display = item.header if item.header else item.uid
            parts.append(
                f'<h2 id="{_esc(item.uid)}">{_esc(heading_display)}'
                f'<span class="item-type-badge badge-heading">Heading</span></h2>'
            )
        elif item_type == "info":
            parts.append(
                f'<h3 id="{_esc(item.uid)}">{_esc(heading_text)}'
                f'<span class="item-type-badge badge-info">Info</span></h3>'
            )
        else:
            parts.append(
                f'<h3 id="{_esc(item.uid)}">{_esc(heading_text)}'
                f'<span class="item-type-badge badge-requirement">Req</span></h3>'
            )

        if item.text:
            parts.append(f"<p>{_esc(item.text)}</p>")

        if include_links and item.links:
            link_parts = []
            for link_uid in item.links:
                if link_uid in all_uids:
                    link_parts.append(f'<a href="#{_esc(link_uid)}">{_esc(link_uid)}</a>')
                else:
                    link_parts.append(_esc(link_uid))
            parts.append(f'<p class="links"><strong>Links:</strong> {", ".join(link_parts)}</p>')

        if include_links and graph is not None:
            children = graph.item_children.get(item.uid, [])
            # Only show children that are in the rendered set
            visible_children = [c for c in children if c in all_uids]
            if visible_children:
                child_parts = []
                for child_uid in visible_children:
                    child_parts.append(f'<a href="#{_esc(child_uid)}">{_esc(child_uid)}</a>')
                parts.append(f'<p class="child-links"><strong>Linked from:</strong> {", ".join(child_parts)}</p>')

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
