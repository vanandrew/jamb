"""Word (DOCX) document output for publishing."""

import io

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import RGBColor

from jamb.core.models import Item, TraceabilityGraph


def _add_bookmark(paragraph, bookmark_name: str) -> None:
    """Add a bookmark to a paragraph for internal linking."""
    # Create bookmark start
    bookmark_start = OxmlElement("w:bookmarkStart")
    bookmark_start.set(qn("w:id"), "0")
    bookmark_start.set(qn("w:name"), bookmark_name)

    # Create bookmark end
    bookmark_end = OxmlElement("w:bookmarkEnd")
    bookmark_end.set(qn("w:id"), "0")

    # Insert into paragraph
    paragraph._p.insert(0, bookmark_start)
    paragraph._p.append(bookmark_end)


def _add_hyperlink(paragraph, anchor: str, text: str) -> None:
    """Add an internal hyperlink to a paragraph."""
    # Create hyperlink element
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("w:anchor"), anchor)

    # Create run with text
    run = OxmlElement("w:r")
    run_props = OxmlElement("w:rPr")

    # Add hyperlink styling (blue, underlined)
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0000FF")
    run_props.append(color)

    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    run_props.append(underline)

    run.append(run_props)

    # Add text
    text_elem = OxmlElement("w:t")
    text_elem.text = text
    run.append(text_elem)

    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def render_docx(
    items: list[Item],
    title: str,
    include_child_links: bool = True,
    document_order: list[str] | None = None,
    graph: TraceabilityGraph | None = None,
) -> bytes:
    """Render items as a Word document.

    Args:
        items: List of Item objects to include in the document.
        title: The document title.
        include_child_links: Whether to include links section for each item.
        document_order: Optional list of document prefixes in hierarchy order
                       (root first, then children). If None, sorts alphabetically.

    Returns:
        Bytes representing the DOCX file.
    """
    doc = Document()

    # Build set of all item UIDs for link validation
    all_uids = {item.uid for item in items}

    # Add title
    title_para = doc.add_heading(title, level=0)
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Add summary paragraph
    doc.add_paragraph(f"Total items: {len(items)}")
    doc.add_paragraph()

    # Build document order index for sorting
    if document_order:
        doc_order_index = {prefix: i for i, prefix in enumerate(document_order)}
    else:
        doc_order_index = {}

    def get_doc_order(item: Item) -> int:
        return doc_order_index.get(item.document_prefix, 999)

    # Sort items by document hierarchy, then UID
    sorted_items = sorted(
        items, key=lambda x: (get_doc_order(x), x.document_prefix, x.uid)
    )

    # Track current document for section headers
    current_doc = None

    for item in sorted_items:
        # Add document section header if document changed
        if item.document_prefix != current_doc:
            current_doc = item.document_prefix
            doc.add_heading(f"{current_doc}", level=1)

        # Create heading with UID and optional header
        item_type = getattr(item, "type", "requirement")

        if item_type == "heading":
            heading_display = item.header if item.header else item.uid
            heading = doc.add_heading(heading_display, level=1)
        else:
            if item.header:
                heading_text = f"{item.uid}: {item.header}"
            else:
                heading_text = item.uid
            heading = doc.add_heading(heading_text, level=2)

        # Add bookmark for this item so links can reference it
        _add_bookmark(heading, item.uid)

        # Add item text
        if item.text:
            if item_type == "info":
                para = doc.add_paragraph()
                run = para.add_run(item.text)
                run.italic = True
                run.font.color.rgb = RGBColor(0x7F, 0x8C, 0x8D)
            else:
                doc.add_paragraph(item.text)

        # Add links section with hyperlinks
        if include_child_links and item.links:
            links_para = doc.add_paragraph()
            links_run = links_para.add_run("Links: ")
            links_run.bold = True

            for i, link_uid in enumerate(item.links):
                if i > 0:
                    links_para.add_run(", ")

                # Add as hyperlink if target exists, otherwise plain text
                if link_uid in all_uids:
                    _add_hyperlink(links_para, link_uid, link_uid)
                else:
                    links_para.add_run(link_uid)

        # Add child links section (reverse links)
        if include_child_links and graph is not None:
            children = graph.item_children.get(item.uid, [])
            visible_children = [c for c in children if c in all_uids]
            if visible_children:
                child_para = doc.add_paragraph()
                child_run = child_para.add_run("Linked from: ")
                child_run.bold = True

                for i, child_uid in enumerate(visible_children):
                    if i > 0:
                        child_para.add_run(", ")
                    _add_hyperlink(child_para, child_uid, child_uid)

        # Add spacing between items
        doc.add_paragraph()

    # Save to bytes
    output = io.BytesIO()
    doc.save(output)
    return output.getvalue()
