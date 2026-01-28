"""Tests for jamb.matrix.formats module."""

import csv
import io
import json

import pytest
from openpyxl import load_workbook

from jamb.core.models import Item, ItemCoverage, LinkedTest, TraceabilityGraph
from jamb.matrix.formats.csv import render_csv
from jamb.matrix.formats.html import render_html
from jamb.matrix.formats.json import render_json
from jamb.matrix.formats.markdown import render_markdown
from jamb.matrix.formats.xlsx import render_xlsx


@pytest.fixture
def sample_coverage():
    """Sample coverage data for testing renderers."""
    item = Item(
        uid="SRS001",
        text="Software shall validate credentials",
        document_prefix="SRS",
        links=["SYS001"],
    )
    link = LinkedTest(
        test_nodeid="test_auth.py::test_valid",
        item_uid="SRS001",
        test_outcome="passed",
    )
    return {"SRS001": ItemCoverage(item=item, linked_tests=[link])}


@pytest.fixture
def sample_graph():
    """Sample graph for testing renderers."""
    graph = TraceabilityGraph()
    sys_item = Item(uid="SYS001", text="System req", document_prefix="SYS")
    graph.add_item(sys_item)
    graph.set_document_parent("SRS", "SYS")
    graph.set_document_parent("SYS", None)
    return graph


@pytest.fixture
def uncovered_coverage():
    """Coverage data with uncovered item."""
    item = Item(
        uid="SRS002",
        text="Uncovered requirement",
        document_prefix="SRS",
    )
    return {"SRS002": ItemCoverage(item=item, linked_tests=[])}


@pytest.fixture
def failed_coverage():
    """Coverage data with failed test."""
    item = Item(
        uid="SRS003",
        text="Failed requirement",
        document_prefix="SRS",
    )
    link = LinkedTest(
        test_nodeid="test_fail.py::test_bad",
        item_uid="SRS003",
        test_outcome="failed",
    )
    return {"SRS003": ItemCoverage(item=item, linked_tests=[link])}


@pytest.fixture
def coverage_with_messages():
    """Coverage data with test notes."""
    item = Item(
        uid="SRS004",
        text="Requirement with messages",
        document_prefix="SRS",
    )
    link = LinkedTest(
        test_nodeid="test_msg.py::test_with_messages",
        item_uid="SRS004",
        test_outcome="passed",
        notes=["Custom verification message", "Second test note"],
        test_actions=["Entered valid data", "Clicked submit"],
        expected_results=["Form accepted", "Success page shown"],
    )
    return {"SRS004": ItemCoverage(item=item, linked_tests=[link])}


@pytest.fixture
def coverage_with_failure_message():
    """Coverage data with failure message."""
    item = Item(
        uid="SRS005",
        text="Requirement with failure",
        document_prefix="SRS",
    )
    link = LinkedTest(
        test_nodeid="test_fail.py::test_assertion",
        item_uid="SRS005",
        test_outcome="failed",
        notes=["[FAILURE] AssertionError: expected 1, got 2"],
    )
    return {"SRS005": ItemCoverage(item=item, linked_tests=[link])}


class TestRenderHtml:
    """Tests for HTML renderer."""

    def test_renders_basic_structure(self, sample_coverage, sample_graph):
        """Test that HTML output has basic structure."""
        html = render_html(sample_coverage, sample_graph)

        assert "<html" in html
        assert "<table" in html
        assert "</html>" in html

    def test_contains_charset_meta_tag(self, sample_coverage, sample_graph):
        """Test that HTML output declares UTF-8 charset."""
        html = render_html(sample_coverage, sample_graph)

        assert '<meta charset="utf-8">' in html

    def test_contains_item_uid(self, sample_coverage, sample_graph):
        """Test that HTML contains item UID."""
        html = render_html(sample_coverage, sample_graph)

        assert "SRS001" in html

    def test_passed_status_class(self, sample_coverage, sample_graph):
        """Test that passed items have correct CSS class."""
        html = render_html(sample_coverage, sample_graph)

        assert "passed" in html.lower()

    def test_uncovered_status_class(self, uncovered_coverage, sample_graph):
        """Test that uncovered items have correct CSS class."""
        html = render_html(uncovered_coverage, sample_graph)

        assert "uncovered" in html.lower()

    def test_failed_status_class(self, failed_coverage, sample_graph):
        """Test that failed items have correct CSS class."""
        html = render_html(failed_coverage, sample_graph)

        assert "failed" in html.lower()

    def test_escapes_html_in_text(self, sample_graph):
        """Test that HTML special characters are escaped."""
        item = Item(
            uid="SRS001",
            text="Test <script>alert('xss')</script>",
            document_prefix="SRS",
        )
        coverage = {"SRS001": ItemCoverage(item=item, linked_tests=[])}

        html = render_html(coverage, sample_graph)

        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_contains_test_name(self, sample_coverage, sample_graph):
        """Test that HTML contains test name."""
        html = render_html(sample_coverage, sample_graph)

        # HTML uses abbreviated test names (just the function name)
        assert "test_valid" in html


class TestRenderMarkdown:
    """Tests for Markdown renderer."""

    def test_renders_table_structure(self, sample_coverage, sample_graph):
        """Test that Markdown output has table structure."""
        md = render_markdown(sample_coverage, sample_graph)

        assert "|" in md
        assert "---" in md  # Table header separator

    def test_contains_item_uid(self, sample_coverage, sample_graph):
        """Test that Markdown contains item UID."""
        md = render_markdown(sample_coverage, sample_graph)

        assert "SRS001" in md

    def test_contains_status(self, sample_coverage, sample_graph):
        """Test that Markdown contains status."""
        md = render_markdown(sample_coverage, sample_graph)

        assert "Passed" in md

    def test_uncovered_status(self, uncovered_coverage, sample_graph):
        """Test that uncovered items show Not Covered status."""
        md = render_markdown(uncovered_coverage, sample_graph)

        assert "Not Covered" in md

    def test_escapes_pipes_in_description(self, sample_graph):
        """Test that pipe characters are escaped in Markdown."""
        item = Item(
            uid="SRS001",
            text="Test with | pipe character",
            document_prefix="SRS",
        )
        coverage = {"SRS001": ItemCoverage(item=item, linked_tests=[])}

        md = render_markdown(coverage, sample_graph)

        # Pipe in text should be escaped to \|
        assert "\\|" in md


class TestRenderJson:
    """Tests for JSON renderer."""

    def test_renders_valid_json(self, sample_coverage, sample_graph):
        """Test that output is valid JSON."""
        json_str = render_json(sample_coverage, sample_graph)

        # Should not raise
        data = json.loads(json_str)
        assert isinstance(data, dict)

    def test_contains_items_key(self, sample_coverage, sample_graph):
        """Test that JSON has items key."""
        json_str = render_json(sample_coverage, sample_graph)
        data = json.loads(json_str)

        assert "items" in data

    def test_contains_summary_key(self, sample_coverage, sample_graph):
        """Test that JSON has summary key."""
        json_str = render_json(sample_coverage, sample_graph)
        data = json.loads(json_str)

        assert "summary" in data

    def test_item_structure(self, sample_coverage, sample_graph):
        """Test that items have expected structure."""
        json_str = render_json(sample_coverage, sample_graph)
        data = json.loads(json_str)

        # items is a dict keyed by UID
        item = data["items"]["SRS001"]
        assert "uid" in item
        assert "text" in item
        assert "is_covered" in item
        assert "linked_tests" in item

    def test_summary_statistics(self, sample_coverage, sample_graph):
        """Test that summary has statistics."""
        json_str = render_json(sample_coverage, sample_graph)
        data = json.loads(json_str)

        summary = data["summary"]
        assert "total_items" in summary
        assert "covered" in summary
        assert "all_tests_passing" in summary

    def test_empty_coverage(self, sample_graph):
        """Test rendering with empty coverage."""
        json_str = render_json({}, sample_graph)
        data = json.loads(json_str)

        assert data["items"] == {}
        assert data["summary"]["total_items"] == 0


class TestRenderCsv:
    """Tests for CSV renderer."""

    def test_renders_valid_csv(self, sample_coverage, sample_graph):
        """Test that output is valid CSV."""
        csv_str = render_csv(sample_coverage, sample_graph)

        # Should be parseable as CSV
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) >= 2  # Header + at least one data row

    def test_has_header_row(self, sample_coverage, sample_graph):
        """Test that CSV has header row."""
        csv_str = render_csv(sample_coverage, sample_graph)

        reader = csv.reader(io.StringIO(csv_str))
        header = next(reader)

        assert "UID" in header
        assert "Description" in header
        assert "Status" in header

    def test_contains_item_uid(self, sample_coverage, sample_graph):
        """Test that CSV contains item UID."""
        csv_str = render_csv(sample_coverage, sample_graph)

        assert "SRS001" in csv_str

    def test_contains_status(self, sample_coverage, sample_graph):
        """Test that CSV contains status."""
        csv_str = render_csv(sample_coverage, sample_graph)

        assert "Passed" in csv_str

    def test_uncovered_status(self, uncovered_coverage, sample_graph):
        """Test that uncovered items show Not Covered status."""
        csv_str = render_csv(uncovered_coverage, sample_graph)

        assert "Not Covered" in csv_str

    def test_failed_status(self, failed_coverage, sample_graph):
        """Test that failed items show Failed status."""
        csv_str = render_csv(failed_coverage, sample_graph)

        assert "Failed" in csv_str

    def test_handles_commas_in_text(self, sample_graph):
        """Test that commas in text are properly escaped."""
        item = Item(
            uid="SRS001",
            text="Test with, comma character",
            document_prefix="SRS",
        )
        coverage = {"SRS001": ItemCoverage(item=item, linked_tests=[])}

        csv_str = render_csv(coverage, sample_graph)

        # CSV should still be valid and contain the text
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        assert any("comma character" in str(row) for row in rows)


class TestRenderXlsx:
    """Tests for XLSX renderer."""

    def test_renders_valid_xlsx(self, sample_coverage, sample_graph):
        """Test that output is valid XLSX."""
        xlsx_bytes = render_xlsx(sample_coverage, sample_graph)

        # Should be loadable as a workbook
        wb = load_workbook(io.BytesIO(xlsx_bytes))
        assert wb.active is not None

    def test_has_title(self, sample_coverage, sample_graph):
        """Test that worksheet has correct title."""
        xlsx_bytes = render_xlsx(sample_coverage, sample_graph)
        wb = load_workbook(io.BytesIO(xlsx_bytes))

        assert wb.active.title == "Traceability Matrix"

    def test_contains_summary(self, sample_coverage, sample_graph):
        """Test that XLSX contains summary section."""
        xlsx_bytes = render_xlsx(sample_coverage, sample_graph)
        wb = load_workbook(io.BytesIO(xlsx_bytes))
        ws = wb.active

        # Check for summary title
        assert "Traceability and Test Record Matrix" in str(ws["A1"].value)

    def test_contains_header_row(self, sample_coverage, sample_graph):
        """Test that XLSX contains header row."""
        xlsx_bytes = render_xlsx(sample_coverage, sample_graph)
        wb = load_workbook(io.BytesIO(xlsx_bytes))
        ws = wb.active

        # Header is in row 7
        assert ws.cell(row=7, column=1).value == "UID"
        assert ws.cell(row=7, column=5).value == "Test Actions"
        assert ws.cell(row=7, column=6).value == "Expected Results"
        assert ws.cell(row=7, column=7).value == "Actual Results"
        assert ws.cell(row=7, column=8).value == "Notes"
        assert ws.cell(row=7, column=9).value == "Status"

    def test_contains_item_uid(self, sample_coverage, sample_graph):
        """Test that XLSX contains item UID."""
        xlsx_bytes = render_xlsx(sample_coverage, sample_graph)
        wb = load_workbook(io.BytesIO(xlsx_bytes))
        ws = wb.active

        # Data starts in row 8
        assert ws.cell(row=8, column=1).value == "SRS001"

    def test_contains_status(self, sample_coverage, sample_graph):
        """Test that XLSX contains status."""
        xlsx_bytes = render_xlsx(sample_coverage, sample_graph)
        wb = load_workbook(io.BytesIO(xlsx_bytes))
        ws = wb.active

        # Status is in column 9 (after Actual Results and Notes columns)
        assert ws.cell(row=8, column=9).value == "Passed"

    def test_uncovered_status(self, uncovered_coverage, sample_graph):
        """Test that uncovered items show Not Covered status."""
        xlsx_bytes = render_xlsx(uncovered_coverage, sample_graph)
        wb = load_workbook(io.BytesIO(xlsx_bytes))
        ws = wb.active

        assert ws.cell(row=8, column=9).value == "Not Covered"

    def test_failed_status(self, failed_coverage, sample_graph):
        """Test that failed items show Failed status."""
        xlsx_bytes = render_xlsx(failed_coverage, sample_graph)
        wb = load_workbook(io.BytesIO(xlsx_bytes))
        ws = wb.active

        assert ws.cell(row=8, column=9).value == "Failed"

    def test_empty_coverage(self, sample_graph):
        """Test rendering with empty coverage."""
        xlsx_bytes = render_xlsx({}, sample_graph)
        wb = load_workbook(io.BytesIO(xlsx_bytes))

        # Should still be valid
        assert wb.active is not None


class TestTraceToIgnore:
    """Tests for trace_to_ignore filtering in renderers."""

    @pytest.fixture
    def trace_graph(self):
        """Graph with PRJ -> UN -> SYS -> SRS hierarchy."""
        graph = TraceabilityGraph()
        prj = Item(uid="PRJ001", text="Project req", document_prefix="PRJ")
        un = Item(uid="UN001", text="User need", document_prefix="UN", links=["PRJ001"])
        sys_item = Item(
            uid="SYS001", text="System req", document_prefix="SYS", links=["UN001"]
        )
        srs = Item(
            uid="SRS001", text="Software req", document_prefix="SRS", links=["SYS001"]
        )
        graph.add_item(prj)
        graph.add_item(un)
        graph.add_item(sys_item)
        graph.add_item(srs)
        graph.set_document_parent("PRJ", None)
        graph.set_document_parent("UN", "PRJ")
        graph.set_document_parent("SYS", "UN")
        graph.set_document_parent("SRS", "SYS")
        return graph

    @pytest.fixture
    def trace_coverage(self):
        """Coverage for SRS001."""
        item = Item(
            uid="SRS001",
            text="Software req",
            document_prefix="SRS",
            links=["SYS001"],
        )
        link = LinkedTest(
            test_nodeid="test_req.py::test_srs",
            item_uid="SRS001",
            test_outcome="passed",
        )
        return {"SRS001": ItemCoverage(item=item, linked_tests=[link])}

    def test_csv_excludes_ignored_prefix(self, trace_coverage, trace_graph):
        """Test CSV excludes PRJ ancestors when trace_to_ignore={'PRJ'}."""
        csv_str = render_csv(trace_coverage, trace_graph, trace_to_ignore={"PRJ"})
        assert "PRJ001" not in csv_str
        assert "SYS001" in csv_str

    def test_csv_includes_all_when_empty(self, trace_coverage, trace_graph):
        """Test CSV includes all ancestors when trace_to_ignore is empty."""
        csv_str = render_csv(trace_coverage, trace_graph)
        assert "PRJ001" in csv_str
        assert "SYS001" in csv_str

    def test_markdown_excludes_ignored_prefix(self, trace_coverage, trace_graph):
        """Test Markdown excludes PRJ ancestors when trace_to_ignore={'PRJ'}."""
        md = render_markdown(trace_coverage, trace_graph, trace_to_ignore={"PRJ"})
        assert "PRJ001" not in md
        assert "SYS001" in md

    def test_markdown_includes_all_when_empty(self, trace_coverage, trace_graph):
        """Test Markdown includes all ancestors when trace_to_ignore is empty."""
        md = render_markdown(trace_coverage, trace_graph)
        assert "PRJ001" in md

    def test_html_excludes_ignored_prefix(self, trace_coverage, trace_graph):
        """Test HTML excludes PRJ ancestors when trace_to_ignore={'PRJ'}."""
        html = render_html(trace_coverage, trace_graph, trace_to_ignore={"PRJ"})
        assert "PRJ001" not in html
        assert "SYS001" in html

    def test_html_includes_all_when_empty(self, trace_coverage, trace_graph):
        """Test HTML includes all ancestors when trace_to_ignore is empty."""
        html = render_html(trace_coverage, trace_graph)
        assert "PRJ001" in html

    def test_json_excludes_ignored_prefix(self, trace_coverage, trace_graph):
        """Test JSON excludes PRJ ancestors when trace_to_ignore={'PRJ'}."""
        json_str = render_json(trace_coverage, trace_graph, trace_to_ignore={"PRJ"})
        data = json.loads(json_str)
        traces = data["items"]["SRS001"]["traces_to"]
        uids = [t["uid"] for t in traces]
        assert "PRJ001" not in uids
        assert "SYS001" in uids

    def test_json_includes_all_when_empty(self, trace_coverage, trace_graph):
        """Test JSON includes all ancestors when trace_to_ignore is empty."""
        json_str = render_json(trace_coverage, trace_graph)
        data = json.loads(json_str)
        traces = data["items"]["SRS001"]["traces_to"]
        uids = [t["uid"] for t in traces]
        assert "PRJ001" in uids

    def test_xlsx_excludes_ignored_prefix(self, trace_coverage, trace_graph):
        """Test XLSX excludes PRJ ancestors when trace_to_ignore={'PRJ'}."""
        xlsx_bytes = render_xlsx(trace_coverage, trace_graph, trace_to_ignore={"PRJ"})
        wb = load_workbook(io.BytesIO(xlsx_bytes))
        ws = wb.active
        traces_to = ws.cell(row=8, column=3).value or ""
        assert "PRJ001" not in traces_to
        assert "SYS001" in traces_to

    def test_xlsx_includes_all_when_empty(self, trace_coverage, trace_graph):
        """Test XLSX includes all ancestors when trace_to_ignore is empty."""
        xlsx_bytes = render_xlsx(trace_coverage, trace_graph)
        wb = load_workbook(io.BytesIO(xlsx_bytes))
        ws = wb.active
        traces_to = ws.cell(row=8, column=3).value or ""
        assert "PRJ001" in traces_to


class TestNotesInRenderers:
    """Tests for notes display in all renderers."""

    def test_html_contains_custom_notes(self, coverage_with_messages, sample_graph):
        """Test that HTML output contains custom notes."""
        html = render_html(coverage_with_messages, sample_graph)

        assert "Custom verification message" in html
        assert "Second test note" in html

    def test_html_contains_test_actions(self, coverage_with_messages, sample_graph):
        """Test that HTML output contains test actions."""
        html = render_html(coverage_with_messages, sample_graph)

        assert "Entered valid data" in html
        assert "Clicked submit" in html
        assert "<th>Test Actions</th>" in html

    def test_html_contains_expected_results(self, coverage_with_messages, sample_graph):
        """Test that HTML output contains expected results."""
        html = render_html(coverage_with_messages, sample_graph)

        assert "Form accepted" in html
        assert "Success page shown" in html
        assert "<th>Expected Results</th>" in html

    def test_html_contains_failure_message(
        self, coverage_with_failure_message, sample_graph
    ):
        """Test that HTML output contains failure messages with correct class."""
        html = render_html(coverage_with_failure_message, sample_graph)

        assert "[FAILURE]" in html
        assert 'class="message failure"' in html

    def test_json_contains_notes(self, coverage_with_messages, sample_graph):
        """Test that JSON output includes notes array."""
        json_str = render_json(coverage_with_messages, sample_graph)
        data = json.loads(json_str)

        item = data["items"]["SRS004"]
        test = item["linked_tests"][0]
        assert "notes" in test
        assert "Custom verification message" in test["notes"]
        assert "Second test note" in test["notes"]

    def test_json_contains_test_actions(self, coverage_with_messages, sample_graph):
        """Test that JSON output includes test_actions array."""
        json_str = render_json(coverage_with_messages, sample_graph)
        data = json.loads(json_str)

        item = data["items"]["SRS004"]
        test = item["linked_tests"][0]
        assert "test_actions" in test
        assert "Entered valid data" in test["test_actions"]

    def test_json_contains_expected_results(self, coverage_with_messages, sample_graph):
        """Test that JSON output includes expected_results array."""
        json_str = render_json(coverage_with_messages, sample_graph)
        data = json.loads(json_str)

        item = data["items"]["SRS004"]
        test = item["linked_tests"][0]
        assert "expected_results" in test
        assert "Form accepted" in test["expected_results"]

    def test_csv_contains_notes_column(self, coverage_with_messages, sample_graph):
        """Test that CSV output has Notes column."""
        csv_str = render_csv(coverage_with_messages, sample_graph)

        reader = csv.reader(io.StringIO(csv_str))
        header = next(reader)
        assert "Notes" in header

    def test_csv_contains_test_actions_column(
        self, coverage_with_messages, sample_graph
    ):
        """Test that CSV output has Test Actions column."""
        csv_str = render_csv(coverage_with_messages, sample_graph)

        reader = csv.reader(io.StringIO(csv_str))
        header = next(reader)
        assert "Test Actions" in header

    def test_csv_contains_expected_results_column(
        self, coverage_with_messages, sample_graph
    ):
        """Test that CSV output has Expected Results column."""
        csv_str = render_csv(coverage_with_messages, sample_graph)

        reader = csv.reader(io.StringIO(csv_str))
        header = next(reader)
        assert "Expected Results" in header

    def test_csv_contains_note_content(self, coverage_with_messages, sample_graph):
        """Test that CSV output contains note content."""
        csv_str = render_csv(coverage_with_messages, sample_graph)

        assert "Custom verification message" in csv_str

    def test_csv_contains_test_action_content(
        self, coverage_with_messages, sample_graph
    ):
        """Test that CSV output contains test action content."""
        csv_str = render_csv(coverage_with_messages, sample_graph)

        assert "Entered valid data" in csv_str

    def test_xlsx_contains_notes_column(self, coverage_with_messages, sample_graph):
        """Test that XLSX output has Notes column."""
        xlsx_bytes = render_xlsx(coverage_with_messages, sample_graph)
        wb = load_workbook(io.BytesIO(xlsx_bytes))
        ws = wb.active

        # Notes is in column 8 (after Actual Results)
        assert ws.cell(row=7, column=8).value == "Notes"

    def test_xlsx_contains_test_actions_column(
        self, coverage_with_messages, sample_graph
    ):
        """Test that XLSX output has Test Actions column."""
        xlsx_bytes = render_xlsx(coverage_with_messages, sample_graph)
        wb = load_workbook(io.BytesIO(xlsx_bytes))
        ws = wb.active

        assert ws.cell(row=7, column=5).value == "Test Actions"

    def test_xlsx_contains_expected_results_column(
        self, coverage_with_messages, sample_graph
    ):
        """Test that XLSX output has Expected Results column."""
        xlsx_bytes = render_xlsx(coverage_with_messages, sample_graph)
        wb = load_workbook(io.BytesIO(xlsx_bytes))
        ws = wb.active

        assert ws.cell(row=7, column=6).value == "Expected Results"

    def test_xlsx_contains_note_content(self, coverage_with_messages, sample_graph):
        """Test that XLSX output contains note content."""
        xlsx_bytes = render_xlsx(coverage_with_messages, sample_graph)
        wb = load_workbook(io.BytesIO(xlsx_bytes))
        ws = wb.active

        # Notes are in column 8, data row 8
        notes_cell = ws.cell(row=8, column=8).value
        assert "Custom verification message" in notes_cell

    def test_markdown_contains_notes_column(self, coverage_with_messages, sample_graph):
        """Test that Markdown output has Notes column."""
        md = render_markdown(coverage_with_messages, sample_graph)

        assert "| Notes |" in md

    def test_markdown_contains_test_actions_column(
        self, coverage_with_messages, sample_graph
    ):
        """Test that Markdown output has Test Actions column."""
        md = render_markdown(coverage_with_messages, sample_graph)

        assert "| Test Actions |" in md

    def test_markdown_contains_expected_results_column(
        self, coverage_with_messages, sample_graph
    ):
        """Test that Markdown output has Expected Results column."""
        md = render_markdown(coverage_with_messages, sample_graph)

        assert "| Expected Results |" in md

    def test_markdown_contains_note_content(self, coverage_with_messages, sample_graph):
        """Test that Markdown output contains note content."""
        md = render_markdown(coverage_with_messages, sample_graph)

        assert "Custom verification message" in md


# =========================================================================
# Gap 9 — XLSX conditional formatting (fill colors)
# =========================================================================


class TestXlsxConditionalFormatting:
    """Tests for XLSX status cell fill colors."""

    def test_passed_cell_has_green_fill(self, sample_coverage, sample_graph):
        """Passed status cell has green fill (C6EFCE)."""
        xlsx_bytes = render_xlsx(sample_coverage, sample_graph)
        wb = load_workbook(io.BytesIO(xlsx_bytes))
        ws = wb.active

        status_cell = ws.cell(row=8, column=9)
        assert status_cell.value == "Passed"
        assert status_cell.fill.start_color.rgb == "00C6EFCE"

    def test_failed_cell_has_red_fill(self, failed_coverage, sample_graph):
        """Failed status cell has red fill (FFC7CE)."""
        xlsx_bytes = render_xlsx(failed_coverage, sample_graph)
        wb = load_workbook(io.BytesIO(xlsx_bytes))
        ws = wb.active

        status_cell = ws.cell(row=8, column=9)
        assert status_cell.value == "Failed"
        assert status_cell.fill.start_color.rgb == "00FFC7CE"

    def test_uncovered_cell_has_yellow_fill(self, uncovered_coverage, sample_graph):
        """Uncovered status cell has yellow fill (FFEB9C)."""
        xlsx_bytes = render_xlsx(uncovered_coverage, sample_graph)
        wb = load_workbook(io.BytesIO(xlsx_bytes))
        ws = wb.active

        status_cell = ws.cell(row=8, column=9)
        assert status_cell.value == "Not Covered"
        assert status_cell.fill.start_color.rgb == "00FFEB9C"


# =========================================================================
# Tests for actual_results field in matrices
# =========================================================================


class TestActualResultsInRenderers:
    """Tests for actual_results display in all renderers."""

    @pytest.fixture
    def coverage_with_actual_results(self):
        """Coverage data with actual results."""
        item = Item(
            uid="SRS010",
            text="Requirement with actual results",
            document_prefix="SRS",
        )
        link = LinkedTest(
            test_nodeid="test_actual.py::test_with_actual_results",
            item_uid="SRS010",
            test_outcome="passed",
            test_actions=["Submit login form"],
            expected_results=["Login succeeds"],
            actual_results=["Login returned: success", "Token generated"],
        )
        return {"SRS010": ItemCoverage(item=item, linked_tests=[link])}

    def test_html_contains_actual_results(
        self, coverage_with_actual_results, sample_graph
    ):
        """Test that HTML output contains actual results."""
        html = render_html(coverage_with_actual_results, sample_graph)
        assert "Login returned: success" in html
        assert "Token generated" in html
        assert "<th>Actual Results</th>" in html

    def test_json_contains_actual_results(
        self, coverage_with_actual_results, sample_graph
    ):
        """Test that JSON output includes actual_results array."""
        json_str = render_json(coverage_with_actual_results, sample_graph)
        data = json.loads(json_str)
        test = data["items"]["SRS010"]["linked_tests"][0]
        assert "actual_results" in test
        assert "Login returned: success" in test["actual_results"]

    def test_csv_contains_actual_results(
        self, coverage_with_actual_results, sample_graph
    ):
        """Test that CSV output has Actual Results column and content."""
        csv_str = render_csv(coverage_with_actual_results, sample_graph)
        reader = csv.reader(io.StringIO(csv_str))
        header = next(reader)
        assert "Actual Results" in header
        assert "Login returned: success" in csv_str

    def test_markdown_contains_actual_results(
        self, coverage_with_actual_results, sample_graph
    ):
        """Test that Markdown output has Actual Results column and content."""
        md = render_markdown(coverage_with_actual_results, sample_graph)
        assert "| Actual Results |" in md
        assert "Login returned: success" in md

    def test_xlsx_contains_actual_results(
        self, coverage_with_actual_results, sample_graph
    ):
        """Test that XLSX output has Actual Results column and content."""
        xlsx_bytes = render_xlsx(coverage_with_actual_results, sample_graph)
        wb = load_workbook(io.BytesIO(xlsx_bytes))
        ws = wb.active
        assert ws.cell(row=7, column=7).value == "Actual Results"
        actual_cell = ws.cell(row=8, column=7).value
        assert "Login returned: success" in actual_cell


# =========================================================================
# Tests for multi-test grouping (test name headers)
# =========================================================================


class TestMultiTestGrouping:
    """Tests for grouping entries by test name when multi-test items."""

    @pytest.fixture
    def coverage_with_multiple_tests(self):
        """Coverage data with multiple tests linked to one requirement."""
        item = Item(
            uid="SRS020",
            text="Requirement with multiple tests",
            document_prefix="SRS",
        )
        test1 = LinkedTest(
            test_nodeid="test_multi.py::test_first",
            item_uid="SRS020",
            test_outcome="passed",
            test_actions=["First action"],
            expected_results=["First expected"],
            actual_results=["First actual"],
            notes=["First note"],
        )
        test2 = LinkedTest(
            test_nodeid="test_multi.py::test_second",
            item_uid="SRS020",
            test_outcome="passed",
            test_actions=["Second action"],
            expected_results=["Second expected"],
            actual_results=["Second actual"],
            notes=["Second note"],
        )
        return {"SRS020": ItemCoverage(item=item, linked_tests=[test1, test2])}

    def test_html_groups_by_test_name(self, coverage_with_multiple_tests, sample_graph):
        """Test that HTML shows test name headers for multi-test items."""
        html = render_html(coverage_with_multiple_tests, sample_graph)
        assert "test_first" in html
        assert "test_second" in html
        assert 'class="test-header"' in html

    def test_markdown_prefixes_with_test_name(
        self, coverage_with_multiple_tests, sample_graph
    ):
        """Test that Markdown prefixes entries with [test_name] for multi-test items."""
        md = render_markdown(coverage_with_multiple_tests, sample_graph)
        assert "[test_first]" in md
        assert "[test_second]" in md

    def test_csv_prefixes_with_test_name(
        self, coverage_with_multiple_tests, sample_graph
    ):
        """Test that CSV prefixes entries with [test_name] for multi-test items."""
        csv_str = render_csv(coverage_with_multiple_tests, sample_graph)
        assert "[test_first]" in csv_str
        assert "[test_second]" in csv_str

    def test_xlsx_groups_by_test_name(self, coverage_with_multiple_tests, sample_graph):
        """Test that XLSX shows test name headers for multi-test items."""
        xlsx_bytes = render_xlsx(coverage_with_multiple_tests, sample_graph)
        wb = load_workbook(io.BytesIO(xlsx_bytes))
        ws = wb.active
        actions_cell = ws.cell(row=8, column=5).value
        assert "[test_first]" in actions_cell
        assert "[test_second]" in actions_cell

    def test_single_test_no_prefix(self, sample_coverage, sample_graph):
        """Test that single-test items don't get test name prefix."""
        md = render_markdown(sample_coverage, sample_graph)
        # Should not have brackets around test name in the content
        assert "[test_valid]" not in md


# =========================================================================
# Tests for metadata in matrix output
# =========================================================================


class TestMatrixMetadata:
    """Tests for metadata header in matrix output."""

    @pytest.fixture
    def sample_metadata(self):
        """Sample metadata for testing."""
        from jamb.core.models import MatrixMetadata, TestEnvironment

        return MatrixMetadata(
            software_version="1.2.3",
            tester_id="QA Team",
            execution_timestamp="2026-01-28T12:00:00Z",
            environment=TestEnvironment(
                os_name="Darwin",
                os_version="25.2.0",
                python_version="3.12.0",
                platform="arm64",
                processor="arm",
                hostname="test-machine",
                cpu_count=10,
                test_tools={"pytest": "8.0.0", "jamb": "1.0.0"},
            ),
        )

    def test_html_contains_metadata(
        self, sample_coverage, sample_graph, sample_metadata
    ):
        """Test that HTML output contains metadata section."""
        html = render_html(sample_coverage, sample_graph, metadata=sample_metadata)
        assert "1.2.3" in html
        assert "QA Team" in html
        assert "2026-01-28T12:00:00Z" in html
        assert "Darwin" in html
        assert "pytest 8.0.0" in html

    def test_json_contains_metadata(
        self, sample_coverage, sample_graph, sample_metadata
    ):
        """Test that JSON output contains metadata object."""
        json_str = render_json(sample_coverage, sample_graph, metadata=sample_metadata)
        data = json.loads(json_str)
        assert "metadata" in data
        assert data["metadata"]["software_version"] == "1.2.3"
        assert data["metadata"]["tester_id"] == "QA Team"
        assert data["metadata"]["test_tools"]["pytest"] == "8.0.0"

    def test_markdown_contains_metadata(
        self, sample_coverage, sample_graph, sample_metadata
    ):
        """Test that Markdown output contains metadata section."""
        md = render_markdown(sample_coverage, sample_graph, metadata=sample_metadata)
        assert "**Software Version:** 1.2.3" in md
        assert "**Tester:** QA Team" in md
        assert "pytest 8.0.0" in md

    def test_csv_contains_metadata(
        self, sample_coverage, sample_graph, sample_metadata
    ):
        """Test that CSV output contains metadata rows."""
        csv_str = render_csv(sample_coverage, sample_graph, metadata=sample_metadata)
        assert "Software Version,1.2.3" in csv_str
        assert "Tester,QA Team" in csv_str

    def test_xlsx_contains_metadata(
        self, sample_coverage, sample_graph, sample_metadata
    ):
        """Test that XLSX output contains metadata rows."""
        xlsx_bytes = render_xlsx(
            sample_coverage, sample_graph, metadata=sample_metadata
        )
        wb = load_workbook(io.BytesIO(xlsx_bytes))
        ws = wb.active
        # Metadata starts at row 3
        assert ws.cell(row=3, column=1).value == "Software Version:"
        assert ws.cell(row=3, column=2).value == "1.2.3"


# =========================================================================
# Tests for testable: false items (N/A status)
# =========================================================================


class TestNonTestableItems:
    """Tests for non-testable items showing N/A status."""

    @pytest.fixture
    def nontestable_coverage(self):
        """Coverage data with non-testable item."""
        item = Item(
            uid="SRS099",
            text="User manual shall be provided",
            document_prefix="SRS",
            testable=False,
        )
        return {"SRS099": ItemCoverage(item=item, linked_tests=[])}

    def test_html_shows_na_status(self, nontestable_coverage, sample_graph):
        """Test that HTML shows N/A status for non-testable items."""
        html = render_html(nontestable_coverage, sample_graph)
        assert "N/A" in html
        assert 'class="na"' in html or "na" in html.lower()

    def test_json_shows_na_status(self, nontestable_coverage, sample_graph):
        """Test that JSON shows N/A status for non-testable items."""
        json_str = render_json(nontestable_coverage, sample_graph)
        data = json.loads(json_str)
        assert data["items"]["SRS099"]["status"] == "N/A"
        assert data["items"]["SRS099"]["testable"] is False

    def test_markdown_shows_na_status(self, nontestable_coverage, sample_graph):
        """Test that Markdown shows N/A status for non-testable items."""
        md = render_markdown(nontestable_coverage, sample_graph)
        assert "| N/A |" in md

    def test_csv_shows_na_status(self, nontestable_coverage, sample_graph):
        """Test that CSV shows N/A status for non-testable items."""
        csv_str = render_csv(nontestable_coverage, sample_graph)
        assert ",N/A" in csv_str

    def test_xlsx_shows_na_status(self, nontestable_coverage, sample_graph):
        """Test that XLSX shows N/A status for non-testable items."""
        xlsx_bytes = render_xlsx(nontestable_coverage, sample_graph)
        wb = load_workbook(io.BytesIO(xlsx_bytes))
        ws = wb.active
        assert ws.cell(row=8, column=9).value == "N/A"

    def test_xlsx_na_has_gray_fill(self, nontestable_coverage, sample_graph):
        """Test that N/A status cell has gray fill (D9D9D9)."""
        xlsx_bytes = render_xlsx(nontestable_coverage, sample_graph)
        wb = load_workbook(io.BytesIO(xlsx_bytes))
        ws = wb.active
        status_cell = ws.cell(row=8, column=9)
        assert status_cell.fill.start_color.rgb == "00D9D9D9"
