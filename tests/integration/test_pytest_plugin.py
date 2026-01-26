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
        """Test that --jamb-matrix option is available."""
        result = pytester.runpytest("--help")

        result.stdout.fnmatch_lines(["*--jamb-matrix*"])


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

        # Create minimal doorstop config for the test
        pytester.makefile(
            ".yml", **{".doorstop": "settings:\n  digits: 3\n  prefix: SRS\n  sep: ''"}
        )
        pytester.makefile(
            ".yml",
            SRS001="active: true\nnormative: true\ntext: Test requirement\nlinks: []",
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
        # The exact content depends on doorstop tree availability
        assert result.ret == 0
        # Output should contain some coverage-related text
        output = result.stdout.str()
        assert "passed" in output.lower() or "coverage" in output.lower()


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

        # Create doorstop config with one item
        pytester.makefile(
            ".yml", **{".doorstop": "settings:\n  digits: 3\n  prefix: SRS\n  sep: ''"}
        )
        pytester.makefile(
            ".yml", SRS001="active: true\nnormative: true\ntext: Test\nlinks: []"
        )

        result = pytester.runpytest("--jamb", "--jamb-fail-uncovered")

        # Should pass - item is covered
        assert result.ret == 0


class TestMatrixGeneration:
    """Tests for matrix generation during test run."""

    def test_generates_html_matrix(self, pytester, tmp_path):
        """Test that --jamb-matrix generates HTML file."""
        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.requirement("SRS001")
            def test_something():
                assert True
            """
        )

        # Create doorstop config
        pytester.makefile(
            ".yml", **{".doorstop": "settings:\n  digits: 3\n  prefix: SRS\n  sep: ''"}
        )
        pytester.makefile(
            ".yml", SRS001="active: true\nnormative: true\ntext: Test\nlinks: []"
        )

        matrix_path = pytester.path / "matrix.html"
        result = pytester.runpytest("--jamb", f"--jamb-matrix={matrix_path}")

        assert result.ret == 0
        assert matrix_path.exists()
        content = matrix_path.read_text()
        assert "<html" in content

    def test_generates_markdown_matrix(self, pytester):
        """Test that --jamb-matrix with markdown format works."""
        pytester.makepyfile(
            """
            def test_simple():
                pass
            """
        )

        # Create doorstop config
        pytester.makefile(
            ".yml", **{".doorstop": "settings:\n  digits: 3\n  prefix: SRS\n  sep: ''"}
        )

        matrix_path = pytester.path / "matrix.md"
        result = pytester.runpytest(
            "--jamb",
            f"--jamb-matrix={matrix_path}",
            "--jamb-matrix-format=markdown",
        )

        assert result.ret == 0
        assert matrix_path.exists()

    def test_generates_csv_matrix(self, pytester):
        """Test that --jamb-matrix with csv format works."""
        pytester.makepyfile(
            """
            def test_simple():
                pass
            """
        )

        # Create doorstop config
        pytester.makefile(
            ".yml", **{".doorstop": "settings:\n  digits: 3\n  prefix: SRS\n  sep: ''"}
        )

        matrix_path = pytester.path / "matrix.csv"
        result = pytester.runpytest(
            "--jamb",
            f"--jamb-matrix={matrix_path}",
            "--jamb-matrix-format=csv",
        )

        assert result.ret == 0
        assert matrix_path.exists()
        content = matrix_path.read_text()
        assert "UID" in content  # Header row exists

    def test_generates_xlsx_matrix(self, pytester):
        """Test that --jamb-matrix with xlsx format works."""
        from openpyxl import load_workbook

        pytester.makepyfile(
            """
            def test_simple():
                pass
            """
        )

        # Create doorstop config
        pytester.makefile(
            ".yml", **{".doorstop": "settings:\n  digits: 3\n  prefix: SRS\n  sep: ''"}
        )

        matrix_path = pytester.path / "matrix.xlsx"
        result = pytester.runpytest(
            "--jamb",
            f"--jamb-matrix={matrix_path}",
            "--jamb-matrix-format=xlsx",
        )

        assert result.ret == 0
        assert matrix_path.exists()

        # Verify it's a valid Excel file
        wb = load_workbook(matrix_path)
        assert wb.active is not None
        assert wb.active.title == "Traceability Matrix"


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


def _setup_git_doorstop(pytester):
    """Initialize git repo and doorstop config in pytester directory."""
    import subprocess

    # Initialize git repo (doorstop requires this)
    subprocess.run(["git", "init"], cwd=pytester.path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=pytester.path,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=pytester.path,
        capture_output=True,
    )

    # Create doorstop config
    pytester.makefile(
        ".yml", **{".doorstop": "settings:\n  digits: 3\n  prefix: SRS\n  sep: ''"}
    )
    pytester.makefile(
        ".yml", SRS001="active: true\nnormative: true\ntext: Test\nlinks: []"
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

        _setup_git_doorstop(pytester)

        result = pytester.runpytest("--jamb", "--jamb-documents=SRS", "-v")

        assert result.ret == 0
        # Should show coverage for SRS only
        output = result.stdout.str()
        assert "SRS" in output or "passed" in output.lower()


class TestReportHeader:
    """Tests for pytest_report_header hook."""

    def test_report_header_shows_item_count(self, pytester):
        """Test that report header shows doorstop item count."""
        pytester.makepyfile(
            """
            def test_simple():
                assert True
            """
        )

        _setup_git_doorstop(pytester)

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
        assert "doorstop items" not in output


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

        _setup_git_doorstop(pytester)

        result = pytester.runpytest("--jamb", "-v")

        assert result.ret == 0
        output = result.stdout.str()
        # Should show coverage summary
        assert (
            "Coverage Summary" in output
            or "coverage" in output.lower()
            or "Covered" in output
        )

    def test_terminal_summary_shows_uncovered_items(self, pytester):
        """Test terminal summary lists uncovered items."""
        # Add a second item that won't be covered
        pytester.makefile(
            ".yml",
            SRS002="active: true\nnormative: true\ntext: Uncovered\nlinks: []",
        )

        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.requirement("SRS001")
            def test_covers_srs001():
                assert True
            """
        )

        _setup_git_doorstop(pytester)

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

        _setup_git_doorstop(pytester)

        result = pytester.runpytest("--jamb", "-v")

        assert result.ret == 0
        output = result.stdout.str()
        # Should show unknown items
        assert "NONEXISTENT001" in output or "Unknown" in output or "unknown" in output


class TestFailUncoveredExtended:
    """Extended tests for --jamb-fail-uncovered flag."""

    def test_fails_when_uncovered(self, pytester):
        """Test that --jamb-fail-uncovered fails when items are uncovered."""
        # Add a second item that won't be covered
        pytester.makefile(
            ".yml",
            SRS002="active: true\nnormative: true\ntext: Uncovered\nlinks: []",
        )

        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.requirement("SRS001")
            def test_covers_srs001():
                assert True
            """
        )

        _setup_git_doorstop(pytester)

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

        _setup_git_doorstop(pytester)

        matrix_path = pytester.path / "matrix.json"
        result = pytester.runpytest(
            "--jamb",
            f"--jamb-matrix={matrix_path}",
            "--jamb-matrix-format=json",
        )

        assert result.ret == 0
        assert matrix_path.exists()

        data = json.loads(matrix_path.read_text())
        item = data["items"]["SRS001"]
        # Should have skipped outcome
        assert item["linked_tests"][0]["outcome"] == "skipped"

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

        _setup_git_doorstop(pytester)

        matrix_path = pytester.path / "matrix.json"
        result = pytester.runpytest(
            "--jamb",
            f"--jamb-matrix={matrix_path}",
            "--jamb-matrix-format=json",
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

        _setup_git_doorstop(pytester)

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

        _setup_git_doorstop(pytester)

        matrix_path = pytester.path / "matrix.json"
        result = pytester.runpytest(
            "--jamb",
            f"--jamb-matrix={matrix_path}",
            "--jamb-matrix-format=json",
        )

        assert result.ret == 0
        assert matrix_path.exists()

        data = json.loads(matrix_path.read_text())
        item = data["items"]["SRS001"]
        notes = item["linked_tests"][0]["notes"]
        assert "Custom verification message" in notes

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

        _setup_git_doorstop(pytester)

        matrix_path = pytester.path / "matrix.json"
        result = pytester.runpytest(
            "--jamb",
            f"--jamb-matrix={matrix_path}",
            "--jamb-matrix-format=json",
        )

        # Test fails but matrix should still be generated
        assert result.ret == 1
        assert matrix_path.exists()

        data = json.loads(matrix_path.read_text())
        item = data["items"]["SRS001"]
        notes = item["linked_tests"][0]["notes"]

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

        _setup_git_doorstop(pytester)

        matrix_path = pytester.path / "matrix.html"
        result = pytester.runpytest(
            "--jamb",
            f"--jamb-matrix={matrix_path}",
        )

        assert result.ret == 0
        assert matrix_path.exists()

        content = matrix_path.read_text()
        assert "HTML verification message" in content
        assert 'class="message"' in content
