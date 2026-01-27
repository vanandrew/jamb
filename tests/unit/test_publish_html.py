"""Unit tests for HTML publishing."""

from jamb.core.models import Item, TraceabilityGraph
from jamb.publish.formats.html import render_html


class TestRenderHtml:
    """Tests for the render_html function."""

    def test_render_html_returns_string(self):
        """Test that render_html returns a string."""
        items = [
            Item(uid="SRS001", text="Test requirement", document_prefix="SRS"),
        ]
        result = render_html(items, "SRS")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_render_html_valid_structure(self):
        """Test that render_html produces valid HTML structure."""
        items = [
            Item(uid="SRS001", text="Test requirement", document_prefix="SRS"),
        ]
        result = render_html(items, "SRS")

        assert "<!DOCTYPE html>" in result
        assert "<html" in result
        assert "</html>" in result
        assert "<head>" in result
        assert "<style>" in result
        assert "<body>" in result

    def test_render_html_contains_title(self):
        """Test that render_html includes document title."""
        items = [
            Item(uid="SRS001", text="Test requirement", document_prefix="SRS"),
        ]
        result = render_html(items, "SRS Requirements")

        assert "<h1>SRS Requirements</h1>" in result

    def test_render_html_contains_summary(self):
        """Test that render_html includes item count summary."""
        items = [
            Item(uid="SRS001", text="Req 1", document_prefix="SRS"),
            Item(uid="SRS002", text="Req 2", document_prefix="SRS"),
        ]
        result = render_html(items, "SRS")

        assert "Total items: 2" in result

    def test_render_html_contains_item_uid_and_text(self):
        """Test that render_html includes item UIDs and text."""
        items = [
            Item(uid="SRS001", text="Authenticate users", document_prefix="SRS"),
            Item(uid="SRS002", text="Log events", document_prefix="SRS"),
        ]
        result = render_html(items, "SRS")

        assert "SRS001" in result
        assert "SRS002" in result
        assert "Authenticate users" in result
        assert "Log events" in result

    def test_render_html_item_anchors(self):
        """Test that items have anchor IDs."""
        items = [
            Item(uid="SRS001", text="Test", document_prefix="SRS"),
        ]
        result = render_html(items, "SRS")

        assert 'id="SRS001"' in result

    def test_render_html_contains_headers(self):
        """Test that render_html includes item headers."""
        items = [
            Item(
                uid="SRS001",
                text="Some text",
                header="Auth Requirement",
                document_prefix="SRS",
            ),
        ]
        result = render_html(items, "SRS")

        assert "SRS001: Auth Requirement" in result

    def test_render_html_parent_links_as_hyperlinks(self):
        """Test that parent links are rendered as anchor hyperlinks."""
        items = [
            Item(uid="UN001", text="User need", document_prefix="UN"),
            Item(
                uid="SRS001",
                text="Software req",
                document_prefix="SRS",
                links=["UN001"],
            ),
        ]
        result = render_html(items, "Requirements")

        assert '<a href="#UN001">UN001</a>' in result
        assert "Links:" in result

    def test_render_html_child_links_as_hyperlinks(self):
        """Test that child links are rendered as anchor hyperlinks."""
        graph = TraceabilityGraph()
        un_item = Item(uid="UN001", text="User need", document_prefix="UN")
        srs_item = Item(
            uid="SRS001", text="Software req", document_prefix="SRS", links=["UN001"]
        )
        graph.add_item(un_item)
        graph.add_item(srs_item)

        items = [un_item, srs_item]
        result = render_html(items, "Requirements", graph=graph)

        # UN001 should show "Linked from: SRS001"
        assert "Linked from:" in result
        assert '<a href="#SRS001">SRS001</a>' in result

    def test_render_html_no_links_when_disabled(self):
        """Test that include_links=False suppresses both parent and child links."""
        graph = TraceabilityGraph()
        un_item = Item(uid="UN001", text="User need", document_prefix="UN")
        srs_item = Item(
            uid="SRS001", text="Software req", document_prefix="SRS", links=["UN001"]
        )
        graph.add_item(un_item)
        graph.add_item(srs_item)

        items = [un_item, srs_item]
        result = render_html(items, "Requirements", include_links=False, graph=graph)

        assert "Links:" not in result
        assert "Linked from:" not in result

    def test_render_html_document_sections(self):
        """Test that multi-document output has section headers."""
        items = [
            Item(uid="UN001", text="User need", document_prefix="UN"),
            Item(uid="SRS001", text="Software req", document_prefix="SRS"),
        ]
        result = render_html(items, "Requirements", document_order=["UN", "SRS"])

        assert 'id="doc-UN"' in result
        assert 'id="doc-SRS"' in result

    def test_render_html_sorts_by_document_order(self):
        """Test items sorted by document order, then UID."""
        items = [
            Item(uid="SRS001", text="Software req", document_prefix="SRS"),
            Item(uid="UN001", text="User need", document_prefix="UN"),
        ]
        result = render_html(items, "Requirements", document_order=["UN", "SRS"])

        # UN should come before SRS
        un_pos = result.find("UN001")
        srs_pos = result.find("SRS001")
        assert un_pos < srs_pos

    def test_render_html_empty_items(self):
        """Test that render_html handles empty items list."""
        result = render_html([], "Empty Document")

        assert "<!DOCTYPE html>" in result
        assert "Total items: 0" in result

    def test_render_html_escapes_special_chars(self):
        """Test that HTML special characters are escaped."""
        items = [
            Item(uid="SRS001", text="x < 5 & y > 3", document_prefix="SRS"),
        ]
        result = render_html(items, "Test <Script>")

        assert "&lt;" in result
        assert "&amp;" in result
        assert "&gt;" in result
        # Title should also be escaped
        assert "Test &lt;Script&gt;" in result

    def test_render_html_external_link_plain_text(self):
        """Test that links to items not in the document are plain text."""
        items = [
            Item(
                uid="SRS001",
                text="Software req",
                document_prefix="SRS",
                links=["EXTERNAL001"],
            ),
        ]
        result = render_html(items, "SRS")

        # EXTERNAL001 should appear but NOT as a hyperlink
        assert "EXTERNAL001" in result
        assert '<a href="#EXTERNAL001">' not in result
