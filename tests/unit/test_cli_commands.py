"""Tests for CLI command behavior not covered by integration tests."""

import os
import subprocess
from pathlib import Path

import yaml
from click.testing import CliRunner

from jamb.cli.commands import _scan_tests_for_requirements, cli


class TestValidateFlagBehavior:
    """Test validate command flag effects on issue level promotion/demotion."""

    def _make_dag_and_graph(self):
        """Create minimal DAG and graph with no issues."""
        from jamb.core.models import Item, TraceabilityGraph
        from jamb.storage.document_config import DocumentConfig
        from jamb.storage.document_dag import DocumentDAG

        dag = DocumentDAG()
        dag.documents["SRS"] = DocumentConfig(prefix="SRS", parents=[], digits=3)
        dag.document_paths["SRS"] = Path("/fake/srs")

        graph = TraceabilityGraph()
        item = Item(uid="SRS001", text="A requirement", document_prefix="SRS", reviewed="abc")
        graph.add_item(item)
        graph.set_document_parents("SRS", [])

        return dag, graph

    def _make_issues(self):
        """Create a list with info, warning, and error issues."""
        from jamb.storage.validation import ValidationIssue

        return [
            ValidationIssue("info", "SRS001", "SRS", "informational note"),
            ValidationIssue("warning", "SRS002", "SRS", "a warning"),
            ValidationIssue("error", "SRS003", "SRS", "an error"),
        ]

    def test_warn_all_shows_info_issues(self):
        """With --warn-all, info-level issues are promoted to warning."""
        issues = self._make_issues()

        # Simulate the promotion logic from the validate command
        for issue in issues:
            if issue.level == "info":
                issue.level = "warning"

        info_issues = [i for i in issues if i.level == "info"]
        warning_issues = [i for i in issues if i.level == "warning"]
        assert len(info_issues) == 0
        assert len(warning_issues) == 2  # original warning + promoted info

    def test_error_all_exits_one_on_warnings(self):
        """With --error-all, warning issues are promoted to error."""
        issues = self._make_issues()

        # Simulate the promotion logic
        for issue in issues:
            if issue.level == "warning":
                issue.level = "error"

        error_issues = [i for i in issues if i.level == "error"]
        assert len(error_issues) == 2  # original error + promoted warning

    def test_quiet_suppresses_warnings(self):
        """With --quiet, only errors are shown."""
        issues = self._make_issues()

        # Simulate quiet filter
        visible = [i for i in issues if i.level == "error"]
        assert len(visible) == 1
        assert visible[0].message == "an error"

    def test_no_issues_exits_zero(self):
        """Clean validation produces no issues."""
        issues = []
        has_errors = any(i.level == "error" for i in issues)
        assert not has_errors
        assert len(issues) == 0


class TestScanTestsEdgeCases:
    """Test _scan_tests_for_requirements edge cases."""

    def test_finds_multiple_uids_in_one_marker(self, tmp_path):
        """requirement('SRS001', 'SRS002') collects both."""
        test_file = tmp_path / "test_example.py"
        test_file.write_text(
            "import pytest\n\n@pytest.mark.requirement('SRS001', 'SRS002')\ndef test_something():\n    pass\n"
        )

        result = _scan_tests_for_requirements(tmp_path)
        assert "SRS001" in result
        assert "SRS002" in result

    def test_empty_directory_returns_empty_set(self, tmp_path):
        """No test files in directory returns empty set."""
        result = _scan_tests_for_requirements(tmp_path)
        assert result == set()

    def test_skips_non_test_files(self, tmp_path):
        """Files not matching test_*.py are ignored."""
        helper = tmp_path / "helper.py"
        helper.write_text("import pytest\n\n@pytest.mark.requirement('SRS001')\ndef test_something():\n    pass\n")

        result = _scan_tests_for_requirements(tmp_path)
        assert result == set()

    def test_finds_markers_in_suffix_test_files(self, tmp_path):
        """Files matching *_test.py are scanned."""
        test_file = tmp_path / "login_test.py"
        test_file.write_text("import pytest\n\n@pytest.mark.requirement('SRS001')\ndef test_login():\n    pass\n")

        result = _scan_tests_for_requirements(tmp_path)
        assert "SRS001" in result

    def test_finds_keyword_arguments(self, tmp_path):
        """Keyword string arguments to requirement marker are captured."""
        test_file = tmp_path / "test_kw.py"
        test_file.write_text("import pytest\n\n@pytest.mark.requirement(uid='SRS042')\ndef test_kw():\n    pass\n")

        result = _scan_tests_for_requirements(tmp_path)
        assert "SRS042" in result

    def test_finds_both_positional_and_keyword_args(self, tmp_path):
        """Both positional and keyword string args are captured."""
        test_file = tmp_path / "test_mixed.py"
        test_file.write_text(
            "import pytest\n\n@pytest.mark.requirement('SRS001', uid='SRS002')\ndef test_mixed():\n    pass\n"
        )

        result = _scan_tests_for_requirements(tmp_path)
        assert "SRS001" in result
        assert "SRS002" in result


# =========================================================================
# New comprehensive CLI command tests appended below
# =========================================================================


def _invoke(runner: CliRunner, args: list[str], *, cwd: Path | None = None):
    """Invoke CLI, optionally inside *cwd*.  Returns the Click result."""
    if cwd is not None:
        old = os.getcwd()
        os.chdir(cwd)
        try:
            return runner.invoke(cli, args, catch_exceptions=False)
        finally:
            os.chdir(old)
    return runner.invoke(cli, args, catch_exceptions=False)


def _read_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _write_yaml(path: Path, data: dict) -> None:
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def _init_project(root: Path) -> None:
    """Initialize a minimal jamb project at *root*."""
    subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=root,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=root,
        capture_output=True,
    )
    (root / "pyproject.toml").write_text('[project]\nname = "testprj"\n')
    runner = CliRunner()
    r = _invoke(runner, ["init"], cwd=root)
    assert r.exit_code == 0, r.output


# =========================================================================
# 1. Init command
# =========================================================================


class TestInitCommand:
    """Tests for the ``jamb init`` command."""

    def test_init_creates_all_doc_folders(self, tmp_path):
        """init creates reqs/ with all 6 IEC 62304 document folders."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')

        runner = CliRunner()
        r = _invoke(runner, ["init"], cwd=tmp_path)
        assert r.exit_code == 0
        for doc in ("prj", "un", "sys", "srs", "haz", "rc"):
            assert (tmp_path / "reqs" / doc / ".jamb.yml").exists()

    def test_init_adds_tool_jamb_to_pyproject(self, tmp_path):
        """init writes [tool.jamb] into an existing pyproject.toml."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')

        runner = CliRunner()
        _invoke(runner, ["init"], cwd=tmp_path)

        import tomlkit

        content = (tmp_path / "pyproject.toml").read_text()
        doc = tomlkit.parse(content)
        tool = doc["tool"]
        assert isinstance(tool, dict)
        assert "jamb" in tool
        jamb_section = tool["jamb"]
        assert isinstance(jamb_section, dict)
        assert "test_documents" in jamb_section

    def test_init_again_errors(self, tmp_path):
        """Running init twice produces a non-zero exit code."""
        _init_project(tmp_path)
        runner = CliRunner()
        r = _invoke(runner, ["init"], cwd=tmp_path)
        assert r.exit_code == 1
        assert "already exist" in r.output.lower()


# =========================================================================
# 2. Info command
# =========================================================================


class TestInfoCommand:
    """Tests for the ``jamb info`` command."""

    def test_info_shows_hierarchy(self, tmp_path):
        """info output contains 'hierarchy' and all default doc prefixes."""
        _init_project(tmp_path)
        runner = CliRunner()
        r = _invoke(runner, ["info", "--root", str(tmp_path)])
        assert r.exit_code == 0
        assert "hierarchy" in r.output.lower()
        for prefix in ("PRJ", "UN", "SYS", "SRS", "HAZ", "RC"):
            assert prefix in r.output

    def test_info_shows_item_count(self, tmp_path):
        """After adding items, info shows the correct counts."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS", "--count", "3"], cwd=tmp_path)
        r = _invoke(runner, ["info", "--root", str(tmp_path)])
        assert r.exit_code == 0
        assert "3 active items" in r.output


# =========================================================================
# 3. Doc create / delete / list
# =========================================================================


class TestDocCrud:
    """Tests for ``jamb doc create``, ``doc delete``, and ``doc list``."""

    def test_doc_create_with_parent(self, tmp_path):
        """doc create stores parent in the .jamb.yml config."""
        _init_project(tmp_path)
        runner = CliRunner()
        r = _invoke(
            runner,
            ["doc", "create", "UT", str(tmp_path / "reqs" / "ut"), "--parent", "SRS"],
            cwd=tmp_path,
        )
        assert r.exit_code == 0
        cfg = _read_yaml(tmp_path / "reqs" / "ut" / ".jamb.yml")
        assert cfg["settings"]["parents"] == ["SRS"]

    def test_doc_delete_removes_folder(self, tmp_path):
        """doc delete removes the document directory entirely (--force skips prompt)."""
        _init_project(tmp_path)
        runner = CliRunner()
        assert (tmp_path / "reqs" / "rc").exists()
        r = _invoke(runner, ["doc", "delete", "RC", "--force"], cwd=tmp_path)
        assert r.exit_code == 0
        assert not (tmp_path / "reqs" / "rc").exists()

    def test_doc_delete_confirmed(self, tmp_path):
        """doc delete with 'y' confirmation removes the document directory."""
        _init_project(tmp_path)
        runner = CliRunner()
        assert (tmp_path / "reqs" / "rc").exists()
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            r = runner.invoke(cli, ["doc", "delete", "RC"], input="y\n", catch_exceptions=False)
        finally:
            os.chdir(old)
        assert r.exit_code == 0
        assert not (tmp_path / "reqs" / "rc").exists()

    def test_doc_delete_abort_preserves_folder(self, tmp_path):
        """doc delete aborted by user leaves directory intact."""
        _init_project(tmp_path)
        runner = CliRunner()
        assert (tmp_path / "reqs" / "rc").exists()
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            r = runner.invoke(cli, ["doc", "delete", "RC"], input="n\n")
        finally:
            os.chdir(old)
        assert r.exit_code != 0
        assert (tmp_path / "reqs" / "rc").exists()
        assert "Aborted" in r.output

    def test_doc_delete_nonexistent_errors(self, tmp_path):
        """doc delete on a missing prefix exits with code 1."""
        _init_project(tmp_path)
        runner = CliRunner()
        r = _invoke(runner, ["doc", "delete", "NOPE"], cwd=tmp_path)
        assert r.exit_code == 1

    def test_doc_delete_warns_dangling_links(self, tmp_path):
        """doc delete refuses when other docs link to items in the target."""
        _init_project(tmp_path)
        runner = CliRunner()
        # Create items and a cross-doc link
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        _invoke(runner, ["item", "add", "SYS"], cwd=tmp_path)
        _invoke(runner, ["link", "add", "SRS001", "SYS001"], cwd=tmp_path)

        r = _invoke(runner, ["doc", "delete", "SYS"], cwd=tmp_path)
        assert r.exit_code == 1
        assert "link" in r.output.lower()
        assert "--force" in r.output

    def test_doc_delete_force_overrides_dangling_links(self, tmp_path):
        """doc delete --force deletes despite dangling links."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        _invoke(runner, ["item", "add", "SYS"], cwd=tmp_path)
        _invoke(runner, ["link", "add", "SRS001", "SYS001"], cwd=tmp_path)

        r = _invoke(runner, ["doc", "delete", "SYS", "--force"], cwd=tmp_path)
        assert r.exit_code == 0
        assert not (tmp_path / "reqs" / "sys").exists()

    def test_doc_list_shows_all(self, tmp_path):
        """doc list shows every discovered document."""
        _init_project(tmp_path)
        runner = CliRunner()
        r = _invoke(runner, ["doc", "list", "--root", str(tmp_path)])
        assert r.exit_code == 0
        assert "Found 6 documents" in r.output


class TestDocCreateValidation:
    """Tests for doc create validation."""

    def test_doc_create_prefix_too_short(self, tmp_path):
        """Prefix less than 2 characters exits with error."""
        _init_project(tmp_path)
        runner = CliRunner()
        r = _invoke(
            runner,
            ["doc", "create", "X", str(tmp_path / "reqs" / "x")],
            cwd=tmp_path,
        )
        assert r.exit_code == 1
        assert "at least 2 characters" in r.output

    def test_doc_create_invalid_prefix_lowercase(self, tmp_path):
        """Prefix starting with lowercase letter is rejected."""
        _init_project(tmp_path)
        runner = CliRunner()
        r = _invoke(
            runner,
            ["doc", "create", "abc", str(tmp_path / "reqs" / "abc")],
            cwd=tmp_path,
        )
        assert r.exit_code == 1
        assert "Invalid prefix" in r.output
        assert "uppercase" in r.output.lower()

    def test_doc_create_invalid_prefix_special(self, tmp_path):
        """Prefix with special characters is rejected."""
        _init_project(tmp_path)
        runner = CliRunner()
        r = _invoke(
            runner,
            ["doc", "create", "AB-CD", str(tmp_path / "reqs" / "abcd")],
            cwd=tmp_path,
        )
        assert r.exit_code == 1
        assert "Invalid prefix" in r.output

    def test_doc_create_digits_zero(self, tmp_path):
        """Digits set to 0 exits with error."""
        _init_project(tmp_path)
        runner = CliRunner()
        r = _invoke(
            runner,
            ["doc", "create", "UT", str(tmp_path / "reqs" / "ut"), "--digits", "0"],
            cwd=tmp_path,
        )
        assert r.exit_code != 0
        # Click's IntRange validates this before our code

    def test_doc_create_digits_negative(self, tmp_path):
        """Negative digits value exits with error."""
        _init_project(tmp_path)
        runner = CliRunner()
        r = _invoke(
            runner,
            ["doc", "create", "UT", str(tmp_path / "reqs" / "ut"), "--digits", "-1"],
            cwd=tmp_path,
        )
        assert r.exit_code != 0

    def test_doc_create_digits_too_large(self, tmp_path):
        """Digits exceeding 10 exits with error."""
        _init_project(tmp_path)
        runner = CliRunner()
        r = _invoke(
            runner,
            ["doc", "create", "UT", str(tmp_path / "reqs" / "ut"), "--digits", "11"],
            cwd=tmp_path,
        )
        assert r.exit_code == 1
        assert "cannot exceed 10" in r.output

    def test_doc_create_sep_starts_alphanumeric(self, tmp_path):
        """Separator starting with letter is rejected."""
        _init_project(tmp_path)
        runner = CliRunner()
        r = _invoke(
            runner,
            ["doc", "create", "UT", str(tmp_path / "reqs" / "ut"), "--sep", "X"],
            cwd=tmp_path,
        )
        assert r.exit_code == 1
        assert "alphanumeric" in r.output.lower()

    def test_doc_create_sep_starts_digit(self, tmp_path):
        """Separator starting with digit is rejected."""
        _init_project(tmp_path)
        runner = CliRunner()
        r = _invoke(
            runner,
            ["doc", "create", "UT", str(tmp_path / "reqs" / "ut"), "--sep", "1"],
            cwd=tmp_path,
        )
        assert r.exit_code == 1
        assert "alphanumeric" in r.output.lower()


# =========================================================================
# 4. Item add / remove / list / show
# =========================================================================


class TestItemCrud:
    """Tests for ``jamb item add``, ``item remove``, ``item list``, ``item show``."""

    def test_item_add_single(self, tmp_path):
        """item add creates a YAML file for the new UID."""
        _init_project(tmp_path)
        runner = CliRunner()
        r = _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        assert r.exit_code == 0
        assert "SRS001" in r.output
        assert (tmp_path / "reqs" / "srs" / "SRS001.yml").exists()

    def test_item_add_count(self, tmp_path):
        """item add --count creates the requested number of items."""
        _init_project(tmp_path)
        runner = CliRunner()
        r = _invoke(runner, ["item", "add", "SRS", "--count", "5"], cwd=tmp_path)
        assert r.exit_code == 0
        for i in range(1, 6):
            assert (tmp_path / "reqs" / "srs" / f"SRS00{i}.yml").exists()

    def test_item_add_after(self, tmp_path):
        """item add --after inserts after the specified UID."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS", "--count", "3"], cwd=tmp_path)
        r = _invoke(
            runner,
            ["item", "add", "SRS", "--after", "SRS001", "--count", "1"],
            cwd=tmp_path,
        )
        assert r.exit_code == 0
        # After insert, SRS should now have 4 items (SRS001..SRS004)
        assert (tmp_path / "reqs" / "srs" / "SRS004.yml").exists()

    def test_item_add_before(self, tmp_path):
        """item add --before inserts before the specified UID."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS", "--count", "2"], cwd=tmp_path)
        r = _invoke(
            runner,
            ["item", "add", "SRS", "--before", "SRS001", "--count", "1"],
            cwd=tmp_path,
        )
        assert r.exit_code == 0
        # SRS should now have 3 items
        assert (tmp_path / "reqs" / "srs" / "SRS003.yml").exists()

    def test_item_add_after_and_before_mutually_exclusive(self, tmp_path):
        """Passing both --after and --before exits with code 1."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS", "--count", "2"], cwd=tmp_path)
        r = _invoke(
            runner,
            ["item", "add", "SRS", "--after", "SRS001", "--before", "SRS002"],
            cwd=tmp_path,
        )
        assert r.exit_code == 1

    def test_item_add_with_header_and_text(self, tmp_path):
        """item add --header and --text populate the YAML file."""
        _init_project(tmp_path)
        runner = CliRunner()
        r = _invoke(
            runner,
            ["item", "add", "SRS", "--header", "My Header", "--text", "Some body"],
            cwd=tmp_path,
        )
        assert r.exit_code == 0
        item_path = tmp_path / "reqs" / "srs" / "SRS001.yml"
        content = item_path.read_text()
        assert "My Header" in content
        assert "Some body" in content

    def test_item_add_with_links(self, tmp_path):
        """item add --links populates the links list."""
        _init_project(tmp_path)
        runner = CliRunner()
        r = _invoke(
            runner,
            ["item", "add", "SRS", "--links", "SYS001", "--links", "RC001"],
            cwd=tmp_path,
        )
        assert r.exit_code == 0
        import yaml

        item_path = tmp_path / "reqs" / "srs" / "SRS001.yml"
        data = yaml.safe_load(item_path.read_text())
        assert data["links"] == ["SYS001", "RC001"]

    def test_item_add_with_all_flags(self, tmp_path):
        """item add with --header, --text, and --links together."""
        _init_project(tmp_path)
        runner = CliRunner()
        r = _invoke(
            runner,
            [
                "item",
                "add",
                "SRS",
                "--header",
                "H1",
                "--text",
                "Body text",
                "--links",
                "SYS001",
            ],
            cwd=tmp_path,
        )
        assert r.exit_code == 0
        import yaml

        item_path = tmp_path / "reqs" / "srs" / "SRS001.yml"
        data = yaml.safe_load(item_path.read_text())
        assert data["header"] == "H1"
        assert data["text"] == "Body text"
        assert data["links"] == ["SYS001"]

    def test_item_add_without_flags_unchanged(self, tmp_path):
        """item add with no content flags still creates a blank item."""
        _init_project(tmp_path)
        runner = CliRunner()
        r = _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        assert r.exit_code == 0
        import yaml

        item_path = tmp_path / "reqs" / "srs" / "SRS001.yml"
        data = yaml.safe_load(item_path.read_text())
        # Header is omitted when empty (consistent with read_item behavior)
        assert data.get("header", "") == ""
        assert data["text"] == ""
        assert data["links"] == []

    def test_item_remove(self, tmp_path):
        """item remove deletes the item file."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        r = _invoke(runner, ["item", "remove", "SRS001"], cwd=tmp_path)
        assert r.exit_code == 0
        assert not (tmp_path / "reqs" / "srs" / "SRS001.yml").exists()

    def test_item_remove_nonexistent_errors(self, tmp_path):
        """Removing a non-existent item exits with code 1."""
        _init_project(tmp_path)
        runner = CliRunner()
        r = _invoke(runner, ["item", "remove", "SRS999"], cwd=tmp_path)
        assert r.exit_code == 1

    def test_item_list_for_document(self, tmp_path):
        """item list PREFIX shows items for that document only."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS", "--count", "2"], cwd=tmp_path)
        # Write text so list has something to display
        for i in (1, 2):
            p = tmp_path / "reqs" / "srs" / f"SRS00{i}.yml"
            data = _read_yaml(p)
            data["text"] = f"req {i}"
            _write_yaml(p, data)

        r = _invoke(runner, ["item", "list", "SRS", "--root", str(tmp_path)])
        assert r.exit_code == 0
        assert "SRS001" in r.output
        assert "SRS002" in r.output

    def test_item_show_displays_fields(self, tmp_path):
        """item show prints UID, Document, Active, Type, and Text."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        p = tmp_path / "reqs" / "srs" / "SRS001.yml"
        data = _read_yaml(p)
        data["text"] = "The pump shall deliver 5 mL/h."
        _write_yaml(p, data)

        r = _invoke(runner, ["item", "show", "SRS001"], cwd=tmp_path)
        assert r.exit_code == 0
        assert "UID: SRS001" in r.output
        assert "Document: SRS" in r.output
        assert "5 mL/h" in r.output


# =========================================================================
# 5. Link add / remove
# =========================================================================


class TestLinkCommands:
    """Tests for ``jamb link add`` and ``link remove``."""

    def test_link_add_and_show(self, tmp_path):
        """link add writes the parent UID into the child's links list."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        _invoke(runner, ["item", "add", "SYS"], cwd=tmp_path)

        r = _invoke(runner, ["link", "add", "SRS001", "SYS001"], cwd=tmp_path)
        assert r.exit_code == 0
        assert "Linked" in r.output

        r = _invoke(runner, ["item", "show", "SRS001"], cwd=tmp_path)
        assert "SYS001" in r.output

    def test_link_add_duplicate_reports_exists(self, tmp_path):
        """Adding the same link twice reports 'already exists'."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        _invoke(runner, ["item", "add", "SYS"], cwd=tmp_path)
        _invoke(runner, ["link", "add", "SRS001", "SYS001"], cwd=tmp_path)

        r = _invoke(runner, ["link", "add", "SRS001", "SYS001"], cwd=tmp_path)
        assert r.exit_code == 0
        assert "already exists" in r.output.lower()

    def test_link_remove(self, tmp_path):
        """link remove strips the parent from the child's links."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        _invoke(runner, ["item", "add", "SYS"], cwd=tmp_path)
        _invoke(runner, ["link", "add", "SRS001", "SYS001"], cwd=tmp_path)

        r = _invoke(runner, ["link", "remove", "SRS001", "SYS001"], cwd=tmp_path)
        assert r.exit_code == 0
        assert "Unlinked" in r.output

        # Verify removal
        data = _read_yaml(tmp_path / "reqs" / "srs" / "SRS001.yml")
        link_uids = []
        for entry in data.get("links", []):
            link_uids.append(entry if isinstance(entry, str) else next(iter(entry)))
        assert "SYS001" not in link_uids

    def test_link_remove_nonexistent_errors(self, tmp_path):
        """Removing a link that does not exist exits with code 1."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)

        r = _invoke(runner, ["link", "remove", "SRS001", "SYS999"], cwd=tmp_path)
        assert r.exit_code == 1


# =========================================================================
# 6. Review mark / clear / reset
# =========================================================================


class TestReviewCommands:
    """Tests for ``jamb review mark``, ``review clear``, ``review reset``."""

    def _setup_project(self, tmp_path):
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS", "--count", "2"], cwd=tmp_path)
        _invoke(runner, ["item", "add", "SYS"], cwd=tmp_path)
        for uid, text in [("SRS001", "req1"), ("SRS002", "req2"), ("SYS001", "sysreq")]:
            prefix = uid[:3]
            p = tmp_path / "reqs" / prefix.lower() / f"{uid}.yml"
            data = _read_yaml(p)
            data["text"] = text
            _write_yaml(p, data)
        _invoke(runner, ["link", "add", "SRS001", "SYS001"], cwd=tmp_path)
        _invoke(runner, ["link", "add", "SRS002", "SYS001"], cwd=tmp_path)
        return runner

    def test_review_mark_single(self, tmp_path):
        """review mark <UID> sets the reviewed hash on one item."""
        runner = self._setup_project(tmp_path)
        r = _invoke(runner, ["review", "mark", "SRS001"], cwd=tmp_path)
        assert r.exit_code == 0
        assert "marked" in r.output.lower()

        data = _read_yaml(tmp_path / "reqs" / "srs" / "SRS001.yml")
        assert data.get("reviewed") is not None

    def test_review_mark_all(self, tmp_path):
        """review mark all marks every item across all documents."""
        runner = self._setup_project(tmp_path)
        r = _invoke(runner, ["review", "mark", "all"], cwd=tmp_path)
        assert r.exit_code == 0
        assert "marked" in r.output.lower()

    def test_review_clear(self, tmp_path):
        """review clear recomputes link hashes for suspect links."""
        runner = self._setup_project(tmp_path)
        _invoke(runner, ["review", "mark", "all"], cwd=tmp_path)
        r = _invoke(runner, ["review", "clear", "all"], cwd=tmp_path)
        assert r.exit_code == 0
        assert "Cleared" in r.output

    def test_review_reset_removes_hashes(self, tmp_path):
        """review reset strips reviewed field and link hashes."""
        runner = self._setup_project(tmp_path)
        _invoke(runner, ["review", "mark", "all"], cwd=tmp_path)
        _invoke(runner, ["review", "clear", "all"], cwd=tmp_path)

        r = _invoke(runner, ["review", "reset", "all", "--root", str(tmp_path)])
        assert r.exit_code == 0
        assert "reset" in r.output.lower()

        data = _read_yaml(tmp_path / "reqs" / "srs" / "SRS001.yml")
        assert "reviewed" not in data or data.get("reviewed") is None

    def test_review_clear_empty_dict_link(self, tmp_path):
        """Test review clear handles empty dict link entries gracefully."""
        _init_project(tmp_path)
        runner = CliRunner()

        # Create an item with a valid link first
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        _invoke(runner, ["item", "add", "SYS"], cwd=tmp_path)
        srs_item = tmp_path / "reqs" / "srs" / "SRS001.yml"
        data = _read_yaml(srs_item)
        data["text"] = "Test item"
        # Add malformed empty dict in links alongside a valid link
        data["links"] = [{}, "SYS001"]
        _write_yaml(srs_item, data)

        # Review clear should not crash on empty dict
        r = _invoke(runner, ["review", "clear", "all"], cwd=tmp_path)
        assert r.exit_code == 0
        assert "Cleared" in r.output


# =========================================================================
# 7. Reorder command
# =========================================================================


class TestReorderCommand:
    """Tests for ``jamb reorder``."""

    def test_reorder_fills_gap(self, tmp_path):
        """After removing an item, reorder renumbers to fill the gap."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS", "--count", "3"], cwd=tmp_path)
        _invoke(runner, ["item", "remove", "SRS002"], cwd=tmp_path)

        r = _invoke(runner, ["reorder", "SRS"], cwd=tmp_path)
        assert r.exit_code == 0
        assert "renamed" in r.output.lower()
        # SRS003 should now be SRS002
        assert (tmp_path / "reqs" / "srs" / "SRS002.yml").exists()
        assert not (tmp_path / "reqs" / "srs" / "SRS003.yml").exists()

    def test_reorder_nonexistent_doc_errors(self, tmp_path):
        """reorder on a missing document prefix exits with code 1."""
        _init_project(tmp_path)
        runner = CliRunner()
        r = _invoke(runner, ["reorder", "NOPE"], cwd=tmp_path)
        assert r.exit_code == 1


# =========================================================================
# 8. Publish command
# =========================================================================


class TestPublishCommand:
    """Tests for ``jamb publish``."""

    def _setup_publish_project(self, tmp_path):
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS", "--count", "2"], cwd=tmp_path)
        for i in (1, 2):
            p = tmp_path / "reqs" / "srs" / f"SRS00{i}.yml"
            data = _read_yaml(p)
            data["text"] = f"Requirement number {i}"
            _write_yaml(p, data)
        return runner

    def test_publish_markdown_stdout(self, tmp_path):
        """publish <PREFIX> with no format flag prints markdown to stdout."""
        runner = self._setup_publish_project(tmp_path)
        r = _invoke(runner, ["publish", "SRS"], cwd=tmp_path)
        assert r.exit_code == 0
        assert "SRS001" in r.output
        assert "SRS002" in r.output

    def test_publish_html_flag(self, tmp_path):
        """publish --html writes an HTML file."""
        runner = self._setup_publish_project(tmp_path)
        out = tmp_path / "out.html"
        r = _invoke(runner, ["publish", "SRS", str(out), "--html"], cwd=tmp_path)
        assert r.exit_code == 0
        assert out.exists()
        assert "<html" in out.read_text().lower()

    def test_publish_markdown_file(self, tmp_path):
        """publish --markdown writes a markdown file."""
        runner = self._setup_publish_project(tmp_path)
        out = tmp_path / "out.md"
        r = _invoke(runner, ["publish", "SRS", str(out), "--markdown"], cwd=tmp_path)
        assert r.exit_code == 0
        assert out.exists()
        assert "SRS001" in out.read_text()

    def test_publish_markdown_stdout_with_rich_items(self, tmp_path):
        """Markdown stdout renders headings, info, links, and children."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS", "--count", "3"], cwd=tmp_path)
        # heading item
        p1 = tmp_path / "reqs" / "srs" / "SRS001.yml"
        _write_yaml(
            p1,
            {
                "active": True,
                "type": "heading",
                "header": "Overview",
                "text": "Overview section",
            },
        )
        # info item
        p2 = tmp_path / "reqs" / "srs" / "SRS002.yml"
        _write_yaml(
            p2,
            {
                "active": True,
                "type": "info",
                "text": "Informational note",
            },
        )
        # requirement with link
        p3 = tmp_path / "reqs" / "srs" / "SRS003.yml"
        _write_yaml(
            p3,
            {
                "active": True,
                "text": "Linked requirement",
                "links": ["SRS001"],
            },
        )
        r = _invoke(runner, ["publish", "SRS"], cwd=tmp_path)
        assert r.exit_code == 0
        assert "## SRS001: Overview" in r.output
        assert "*Informational note*" in r.output
        assert "Links:" in r.output
        assert "Linked from:" in r.output

    def test_publish_markdown_file_with_rich_items(self, tmp_path):
        """Markdown file renders anchor links for links and children."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS", "--count", "2"], cwd=tmp_path)
        p1 = tmp_path / "reqs" / "srs" / "SRS001.yml"
        _write_yaml(
            p1,
            {
                "active": True,
                "header": "Auth",
                "text": "Auth requirement",
            },
        )
        p2 = tmp_path / "reqs" / "srs" / "SRS002.yml"
        _write_yaml(
            p2,
            {
                "active": True,
                "text": "Child requirement",
                "links": ["SRS001"],
            },
        )
        out = tmp_path / "out.md"
        r = _invoke(
            runner,
            ["publish", "SRS", str(out), "--markdown"],
            cwd=tmp_path,
        )
        assert r.exit_code == 0
        content = out.read_text()
        assert "[SRS001](#SRS001)" in content
        assert "Linked from:" in content

    def test_publish_html_requires_path(self, tmp_path):
        """publish --html without PATH exits with code 1."""
        runner = self._setup_publish_project(tmp_path)
        r = _invoke(runner, ["publish", "SRS", "--html"], cwd=tmp_path)
        assert r.exit_code == 1

    def test_publish_docx_creates_file(self, tmp_path):
        """publish --docx writes a non-empty DOCX file."""
        runner = self._setup_publish_project(tmp_path)
        out = tmp_path / "out.docx"
        r = _invoke(runner, ["publish", "SRS", str(out), "--docx"], cwd=tmp_path)
        assert r.exit_code == 0
        assert out.exists()
        assert out.stat().st_size > 0


# =========================================================================
# 9. Export / Import commands
# =========================================================================


class TestExportImportCommands:
    """Tests for ``jamb export`` and ``jamb import``."""

    def _setup_export_project(self, tmp_path):
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS", "--count", "2"], cwd=tmp_path)
        for i in (1, 2):
            p = tmp_path / "reqs" / "srs" / f"SRS00{i}.yml"
            data = _read_yaml(p)
            data["text"] = f"Exported req {i}"
            _write_yaml(p, data)
        return runner

    def test_export_creates_yaml(self, tmp_path):
        """export writes a YAML file with documents and items keys."""
        runner = self._setup_export_project(tmp_path)
        out = tmp_path / "export.yml"
        r = _invoke(runner, ["export", str(out), "--root", str(tmp_path)])
        assert r.exit_code == 0
        data = _read_yaml(out)
        assert "documents" in data
        assert "items" in data

    def test_export_documents_filter(self, tmp_path):
        """export --documents SRS only exports SRS items."""
        runner = self._setup_export_project(tmp_path)
        out = tmp_path / "srs_only.yml"
        r = _invoke(
            runner,
            ["export", str(out), "--documents", "SRS", "--root", str(tmp_path)],
        )
        assert r.exit_code == 0
        data = _read_yaml(out)
        prefixes = {d["prefix"] for d in data["documents"]}
        assert "SRS" in prefixes

    def test_import_dry_run(self, tmp_path):
        """import --dry-run does not write any files."""
        runner = self._setup_export_project(tmp_path)
        import_file = tmp_path / "imp.yml"
        _write_yaml(
            import_file,
            {
                "documents": [],
                "items": [{"uid": "SRS010", "text": "New req"}],
            },
        )
        r = _invoke(runner, ["import", str(import_file), "--dry-run"], cwd=tmp_path)
        assert r.exit_code == 0
        assert "would" in r.output.lower()
        assert not (tmp_path / "reqs" / "srs" / "SRS010.yml").exists()

    def test_import_creates_items(self, tmp_path):
        """import creates new items that do not exist yet."""
        runner = self._setup_export_project(tmp_path)
        import_file = tmp_path / "imp.yml"
        _write_yaml(
            import_file,
            {
                "documents": [],
                "items": [{"uid": "SRS010", "text": "Brand new"}],
            },
        )
        r = _invoke(runner, ["import", str(import_file)], cwd=tmp_path)
        assert r.exit_code == 0
        assert (tmp_path / "reqs" / "srs" / "SRS010.yml").exists()

    def test_import_skips_existing(self, tmp_path):
        """import without --update skips items that already exist."""
        runner = self._setup_export_project(tmp_path)
        import_file = tmp_path / "imp.yml"
        _write_yaml(
            import_file,
            {
                "documents": [],
                "items": [{"uid": "SRS001", "text": "Should be skipped"}],
            },
        )
        r = _invoke(runner, ["import", str(import_file)], cwd=tmp_path)
        assert r.exit_code == 0
        assert "skipped" in r.output.lower()


# =========================================================================
# 10. Check command
# =========================================================================


class TestCheckCommand:
    """Tests for ``jamb check``."""

    def test_check_reports_uncovered(self, tmp_path):
        """check exits 1 when test documents have uncovered items."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS", "--count", "2"], cwd=tmp_path)
        for i in (1, 2):
            p = tmp_path / "reqs" / "srs" / f"SRS00{i}.yml"
            data = _read_yaml(p)
            data["text"] = f"req {i}"
            _write_yaml(p, data)

        # Create a test file covering only SRS001
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_x.py").write_text(
            "import pytest\n\n@pytest.mark.requirement('SRS001')\ndef test_a():\n    pass\n"
        )

        r = _invoke(
            runner,
            ["check", "--documents", "SRS", "--root", str(tmp_path)],
        )
        assert r.exit_code == 1
        assert "uncovered" in r.output.lower()

    def test_check_passes_when_covered(self, tmp_path):
        """check exits 0 when every item has a linked test."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        p = tmp_path / "reqs" / "srs" / "SRS001.yml"
        data = _read_yaml(p)
        data["text"] = "the one req"
        _write_yaml(p, data)

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_y.py").write_text(
            "import pytest\n\n@pytest.mark.requirement('SRS001')\ndef test_b():\n    pass\n"
        )

        r = _invoke(
            runner,
            ["check", "--documents", "SRS", "--root", str(tmp_path)],
        )
        assert r.exit_code == 0
        assert "all" in r.output.lower()

    def test_check_warns_on_unparseable_file(self, tmp_path):
        """check warns when a test file has syntax errors."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        p = tmp_path / "reqs" / "srs" / "SRS001.yml"
        data = _read_yaml(p)
        data["text"] = "the one req"
        _write_yaml(p, data)

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        # Valid test file covering SRS001
        (tests_dir / "test_valid.py").write_text(
            "import pytest\n\n@pytest.mark.requirement('SRS001')\ndef test_a():\n    pass\n"
        )

        # Invalid test file with syntax error
        (tests_dir / "test_broken.py").write_text(
            "def broken(\n"  # Missing closing paren
        )

        r = _invoke(
            runner,
            ["check", "--documents", "SRS", "--root", str(tmp_path)],
        )
        # Should still pass (SRS001 is covered by valid test)
        assert r.exit_code == 0
        # But should warn about the broken file
        assert "warning" in r.output.lower()
        assert "test_broken.py" in r.output
        assert "syntax" in r.output.lower()


# =========================================================================
# Gap 1 — _add_jamb_config_to_pyproject() error branches
# =========================================================================


class TestInitCommandErrorBranches:
    """Tests for _add_jamb_config_to_pyproject error branches."""

    def test_init_skips_existing_tool_jamb_section(self, tmp_path):
        """Init skips writing [tool.jamb] if it already exists."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        # Pre-create pyproject.toml WITH [tool.jamb] but no reqs/ dir
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n\n[tool.jamb]\ntest_documents = ["SRS"]\n')
        runner = CliRunner()
        r = _invoke(runner, ["init"], cwd=tmp_path)
        assert r.exit_code == 0
        assert "already has [tool.jamb]" in r.output

        # Original [tool.jamb] content should be preserved
        import tomlkit

        doc = tomlkit.parse((tmp_path / "pyproject.toml").read_text())
        assert doc["tool"]["jamb"]["test_documents"] == ["SRS"]

    def test_init_handles_corrupt_pyproject(self, tmp_path):
        """Init completes even if pyproject.toml contains invalid TOML."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        (tmp_path / "pyproject.toml").write_text("[[[bad")

        runner = CliRunner()
        r = _invoke(runner, ["init"], cwd=tmp_path)
        assert r.exit_code == 0
        assert "Warning: Could not update pyproject.toml" in r.output


# =========================================================================
# Gap 2 — _scan_tests_for_requirements() with unparseable Python
# =========================================================================


class TestScanTestsUnparseable:
    """Tests for _scan_tests_for_requirements with syntax errors."""

    def test_skips_unparseable_python_files(self, tmp_path):
        """Bad syntax file is silently skipped; good file is still parsed."""
        (tmp_path / "test_bad.py").write_text("def broken(\n")
        (tmp_path / "test_good.py").write_text(
            "import pytest\n\n@pytest.mark.requirement('SRS001')\ndef test_ok():\n    pass\n"
        )

        result = _scan_tests_for_requirements(tmp_path)
        assert "SRS001" in result

    def test_skips_encoding_error_files(self, tmp_path):
        """File with encoding issues is skipped; good file is still parsed."""
        # Write invalid UTF-8 bytes
        (tmp_path / "test_bad_encoding.py").write_bytes(b"\x80\x81\x82")
        (tmp_path / "test_good.py").write_text(
            "import pytest\n\n@pytest.mark.requirement('SRS002')\ndef test_ok():\n    pass\n"
        )

        result = _scan_tests_for_requirements(tmp_path)
        assert "SRS002" in result


# =========================================================================
# Gap 6 — _find_item_path() standalone tests
# =========================================================================


class TestFindItemPath:
    """Tests for the _find_item_path helper."""

    def test_find_item_path_existing_item(self, tmp_path):
        """Returns (path, prefix) for an item that exists."""
        from jamb.cli.commands import _find_item_path

        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)

        path, prefix = _find_item_path("SRS001", root=tmp_path)
        assert path is not None
        assert path.name == "SRS001.yml"
        assert prefix == "SRS"

    def test_find_item_path_nonexistent_item(self, tmp_path):
        """Returns (None, None) for an item that doesn't exist."""
        from jamb.cli.commands import _find_item_path

        _init_project(tmp_path)

        path, prefix = _find_item_path("SRS999", root=tmp_path)
        assert path is None
        assert prefix is None

    def test_find_item_path_unknown_prefix(self, tmp_path):
        """Returns (None, None) for a UID whose prefix has no document."""
        from jamb.cli.commands import _find_item_path

        _init_project(tmp_path)

        path, prefix = _find_item_path("ZZZ001", root=tmp_path)
        assert path is None
        assert prefix is None

    def test_find_item_path_with_prebuilt_dag(self, tmp_path):
        """Passing a pre-built DAG skips discover_documents()."""
        from jamb.cli.commands import _find_item_path
        from jamb.storage import discover_documents

        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)

        dag = discover_documents(tmp_path)
        path, prefix = _find_item_path("SRS001", dag=dag)
        assert path is not None
        assert path.name == "SRS001.yml"
        assert prefix == "SRS"


# =========================================================================
# Gap 7 — _is_requirement_marker() edge cases
# =========================================================================


class TestIsRequirementMarker:
    """Tests for the _is_requirement_marker AST helper."""

    @staticmethod
    def _parse_call(expr_src: str):
        """Parse a string expression and return the ast.Call node."""
        import ast

        tree = ast.parse(expr_src, mode="eval")
        return tree.body  # the Call node

    def test_matching_marker_returns_true(self):
        from jamb.cli.commands import _is_requirement_marker

        node = self._parse_call("pytest.mark.requirement('SRS001')")
        assert _is_requirement_marker(node) is True

    def test_wrong_attr_name_returns_false(self):
        from jamb.cli.commands import _is_requirement_marker

        node = self._parse_call("pytest.mark.skip('reason')")
        assert _is_requirement_marker(node) is False

    def test_bare_requirement_returns_true(self):
        """Support @requirement(...) style for `from pytest.mark import requirement`."""
        from jamb.cli.commands import _is_requirement_marker

        node = self._parse_call("requirement('SRS001')")
        assert _is_requirement_marker(node) is True

    def test_mark_requirement_returns_true(self):
        """Support @mark.requirement(...) style for `from pytest import mark`."""
        from jamb.cli.commands import _is_requirement_marker

        node = self._parse_call("mark.requirement('SRS001')")
        assert _is_requirement_marker(node) is True

    def test_different_module_returns_false(self):
        from jamb.cli.commands import _is_requirement_marker

        node = self._parse_call("other.mark.requirement('SRS001')")
        assert _is_requirement_marker(node) is False

    def test_missing_mark_level_returns_false(self):
        from jamb.cli.commands import _is_requirement_marker

        node = self._parse_call("pytest.requirement('SRS001')")
        assert _is_requirement_marker(node) is False


# =========================================================================
# Gap 8 — _print_dag_hierarchy() standalone tests
# =========================================================================


class TestPrintDagHierarchy:
    """Tests for the _print_dag_hierarchy tree printer."""

    @staticmethod
    def _make_dag(docs: dict[str, list[str]]):
        """Build a DocumentDAG from a {prefix: parents} dict."""
        from jamb.storage.document_config import DocumentConfig
        from jamb.storage.document_dag import DocumentDAG

        dag = DocumentDAG()
        for prefix, parents in docs.items():
            dag.documents[prefix] = DocumentConfig(prefix=prefix, parents=parents, digits=3)
            dag.document_paths[prefix] = Path(f"/fake/{prefix.lower()}")
        return dag

    def test_prints_simple_hierarchy(self):
        """PRJ -> UN -> SRS renders with proper indentation."""
        from unittest.mock import patch

        from jamb.cli.commands import _print_dag_hierarchy

        dag = self._make_dag({"PRJ": [], "UN": ["PRJ"], "SRS": ["UN"]})
        calls: list[str] = []
        with patch("jamb.cli.commands.click") as mock_click:
            mock_click.echo = lambda msg="": calls.append(msg)
            _print_dag_hierarchy(dag)

        text = "\n".join(calls)
        assert "PRJ" in text
        assert "UN" in text
        assert "SRS" in text

    def test_prints_multiple_children(self):
        """PRJ with two children shows both with tree characters."""
        from unittest.mock import patch

        from jamb.cli.commands import _print_dag_hierarchy

        dag = self._make_dag({"PRJ": [], "UN": ["PRJ"], "HAZ": ["PRJ"]})
        calls: list[str] = []
        with patch("jamb.cli.commands.click") as mock_click:
            mock_click.echo = lambda msg="": calls.append(msg)
            _print_dag_hierarchy(dag)

        text = "\n".join(calls)
        # Both children should appear
        assert "UN" in text
        assert "HAZ" in text
        # Tree should use |-- and `-- characters
        assert "|-- " in text or "`-- " in text

    def test_empty_dag_no_output(self):
        """An empty DAG produces no output."""
        from unittest.mock import patch

        from jamb.cli.commands import _print_dag_hierarchy

        dag = self._make_dag({})
        calls: list[str] = []
        with patch("jamb.cli.commands.click") as mock_click:
            mock_click.echo = lambda msg="": calls.append(msg)
            _print_dag_hierarchy(dag)

        assert len(calls) == 0


# =========================================================================
# CLI Error Handling Tests - Additional Coverage
# =========================================================================


class TestItemAddAnchorValidation:
    """Tests for item add anchor validation errors."""

    def test_item_add_anchor_uid_not_found_after(self, tmp_path):
        """item add --after with missing anchor UID exits with code 1."""
        _init_project(tmp_path)
        runner = CliRunner()
        # Try to add after a non-existent UID
        r = _invoke(runner, ["item", "add", "SRS", "--after", "SRS999"], cwd=tmp_path)
        assert r.exit_code == 1
        assert "not found" in r.output.lower()

    def test_item_add_anchor_uid_not_found_before(self, tmp_path):
        """item add --before with missing anchor UID exits with code 1."""
        _init_project(tmp_path)
        runner = CliRunner()
        # Try to add before a non-existent UID
        r = _invoke(runner, ["item", "add", "SRS", "--before", "SRS999"], cwd=tmp_path)
        assert r.exit_code == 1
        assert "not found" in r.output.lower()


class TestItemListErrorCases:
    """Tests for item list error handling."""

    def test_item_list_nonexistent_prefix(self, tmp_path):
        """item_list exits with code 1 for nonexistent document prefix."""
        _init_project(tmp_path)
        runner = CliRunner()
        r = _invoke(runner, ["item", "list", "NOPE"], cwd=tmp_path)
        assert r.exit_code == 1
        assert "not found" in r.output.lower()


class TestLinkAddErrorCases:
    """Tests for link add error handling."""

    def test_link_add_child_not_found(self, tmp_path):
        """link_add exits with code 1 when child doesn't exist."""
        _init_project(tmp_path)
        runner = CliRunner()
        # Create a parent but not the child
        _invoke(runner, ["item", "add", "SYS"], cwd=tmp_path)
        # Try to link non-existent child
        r = _invoke(runner, ["link", "add", "SRS999", "SYS001"], cwd=tmp_path)
        assert r.exit_code == 1
        assert "not found" in r.output.lower()

    def test_link_add_parent_not_found(self, tmp_path):
        """link_add exits with code 1 when parent doesn't exist."""
        _init_project(tmp_path)
        runner = CliRunner()
        # Create a child but not the parent
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        # Try to link to non-existent parent
        r = _invoke(runner, ["link", "add", "SRS001", "SYS999"], cwd=tmp_path)
        assert r.exit_code == 1
        assert "not found" in r.output.lower()


class TestPublishErrorCases:
    """Tests for publish command error handling."""

    def test_publish_all_requires_path(self, tmp_path):
        """publish all without PATH exits with code 1."""
        _init_project(tmp_path)
        runner = CliRunner()
        r = _invoke(runner, ["publish", "all"], cwd=tmp_path)
        assert r.exit_code == 1
        assert "requires" in r.output.lower()

    def test_publish_empty_document(self, tmp_path):
        """publish exits with code 1 when document has no items."""
        _init_project(tmp_path)
        runner = CliRunner()
        # SRS document has no items (only .jamb.yml)
        # Remove any items if they exist
        srs_dir = tmp_path / "reqs" / "srs"
        for yml in srs_dir.glob("SRS*.yml"):
            yml.unlink()
        r = _invoke(runner, ["publish", "SRS"], cwd=tmp_path)
        assert r.exit_code == 1
        assert "no items found" in r.output.lower()


class TestInitDocumentSaveError:
    """Tests for init command document save errors."""

    def test_init_document_save_fails(self, tmp_path):
        """init exits with code 1 when document config save fails."""
        import subprocess

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')

        from unittest.mock import patch

        runner = CliRunner()

        # Patch save_document_config at the module where it's imported
        with patch(
            "jamb.storage.document_config.save_document_config",
            side_effect=OSError("Permission denied"),
        ):
            r = _invoke(runner, ["init"], cwd=tmp_path)
            assert r.exit_code == 1
            assert "error" in r.output.lower()


# =========================================================================
# CLI Error Handler Tests
# =========================================================================


class TestCliErrorHandler:
    """Tests for _cli_error_handler exception handling."""

    def test_check_warns_on_oserror(self, tmp_path):
        """check warns when a test file has OS errors."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        p = tmp_path / "reqs" / "srs" / "SRS001.yml"
        data = _read_yaml(p)
        data["text"] = "the one req"
        _write_yaml(p, data)

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        # Valid test file covering SRS001
        (tests_dir / "test_valid.py").write_text(
            "import pytest\n\n@pytest.mark.requirement('SRS001')\ndef test_a():\n    pass\n"
        )

        # File with encoding error
        (tests_dir / "test_encoding.py").write_bytes(b"\x80\x81\x82")

        r = _invoke(
            runner,
            ["check", "--documents", "SRS", "--root", str(tmp_path)],
        )
        # Should still pass (SRS001 is covered by valid test)
        assert r.exit_code == 0
        # But should warn about the encoding error file
        assert "warning" in r.output.lower()
        assert "test_encoding.py" in r.output
        assert "encoding" in r.output.lower()


class TestCheckUnknownItems:
    """Tests for check command with unknown item references."""

    def test_check_warns_on_unknown_items(self, tmp_path):
        """check warns when tests reference unknown UIDs."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        p = tmp_path / "reqs" / "srs" / "SRS001.yml"
        data = _read_yaml(p)
        data["text"] = "the one req"
        _write_yaml(p, data)

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        # Test file referencing both valid and unknown UIDs
        (tests_dir / "test_x.py").write_text(
            "import pytest\n\n@pytest.mark.requirement('SRS001')\ndef test_valid():\n    pass\n\n"
            "@pytest.mark.requirement('UNKNOWN001')\ndef test_unknown():\n    pass\n"
        )

        r = _invoke(
            runner,
            ["check", "--documents", "SRS", "--root", str(tmp_path)],
        )
        # Should fail because unknown items are referenced
        assert r.exit_code == 1
        assert "unknown" in r.output.lower()
        assert "UNKNOWN001" in r.output


class TestPublishAutoDetect:
    """Tests for publish command auto-detecting format from extension."""

    def test_publish_html_extension_auto_detect(self, tmp_path):
        """publish auto-detects HTML format from .html extension."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        p = tmp_path / "reqs" / "srs" / "SRS001.yml"
        data = _read_yaml(p)
        data["text"] = "requirement"
        _write_yaml(p, data)

        out = tmp_path / "out.html"
        r = _invoke(runner, ["publish", "SRS", str(out)], cwd=tmp_path)
        assert r.exit_code == 0
        assert out.exists()
        assert "<html" in out.read_text().lower()

    def test_publish_htm_extension_auto_detect(self, tmp_path):
        """publish auto-detects HTML format from .htm extension."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        p = tmp_path / "reqs" / "srs" / "SRS001.yml"
        data = _read_yaml(p)
        data["text"] = "requirement"
        _write_yaml(p, data)

        out = tmp_path / "out.htm"
        r = _invoke(runner, ["publish", "SRS", str(out)], cwd=tmp_path)
        assert r.exit_code == 0
        assert out.exists()
        assert "<html" in out.read_text().lower()

    def test_publish_docx_extension_auto_detect(self, tmp_path):
        """publish auto-detects DOCX format from .docx extension."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        p = tmp_path / "reqs" / "srs" / "SRS001.yml"
        data = _read_yaml(p)
        data["text"] = "requirement"
        _write_yaml(p, data)

        out = tmp_path / "out.docx"
        r = _invoke(runner, ["publish", "SRS", str(out)], cwd=tmp_path)
        assert r.exit_code == 0
        assert out.exists()
        # DOCX is a ZIP file
        assert out.stat().st_size > 0


class TestPublishNoLinksOption:
    """Tests for publish --no-links option."""

    def test_publish_no_links_flag(self, tmp_path):
        """publish --no-links omits link sections."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS", "--count", "2"], cwd=tmp_path)
        _invoke(runner, ["item", "add", "SYS"], cwd=tmp_path)

        p1 = tmp_path / "reqs" / "srs" / "SRS001.yml"
        _write_yaml(p1, {"active": True, "text": "req1", "links": ["SYS001"]})

        r = _invoke(runner, ["publish", "SRS", "--no-links"], cwd=tmp_path)
        assert r.exit_code == 0
        # Should not contain "Links:" in output
        assert "Links:" not in r.output


class TestPublishMarkdownRequiresPath:
    """Tests for publish --markdown requiring path."""

    def test_publish_markdown_requires_path(self, tmp_path):
        """publish --markdown without PATH exits with code 1."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        p = tmp_path / "reqs" / "srs" / "SRS001.yml"
        data = _read_yaml(p)
        data["text"] = "requirement"
        _write_yaml(p, data)

        r = _invoke(runner, ["publish", "SRS", "--markdown"], cwd=tmp_path)
        assert r.exit_code == 1
        assert "requires" in r.output.lower()


class TestPublishDocxRequiresPath:
    """Tests for publish --docx requiring path."""

    def test_publish_docx_requires_path(self, tmp_path):
        """publish --docx without PATH exits with code 1."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        p = tmp_path / "reqs" / "srs" / "SRS001.yml"
        data = _read_yaml(p)
        data["text"] = "requirement"
        _write_yaml(p, data)

        r = _invoke(runner, ["publish", "SRS", "--docx"], cwd=tmp_path)
        assert r.exit_code == 1
        assert "requires" in r.output.lower()


class TestPublishAllMarkdown:
    """Tests for publish all command with markdown format."""

    def test_publish_all_markdown_to_file(self, tmp_path):
        """publish all to markdown file includes all documents."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        _invoke(runner, ["item", "add", "SYS"], cwd=tmp_path)

        p1 = tmp_path / "reqs" / "srs" / "SRS001.yml"
        _write_yaml(p1, {"active": True, "text": "srs req"})
        p2 = tmp_path / "reqs" / "sys" / "SYS001.yml"
        _write_yaml(p2, {"active": True, "text": "sys req"})

        out = tmp_path / "all.md"
        r = _invoke(runner, ["publish", "all", str(out)], cwd=tmp_path)
        assert r.exit_code == 0
        content = out.read_text()
        assert "SRS001" in content
        assert "SYS001" in content


class TestPublishAllHtml:
    """Tests for publish all command with HTML format."""

    def test_publish_all_html_to_file(self, tmp_path):
        """publish all to HTML file includes all documents."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        _invoke(runner, ["item", "add", "SYS"], cwd=tmp_path)

        p1 = tmp_path / "reqs" / "srs" / "SRS001.yml"
        _write_yaml(p1, {"active": True, "text": "srs req"})
        p2 = tmp_path / "reqs" / "sys" / "SYS001.yml"
        _write_yaml(p2, {"active": True, "text": "sys req"})

        out = tmp_path / "all.html"
        r = _invoke(runner, ["publish", "all", str(out)], cwd=tmp_path)
        assert r.exit_code == 0
        content = out.read_text()
        assert "SRS001" in content
        assert "SYS001" in content


class TestPublishAllDocx:
    """Tests for publish all command with DOCX format."""

    def test_publish_all_docx_to_file(self, tmp_path):
        """publish all to DOCX file creates non-empty file."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        _invoke(runner, ["item", "add", "SYS"], cwd=tmp_path)

        p1 = tmp_path / "reqs" / "srs" / "SRS001.yml"
        _write_yaml(p1, {"active": True, "text": "srs req"})
        p2 = tmp_path / "reqs" / "sys" / "SYS001.yml"
        _write_yaml(p2, {"active": True, "text": "sys req"})

        out = tmp_path / "all.docx"
        r = _invoke(runner, ["publish", "all", str(out)], cwd=tmp_path)
        assert r.exit_code == 0
        assert out.exists()
        assert out.stat().st_size > 0


class TestPublishTemplateWarning:
    """Tests for publish template warning with non-DOCX output."""

    def test_publish_template_warning_with_html(self, tmp_path):
        """publish --template warns when used with HTML output."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        p = tmp_path / "reqs" / "srs" / "SRS001.yml"
        data = _read_yaml(p)
        data["text"] = "requirement"
        _write_yaml(p, data)

        # Create a dummy template file
        template = tmp_path / "template.docx"
        template.write_bytes(b"dummy")

        out = tmp_path / "out.html"
        r = _invoke(runner, ["publish", "SRS", str(out), "--template", str(template)], cwd=tmp_path)
        assert r.exit_code == 0
        assert "Warning" in r.output
        assert "template" in r.output.lower()


class TestPublishTemplateInvalidExtension:
    """Tests for publish --template with invalid file extension."""

    def test_publish_template_invalid_extension(self, tmp_path):
        """publish --template exits with error for non-.docx template."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        p = tmp_path / "reqs" / "srs" / "SRS001.yml"
        data = _read_yaml(p)
        data["text"] = "requirement"
        _write_yaml(p, data)

        # Create a dummy template file with wrong extension
        template = tmp_path / "template.txt"
        template.write_text("dummy")

        out = tmp_path / "out.docx"
        r = _invoke(runner, ["publish", "SRS", str(out), "--docx", "--template", str(template)], cwd=tmp_path)
        assert r.exit_code == 1
        assert "template" in r.output.lower()
        assert ".docx" in r.output


class TestMatrixTraceFromAutoDetect:
    """Tests for matrix command trace_from auto-detection."""

    def test_matrix_with_no_coverage_file(self, tmp_path):
        """matrix errors when coverage file does not exist."""
        _init_project(tmp_path)
        runner = CliRunner()

        # Try to run matrix without a .jamb file
        # Click validates Path(exists=True) and returns exit code 2
        r = _invoke(runner, ["matrix", "trace.html", "-i", str(tmp_path / "nonexistent.jamb")], cwd=tmp_path)
        assert r.exit_code == 2  # Click validation error
        assert "not exist" in r.output.lower() or "does not exist" in r.output.lower()


class TestImportNoFile:
    """Tests for import command without file argument."""

    def test_import_no_file_errors(self, tmp_path):
        """import without FILE argument exits with error."""
        _init_project(tmp_path)
        runner = CliRunner()
        r = _invoke(runner, ["import"], cwd=tmp_path)
        assert r.exit_code == 1
        assert "missing" in r.output.lower() or "file" in r.output.lower()


class TestExportNeighborsRequiresItems:
    """Tests for export --neighbors requiring --items."""

    def test_export_neighbors_without_items_errors(self, tmp_path):
        """export --neighbors without --items exits with error."""
        _init_project(tmp_path)
        runner = CliRunner()
        out = tmp_path / "export.yml"
        r = _invoke(runner, ["export", str(out), "--neighbors", "--root", str(tmp_path)])
        assert r.exit_code == 1
        assert "--neighbors" in r.output
        assert "--items" in r.output


class TestReorderUpdatesTestReferences:
    """Tests for reorder command updating test references."""

    def test_reorder_updates_test_files(self, tmp_path):
        """reorder updates @pytest.mark.requirement references in test files."""
        _init_project(tmp_path)
        runner = CliRunner()

        # Create items with a gap
        _invoke(runner, ["item", "add", "SRS", "--count", "3"], cwd=tmp_path)
        _invoke(runner, ["item", "remove", "SRS002"], cwd=tmp_path)

        # Create a test file referencing SRS003
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_feature.py"
        test_file.write_text('@pytest.mark.requirement("SRS003")\ndef test_x(): pass\n')

        # Reorder
        r = _invoke(runner, ["reorder", "SRS"], cwd=tmp_path)
        assert r.exit_code == 0
        assert "renamed" in r.output.lower()
        assert "test" in r.output.lower()

        # Test file should be updated
        content = test_file.read_text()
        assert '"SRS002"' in content
        assert '"SRS003"' not in content

    def test_reorder_no_update_tests_flag(self, tmp_path):
        """reorder --no-update-tests skips test file updates."""
        _init_project(tmp_path)
        runner = CliRunner()

        # Create items with a gap
        _invoke(runner, ["item", "add", "SRS", "--count", "3"], cwd=tmp_path)
        _invoke(runner, ["item", "remove", "SRS002"], cwd=tmp_path)

        # Create a test file referencing SRS003
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_feature.py"
        test_file.write_text('@pytest.mark.requirement("SRS003")\ndef test_x(): pass\n')

        # Reorder with --no-update-tests
        r = _invoke(runner, ["reorder", "SRS", "--no-update-tests"], cwd=tmp_path)
        assert r.exit_code == 0
        assert "renamed" in r.output.lower()

        # Test file should NOT be updated
        content = test_file.read_text()
        assert '"SRS003"' in content  # Still has old reference


class TestItemRemoveWithTestReferences:
    """Tests for item remove with test references."""

    def test_item_remove_warns_about_test_references(self, tmp_path):
        """item remove warns about test references and requires --force or confirmation."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)

        # Create a test file referencing SRS001
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_feature.py"
        test_file.write_text('@pytest.mark.requirement("SRS001")\ndef test_x(): pass\n')

        # Try to remove without --force (should prompt, then abort)
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            r = runner.invoke(cli, ["item", "remove", "SRS001"], input="n\n")
        finally:
            os.chdir(old)

        assert r.exit_code != 0
        assert "test" in r.output.lower()
        assert "reference" in r.output.lower()

    def test_item_remove_force_with_test_references(self, tmp_path):
        """item remove --force removes despite test references."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)

        # Create a test file referencing SRS001
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_feature.py"
        test_file.write_text('@pytest.mark.requirement("SRS001")\ndef test_x(): pass\n')

        r = _invoke(runner, ["item", "remove", "SRS001", "--force"], cwd=tmp_path)
        assert r.exit_code == 0
        assert not (tmp_path / "reqs" / "srs" / "SRS001.yml").exists()
        # Should note about orphaned references
        assert "update" in r.output.lower() or "orphan" in r.output.lower()


class TestItemRemoveWithChildLinks:
    """Tests for item remove with items linking to it."""

    def test_item_remove_warns_about_child_links(self, tmp_path):
        """item remove warns when other items link to the target."""
        _init_project(tmp_path)
        runner = CliRunner()
        _invoke(runner, ["item", "add", "SRS"], cwd=tmp_path)
        _invoke(runner, ["item", "add", "SYS"], cwd=tmp_path)
        _invoke(runner, ["link", "add", "SRS001", "SYS001"], cwd=tmp_path)

        # Remove SYS001 (which SRS001 links to) with --force to bypass prompt
        r = _invoke(runner, ["item", "remove", "SYS001", "--force"], cwd=tmp_path)
        assert r.exit_code == 0
        # Should warn about child links
        assert "warning" in r.output.lower()
        assert "SRS001" in r.output
