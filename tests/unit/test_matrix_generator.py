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
    _extract_reserved_numbers,
    _get_base_nodeid,
    _group_nodeids_by_base,
    _num_to_suffix,
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


class TestGetBaseNodeid:
    """Tests for _get_base_nodeid helper function."""

    def test_strips_parameter_suffix(self):
        """Test that parameter suffix is stripped from nodeid."""
        result = _get_base_nodeid("test.py::test_foo[param]")
        assert result == "test.py::test_foo"

    def test_no_parameters_unchanged(self):
        """Test that nodeid without parameters is unchanged."""
        result = _get_base_nodeid("test.py::test_foo")
        assert result == "test.py::test_foo"

    def test_nested_brackets_uses_first(self):
        """Test that only the first bracket index is used."""
        result = _get_base_nodeid("test.py::test_foo[a][b]")
        assert result == "test.py::test_foo"

    def test_empty_parameters(self):
        """Test nodeid with empty parameter brackets."""
        result = _get_base_nodeid("test.py::test_foo[]")
        assert result == "test.py::test_foo"

    def test_complex_parameters(self):
        """Test nodeid with complex parameters."""
        result = _get_base_nodeid("test.py::test_foo[param1-param2-True]")
        assert result == "test.py::test_foo"


class TestNumToSuffix:
    """Tests for _num_to_suffix helper function."""

    def test_zero_returns_a(self):
        """Test that 0 returns 'a'."""
        assert _num_to_suffix(0) == "a"

    def test_25_returns_z(self):
        """Test that 25 returns 'z'."""
        assert _num_to_suffix(25) == "z"

    def test_26_returns_aa(self):
        """Test that 26 returns 'aa'."""
        assert _num_to_suffix(26) == "aa"

    def test_27_returns_ab(self):
        """Test that 27 returns 'ab'."""
        assert _num_to_suffix(27) == "ab"

    def test_51_returns_az(self):
        """Test that 51 returns 'az'."""
        assert _num_to_suffix(51) == "az"

    def test_52_returns_ba(self):
        """Test that 52 returns 'ba'."""
        assert _num_to_suffix(52) == "ba"


class TestExtractReservedNumbers:
    """Tests for _extract_reserved_numbers helper function."""

    def test_extracts_tc_pattern_numbers(self):
        """Test that TC pattern numbers are extracted."""
        manual_tc_ids = {"test::foo": "TC001", "test::bar": "TC042"}
        result = _extract_reserved_numbers(manual_tc_ids)
        assert result == {1, 42}

    def test_ignores_non_matching_patterns(self):
        """Test that non-matching patterns are ignored."""
        manual_tc_ids = {"test::foo": "TC-AUTH-001", "test::bar": "CUSTOM123"}
        result = _extract_reserved_numbers(manual_tc_ids)
        assert result == set()

    def test_empty_dict_returns_empty_set(self):
        """Test that empty dict returns empty set."""
        assert _extract_reserved_numbers({}) == set()

    def test_ignores_suffixed_ids(self):
        """Test that TC IDs with suffixes are ignored."""
        manual_tc_ids = {"test::foo": "TC001a", "test::bar": "TC002b"}
        result = _extract_reserved_numbers(manual_tc_ids)
        assert result == set()

    def test_extracts_large_numbers(self):
        """Test that large TC numbers are extracted."""
        manual_tc_ids = {"test::foo": "TC999", "test::bar": "TC1234"}
        result = _extract_reserved_numbers(manual_tc_ids)
        assert result == {999, 1234}


class TestGroupNodeidsByBase:
    """Tests for _group_nodeids_by_base helper function."""

    def test_groups_parameterized_tests(self):
        """Test that parameterized tests are grouped by base nodeid."""
        nodeids = ["t.py::test[1]", "t.py::test[2]"]
        result = _group_nodeids_by_base(nodeids)
        assert result == {"t.py::test": ["t.py::test[1]", "t.py::test[2]"]}

    def test_single_test_own_group(self):
        """Test that single non-parameterized test is in its own group."""
        nodeids = ["t.py::test_foo"]
        result = _group_nodeids_by_base(nodeids)
        assert result == {"t.py::test_foo": ["t.py::test_foo"]}

    def test_mixed_parameterized_and_single(self):
        """Test mixing parameterized and single tests."""
        nodeids = ["t.py::test_a[1]", "t.py::test_a[2]", "t.py::test_b"]
        result = _group_nodeids_by_base(nodeids)
        assert result == {
            "t.py::test_a": ["t.py::test_a[1]", "t.py::test_a[2]"],
            "t.py::test_b": ["t.py::test_b"],
        }

    def test_empty_list_returns_empty_dict(self):
        """Test that empty list returns empty dict."""
        result = _group_nodeids_by_base([])
        assert result == {}

    def test_preserves_order_within_groups(self):
        """Test that order is preserved within groups."""
        nodeids = ["t.py::test[c]", "t.py::test[a]", "t.py::test[b]"]
        result = _group_nodeids_by_base(nodeids)
        assert result["t.py::test"] == ["t.py::test[c]", "t.py::test[a]", "t.py::test[b]"]


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

    def test_manual_tc_id_takes_precedence(self):
        """Manual TC ID overrides auto-generation."""
        item = Item(uid="SRS001", text="Req", document_prefix="SRS")
        link = LinkedTest(
            test_nodeid="test.py::test_foo",
            item_uid="SRS001",
            test_outcome="passed",
        )
        coverage = {"SRS001": ItemCoverage(item=item, linked_tests=[link])}

        manual_tc_ids = {"test.py::test_foo": "TC-CUSTOM"}
        result = build_test_id_mapping(coverage, manual_tc_ids)

        assert result["test.py::test_foo"] == "TC-CUSTOM"

    def test_reserved_numbers_skipped(self):
        """Auto-numbering skips reserved TC numbers."""
        item = Item(uid="SRS001", text="Req", document_prefix="SRS")
        link1 = LinkedTest(
            test_nodeid="test.py::test_a",
            item_uid="SRS001",
            test_outcome="passed",
        )
        link2 = LinkedTest(
            test_nodeid="test.py::test_b",
            item_uid="SRS001",
            test_outcome="passed",
        )
        coverage = {"SRS001": ItemCoverage(item=item, linked_tests=[link1, link2])}

        # TC001 is reserved by manual ID
        manual_tc_ids = {"test.py::test_a": "TC001"}
        result = build_test_id_mapping(coverage, manual_tc_ids)

        assert result["test.py::test_a"] == "TC001"
        # test_b should get TC002 (skipping reserved TC001)
        assert result["test.py::test_b"] == "TC002"

    def test_parameterized_gets_suffixes(self):
        """Parameterized tests get alphabetic suffixes."""
        item = Item(uid="SRS001", text="Req", document_prefix="SRS")
        link1 = LinkedTest(
            test_nodeid="test.py::test_foo[1]",
            item_uid="SRS001",
            test_outcome="passed",
        )
        link2 = LinkedTest(
            test_nodeid="test.py::test_foo[2]",
            item_uid="SRS001",
            test_outcome="passed",
        )
        link3 = LinkedTest(
            test_nodeid="test.py::test_foo[3]",
            item_uid="SRS001",
            test_outcome="passed",
        )
        coverage = {"SRS001": ItemCoverage(item=item, linked_tests=[link1, link2, link3])}

        result = build_test_id_mapping(coverage)

        assert result["test.py::test_foo[1]"] == "TC001a"
        assert result["test.py::test_foo[2]"] == "TC001b"
        assert result["test.py::test_foo[3]"] == "TC001c"

    def test_single_test_no_suffix(self):
        """Non-parameterized tests have no suffix."""
        item = Item(uid="SRS001", text="Req", document_prefix="SRS")
        link = LinkedTest(
            test_nodeid="test.py::test_foo",
            item_uid="SRS001",
            test_outcome="passed",
        )
        coverage = {"SRS001": ItemCoverage(item=item, linked_tests=[link])}

        result = build_test_id_mapping(coverage)

        assert result["test.py::test_foo"] == "TC001"
        # Verify no suffix is present
        assert not result["test.py::test_foo"].endswith("a")

    def test_manual_id_on_parameterized_test(self):
        """Manual ID applied to all parameter variations with suffixes."""
        item = Item(uid="SRS001", text="Req", document_prefix="SRS")
        link1 = LinkedTest(
            test_nodeid="test.py::test_foo[1]",
            item_uid="SRS001",
            test_outcome="passed",
        )
        link2 = LinkedTest(
            test_nodeid="test.py::test_foo[2]",
            item_uid="SRS001",
            test_outcome="passed",
        )
        coverage = {"SRS001": ItemCoverage(item=item, linked_tests=[link1, link2])}

        # Manual ID for base nodeid
        manual_tc_ids = {"test.py::test_foo[1]": "TC-AUTH"}
        result = build_test_id_mapping(coverage, manual_tc_ids)

        assert result["test.py::test_foo[1]"] == "TC-AUTHa"
        assert result["test.py::test_foo[2]"] == "TC-AUTHb"

    def test_none_manual_ids_same_as_empty(self):
        """None and {} for manual_tc_ids behave the same."""
        item = Item(uid="SRS001", text="Req", document_prefix="SRS")
        link = LinkedTest(
            test_nodeid="test.py::test_foo",
            item_uid="SRS001",
            test_outcome="passed",
        )
        coverage = {"SRS001": ItemCoverage(item=item, linked_tests=[link])}

        result_none = build_test_id_mapping(coverage, None)
        result_empty = build_test_id_mapping(coverage, {})

        assert result_none == result_empty
        assert result_none["test.py::test_foo"] == "TC001"

    def test_skips_multiple_reserved_numbers(self):
        """Auto-numbering skips multiple consecutive reserved numbers."""
        item = Item(uid="SRS001", text="Req", document_prefix="SRS")
        link1 = LinkedTest(
            test_nodeid="test.py::test_a",
            item_uid="SRS001",
            test_outcome="passed",
        )
        link2 = LinkedTest(
            test_nodeid="test.py::test_b",
            item_uid="SRS001",
            test_outcome="passed",
        )
        coverage = {"SRS001": ItemCoverage(item=item, linked_tests=[link1, link2])}

        # Reserve TC001 and TC002 via manual IDs
        manual_tc_ids = {"test.py::test_a": "TC001", "other.py::other": "TC002"}
        result = build_test_id_mapping(coverage, manual_tc_ids)

        assert result["test.py::test_a"] == "TC001"
        # test_b should get TC003 (skipping both TC001 and TC002)
        assert result["test.py::test_b"] == "TC003"


class TestBuildTestIdMappingWithPrefix:
    """Tests for build_test_id_mapping with custom tc_id_prefix."""

    def test_custom_prefix_applied(self):
        """Test that custom prefix is applied to auto-generated IDs."""
        item = Item(uid="SRS001", text="Req", document_prefix="SRS")
        link = LinkedTest(
            test_nodeid="test.py::test_foo",
            item_uid="SRS001",
            test_outcome="passed",
        )
        coverage = {"SRS001": ItemCoverage(item=item, linked_tests=[link])}

        result = build_test_id_mapping(coverage, None, tc_id_prefix="TEST-")

        assert result["test.py::test_foo"] == "TEST-001"

    def test_custom_prefix_with_hyphen(self):
        """Test that hyphenated prefix works correctly."""
        item = Item(uid="SRS001", text="Req", document_prefix="SRS")
        link1 = LinkedTest(
            test_nodeid="test.py::test_a",
            item_uid="SRS001",
            test_outcome="passed",
        )
        link2 = LinkedTest(
            test_nodeid="test.py::test_b",
            item_uid="SRS001",
            test_outcome="passed",
        )
        coverage = {"SRS001": ItemCoverage(item=item, linked_tests=[link1, link2])}

        result = build_test_id_mapping(coverage, None, tc_id_prefix="PROJ-TC-")

        assert "PROJ-TC-001" in result.values()
        assert "PROJ-TC-002" in result.values()

    def test_custom_prefix_with_parameterized(self):
        """Test that custom prefix works with parameterized tests."""
        item = Item(uid="SRS001", text="Req", document_prefix="SRS")
        link1 = LinkedTest(
            test_nodeid="test.py::test_foo[1]",
            item_uid="SRS001",
            test_outcome="passed",
        )
        link2 = LinkedTest(
            test_nodeid="test.py::test_foo[2]",
            item_uid="SRS001",
            test_outcome="passed",
        )
        coverage = {"SRS001": ItemCoverage(item=item, linked_tests=[link1, link2])}

        result = build_test_id_mapping(coverage, None, tc_id_prefix="UNIT-")

        assert result["test.py::test_foo[1]"] == "UNIT-001a"
        assert result["test.py::test_foo[2]"] == "UNIT-001b"

    def test_reserved_numbers_with_custom_prefix(self):
        """Test that reserved numbers work with custom prefix matching."""
        item = Item(uid="SRS001", text="Req", document_prefix="SRS")
        link1 = LinkedTest(
            test_nodeid="test.py::test_a",
            item_uid="SRS001",
            test_outcome="passed",
        )
        link2 = LinkedTest(
            test_nodeid="test.py::test_b",
            item_uid="SRS001",
            test_outcome="passed",
        )
        coverage = {"SRS001": ItemCoverage(item=item, linked_tests=[link1, link2])}

        # Manual ID with same prefix reserves that number
        manual_tc_ids = {"test.py::test_a": "TEST001"}
        result = build_test_id_mapping(coverage, manual_tc_ids, tc_id_prefix="TEST")

        assert result["test.py::test_a"] == "TEST001"
        # test_b should get TEST002 (skipping reserved TEST001)
        assert result["test.py::test_b"] == "TEST002"

    def test_different_prefix_doesnt_reserve(self):
        """Test that manual IDs with different prefix don't reserve numbers."""
        item = Item(uid="SRS001", text="Req", document_prefix="SRS")
        link1 = LinkedTest(
            test_nodeid="test.py::test_a",
            item_uid="SRS001",
            test_outcome="passed",
        )
        link2 = LinkedTest(
            test_nodeid="test.py::test_b",
            item_uid="SRS001",
            test_outcome="passed",
        )
        coverage = {"SRS001": ItemCoverage(item=item, linked_tests=[link1, link2])}

        # Manual ID with TC prefix shouldn't reserve when using TEST prefix
        manual_tc_ids = {"test.py::test_a": "TC001"}
        result = build_test_id_mapping(coverage, manual_tc_ids, tc_id_prefix="TEST")

        # test_a keeps its manual ID
        assert result["test.py::test_a"] == "TC001"
        # test_b should get TEST001 since TC001 doesn't match TEST pattern
        assert result["test.py::test_b"] == "TEST001"

    def test_default_prefix_is_tc(self):
        """Test that default prefix is 'TC' when not specified."""
        item = Item(uid="SRS001", text="Req", document_prefix="SRS")
        link = LinkedTest(
            test_nodeid="test.py::test_foo",
            item_uid="SRS001",
            test_outcome="passed",
        )
        coverage = {"SRS001": ItemCoverage(item=item, linked_tests=[link])}

        result = build_test_id_mapping(coverage)

        assert result["test.py::test_foo"] == "TC001"
