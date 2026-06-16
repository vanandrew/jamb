"""Unit tests for the pure publishing layer (no Quarto binary involved)."""

from __future__ import annotations

import pytest
import yaml

from jamb.core.models import Item, TraceabilityGraph
from jamb.publish.document import build_publish_document
from jamb.publish.formats import OutputFormat, format_from_path
from jamb.publish.qmd import _md_escape, render_qmd
from jamb.publish.quarto import QuartoNotFoundError, find_quarto


def _graph(*items: Item) -> TraceabilityGraph:
    graph = TraceabilityGraph()
    for item in items:
        graph.add_item(item)
    return graph


def _doc(items, *, include_links=True, order=None, graph=None, title="Doc"):
    return build_publish_document(
        items,
        title,
        include_links=include_links,
        document_order=order,
        graph=graph,
    )


# ---------------------------------------------------------------------------
# build_publish_document
# ---------------------------------------------------------------------------


class TestBuildPublishDocument:
    def test_sections_grouped_and_ordered_by_document(self):
        items = [
            Item(uid="SRS001", text="s", document_prefix="SRS"),
            Item(uid="UN001", text="u", document_prefix="UN"),
        ]
        doc = _doc(items, order=["UN", "SRS"])
        assert [s.prefix for s in doc.sections] == ["UN", "SRS"]
        assert doc.total_items == 2

    def test_items_sorted_by_uid_within_section(self):
        items = [
            Item(uid="SRS002", text="b", document_prefix="SRS"),
            Item(uid="SRS001", text="a", document_prefix="SRS"),
        ]
        doc = _doc(items, order=["SRS"])
        assert [i.uid for i in doc.sections[0].items] == ["SRS001", "SRS002"]

    def test_unordered_prefixes_sort_last(self):
        items = [
            Item(uid="ZZZ001", text="z", document_prefix="ZZZ"),
            Item(uid="UN001", text="u", document_prefix="UN"),
        ]
        doc = _doc(items, order=["UN"])
        assert [s.prefix for s in doc.sections] == ["UN", "ZZZ"]

    def test_heading_text_uses_header_when_present(self):
        doc = _doc([Item(uid="SRS001", text="t", document_prefix="SRS", header="Login")], order=["SRS"])
        assert doc.sections[0].items[0].heading_text == "SRS001: Login"

    def test_heading_text_falls_back_to_uid(self):
        doc = _doc([Item(uid="SRS001", text="t", document_prefix="SRS")], order=["SRS"])
        assert doc.sections[0].items[0].heading_text == "SRS001"

    def test_child_links_restricted_to_rendered_set(self):
        parent = Item(uid="UN001", text="u", document_prefix="UN")
        child = Item(uid="SRS001", text="s", document_prefix="SRS", links=["UN001"])
        graph = _graph(parent, child)
        # Only render the parent: its child link to SRS001 must be dropped.
        doc = _doc([parent], order=["UN"], graph=graph)
        assert doc.sections[0].items[0].child_links == ()

    def test_child_links_present_when_target_rendered(self):
        parent = Item(uid="UN001", text="u", document_prefix="UN")
        child = Item(uid="SRS001", text="s", document_prefix="SRS", links=["UN001"])
        graph = _graph(parent, child)
        doc = _doc([parent, child], order=["UN", "SRS"], graph=graph)
        un = doc.sections[0].items[0]
        assert un.child_links == ("SRS001",)

    def test_known_uids_collects_every_item(self):
        items = [
            Item(uid="UN001", text="u", document_prefix="UN"),
            Item(uid="SRS001", text="s", document_prefix="SRS"),
        ]
        doc = _doc(items, order=["UN", "SRS"])
        assert doc.known_uids == frozenset({"UN001", "SRS001"})


# ---------------------------------------------------------------------------
# format_from_path
# ---------------------------------------------------------------------------


class TestFormatFromPath:
    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            ("out.html", OutputFormat.HTML),
            ("out.htm", OutputFormat.HTML),
            ("out.docx", OutputFormat.DOCX),
            ("out.pdf", OutputFormat.PDF),
            ("out.md", OutputFormat.MD),
            ("out.markdown", OutputFormat.MD),
            ("out.qmd", OutputFormat.QMD),
            ("OUT.HTML", OutputFormat.HTML),
        ],
    )
    def test_known_extensions(self, path, expected):
        assert format_from_path(path) == expected

    def test_unknown_extension_returns_none(self):
        assert format_from_path("out.txt") is None
        assert format_from_path("out") is None


# ---------------------------------------------------------------------------
# _md_escape
# ---------------------------------------------------------------------------


class TestMarkdownEscaping:
    @pytest.mark.parametrize("char", list("\\`*_[]{}<>|$~#"))
    def test_inline_specials_escaped(self, char):
        assert _md_escape(f"a{char}b") == f"a\\{char}b"

    def test_empty_string_unchanged(self):
        assert _md_escape("") == ""

    def test_plain_text_unchanged(self):
        assert _md_escape("The system shall log in users.") == "The system shall log in users."

    def test_leading_bullet_escaped(self):
        assert _md_escape("- not a list") == "\\- not a list"

    def test_leading_ordered_marker_escaped(self):
        assert _md_escape("1. not a list") == "1\\. not a list"

    def test_pipe_escaped_to_protect_tables(self):
        assert _md_escape("a | b") == "a \\| b"


# ---------------------------------------------------------------------------
# render_qmd
# ---------------------------------------------------------------------------


class TestRenderQmd:
    def _sample(self, **kw):
        items = [
            Item(uid="UN001", text="User need.", document_prefix="UN"),
            Item(uid="SRS001", text="Shall authenticate.", document_prefix="SRS", links=["UN001"]),
            Item(uid="SRS002", text="Overview.", document_prefix="SRS", type="heading", header="Security", level=3),
            Item(uid="SRS003", text="An informational note.", document_prefix="SRS", type="info"),
        ]
        graph = _graph(*items)
        return _doc(items, order=["UN", "SRS"], graph=graph, title="SRS Requirements Document", **kw)

    def test_front_matter_has_title_and_toc(self):
        src = render_qmd(self._sample(), OutputFormat.HTML)
        front = yaml.safe_load(src.split("---", 2)[1])
        assert front["title"] == "SRS Requirements Document"
        assert front["toc"] is True

    def test_html_front_matter_block(self):
        src = render_qmd(self._sample(), OutputFormat.HTML, theme="theme.scss")
        front = yaml.safe_load(src.split("---", 2)[1])
        assert "html" in front["format"]
        assert front["format"]["html"]["theme"] == "theme.scss"
        assert front["format"]["html"]["embed-resources"] is True
        assert "docx" not in front["format"]

    def test_docx_front_matter_uses_reference_doc(self):
        src = render_qmd(self._sample(), OutputFormat.DOCX, reference_doc="reference.docx")
        front = yaml.safe_load(src.split("---", 2)[1])
        assert front["format"]["docx"]["reference-doc"] == "reference.docx"

    def test_pdf_maps_to_typst(self):
        src = render_qmd(self._sample(), OutputFormat.PDF)
        front = yaml.safe_load(src.split("---", 2)[1])
        assert "typst" in front["format"]

    def test_qmd_includes_all_format_blocks(self):
        src = render_qmd(self._sample(), OutputFormat.QMD)
        front = yaml.safe_load(src.split("---", 2)[1])
        assert set(front["format"]) == {"html", "docx", "typst"}

    def test_markdown_has_no_front_matter(self):
        src = render_qmd(self._sample(), OutputFormat.MD)
        assert not src.startswith("---")

    def test_section_anchors_present(self):
        src = render_qmd(self._sample(), OutputFormat.MD)
        assert "# UN {#doc-UN}" in src
        assert "# SRS {#doc-SRS}" in src

    def test_item_anchor_present(self):
        src = render_qmd(self._sample(), OutputFormat.MD)
        assert "## UN001 {#UN001}" in src

    def test_heading_item_uses_its_level(self):
        src = render_qmd(self._sample(), OutputFormat.MD)
        assert "### SRS002: Security {#SRS002}" in src

    def test_heading_level_defaults_to_two(self):
        item = Item(uid="SRS001", text="t", document_prefix="SRS", type="heading", header="H")
        src = render_qmd(_doc([item], order=["SRS"]), OutputFormat.MD)
        assert "## SRS001: H {#SRS001}" in src

    def test_heading_level_clamped_to_six(self):
        item = Item(uid="SRS001", text="t", document_prefix="SRS", type="heading", header="Deep", level=9)
        src = render_qmd(_doc([item], order=["SRS"]), OutputFormat.MD)
        assert "###### SRS001: Deep {#SRS001}" in src
        assert "####### " not in src  # never more than six

    def test_info_item_renders_callout(self):
        src = render_qmd(self._sample(), OutputFormat.MD)
        # The info item is an anchored heading followed by a note callout.
        assert "## SRS003 {#SRS003}" in src
        assert "::: {.callout-note}" in src
        assert "An informational note." in src
        # It is a callout, not the old italic-emphasis rendering.
        assert "*An informational note.*" not in src

    def test_info_callout_uses_heading_when_body_empty(self):
        item = Item(uid="SRS001", text="", document_prefix="SRS", type="info", header="Note")
        src = render_qmd(_doc([item], order=["SRS"]), OutputFormat.MD)
        assert "::: {.callout-note}" in src
        assert "SRS001: Note" in src

    def test_known_link_is_anchored(self):
        src = render_qmd(self._sample(), OutputFormat.MD)
        assert "**Links:** [UN001](#UN001)" in src

    def test_unknown_link_is_literal(self):
        item = Item(uid="SRS001", text="t", document_prefix="SRS", links=["GHOST9"])
        src = render_qmd(_doc([item], order=["SRS"], graph=_graph(item)), OutputFormat.MD)
        assert "**Links:** GHOST9" in src
        assert "[GHOST9]" not in src

    def test_reverse_links_rendered(self):
        src = render_qmd(self._sample(), OutputFormat.MD)
        assert "**Linked from:** [SRS001](#SRS001)" in src

    def test_links_suppressed_when_disabled(self):
        src = render_qmd(self._sample(include_links=False), OutputFormat.MD)
        assert "Links:" not in src
        assert "Linked from:" not in src

    def test_special_chars_escaped_in_body(self):
        item = Item(uid="SRS001", text="Use * and _ and # and | here.", document_prefix="SRS")
        src = render_qmd(_doc([item], order=["SRS"]), OutputFormat.MD)
        assert "\\*" in src and "\\_" in src and "\\#" in src and "\\|" in src

    def test_empty_body_omits_paragraph(self):
        item = Item(uid="SRS001", text="", document_prefix="SRS", header="Title")
        src = render_qmd(_doc([item], order=["SRS"]), OutputFormat.MD)
        assert "## SRS001: Title {#SRS001}" in src


# ---------------------------------------------------------------------------
# find_quarto resolution order
# ---------------------------------------------------------------------------


class TestFindQuarto:
    def test_env_override_used_when_present(self, tmp_path, monkeypatch):
        fake = tmp_path / "quarto"
        fake.write_text("#!/bin/sh\n")
        monkeypatch.setenv("JAMB_QUARTO", str(fake))
        assert find_quarto() == str(fake)

    def test_env_override_missing_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv("JAMB_QUARTO", str(tmp_path / "nope"))
        with pytest.raises(QuartoNotFoundError):
            find_quarto()

    def test_falls_back_to_path(self, tmp_path, monkeypatch):
        monkeypatch.delenv("JAMB_QUARTO", raising=False)
        monkeypatch.setattr("jamb.publish.quarto._bundled_quarto", lambda: None)
        monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/quarto")
        assert find_quarto() == "/usr/local/bin/quarto"

    def test_not_found_raises(self, monkeypatch):
        monkeypatch.delenv("JAMB_QUARTO", raising=False)
        monkeypatch.setattr("jamb.publish.quarto._bundled_quarto", lambda: None)
        monkeypatch.setattr("shutil.which", lambda name: None)
        with pytest.raises(QuartoNotFoundError):
            find_quarto()
