"""Unit tests for DOCX publishing."""

import io

from docx import Document

from jamb.core.models import Item
from jamb.publish.formats.docx import render_docx


class TestRenderDocx:
    """Tests for the render_docx function."""

    def test_render_docx_returns_bytes(self):
        """Test that render_docx returns bytes."""
        items = [
            Item(uid="SRS001", text="Test requirement", document_prefix="SRS"),
        ]
        result = render_docx(items, "SRS")

        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_render_docx_valid_document(self):
        """Test that render_docx produces a valid DOCX file."""
        items = [
            Item(uid="SRS001", text="Test requirement", document_prefix="SRS"),
        ]
        result = render_docx(items, "SRS")

        # Should be able to open as a valid DOCX
        doc = Document(io.BytesIO(result))
        assert doc is not None

    def test_render_docx_contains_title(self):
        """Test that render_docx includes document title."""
        items = [
            Item(uid="SRS001", text="Test requirement", document_prefix="SRS"),
        ]
        result = render_docx(items, "SRS")

        doc = Document(io.BytesIO(result))
        # First paragraph should contain the document title
        paragraphs = [p.text for p in doc.paragraphs]
        assert any("SRS" in p for p in paragraphs)

    def test_render_docx_contains_item_uid(self):
        """Test that render_docx includes item UIDs."""
        items = [
            Item(uid="SRS001", text="Test requirement 1", document_prefix="SRS"),
            Item(uid="SRS002", text="Test requirement 2", document_prefix="SRS"),
        ]
        result = render_docx(items, "SRS")

        doc = Document(io.BytesIO(result))
        paragraphs = [p.text for p in doc.paragraphs]
        full_text = " ".join(paragraphs)

        assert "SRS001" in full_text
        assert "SRS002" in full_text

    def test_render_docx_contains_item_text(self):
        """Test that render_docx includes item text."""
        items = [
            Item(
                uid="SRS001",
                text="The system shall authenticate users.",
                document_prefix="SRS",
            ),
        ]
        result = render_docx(items, "SRS")

        doc = Document(io.BytesIO(result))
        paragraphs = [p.text for p in doc.paragraphs]
        full_text = " ".join(paragraphs)

        assert "authenticate users" in full_text

    def test_render_docx_contains_headers(self):
        """Test that render_docx includes item headers."""
        items = [
            Item(
                uid="SRS001",
                text="Some text",
                header="Authentication Requirement",
                document_prefix="SRS",
            ),
        ]
        result = render_docx(items, "SRS")

        doc = Document(io.BytesIO(result))
        paragraphs = [p.text for p in doc.paragraphs]
        full_text = " ".join(paragraphs)

        assert "Authentication Requirement" in full_text

    def test_render_docx_contains_links(self):
        """Test that render_docx includes item links."""
        items = [
            Item(
                uid="SRS001",
                text="Test requirement",
                document_prefix="SRS",
                links=["UN001", "UN002"],
            ),
        ]
        result = render_docx(items, "SRS")

        doc = Document(io.BytesIO(result))
        paragraphs = [p.text for p in doc.paragraphs]
        full_text = " ".join(paragraphs)

        assert "Links:" in full_text
        assert "UN001" in full_text
        assert "UN002" in full_text

    def test_render_docx_no_links_when_disabled(self):
        """Test that render_docx omits links when include_child_links is False."""
        items = [
            Item(
                uid="SRS001",
                text="Test requirement",
                document_prefix="SRS",
                links=["UN001"],
            ),
        ]
        result = render_docx(items, "SRS", include_child_links=False)

        doc = Document(io.BytesIO(result))
        paragraphs = [p.text for p in doc.paragraphs]
        full_text = " ".join(paragraphs)

        assert "Links:" not in full_text

    def test_render_docx_empty_items_list(self):
        """Test that render_docx handles empty items list."""
        result = render_docx([], "SRS")

        assert isinstance(result, bytes)
        doc = Document(io.BytesIO(result))
        # Should still have title and summary
        paragraphs = [p.text for p in doc.paragraphs]
        full_text = " ".join(paragraphs)
        assert "Total items: 0" in full_text

    def test_render_docx_sorts_by_level(self):
        """Test that render_docx sorts items by level."""
        items = [
            Item(uid="SRS002", text="Second", document_prefix="SRS", level=2.0),
            Item(uid="SRS001", text="First", document_prefix="SRS", level=1.0),
            Item(uid="SRS003", text="Third", document_prefix="SRS", level=1.5),
        ]
        result = render_docx(items, "SRS")

        doc = Document(io.BytesIO(result))
        paragraphs = [p.text for p in doc.paragraphs]
        full_text = " ".join(paragraphs)

        # Find positions of each item
        pos_001 = full_text.find("SRS001")
        pos_002 = full_text.find("SRS002")
        pos_003 = full_text.find("SRS003")

        # Should be sorted by level: 1.0, 1.5, 2.0
        assert pos_001 < pos_003 < pos_002

    def test_render_docx_item_without_text(self):
        """Test that render_docx handles items without text."""
        items = [
            Item(uid="SRS001", text="", document_prefix="SRS", header="Header Only"),
        ]
        result = render_docx(items, "SRS")

        # Should not raise an error
        assert isinstance(result, bytes)
        doc = Document(io.BytesIO(result))
        assert doc is not None

    def test_render_docx_multiple_documents(self):
        """Test that render_docx handles items from multiple documents."""
        items = [
            Item(uid="UN001", text="Customer need", document_prefix="UN"),
            Item(uid="SRS001", text="Software req", document_prefix="SRS"),
            Item(uid="SYS001", text="System req", document_prefix="SYS"),
        ]
        result = render_docx(items, "Requirements Document")

        doc = Document(io.BytesIO(result))
        paragraphs = [p.text for p in doc.paragraphs]
        full_text = " ".join(paragraphs)

        # Should contain all items
        assert "UN001" in full_text
        assert "SRS001" in full_text
        assert "SYS001" in full_text

    def test_render_docx_links_as_hyperlinks(self):
        """Test that links to items in the document become hyperlinks."""
        items = [
            Item(uid="UN001", text="Customer need", document_prefix="UN"),
            Item(
                uid="SRS001",
                text="Software req",
                document_prefix="SRS",
                links=["UN001"],
            ),
        ]
        result = render_docx(items, "Requirements Document")

        # Should produce valid docx with hyperlinks
        doc = Document(io.BytesIO(result))
        assert doc is not None

        # Check that the document contains the link text
        paragraphs = [p.text for p in doc.paragraphs]
        full_text = " ".join(paragraphs)
        assert "Links:" in full_text
