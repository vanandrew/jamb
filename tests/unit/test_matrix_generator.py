"""Tests for jamb.matrix.generator module."""

from unittest.mock import patch

import pytest

from jamb.core.models import (
    Item,
    ItemCoverage,
    LinkedTest,
    TestRecord,
    TraceabilityGraph,
)
from jamb.matrix.generator import (
    build_test_id_mapping,
    build_test_records,
    generate_full_chain_matrix,
    generate_test_records_matrix,
)
from jamb.matrix.utils import infer_format

# ============================================================================
# Coverage Factory Functions
# ============================================================================


def make_coverage(
    *,
    with_tests: bool = False,
    items: list[dict] | None = None,
) -> dict[str, ItemCoverage]:
    """Create coverage data for testing.

    Args:
        with_tests: If True, includes test links covering multiple requirements.
        items: Optional list of item dicts with keys 'uid', 'text', 'links' (list).
               Each item can optionally have a 'tests' key with test link dicts.

    Returns:
        Coverage dict mapping UIDs to ItemCoverage objects.
    """
    if items is not None:
        coverage = {}
        for item_dict in items:
            item = Item(
                uid=item_dict["uid"],
                text=item_dict.get("text", "Test req"),
                document_prefix=item_dict["uid"][:3],
                links=item_dict.get("links", []),
            )
            tests = []
            for test_dict in item_dict.get("tests", []):
                tests.append(
                    LinkedTest(
                        test_nodeid=test_dict["nodeid"],
                        item_uid=item.uid,
                        test_outcome=test_dict.get("outcome", "passed"),
                        test_actions=test_dict.get("actions", []),
                        expected_results=test_dict.get("expected", []),
                    )
                )
            coverage[item.uid] = ItemCoverage(item=item, linked_tests=tests)
        return coverage

    if not with_tests:
        item = Item(uid="SRS001", text="Test req", document_prefix="SRS")
        return {"SRS001": ItemCoverage(item=item)}

    # Default with_tests=True case: two items with overlapping test coverage
    item1 = Item(uid="SRS001", text="Test req 1", document_prefix="SRS")
    item2 = Item(uid="SRS002", text="Test req 2", document_prefix="SRS")
    link1 = LinkedTest(
        test_nodeid="test_foo.py::test_one",
        item_uid="SRS001",
        test_outcome="passed",
        test_actions=["Click button"],
        expected_results=["Button clicked"],
    )
    link2 = LinkedTest(
        test_nodeid="test_foo.py::test_two",
        item_uid="SRS002",
        test_outcome="failed",
    )
    link3 = LinkedTest(
        test_nodeid="test_foo.py::test_one",
        item_uid="SRS002",
        test_outcome="passed",
    )
    return {
        "SRS001": ItemCoverage(item=item1, linked_tests=[link1]),
        "SRS002": ItemCoverage(item=item2, linked_tests=[link2, link3]),
    }


class TestBuildTestRecords:
    """Tests for build_test_records function."""

    def test_empty_coverage_returns_empty_list(self):
        """Empty coverage returns empty list."""
        records = build_test_records({})
        assert records == []

    def test_coverage_without_tests_returns_empty_list(self):
        """Coverage with no linked tests returns empty list."""
        records = build_test_records(make_coverage())
        assert records == []

    def test_builds_records_from_coverage(self):
        """Builds test records from coverage data."""
        records = build_test_records(make_coverage(with_tests=True))
        assert len(records) == 2

    def test_records_have_sequential_tc_ids(self):
        """Records have sequential TC IDs."""
        records = build_test_records(make_coverage(with_tests=True))
        ids = [r.test_id for r in records]
        assert ids == ["TC001", "TC002"]

    def test_records_sorted_by_first_requirement(self):
        """Records are sorted by first requirement UID."""
        records = build_test_records(make_coverage(with_tests=True))
        # test_one covers SRS001 and SRS002, so first req is SRS001
        # test_two covers only SRS002
        # Sorted: test_one (SRS001) comes before test_two (SRS002)
        assert records[0].test_name == "test_one"
        assert records[1].test_name == "test_two"

    def test_records_include_all_requirements(self):
        """Records include all requirements the test covers."""
        records = build_test_records(make_coverage(with_tests=True))
        # test_one covers both SRS001 and SRS002
        one = next(r for r in records if r.test_name == "test_one")
        assert set(one.requirements) == {"SRS001", "SRS002"}

    def test_records_include_test_actions(self):
        """Records include test actions from linked test."""
        records = build_test_records(make_coverage(with_tests=True))
        one = next(r for r in records if r.test_name == "test_one")
        assert one.test_actions == ["Click button"]

    def test_records_include_outcome(self):
        """Records include outcome from linked test."""
        records = build_test_records(make_coverage(with_tests=True))
        one = next(r for r in records if r.test_name == "test_one")
        two = next(r for r in records if r.test_name == "test_two")
        assert one.outcome == "passed"
        assert two.outcome == "failed"


class TestGenerateTestRecordsMatrix:
    """Tests for generate_test_records_matrix function."""

    def test_html_format(self, tmp_path):
        output = tmp_path / "matrix.html"
        records = [
            TestRecord(
                test_id="TC001",
                test_name="test_one",
                test_nodeid="test.py::test_one",
                outcome="passed",
                requirements=["SRS001"],
            )
        ]
        with patch(
            "jamb.matrix.formats.html.render_test_records_html",
            return_value="<html></html>",
        ) as mock:
            generate_test_records_matrix(records, str(output), output_format="html")
        mock.assert_called_once()
        assert output.read_text() == "<html></html>"

    def test_markdown_format(self, tmp_path):
        output = tmp_path / "matrix.md"
        records = []
        with patch(
            "jamb.matrix.formats.markdown.render_test_records_markdown",
            return_value="# Matrix",
        ) as mock:
            generate_test_records_matrix(records, str(output), output_format="markdown")
        mock.assert_called_once()
        assert output.read_text() == "# Matrix"

    def test_json_format(self, tmp_path):
        output = tmp_path / "matrix.json"
        records = []
        with patch(
            "jamb.matrix.formats.json.render_test_records_json",
            return_value='{"tests":[]}',
        ) as mock:
            generate_test_records_matrix(records, str(output), output_format="json")
        mock.assert_called_once()
        assert output.read_text() == '{"tests":[]}'

    def test_csv_format(self, tmp_path):
        output = tmp_path / "matrix.csv"
        records = []
        with patch(
            "jamb.matrix.formats.csv.render_test_records_csv",
            return_value="tc,name\n",
        ) as mock:
            generate_test_records_matrix(records, str(output), output_format="csv")
        mock.assert_called_once()
        assert output.read_text() == "tc,name\n"

    def test_xlsx_format(self, tmp_path):
        output = tmp_path / "matrix.xlsx"
        records = []
        with patch(
            "jamb.matrix.formats.xlsx.render_test_records_xlsx",
            return_value=b"\x00\x01",
        ) as mock:
            generate_test_records_matrix(records, str(output), output_format="xlsx")
        mock.assert_called_once()
        assert output.read_bytes() == b"\x00\x01"

    def test_unknown_format_raises(self, tmp_path):
        output = tmp_path / "matrix.txt"
        with pytest.raises(ValueError, match="Unknown format: txt"):
            generate_test_records_matrix([], str(output), output_format="txt")

    def test_creates_parent_directories(self, tmp_path):
        output = tmp_path / "subdir" / "nested" / "matrix.html"
        with patch("jamb.matrix.formats.html.render_test_records_html", return_value="<html/>"):
            generate_test_records_matrix([], str(output), output_format="html")
        assert output.exists()


class TestGenerateFullChainMatrix:
    """Tests for generate_full_chain_matrix function."""

    def _make_graph_and_coverage(self):
        """Create a graph and coverage for testing."""
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])
        graph.set_document_parents("SYS", [])

        sys_item = Item(uid="SYS001", text="System req", document_prefix="SYS")
        srs_item = Item(uid="SRS001", text="Software req", document_prefix="SRS", links=["SYS001"])
        graph.add_item(sys_item)
        graph.add_item(srs_item)

        link = LinkedTest(
            test_nodeid="test.py::test_req",
            item_uid="SRS001",
            test_outcome="passed",
        )
        coverage = {
            "SRS001": ItemCoverage(item=srs_item, linked_tests=[link]),
        }
        return graph, coverage

    def test_html_format(self, tmp_path):
        """Test generating full chain matrix in HTML format."""

        graph, coverage = self._make_graph_and_coverage()
        output = tmp_path / "matrix.html"

        with patch(
            "jamb.matrix.formats.html.render_full_chain_html",
            return_value="<html>full chain</html>",
        ) as mock:
            generate_full_chain_matrix(coverage, graph, str(output), output_format="html", trace_from="SYS")

        mock.assert_called_once()
        assert output.read_text() == "<html>full chain</html>"

    def test_markdown_format(self, tmp_path):
        """Test generating full chain matrix in Markdown format."""

        graph, coverage = self._make_graph_and_coverage()
        output = tmp_path / "matrix.md"

        with patch(
            "jamb.matrix.formats.markdown.render_full_chain_markdown",
            return_value="# Full Chain",
        ) as mock:
            generate_full_chain_matrix(coverage, graph, str(output), output_format="markdown", trace_from="SYS")

        mock.assert_called_once()
        assert output.read_text() == "# Full Chain"

    def test_json_format(self, tmp_path):
        """Test generating full chain matrix in JSON format."""

        graph, coverage = self._make_graph_and_coverage()
        output = tmp_path / "matrix.json"

        with patch(
            "jamb.matrix.formats.json.render_full_chain_json",
            return_value='{"matrices":[]}',
        ) as mock:
            generate_full_chain_matrix(coverage, graph, str(output), output_format="json", trace_from="SYS")

        mock.assert_called_once()
        assert output.read_text() == '{"matrices":[]}'

    def test_csv_format(self, tmp_path):
        """Test generating full chain matrix in CSV format."""

        graph, coverage = self._make_graph_and_coverage()
        output = tmp_path / "matrix.csv"

        with patch(
            "jamb.matrix.formats.csv.render_full_chain_csv",
            return_value="path,status\n",
        ) as mock:
            generate_full_chain_matrix(coverage, graph, str(output), output_format="csv", trace_from="SYS")

        mock.assert_called_once()
        assert output.read_text() == "path,status\n"

    def test_xlsx_format(self, tmp_path):
        """Test generating full chain matrix in XLSX format."""

        graph, coverage = self._make_graph_and_coverage()
        output = tmp_path / "matrix.xlsx"

        with patch(
            "jamb.matrix.formats.xlsx.render_full_chain_xlsx",
            return_value=b"\x00\x01\x02",
        ) as mock:
            generate_full_chain_matrix(coverage, graph, str(output), output_format="xlsx", trace_from="SYS")

        mock.assert_called_once()
        assert output.read_bytes() == b"\x00\x01\x02"

    def test_unknown_format_raises(self, tmp_path):
        """Test that unknown format raises ValueError."""

        graph, coverage = self._make_graph_and_coverage()
        output = tmp_path / "matrix.txt"

        with pytest.raises(ValueError, match="Unknown format: txt"):
            generate_full_chain_matrix(coverage, graph, str(output), output_format="txt", trace_from="SYS")

    def test_creates_parent_directories(self, tmp_path):
        """Test that parent directories are created."""

        graph, coverage = self._make_graph_and_coverage()
        output = tmp_path / "subdir" / "nested" / "matrix.html"

        with patch(
            "jamb.matrix.formats.html.render_full_chain_html",
            return_value="<html/>",
        ):
            generate_full_chain_matrix(coverage, graph, str(output), output_format="html", trace_from="SYS")

        assert output.exists()

    def test_include_ancestors_passed_to_builder(self, tmp_path):
        """Test that include_ancestors flag is passed to chain builder."""

        graph, coverage = self._make_graph_and_coverage()
        output = tmp_path / "matrix.html"

        with (
            patch("jamb.matrix.chain_builder.build_full_chain_matrix") as mock_builder,
            patch(
                "jamb.matrix.formats.html.render_full_chain_html",
                return_value="<html/>",
            ),
        ):
            mock_builder.return_value = []
            generate_full_chain_matrix(
                coverage,
                graph,
                str(output),
                output_format="html",
                trace_from="SYS",
                include_ancestors=True,
            )

        mock_builder.assert_called_once()
        call_kwargs = mock_builder.call_args
        assert call_kwargs[1]["include_ancestors"] is True

    def test_tc_mapping_passed_to_renderer(self, tmp_path):
        """Test that tc_mapping is passed to renderer."""

        graph, coverage = self._make_graph_and_coverage()
        output = tmp_path / "matrix.html"
        tc_mapping = {"test.py::test_req": "TC001"}

        with patch(
            "jamb.matrix.formats.html.render_full_chain_html",
            return_value="<html/>",
        ) as mock:
            generate_full_chain_matrix(
                coverage,
                graph,
                str(output),
                output_format="html",
                trace_from="SYS",
                tc_mapping=tc_mapping,
            )

        # Formatter is called with positional args: (matrices, tc_mapping)
        args, _ = mock.call_args
        assert args[1] == tc_mapping

    def test_builds_tc_mapping_when_not_provided(self, tmp_path):
        """Test that TC mapping is built when not provided."""

        graph, coverage = self._make_graph_and_coverage()
        output = tmp_path / "matrix.html"

        with patch(
            "jamb.matrix.formats.html.render_full_chain_html",
            return_value="<html/>",
        ) as mock:
            generate_full_chain_matrix(
                coverage,
                graph,
                str(output),
                output_format="html",
                trace_from="SYS",
            )

        # Formatter is called with positional args: (matrices, tc_mapping)
        args, _ = mock.call_args
        # TC mapping should have been built automatically
        assert args[1] == {"test.py::test_req": "TC001"}


class TestInferFormat:
    """Tests for infer_format utility function."""

    def test_html_extension(self):
        """Test .html extension."""
        assert infer_format("matrix.html") == "html"

    def test_htm_extension(self):
        """Test .htm extension."""
        assert infer_format("matrix.htm") == "html"

    def test_json_extension(self):
        """Test .json extension."""
        assert infer_format("output.json") == "json"

    def test_csv_extension(self):
        """Test .csv extension."""
        assert infer_format("data.csv") == "csv"

    def test_markdown_extension(self):
        """Test .md extension."""
        assert infer_format("readme.md") == "markdown"

    def test_xlsx_extension(self):
        """Test .xlsx extension."""
        assert infer_format("workbook.xlsx") == "xlsx"

    def test_case_insensitive(self):
        """Test that extension matching is case insensitive."""
        assert infer_format("MATRIX.HTML") == "html"
        assert infer_format("Matrix.Json") == "json"

    def test_unrecognized_extension_raises(self):
        """Test that unrecognized extension raises ValueError."""
        with pytest.raises(ValueError, match="Unrecognized file extension"):
            infer_format("file.xyz")

    def test_no_extension_raises(self):
        """Test that file without extension raises ValueError."""
        with pytest.raises(ValueError, match="Unrecognized file extension"):
            infer_format("noextension")


class TestBuildTestIdMapping:
    """Tests for build_test_id_mapping function."""

    def test_empty_coverage_returns_empty_dict(self):
        """Test that empty coverage returns empty dict."""
        result = build_test_id_mapping({})
        assert result == {}

    def test_builds_sequential_ids(self):
        """Test that TC IDs are assigned sequentially."""
        coverage = make_coverage(with_tests=True)
        result = build_test_id_mapping(coverage)

        # Should have 2 tests with TC001 and TC002
        assert len(result) == 2
        assert "TC001" in result.values()
        assert "TC002" in result.values()

    def test_nodeid_to_tc_mapping(self):
        """Test that mapping is from nodeid to TC ID."""
        item = Item(uid="SRS001", text="Req", document_prefix="SRS")
        link = LinkedTest(
            test_nodeid="test.py::test_foo",
            item_uid="SRS001",
            test_outcome="passed",
        )
        coverage = {"SRS001": ItemCoverage(item=item, linked_tests=[link])}

        result = build_test_id_mapping(coverage)

        assert "test.py::test_foo" in result
        assert result["test.py::test_foo"] == "TC001"
