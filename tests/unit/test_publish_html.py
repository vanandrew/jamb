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
        srs_item = Item(uid="SRS001", text="Software req", document_prefix="SRS", links=["UN001"])
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
        srs_item = Item(uid="SRS001", text="Software req", document_prefix="SRS", links=["UN001"])
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

    def test_render_html_heading_item_class_and_h2(self):
        """Test that heading items get item-heading class and render as <h2>."""
        items = [
            Item(
                uid="SRS001",
                text="",
                header="Safety Requirements",
                document_prefix="SRS",
                type="heading",
            ),
        ]
        result = render_html(items, "SRS")

        assert 'class="item item-heading"' in result
        assert "<h2" in result
        assert "Safety Requirements" in result
        # Heading should show header text (badge is appended)
        assert "Safety Requirements<span" in result

    def test_render_html_info_item_class(self):
        """Test that info items get item-info class."""
        items = [
            Item(
                uid="SRS002",
                text="This is informational text.",
                document_prefix="SRS",
                type="info",
            ),
        ]
        result = render_html(items, "SRS")

        assert 'class="item item-info"' in result
        assert "This is informational text." in result

    def test_render_html_requirement_item_class(self):
        """Test that requirement items get item-requirement class."""
        items = [
            Item(
                uid="SRS003",
                text="The system shall do something.",
                document_prefix="SRS",
                type="requirement",
            ),
        ]
        result = render_html(items, "SRS")

        assert 'class="item item-requirement"' in result

    def test_render_html_heading_no_uid_prefix(self):
        """Test that heading items show only header text, not UID prefix."""
        items = [
            Item(
                uid="SRS001",
                text="",
                header="Section Header",
                document_prefix="SRS",
                type="heading",
            ),
        ]
        result = render_html(items, "SRS")

        # Should NOT have "SRS001: Section Header" in the h2
        assert "SRS001: Section Header<span" not in result
        # Header text should appear before the badge span
        assert "Section Header<span" in result

    def test_render_html_child_links_no_graph(self):
        """Child links section not rendered when graph is None."""
        items = [
            Item(uid="UN001", text="Need", document_prefix="UN"),
            Item(uid="SRS001", text="Req", document_prefix="SRS", links=["UN001"]),
        ]
        result = render_html(items, "Test", graph=None)
        assert "Linked from:" not in result

    def test_render_html_document_order_with_missing_prefix(self):
        """Items from unknown prefixes sort after known ones."""
        items = [
            Item(uid="SRS001", text="Software", document_prefix="SRS"),
            Item(uid="UN001", text="Need", document_prefix="UN"),
            Item(uid="OTHER001", text="Other", document_prefix="OTHER"),
        ]
        result = render_html(items, "Test", document_order=["UN", "SRS"])
        un_pos = result.find("UN001")
        srs_pos = result.find("SRS001")
        other_pos = result.find("OTHER001")
        assert un_pos < srs_pos
        # OTHER not in document_order, sorts after known prefixes
        assert srs_pos < other_pos

    def test_render_html_external_child_links_not_shown(self):
        """Child links to items not in the rendered set are not shown."""
        graph = TraceabilityGraph()
        un_item = Item(uid="UN001", text="Need", document_prefix="UN")
        srs_item = Item(uid="SRS001", text="Req", document_prefix="SRS", links=["UN001"])
        graph.add_item(un_item)
        graph.add_item(srs_item)

        # Only render UN001, so SRS001 is not in the output
        items = [un_item]
        result = render_html(items, "Test", graph=graph)
        # SRS001 links to UN001, but SRS001 is not in rendered set
        assert "Linked from:" not in result

    def test_render_html_heading_no_header_falls_back_to_uid(self):
        """6a: Heading item with no header falls back to UID."""
        items = [
            Item(
                uid="SRS001",
                text="",
                document_prefix="SRS",
                type="heading",
                header="",
            ),
        ]
        result = render_html(items, "SRS")
        # Heading display should fall back to UID (followed by badge)
        assert ">SRS001<span" in result

    def test_render_html_text_with_newlines(self):
        """6b: Item text with newline characters appears in output."""
        items = [
            Item(uid="SRS001", text="line1\nline2\nline3", document_prefix="SRS"),
        ]
        result = render_html(items, "SRS")
        assert "line1" in result
        assert "line2" in result
        assert "line3" in result

    def test_render_html_unicode_text(self):
        """6c: Unicode characters in item text are correctly encoded."""
        items = [
            Item(uid="SRS001", text="Ünïcödé — «text» ñ 日本語", document_prefix="SRS"),
        ]
        result = render_html(items, "SRS")
        assert "Ünïcödé" in result
        assert "日本語" in result

    def test_all_unknown_document_order(self):
        """Items with prefixes not in document_order sort alphabetically."""
        items = [
            Item(uid="ZZZ001", text="Zulu item", document_prefix="ZZZ"),
            Item(uid="AAA001", text="Alpha item", document_prefix="AAA"),
        ]
        result = render_html(items, "Test", document_order=["UN"])

        assert "AAA001" in result
        assert "ZZZ001" in result
        # Both unknown prefixes get index 999, so they sort alphabetically
        aaa_pos = result.find("AAA001")
        zzz_pos = result.find("ZZZ001")
        assert aaa_pos < zzz_pos

    def test_header_none_vs_empty_string(self):
        """Items with header=None or header='' produce UID-only headings."""
        items = [
            Item(uid="SRS001", text="First", document_prefix="SRS", header=None),
            Item(uid="SRS002", text="Second", document_prefix="SRS", header=""),
        ]
        result = render_html(items, "SRS")

        # Both should render UID-only headings without ": " (followed by badge)
        assert ">SRS001<span" in result
        assert ">SRS002<span" in result

    def test_empty_links_list(self):
        """Item with links=[] should not render a Links section."""
        items = [
            Item(uid="SRS001", text="No links here", document_prefix="SRS", links=[]),
        ]
        result = render_html(items, "SRS")

        assert "Links:" not in result

    def test_links_none_default(self):
        """Item with default links (not passed) should not render a Links section."""
        items = [
            Item(uid="SRS001", text="Default links", document_prefix="SRS"),
        ]
        result = render_html(items, "SRS")

        assert "Links:" not in result


class TestRenderHtmlStyling:
    """Tests for improved HTML styling features."""

    def test_render_html_has_css_variables(self):
        """Test that CSS includes custom property (variable) definitions."""
        items = [Item(uid="SRS001", text="Test", document_prefix="SRS")]
        result = render_html(items, "SRS")

        assert ":root {" in result
        assert "--color-primary" in result
        assert "--color-text" in result

    def test_render_html_has_print_styles(self):
        """Test that CSS includes print media query."""
        items = [Item(uid="SRS001", text="Test", document_prefix="SRS")]
        result = render_html(items, "SRS")

        assert "@media print" in result

    def test_render_html_item_type_badges(self):
        """Test that items have type badges."""
        items = [
            Item(uid="SRS001", text="Req", document_prefix="SRS", type="requirement"),
            Item(
                uid="SRS002",
                text="",
                header="Section",
                document_prefix="SRS",
                type="heading",
            ),
            Item(uid="SRS003", text="Info", document_prefix="SRS", type="info"),
        ]
        result = render_html(items, "SRS")

        assert "badge-requirement" in result
        assert "badge-heading" in result
        assert "badge-info" in result

    def test_render_html_card_styling(self):
        """Test that items have card-like styling classes."""
        items = [Item(uid="SRS001", text="Test", document_prefix="SRS")]
        result = render_html(items, "SRS")

        # Check for border-radius in CSS (indicates card styling)
        assert "border-radius" in result


class TestRenderHtmlEdgeCases:
    """Additional edge case tests for render_html."""

    def test_mixed_item_types_same_prefix_render_in_sequence(self):
        """Heading, info, and requirement items from same
        prefix render with correct classes."""
        items = [
            Item(
                uid="SRS001",
                text="",
                header="Safety Section",
                document_prefix="SRS",
                type="heading",
            ),
            Item(
                uid="SRS002",
                text="This section covers safety.",
                document_prefix="SRS",
                type="info",
            ),
            Item(
                uid="SRS003",
                text="The system shall be safe.",
                document_prefix="SRS",
                type="requirement",
            ),
        ]
        result = render_html(items, "SRS")

        # All three items should appear in order
        pos_001 = result.find('id="SRS001"')
        pos_002 = result.find('id="SRS002"')
        pos_003 = result.find('id="SRS003"')
        assert pos_001 < pos_002 < pos_003

        # Each has the correct CSS class
        assert 'class="item item-heading"' in result
        assert 'class="item item-info"' in result
        assert 'class="item item-requirement"' in result

        # Heading renders as <h2>, others as <h3>
        # Each item has a type badge appended
        assert ">Safety Section<span" in result
        assert ">SRS002<span" in result
        assert ">SRS003<span" in result

    def test_heading_item_with_links_still_renders_links(self):
        """A heading-type item that has links should still show Links section."""
        items = [
            Item(uid="UN001", text="User need", document_prefix="UN"),
            Item(
                uid="SRS001",
                text="",
                header="Auth Section",
                document_prefix="SRS",
                type="heading",
                links=["UN001"],
            ),
        ]
        result = render_html(items, "Requirements")

        # Even though it's a heading, links should render
        assert "Links:" in result
        assert '<a href="#UN001">UN001</a>' in result

    def test_multiple_unknown_prefixes_alphabetical_sub_order(self):
        """Multiple unknown prefixes sort alphabetically
        among themselves after known ones."""
        items = [
            Item(uid="SRS001", text="Software", document_prefix="SRS"),
            Item(uid="ZZZ001", text="Zulu", document_prefix="ZZZ"),
            Item(uid="MMM001", text="Middle", document_prefix="MMM"),
            Item(uid="AAA001", text="Alpha", document_prefix="AAA"),
        ]
        result = render_html(items, "Test", document_order=["SRS"])

        srs_pos = result.find("SRS001")
        aaa_pos = result.find("AAA001")
        mmm_pos = result.find("MMM001")
        zzz_pos = result.find("ZZZ001")

        # SRS is in document_order, so it comes first
        assert srs_pos < aaa_pos
        # Unknown prefixes sorted alphabetically: AAA < MMM < ZZZ
        assert aaa_pos < mmm_pos < zzz_pos
