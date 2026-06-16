"""Integration tests that render real output through the Quarto binary.

These are marked ``quarto`` and skipped automatically when no Quarto binary is
available (see ``tests/conftest.py``).
"""

from __future__ import annotations

import zipfile

import pytest

from jamb.core.models import Item, TraceabilityGraph
from jamb.publish import OutputFormat, build_publish_document, render_document

pytestmark = pytest.mark.quarto


@pytest.fixture
def sample_document():
    items = [
        Item(uid="UN001", text="The user needs to authenticate.", document_prefix="UN"),
        Item(
            uid="SRS001",
            text="The system shall authenticate via OAuth 2.0.",
            document_prefix="SRS",
            links=["UN001"],
        ),
        Item(uid="SRS002", text="Overview.", document_prefix="SRS", type="heading", header="Security", level=2),
    ]
    graph = TraceabilityGraph()
    for item in items:
        graph.add_item(item)
    return build_publish_document(
        items,
        "SRS Requirements Document",
        include_links=True,
        document_order=["UN", "SRS"],
        graph=graph,
    )


def test_render_html(sample_document, tmp_path):
    out = tmp_path / "out.html"
    render_document(sample_document, OutputFormat.HTML, out)
    content = out.read_text()
    assert content.lstrip().startswith("<!DOCTYPE")
    # Cross-reference anchors survive the Pandoc round-trip.
    assert 'id="SRS001"' in content
    assert 'href="#UN001"' in content
    assert 'id="doc-SRS"' in content


def test_render_pdf(sample_document, tmp_path):
    out = tmp_path / "out.pdf"
    render_document(sample_document, OutputFormat.PDF, out)
    assert out.read_bytes()[:5] == b"%PDF-"


def test_render_docx(sample_document, tmp_path):
    out = tmp_path / "out.docx"
    render_document(sample_document, OutputFormat.DOCX, out)
    data = out.read_bytes()
    assert data[:4] == b"PK\x03\x04"
    # The DOCX is a zip; the body should mention a rendered UID.
    with zipfile.ZipFile(out) as zf:
        document_xml = zf.read("word/document.xml").decode("utf-8")
    assert "SRS001" in document_xml


def test_render_html_with_custom_theme(sample_document, tmp_path):
    theme = tmp_path / "custom.scss"
    theme.write_text("/*-- scss:defaults --*/\n$primary: #ff0000;\n")
    out = tmp_path / "themed.html"
    render_document(sample_document, OutputFormat.HTML, out, template=theme)
    assert out.exists()
    assert out.read_text().lstrip().startswith("<!DOCTYPE")


def test_markdown_does_not_require_binary(sample_document, tmp_path):
    # MD is written directly; this exercises the non-rendered path end to end.
    out = tmp_path / "out.md"
    render_document(sample_document, OutputFormat.MD, out)
    assert "# SRS {#doc-SRS}" in out.read_text()


def test_render_creates_parent_directories(sample_document, tmp_path):
    out = tmp_path / "nested" / "deep" / "out.pdf"
    render_document(sample_document, OutputFormat.PDF, out)
    assert out.exists()


def test_render_failure_raises(sample_document, tmp_path):
    """An invalid reference document surfaces a QuartoRenderError."""
    from jamb.publish import QuartoRenderError

    bogus = tmp_path / "broken.docx"
    bogus.write_text("this is not a valid docx reference document")
    out = tmp_path / "out.docx"
    with pytest.raises(QuartoRenderError):
        render_document(sample_document, OutputFormat.DOCX, out, template=bogus)
