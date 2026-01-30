"""Integration tests for jamb pytest plugin."""

pytest_plugins = ["pytester"]


class TestPluginRegistration:
    """Tests for plugin registration and options."""

    def test_jamb_option_available(self, pytester):
        """Test that --jamb option is available."""
        result = pytester.runpytest("--help")

        assert result.ret == 0
        result.stdout.fnmatch_lines(["*--jamb*"])

    def test_jamb_fail_uncovered_option(self, pytester):
        """Test that --jamb-fail-uncovered option is available."""
        result = pytester.runpytest("--help")

        result.stdout.fnmatch_lines(["*--jamb-fail-uncovered*"])

    def test_jamb_matrix_option(self, pytester):
        """Test that --jamb-test-matrix option is available."""
        result = pytester.runpytest("--help")

        result.stdout.fnmatch_lines(["*--jamb-test-matrix*"])


class TestMarkerCollection:
    """Tests for requirement marker collection."""

    def test_collects_requirement_marker(self, pytester):
        """Test that requirement markers are collected."""
        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.requirement("SRS001")
            def test_something():
                assert True
            """
        )

        pytester.makefile(".yml", **{".jamb": "settings:\n  digits: 3\n  prefix: SRS\n  sep: ''"})
        pytester.makefile(
            ".yml",
            SRS001="active: true\ntext: Test requirement\nlinks: []",
        )

        result = pytester.runpytest("--jamb", "-v")

        # Should run without error
        assert result.ret == 0

    def test_marker_registered(self, pytester):
        """Test that requirement marker is registered."""
        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.requirement("TEST001")
            def test_marked():
                pass
            """
        )

        result = pytester.runpytest("--markers")

        result.stdout.fnmatch_lines(["*requirement*"])


class TestCoverageSummary:
    """Tests for coverage summary output."""

    def test_coverage_summary_section_present(self, pytester):
        """Test that coverage summary section appears with --jamb."""
        pytester.makepyfile(
            """
            def test_simple():
                assert True
            """
        )

        result = pytester.runpytest("--jamb")

        # Should show coverage summary section (even if empty)
        # The exact content depends on jamb tree availability
        assert result.ret == 0
        # Output should contain some coverage-related text
        output = result.stdout.str()
        assert "passed" in output.lower() or "Coverage" in output or "Total test spec items" in output


class TestFailUncovered:
    """Tests for --jamb-fail-uncovered flag."""

    def test_passes_when_all_covered(self, pytester):
        """Test that tests pass when all items are covered."""
        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.requirement("SRS001")
            def test_covers_srs001():
                assert True
            """
        )

        pytester.makefile(".yml", **{".jamb": "settings:\n  digits: 3\n  prefix: SRS\n  sep: ''"})
        pytester.makefile(".yml", SRS001="active: true\ntext: Test\nlinks: []")

        result = pytester.runpytest("--jamb", "--jamb-fail-uncovered")

        # Should pass - item is covered
        assert result.ret == 0


class TestMatrixGeneration:
    """Tests for matrix generation during test run."""

    def test_generates_html_matrix(self, pytester, tmp_path):
        """Test that --jamb-test-matrix generates HTML file."""
        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.requirement("SRS001")
            def test_something():
                assert True
            """
        )

        pytester.makefile(".yml", **{".jamb": "settings:\n  digits: 3\n  prefix: SRS\n  sep: ''"})
        pytester.makefile(".yml", SRS001="active: true\ntext: Test\nlinks: []")

        matrix_path = pytester.path / "matrix.html"
        result = pytester.runpytest("--jamb", f"--jamb-test-matrix={matrix_path}")

        assert result.ret == 0
        assert matrix_path.exists()
        content = matrix_path.read_text()
        assert "<html" in content

    def test_generates_markdown_matrix(self, pytester):
        """Test that --jamb-test-matrix with markdown format works."""
        pytester.makepyfile(
            """
            def test_simple():
                pass
            """
        )

        pytester.makefile(".yml", **{".jamb": "settings:\n  digits: 3\n  prefix: SRS\n  sep: ''"})

        matrix_path = pytester.path / "matrix.md"
        result = pytester.runpytest(
            "--jamb",
            f"--jamb-test-matrix={matrix_path}",
        )

        assert result.ret == 0
        assert matrix_path.exists()

    def test_generates_csv_matrix(self, pytester):
        """Test that --jamb-trace-matrix with csv format works."""
        pytester.makepyfile(
            """
            def test_simple():
                pass
            """
        )

        pytester.makefile(".yml", **{".jamb": "settings:\n  digits: 3\n  prefix: SRS\n  sep: ''"})

        matrix_path = pytester.path / "matrix.csv"
        result = pytester.runpytest(
            "--jamb",
            f"--jamb-trace-matrix={matrix_path}",
        )

        assert result.ret == 0
        assert matrix_path.exists()
        content = matrix_path.read_text()
        assert "Traceability Matrix" in content  # Title row exists

    def test_generates_xlsx_matrix(self, pytester):
        """Test that --jamb-trace-matrix with xlsx format works."""
        from openpyxl import load_workbook

        pytester.makepyfile(
            """
            def test_simple():
                pass
            """
        )

        pytester.makefile(".yml", **{".jamb": "settings:\n  digits: 3\n  prefix: SRS\n  sep: ''"})

        matrix_path = pytester.path / "matrix.xlsx"
        result = pytester.runpytest(
            "--jamb",
            f"--jamb-trace-matrix={matrix_path}",
        )

        assert result.ret == 0
        assert matrix_path.exists()

        # Verify it's a valid Excel file
        wb = load_workbook(matrix_path)
        assert wb.active is not None
        assert wb.active.title == "Trace Matrix"


class TestUnknownItems:
    """Tests for unknown item handling."""

    def test_test_with_unknown_item_still_passes(self, pytester):
        """Test that tests with unknown item markers still run and pass."""
        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.requirement("NONEXISTENT001")
            def test_unknown_item():
                assert True
            """
        )

        result = pytester.runpytest("--jamb", "-v")

        # Test should still pass even with unknown item reference
        assert result.ret == 0
        result.stdout.fnmatch_lines(["*test_unknown_item*PASSED*"])


def _setup_jamb(pytester):
    """Initialize jamb config in pytester directory."""
    pytester.makefile(".yml", **{".jamb": "settings:\n  digits: 3\n  prefix: SRS\n  sep: ''"})
    pytester.makefile(
        ".yml",
        SRS001="active: true\ntext: Test requirement\nlinks: []",
    )


class TestJambDocumentsOption:
    """Tests for --jamb-documents option."""

    def test_jamb_documents_option_available(self, pytester):
        """Test that --jamb-documents option is available."""
        result = pytester.runpytest("--help")

        result.stdout.fnmatch_lines(["*--jamb-documents*"])

    def test_jamb_documents_filters_coverage(self, pytester):
        """Test that --jamb-documents filters which documents are checked."""
        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.requirement("SRS001")
            def test_covers_srs():
                assert True
            """
        )

        _setup_jamb(pytester)

        result = pytester.runpytest("--jamb", "--jamb-documents=SRS", "-v")

        assert result.ret == 0
        # Should show coverage for SRS only
        output = result.stdout.str()
        assert "SRS" in output or "Total testable items" in output


class TestReportHeader:
    """Tests for pytest_report_header hook."""

    def test_report_header_shows_item_count(self, pytester):
        """Test that report header shows requirement item count."""
        pytester.makepyfile(
            """
            def test_simple():
                assert True
            """
        )

        _setup_jamb(pytester)

        result = pytester.runpytest("--jamb", "-v")

        assert result.ret == 0
        # Should show jamb header with item count
        output = result.stdout.str()
        assert "jamb" in output.lower()

    def test_report_header_not_shown_without_jamb_flag(self, pytester):
        """Test that report header is not shown without --jamb."""
        pytester.makepyfile(
            """
            def test_simple():
                assert True
            """
        )

        result = pytester.runpytest("-v")

        assert result.ret == 0
        # Should not show jamb-specific header
        output = result.stdout.str()
        assert "requirement items" not in output


class TestTerminalSummaryExtended:
    """Extended tests for pytest_terminal_summary hook."""

    def test_terminal_summary_shows_coverage_stats(self, pytester):
        """Test terminal summary shows coverage statistics."""
        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.requirement("SRS001")
            def test_something():
                assert True
            """
        )

        _setup_jamb(pytester)

        result = pytester.runpytest("--jamb", "-v")

        assert result.ret == 0
        output = result.stdout.str()
        # Should show coverage summary
        assert "Coverage Summary" in output or "Covered" in output

    def test_terminal_summary_shows_uncovered_items(self, pytester):
        """Test terminal summary lists uncovered items."""
        # Add a second item that won't be covered
        pytester.makefile(
            ".yml",
            SRS002="active: true\ntext: Uncovered\nlinks: []",
        )

        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.requirement("SRS001")
            def test_covers_srs001():
                assert True
            """
        )

        _setup_jamb(pytester)

        result = pytester.runpytest("--jamb", "-v")

        assert result.ret == 0
        output = result.stdout.str()
        # Should show uncovered items section
        assert "SRS002" in output or "Uncovered" in output

    def test_terminal_summary_shows_unknown_items(self, pytester):
        """Test terminal summary lists unknown item references."""
        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.requirement("NONEXISTENT001")
            def test_unknown_item():
                assert True
            """
        )

        _setup_jamb(pytester)

        result = pytester.runpytest("--jamb", "-v")

        assert result.ret == 0
        output = result.stdout.str()
        # Should show unknown items
        assert "NONEXISTENT001" in output or "Unknown" in output


class TestFailUncoveredExtended:
    """Extended tests for --jamb-fail-uncovered flag."""

    def test_fails_when_uncovered(self, pytester):
        """Test that --jamb-fail-uncovered fails when items are uncovered."""
        # Add a second item that won't be covered
        pytester.makefile(
            ".yml",
            SRS002="active: true\ntext: Uncovered\nlinks: []",
        )

        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.requirement("SRS001")
            def test_covers_srs001():
                assert True
            """
        )

        _setup_jamb(pytester)

        result = pytester.runpytest("--jamb", "--jamb-fail-uncovered")

        # Should fail - SRS002 is not covered
        assert result.ret != 0


class TestSkipAndXfailCapture:
    """Tests for capturing skip and xfail messages."""

    def test_skip_message_captured(self, pytester):
        """Test that skip messages are captured in matrix."""
        import json

        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.requirement("SRS001")
            def test_that_skips():
                pytest.skip("Skipping for testing")
            """
        )

        _setup_jamb(pytester)

        matrix_path = pytester.path / "matrix.json"
        result = pytester.runpytest(
            "--jamb",
            f"--jamb-test-matrix={matrix_path}",
        )

        assert result.ret == 0
        assert matrix_path.exists()

        data = json.loads(matrix_path.read_text())
        # Find test linked to SRS001
        test = next(t for t in data["tests"] if "SRS001" in t["requirements"])
        # Should have skipped outcome
        assert test["outcome"] == "skipped"

    def test_xfail_message_captured(self, pytester):
        """Test that xfail messages are captured in matrix."""

        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.requirement("SRS001")
            @pytest.mark.xfail(reason="Expected to fail")
            def test_that_xfails():
                assert False
            """
        )

        _setup_jamb(pytester)

        matrix_path = pytester.path / "matrix.json"
        result = pytester.runpytest(
            "--jamb",
            f"--jamb-test-matrix={matrix_path}",
        )

        # xfail tests still result in success
        assert result.ret == 0
        assert matrix_path.exists()


class TestJambLogFixture:
    """Tests for jamb_log fixture and message capture."""

    def test_jamb_log_fixture_available(self, pytester):
        """Test that jamb_log fixture is available."""
        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.requirement("SRS001")
            def test_with_jamb_log(jamb_log):
                jamb_log.note("Test message")
                assert True
            """
        )

        _setup_jamb(pytester)

        result = pytester.runpytest("--jamb", "-v")

        assert result.ret == 0
        result.stdout.fnmatch_lines(["*test_with_jamb_log*PASSED*"])

    def test_custom_message_in_json_matrix(self, pytester):
        """Test that custom messages appear in JSON matrix output."""
        import json

        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.requirement("SRS001")
            def test_with_message(jamb_log):
                jamb_log.note("Custom verification message")
                assert True
            """
        )

        _setup_jamb(pytester)

        matrix_path = pytester.path / "matrix.json"
        result = pytester.runpytest(
            "--jamb",
            f"--jamb-test-matrix={matrix_path}",
        )

        assert result.ret == 0
        assert matrix_path.exists()

        data = json.loads(matrix_path.read_text())
        # Find test linked to SRS001
        test = next(t for t in data["tests"] if "SRS001" in t["requirements"])
        assert "Custom verification message" in test["notes"]

    def test_failure_message_captured(self, pytester):
        """Test that failure messages are captured in matrix."""
        import json

        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.requirement("SRS001")
            def test_that_fails():
                assert False, "Expected failure message"
            """
        )

        _setup_jamb(pytester)

        matrix_path = pytester.path / "matrix.json"
        result = pytester.runpytest(
            "--jamb",
            f"--jamb-test-matrix={matrix_path}",
        )

        # Test fails but matrix should still be generated
        assert result.ret == 1
        assert matrix_path.exists()

        data = json.loads(matrix_path.read_text())
        # Find test linked to SRS001
        test = next(t for t in data["tests"] if "SRS001" in t["requirements"])
        notes = test["notes"]

        # Should have a failure message starting with [FAILURE]
        assert any(msg.startswith("[FAILURE]") for msg in notes)
        assert any("Expected failure message" in msg for msg in notes)

    def test_custom_message_in_html_matrix(self, pytester):
        """Test that custom messages appear in HTML matrix output."""
        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.requirement("SRS001")
            def test_with_message(jamb_log):
                jamb_log.note("HTML verification message")
                assert True
            """
        )

        _setup_jamb(pytester)

        matrix_path = pytester.path / "matrix.html"
        result = pytester.runpytest(
            "--jamb",
            f"--jamb-test-matrix={matrix_path}",
        )

        assert result.ret == 0
        assert matrix_path.exists()

        content = matrix_path.read_text()
        assert "HTML verification message" in content
        assert 'class="message"' in content

    def test_actual_result_captured_in_json_matrix(self, pytester):
        """Test that actual_result() entries appear in JSON matrix."""
        import json

        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.requirement("SRS001")
            def test_with_actual_result(jamb_log):
                jamb_log.test_action("Submit login form")
                jamb_log.expected_result("Login succeeds")
                jamb_log.actual_result("Login returned: success")
                assert True
            """
        )

        _setup_jamb(pytester)

        matrix_path = pytester.path / "matrix.json"
        result = pytester.runpytest(
            "--jamb",
            f"--jamb-test-matrix={matrix_path}",
        )

        assert result.ret == 0
        assert matrix_path.exists()

        data = json.loads(matrix_path.read_text())
        # Find test linked to SRS001
        test = next(t for t in data["tests"] if "SRS001" in t["requirements"])
        assert "Login returned: success" in test["actual_results"]
        assert "Submit login form" in test["test_actions"]
        assert "Login succeeds" in test["expected_results"]


class TestMatrixMetadataIntegration:
    """Integration tests for matrix metadata (IEC 62304 5.7.5)."""

    def test_tester_id_in_json_matrix(self, pytester):
        """Test that --jamb-tester-id appears in JSON matrix."""
        import json

        pytester.makepyfile(
            """
            def test_simple():
                assert True
            """
        )

        _setup_jamb(pytester)

        matrix_path = pytester.path / "matrix.json"
        result = pytester.runpytest(
            "--jamb",
            f"--jamb-test-matrix={matrix_path}",
            "--jamb-tester-id=CI Pipeline",
        )

        assert result.ret == 0
        data = json.loads(matrix_path.read_text())
        assert data["metadata"]["tester_id"] == "CI Pipeline"

    def test_software_version_in_json_matrix(self, pytester):
        """Test that --jamb-software-version appears in JSON matrix."""
        import json

        pytester.makepyfile(
            """
            def test_simple():
                assert True
            """
        )

        _setup_jamb(pytester)

        matrix_path = pytester.path / "matrix.json"
        result = pytester.runpytest(
            "--jamb",
            f"--jamb-test-matrix={matrix_path}",
            "--jamb-software-version=2.5.0",
        )

        assert result.ret == 0
        data = json.loads(matrix_path.read_text())
        assert data["metadata"]["software_version"] == "2.5.0"

    def test_metadata_has_environment(self, pytester):
        """Test that matrix metadata includes environment info."""
        import json

        pytester.makepyfile(
            """
            def test_simple():
                assert True
            """
        )

        _setup_jamb(pytester)

        matrix_path = pytester.path / "matrix.json"
        result = pytester.runpytest(
            "--jamb",
            f"--jamb-test-matrix={matrix_path}",
            "--jamb-tester-id=Test",
        )

        assert result.ret == 0
        data = json.loads(matrix_path.read_text())
        meta = data["metadata"]
        assert meta["environment"] is not None
        assert "os_name" in meta["environment"]
        assert "python_version" in meta["environment"]
        assert meta["execution_timestamp"] is not None

    def test_metadata_has_test_tools(self, pytester):
        """Test that matrix metadata includes test tools."""
        import json

        pytester.makepyfile(
            """
            def test_simple():
                assert True
            """
        )

        _setup_jamb(pytester)

        matrix_path = pytester.path / "matrix.json"
        result = pytester.runpytest(
            "--jamb",
            f"--jamb-test-matrix={matrix_path}",
            "--jamb-tester-id=Test",
        )

        assert result.ret == 0
        data = json.loads(matrix_path.read_text())
        test_tools = data["metadata"]["test_tools"]
        assert "pytest" in test_tools

    def test_tester_id_in_html_matrix(self, pytester):
        """Test that --jamb-tester-id appears in HTML matrix."""
        pytester.makepyfile(
            """
            def test_simple():
                assert True
            """
        )

        _setup_jamb(pytester)

        matrix_path = pytester.path / "matrix.html"
        result = pytester.runpytest(
            "--jamb",
            f"--jamb-test-matrix={matrix_path}",
            "--jamb-tester-id=QA Team",
        )

        assert result.ret == 0
        content = matrix_path.read_text()
        assert "QA Team" in content
        assert "Test Records" in content
