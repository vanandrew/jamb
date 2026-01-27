"""Tests for jamb.matrix.generator module."""

from unittest.mock import patch

import pytest

from jamb.core.models import Item, ItemCoverage, TraceabilityGraph
from jamb.matrix.generator import generate_matrix


def _make_coverage():
    """Create minimal coverage data for testing."""
    item = Item(uid="SRS001", text="Test req", document_prefix="SRS")
    return {"SRS001": ItemCoverage(item=item)}


class TestGenerateMatrix:
    def test_html_format(self, tmp_path):
        output = tmp_path / "matrix.html"
        with patch(
            "jamb.matrix.formats.html.render_html", return_value="<html></html>"
        ) as mock:
            generate_matrix(_make_coverage(), None, str(output), format="html")
        mock.assert_called_once()
        assert output.read_text() == "<html></html>"

    def test_markdown_format(self, tmp_path):
        output = tmp_path / "matrix.md"
        with patch(
            "jamb.matrix.formats.markdown.render_markdown", return_value="# Matrix"
        ) as mock:
            generate_matrix(_make_coverage(), None, str(output), format="markdown")
        mock.assert_called_once()
        assert output.read_text() == "# Matrix"

    def test_json_format(self, tmp_path):
        output = tmp_path / "matrix.json"
        with patch(
            "jamb.matrix.formats.json.render_json", return_value='{"items":[]}'
        ) as mock:
            generate_matrix(_make_coverage(), None, str(output), format="json")
        mock.assert_called_once()
        assert output.read_text() == '{"items":[]}'

    def test_csv_format(self, tmp_path):
        output = tmp_path / "matrix.csv"
        with patch(
            "jamb.matrix.formats.csv.render_csv", return_value="uid,text\n"
        ) as mock:
            generate_matrix(_make_coverage(), None, str(output), format="csv")
        mock.assert_called_once()
        assert output.read_text() == "uid,text\n"

    def test_xlsx_format(self, tmp_path):
        output = tmp_path / "matrix.xlsx"
        with patch(
            "jamb.matrix.formats.xlsx.render_xlsx", return_value=b"\x00\x01"
        ) as mock:
            generate_matrix(_make_coverage(), None, str(output), format="xlsx")
        mock.assert_called_once()
        assert output.read_bytes() == b"\x00\x01"

    def test_unknown_format_raises(self, tmp_path):
        output = tmp_path / "matrix.txt"
        with pytest.raises(ValueError, match="Unknown format: txt"):
            generate_matrix(_make_coverage(), None, str(output), format="txt")

    def test_creates_parent_directories(self, tmp_path):
        output = tmp_path / "subdir" / "nested" / "matrix.html"
        with patch("jamb.matrix.formats.html.render_html", return_value="<html/>"):
            generate_matrix(_make_coverage(), None, str(output), format="html")
        assert output.exists()

    def test_trace_to_ignore_passed_to_renderer(self, tmp_path):
        output = tmp_path / "matrix.html"
        ignore = {"SRS"}
        with patch(
            "jamb.matrix.formats.html.render_html", return_value="<html/>"
        ) as mock:
            generate_matrix(
                _make_coverage(),
                None,
                str(output),
                format="html",
                trace_to_ignore=ignore,
            )
        _, kwargs = mock.call_args
        assert kwargs["trace_to_ignore"] == ignore

    def test_trace_to_ignore_defaults_to_frozenset(self, tmp_path):
        output = tmp_path / "matrix.html"
        with patch(
            "jamb.matrix.formats.html.render_html", return_value="<html/>"
        ) as mock:
            generate_matrix(
                _make_coverage(), None, str(output), format="html", trace_to_ignore=None
            )
        _, kwargs = mock.call_args
        assert kwargs["trace_to_ignore"] == frozenset()

    def test_graph_passed_to_renderer(self, tmp_path):
        output = tmp_path / "matrix.html"
        graph = TraceabilityGraph()
        with patch(
            "jamb.matrix.formats.html.render_html", return_value="<html/>"
        ) as mock:
            generate_matrix(_make_coverage(), graph, str(output), format="html")
        args, _ = mock.call_args
        assert args[1] is graph

    def test_empty_coverage_dict(self, tmp_path):
        """generate_matrix({}, ...) still creates output."""
        output = tmp_path / "matrix.html"
        with patch(
            "jamb.matrix.formats.html.render_html", return_value="<empty/>"
        ) as mock:
            generate_matrix({}, None, str(output), format="html")
        mock.assert_called_once()
        assert output.read_text() == "<empty/>"

    def test_deeply_nested_output_path(self, tmp_path):
        """a/b/c/d/matrix.html creates all parents."""
        output = tmp_path / "a" / "b" / "c" / "d" / "matrix.html"
        with patch("jamb.matrix.formats.html.render_html", return_value="<html/>"):
            generate_matrix(_make_coverage(), None, str(output), format="html")
        assert output.exists()

    def test_overwrite_existing_file(self, tmp_path):
        """Writes new content over old file."""
        output = tmp_path / "matrix.html"
        output.write_text("old content")
        with patch("jamb.matrix.formats.html.render_html", return_value="new content"):
            generate_matrix(_make_coverage(), None, str(output), format="html")
        assert output.read_text() == "new content"

    def test_empty_string_format_raises(self, tmp_path):
        """format='' raises ValueError."""
        output = tmp_path / "matrix.txt"
        with pytest.raises(ValueError, match="Unknown format: "):
            generate_matrix(_make_coverage(), None, str(output), format="")
