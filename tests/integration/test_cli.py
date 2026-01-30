"""Integration tests for jamb CLI commands."""

import pytest
from click.testing import CliRunner

from jamb.cli.commands import cli


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def jamb_project(tmp_path):
    """Create a jamb project for testing."""
    # Create UN document
    (tmp_path / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: UN\n  sep: ''\n")
    (tmp_path / "UN001.yml").write_text("active: true\ntext: User need\nlinks: []\n")

    # Create SRS document
    srs_dir = tmp_path / "srs"
    srs_dir.mkdir()
    (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  parents:\n  - UN\n  prefix: SRS\n  sep: ''\n")
    (srs_dir / "SRS001.yml").write_text("active: true\ntext: Software req\nlinks:\n- UN001\n")

    return tmp_path


class TestInfoCommand:
    """Tests for the info command."""

    def test_info_help(self, runner):
        """Test that info --help works."""
        result = runner.invoke(cli, ["info", "--help"])

        assert result.exit_code == 0
        assert "Display" in result.output or "info" in result.output.lower()

    def test_info_with_project(self, runner, jamb_project):
        """Test info command with project."""
        result = runner.invoke(cli, ["info", "--root", str(jamb_project)])

        # Should succeed with valid project
        assert result.exit_code == 0


class TestCheckCommand:
    """Tests for the check command."""

    def test_check_help(self, runner):
        """Test that check --help works."""
        result = runner.invoke(cli, ["check", "--help"])

        assert result.exit_code == 0
        assert "Check" in result.output or "coverage" in result.output.lower()


class TestDocCommands:
    """Tests for doc subcommands."""

    def test_doc_help(self, runner):
        """Test that doc --help works."""
        result = runner.invoke(cli, ["doc", "--help"])

        assert result.exit_code == 0
        assert "create" in result.output.lower()
        assert "list" in result.output.lower()

    def test_doc_create_help(self, runner):
        """Test that doc create --help works."""
        result = runner.invoke(cli, ["doc", "create", "--help"])

        assert result.exit_code == 0
        assert "PREFIX" in result.output
        assert "PATH" in result.output

    def test_doc_list_with_project(self, runner, jamb_project):
        """Test doc list command with project."""
        result = runner.invoke(cli, ["doc", "list", "--root", str(jamb_project)])

        assert result.exit_code == 0
        assert "UN" in result.output
        assert "SRS" in result.output


class TestItemCommands:
    """Tests for item subcommands."""

    def test_item_help(self, runner):
        """Test that item --help works."""
        result = runner.invoke(cli, ["item", "--help"])

        assert result.exit_code == 0
        assert "add" in result.output.lower()
        assert "list" in result.output.lower()

    def test_item_list_with_project(self, runner, jamb_project):
        """Test item list command with project."""
        result = runner.invoke(cli, ["item", "list", "--root", str(jamb_project)])

        assert result.exit_code == 0
        assert "UN001" in result.output or "SRS001" in result.output

    def test_item_show_help(self, runner):
        """Test that item show --help works."""
        result = runner.invoke(cli, ["item", "show", "--help"])

        assert result.exit_code == 0
        assert "UID" in result.output


class TestLinkCommands:
    """Tests for link subcommands."""

    def test_link_help(self, runner):
        """Test that link --help works."""
        result = runner.invoke(cli, ["link", "--help"])

        assert result.exit_code == 0
        assert "add" in result.output.lower()
        assert "remove" in result.output.lower()


class TestReviewCommands:
    """Tests for review subcommands."""

    def test_review_help(self, runner):
        """Test that review --help works."""
        result = runner.invoke(cli, ["review", "--help"])

        assert result.exit_code == 0
        assert "mark" in result.output.lower()


class TestPublishCommand:
    """Tests for publish command."""

    def test_publish_help(self, runner):
        """Test that publish --help works."""
        result = runner.invoke(cli, ["publish", "--help"])

        assert result.exit_code == 0
        assert "PREFIX" in result.output
        assert "--html" in result.output or "-H" in result.output
        assert "--markdown" in result.output or "-m" in result.output

    def test_publish_shows_format_options(self, runner):
        """Test that publish help shows format options."""
        result = runner.invoke(cli, ["publish", "--help"])

        assert result.exit_code == 0
        assert "html" in result.output.lower()
        assert "markdown" in result.output.lower()
        assert "docx" in result.output.lower()
        assert "--template" in result.output
        # Removed formats should NOT appear
        assert "--latex" not in result.output
        assert "--text" not in result.output


class TestValidateCommand:
    """Tests for validate command."""

    def test_validate_help(self, runner):
        """Test that validate --help works."""
        result = runner.invoke(cli, ["validate", "--help"])

        assert result.exit_code == 0
        assert "validate" in result.output.lower()

    def test_validate_passes_flags(self, runner, jamb_project):
        """Test that flags like -v are accepted."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(jamb_project)
            result = runner.invoke(cli, ["validate", "-v"], catch_exceptions=False)
            # -v should be accepted (not rejected by Click)
            # If Click was intercepting flags, we'd get an error
            assert result.exit_code == 0
        finally:
            os.chdir(original_cwd)


class TestMainCli:
    """Tests for the main CLI entry point."""

    def test_cli_help(self, runner):
        """Test that --help works."""
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "jamb" in result.output.lower() or "validate" in result.output.lower()

    def test_cli_version_or_help_shows_commands(self, runner):
        """Test that help shows available commands."""
        result = runner.invoke(cli, ["--help"])

        assert "validate" in result.output
        assert "check" in result.output
        assert "doc" in result.output
        assert "item" in result.output


class TestExportCommand:
    """Tests for export command."""

    def test_export_help(self, runner):
        """Test that export --help works."""
        result = runner.invoke(cli, ["export", "--help"])

        assert result.exit_code == 0
        assert "OUTPUT" in result.output
        assert "documents" in result.output.lower()

    def test_export_to_yaml(self, runner, jamb_project):
        """Test exporting to YAML file."""
        output_file = jamb_project / "exported.yml"

        result = runner.invoke(cli, ["export", str(output_file), "--root", str(jamb_project)])

        # Print output for debugging if test fails
        if result.exit_code != 0:
            print(f"Output: {result.output}")
            print(f"Exception: {result.exception}")

        assert result.exit_code == 0, f"Export failed: {result.output}"
        assert output_file.exists()
        content = output_file.read_text()
        assert "documents:" in content
        assert "items:" in content

    def test_export_paths_are_relative(self, runner, jamb_project):
        """Test that exported paths are relative, not absolute."""
        output_file = jamb_project / "exported.yml"

        result = runner.invoke(cli, ["export", str(output_file), "--root", str(jamb_project)])

        assert result.exit_code == 0
        content = output_file.read_text()
        # Paths should NOT contain absolute path prefix
        assert str(jamb_project) not in content
        # Paths should be relative like "srs" or "."
        import yaml

        data = yaml.safe_load(content)
        for doc in data["documents"]:
            path = doc["path"]
            assert not path.startswith("/"), f"Path should be relative: {path}"


class TestImportCommand:
    """Tests for import command."""

    def test_import_help(self, runner):
        """Test that import --help works."""
        result = runner.invoke(cli, ["import", "--help"])

        assert result.exit_code == 0
        assert "FILE" in result.output
        assert "dry-run" in result.output.lower()

    def test_import_dry_run(self, runner, jamb_project):
        """Test import with --dry-run flag."""
        yaml_file = jamb_project / "import.yml"
        yaml_file.write_text(
            """
documents: []
items:
  - uid: SRS002
    text: New requirement
"""
        )

        result = runner.invoke(cli, ["import", str(yaml_file), "--dry-run"], catch_exceptions=False)

        # Should show what would be created
        assert "dry run" in result.output.lower() or "would" in result.output.lower()

    def test_import_help_shows_update_flag(self, runner):
        """Test that import --help shows --update option."""
        result = runner.invoke(cli, ["import", "--help"])

        assert result.exit_code == 0
        assert "--update" in result.output

    def test_import_without_update_skips_existing(self, runner, jamb_project):
        """Test import without --update skips existing items."""
        import os

        yaml_file = jamb_project / "import.yml"
        yaml_file.write_text(
            """
documents: []
items:
  - uid: SRS001
    text: Should not update
"""
        )

        original_cwd = os.getcwd()
        try:
            os.chdir(jamb_project)
            result = runner.invoke(cli, ["import", str(yaml_file)], catch_exceptions=False)
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        assert "skipped" in result.output.lower()
        # Original text should remain
        srs_file = jamb_project / "srs" / "SRS001.yml"
        assert "Software req" in srs_file.read_text()

    def test_import_update_modifies_existing_item(self, runner, jamb_project):
        """Test import --update modifies existing items."""
        import os

        yaml_file = jamb_project / "import.yml"
        yaml_file.write_text(
            """
documents: []
items:
  - uid: SRS001
    text: Updated requirement text
"""
        )

        original_cwd = os.getcwd()
        try:
            os.chdir(jamb_project)
            result = runner.invoke(cli, ["import", str(yaml_file), "--update"], catch_exceptions=False)
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        assert "updated" in result.output.lower()
        # Text should be updated
        srs_file = jamb_project / "srs" / "SRS001.yml"
        assert "Updated requirement text" in srs_file.read_text()

    def test_import_update_dry_run_shows_would_update(self, runner, jamb_project):
        """Test import --update --dry-run shows what would be updated."""
        import os

        yaml_file = jamb_project / "import.yml"
        yaml_file.write_text(
            """
documents: []
items:
  - uid: SRS001
    text: Would update this
  - uid: SRS999
    text: Would create this
"""
        )

        original_cwd = os.getcwd()
        try:
            os.chdir(jamb_project)
            result = runner.invoke(
                cli,
                ["import", str(yaml_file), "--update", "--dry-run"],
                catch_exceptions=False,
            )
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        assert "would update" in result.output.lower()
        assert "would create" in result.output.lower()
        # File should not be modified
        srs_file = jamb_project / "srs" / "SRS001.yml"
        assert "Software req" in srs_file.read_text()

    def test_import_update_clears_reviewed(self, runner, jamb_project):
        """Test that --update clears reviewed status."""
        import os

        # Add reviewed field to existing item
        srs_file = jamb_project / "srs" / "SRS001.yml"
        srs_file.write_text("active: true\nreviewed: abc123\ntext: Software req\nlinks:\n- UN001\n")

        yaml_file = jamb_project / "import.yml"
        yaml_file.write_text(
            """
documents: []
items:
  - uid: SRS001
    text: Updated text
"""
        )

        original_cwd = os.getcwd()
        try:
            os.chdir(jamb_project)
            runner.invoke(cli, ["import", str(yaml_file), "--update"], catch_exceptions=False)
        finally:
            os.chdir(original_cwd)

        content = srs_file.read_text()
        assert "reviewed" not in content
        assert "Updated text" in content


class TestCheckCommandExtended:
    """Extended tests for check command."""

    def test_check_with_documents_option(self, runner, jamb_project):
        """Test check command with --documents option."""
        # Create a test file with requirement marker
        test_file = jamb_project / "test_reqs.py"
        test_file.write_text(
            """
import pytest

@pytest.mark.requirement("SRS001")
def test_req():
    pass
"""
        )

        result = runner.invoke(
            cli,
            [
                "check",
                "--documents",
                "SRS",
                "--root",
                str(jamb_project),
            ],
        )

        assert result.exit_code == 0
        assert "SRS" in result.output

    def test_check_finds_uncovered_items(self, runner, jamb_project):
        """Test check command exits 1 when items are uncovered."""
        # No test file with requirement markers
        result = runner.invoke(
            cli,
            [
                "check",
                "--documents",
                "SRS",
                "--root",
                str(jamb_project),
            ],
        )

        # Should fail - SRS001 is not covered
        assert result.exit_code == 1
        assert "uncovered" in result.output.lower()
        assert "SRS001" in result.output


class TestInfoCommandExtended:
    """Extended tests for info command."""

    def test_info_shows_document_hierarchy(self, runner, jamb_project):
        """Test info shows document hierarchy tree."""
        result = runner.invoke(cli, ["info", "--root", str(jamb_project)])

        assert result.exit_code == 0
        assert "hierarchy" in result.output.lower()
        assert "UN" in result.output
        assert "SRS" in result.output


class TestItemShowCommand:
    """Tests for item show command."""

    def test_item_show_displays_details(self, runner, jamb_project):
        """Test item show displays all item details."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(jamb_project)
            result = runner.invoke(cli, ["item", "show", "SRS001"], catch_exceptions=False)
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        assert "UID: SRS001" in result.output
        assert "Document: SRS" in result.output
        assert "Active: True" in result.output
        assert "Text:" in result.output

    def test_item_show_with_links(self, runner, jamb_project):
        """Test item show displays links."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(jamb_project)
            result = runner.invoke(cli, ["item", "show", "SRS001"], catch_exceptions=False)
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        assert "Links: UN001" in result.output


class TestPublishCommandExtended:
    """Extended tests for publish command."""

    def test_publish_all_requires_path(self, runner):
        """Test publish 'all' requires output path."""
        result = runner.invoke(cli, ["publish", "all"])

        assert result.exit_code == 1
        assert "requires" in result.output.lower() and "path" in result.output.lower()

    def test_publish_docx_with_template(self, runner, jamb_project):
        """Test publish with --template option creates DOCX using template."""
        import os

        template_path = jamb_project / "template.docx"
        output_path = jamb_project / "output.docx"

        # First generate a template
        original_cwd = os.getcwd()
        try:
            os.chdir(jamb_project)
            result = runner.invoke(cli, ["publish-template", str(template_path)], catch_exceptions=False)
            assert result.exit_code == 0
            assert template_path.exists()

            # Now publish with the template
            result = runner.invoke(
                cli,
                [
                    "publish",
                    "SRS",
                    str(output_path),
                    "--template",
                    str(template_path),
                ],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            assert output_path.exists()
            assert "Published to" in result.output
        finally:
            os.chdir(original_cwd)

    def test_publish_template_warning_with_html(self, runner, jamb_project):
        """Test that --template with HTML output shows warning."""
        import os

        template_path = jamb_project / "template.docx"
        output_path = jamb_project / "output.html"

        original_cwd = os.getcwd()
        try:
            os.chdir(jamb_project)
            # Generate template first
            runner.invoke(cli, ["publish-template", str(template_path)])

            # Try to use with HTML
            result = runner.invoke(
                cli,
                [
                    "publish",
                    "SRS",
                    str(output_path),
                    "--html",
                    "--template",
                    str(template_path),
                ],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            assert "Warning" in result.output
            assert "DOCX" in result.output
        finally:
            os.chdir(original_cwd)

    def test_publish_template_must_be_docx(self, runner, jamb_project):
        """Test that --template must be a .docx file."""
        import os

        # Create a non-docx file
        template_path = jamb_project / "template.txt"
        template_path.write_text("not a docx")
        output_path = jamb_project / "output.docx"

        original_cwd = os.getcwd()
        try:
            os.chdir(jamb_project)
            result = runner.invoke(
                cli,
                [
                    "publish",
                    "SRS",
                    str(output_path),
                    "--docx",
                    "--template",
                    str(template_path),
                ],
            )
            assert result.exit_code == 1
            assert "must be a .docx file" in result.output
        finally:
            os.chdir(original_cwd)


class TestPublishTemplateCommand:
    """Tests for publish-template command."""

    def test_publish_template_help(self, runner):
        """Test that publish-template --help works."""
        result = runner.invoke(cli, ["publish-template", "--help"])

        assert result.exit_code == 0
        assert "template" in result.output.lower()
        assert "jamb" in result.output.lower()

    def test_publish_template_creates_file(self, runner, tmp_path):
        """Test that publish-template creates a DOCX file."""
        import os

        output_path = tmp_path / "my-template.docx"

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(cli, ["publish-template", str(output_path)], catch_exceptions=False)

            assert result.exit_code == 0
            assert output_path.exists()
            assert "Generated template" in result.output
            assert "Next steps" in result.output
        finally:
            os.chdir(original_cwd)

    def test_publish_template_default_name(self, runner, tmp_path):
        """Test publish-template uses default filename."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(cli, ["publish-template"], catch_exceptions=False)

            assert result.exit_code == 0
            assert (tmp_path / "jamb-template.docx").exists()
        finally:
            os.chdir(original_cwd)

    def test_publish_template_overwrite_prompt(self, runner, tmp_path):
        """Test publish-template prompts before overwriting."""
        import os

        output_path = tmp_path / "template.docx"
        output_path.write_bytes(b"existing content")

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            # Answer 'n' to overwrite prompt
            result = runner.invoke(cli, ["publish-template", str(output_path)], input="n\n")

            assert result.exit_code == 0
            assert "Aborted" in result.output
            # Original content should be preserved
            assert output_path.read_bytes() == b"existing content"
        finally:
            os.chdir(original_cwd)


class TestExportCommandExtended:
    """Extended tests for export command."""

    def test_export_specific_documents(self, runner, jamb_project):
        """Test export with --documents option."""
        output_file = jamb_project / "exported.yml"

        result = runner.invoke(
            cli,
            [
                "export",
                str(output_file),
                "--documents",
                "SRS",
                "--root",
                str(jamb_project),
            ],
        )

        assert result.exit_code == 0
        assert output_file.exists()
        content = output_file.read_text()
        assert "SRS" in content


class TestImportCommandExtended:
    """Extended tests for import command."""

    def test_import_creates_new_items(self, runner, jamb_project):
        """Test import creates new items."""
        import os

        yaml_file = jamb_project / "import.yml"
        yaml_file.write_text(
            """
documents: []
items:
  - uid: SRS002
    text: New requirement text
"""
        )

        original_cwd = os.getcwd()
        try:
            os.chdir(jamb_project)
            result = runner.invoke(cli, ["import", str(yaml_file)], catch_exceptions=False)
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        # Check item was created
        new_item = jamb_project / "srs" / "SRS002.yml"
        assert new_item.exists()
        assert "New requirement text" in new_item.read_text()

    def test_import_verbose(self, runner, jamb_project):
        """Test import with --verbose flag."""
        import os

        yaml_file = jamb_project / "import.yml"
        yaml_file.write_text(
            """
documents: []
items:
  - uid: SRS003
    text: Another requirement
"""
        )

        original_cwd = os.getcwd()
        try:
            os.chdir(jamb_project)
            result = runner.invoke(cli, ["import", str(yaml_file), "--verbose"], catch_exceptions=False)
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        # Verbose should show more detailed output
        assert "SRS003" in result.output or "created" in result.output.lower()


class TestDocCreateWithMock:
    """Tests for doc create command (native, no subprocess)."""

    def test_doc_create_with_parent(self, runner, tmp_path):
        """Test doc create with --parent option creates .jamb.yml."""
        doc_path = tmp_path / "srs"
        result = runner.invoke(cli, ["doc", "create", "SRS", str(doc_path), "--parent", "UN"])

        assert result.exit_code == 0
        jamb_yml = doc_path / ".jamb.yml"
        assert jamb_yml.exists()
        import yaml

        data = yaml.safe_load(jamb_yml.read_text())
        assert data["settings"]["prefix"] == "SRS"
        assert data["settings"]["parents"] == ["UN"]

    def test_doc_create_with_digits_and_sep(self, runner, tmp_path):
        """Test doc create with --digits and --sep options."""
        doc_path = tmp_path / "srs"
        result = runner.invoke(
            cli,
            [
                "doc",
                "create",
                "SRS",
                str(doc_path),
                "--parent",
                "UN",
                "--digits",
                "4",
                "--sep",
                "-",
            ],
        )

        assert result.exit_code == 0
        jamb_yml = doc_path / ".jamb.yml"
        assert jamb_yml.exists()
        import yaml

        data = yaml.safe_load(jamb_yml.read_text())
        assert data["settings"]["prefix"] == "SRS"
        assert data["settings"]["digits"] == 4
        assert data["settings"]["sep"] == "-"
        assert data["settings"]["parents"] == ["UN"]


class TestDocDeleteWithMock:
    """Tests for doc delete command (native, no subprocess)."""

    def test_doc_delete(self, runner, tmp_path, monkeypatch):
        """Test doc delete removes the document directory."""
        # Create a document directory with .jamb.yml
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n")
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: req\n")

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["doc", "delete", "SRS", "--force"])

        assert result.exit_code == 0
        assert not srs_dir.exists()
        assert "Deleted" in result.output


class TestReorderCommand:
    """Tests for top-level reorder command."""

    def test_reorder_fills_gaps(self, runner, tmp_path, monkeypatch):
        """Test reorder renumbers items sequentially to fill gaps."""
        import yaml

        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n")
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: req1\n")
        (srs_dir / "SRS003.yml").write_text("active: true\ntext: req3\n")

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["reorder", "SRS"])

        assert result.exit_code == 0
        assert "1 renamed" in result.output
        assert "1 unchanged" in result.output

        # SRS003 should have become SRS002
        assert (srs_dir / "SRS001.yml").exists()
        assert (srs_dir / "SRS002.yml").exists()
        assert not (srs_dir / "SRS003.yml").exists()
        data = yaml.safe_load((srs_dir / "SRS002.yml").read_text())
        assert data["text"] == "req3"

    def test_reorder_empty_document(self, runner, tmp_path, monkeypatch):
        """Test reorder with empty document is a no-op."""
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n")

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["reorder", "SRS"])

        assert result.exit_code == 0
        assert "0 renamed" in result.output

    def test_reorder_nonexistent_document(self, runner, tmp_path, monkeypatch):
        """Test reorder with nonexistent prefix."""
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n")

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["reorder", "NOPE"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_reorder_broken_links_aborts(self, runner, tmp_path, monkeypatch):
        """Test reorder aborts with exit code 1 when broken links exist."""
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n")
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: req1\nlinks:\n- NONEXIST\n")
        (srs_dir / "SRS002.yml").write_text("active: true\ntext: req2\n")

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["reorder", "SRS"])

        assert result.exit_code == 1
        assert "Broken links" in result.output or "broken link" in result.output.lower()

    def test_reorder_updates_test_files(self, runner, tmp_path, monkeypatch):
        """Test reorder updates @pytest.mark.requirement decorators in test files."""
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n")
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: req1\n")
        (srs_dir / "SRS003.yml").write_text("active: true\ntext: req3\n")

        # Create test file with reference to SRS003
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_feature.py"
        test_file.write_text("""
import pytest

@pytest.mark.requirement("SRS003")
def test_feature():
    pass
""")

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["reorder", "SRS"])

        assert result.exit_code == 0
        assert "1 renamed" in result.output
        assert "Updated test references" in result.output
        assert "SRS003->SRS002" in result.output

        # Verify test file was updated
        content = test_file.read_text()
        assert '"SRS002"' in content
        assert '"SRS003"' not in content

    def test_reorder_no_update_tests_flag(self, runner, tmp_path, monkeypatch):
        """Test reorder --no-update-tests skips test file updates."""
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n")
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: req1\n")
        (srs_dir / "SRS003.yml").write_text("active: true\ntext: req3\n")

        # Create test file with reference to SRS003
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_feature.py"
        test_file.write_text("""
import pytest

@pytest.mark.requirement("SRS003")
def test_feature():
    pass
""")

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["reorder", "SRS", "--no-update-tests"])

        assert result.exit_code == 0
        assert "1 renamed" in result.output
        assert "Updated test references" not in result.output

        # Verify test file was NOT updated
        content = test_file.read_text()
        assert '"SRS003"' in content
        assert '"SRS002"' not in content


class TestItemRemoveTestRefs:
    """Tests for item remove command with test reference handling."""

    def test_item_remove_warns_about_test_refs(self, runner, tmp_path, monkeypatch):
        """Test item remove warns about test references and prompts."""
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n")
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: req1\n")

        # Create test file with reference to SRS001
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_feature.py"
        test_file.write_text("""
import pytest

@pytest.mark.requirement("SRS001")
def test_feature():
    pass
""")

        monkeypatch.chdir(tmp_path)
        # Answer 'n' to confirmation
        result = runner.invoke(cli, ["item", "remove", "SRS001"], input="n\n")

        assert result.exit_code == 1
        assert "WARNING" in result.output
        assert "SRS001" in result.output
        assert "referenced by" in result.output
        assert "test_feature.py" in result.output

        # Verify item was NOT removed
        assert (srs_dir / "SRS001.yml").exists()

    def test_item_remove_force_skips_confirmation(self, runner, tmp_path, monkeypatch):
        """Test item remove --force skips test reference confirmation."""
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n")
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: req1\n")

        # Create test file with reference to SRS001
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_feature.py"
        test_file.write_text("""
import pytest

@pytest.mark.requirement("SRS001")
def test_feature():
    pass
""")

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["item", "remove", "SRS001", "--force"])

        assert result.exit_code == 0
        assert "Removed item: SRS001" in result.output
        assert "Note: Update test files" in result.output

        # Verify item was removed
        assert not (srs_dir / "SRS001.yml").exists()

    def test_item_remove_no_test_refs_no_prompt(self, runner, tmp_path, monkeypatch):
        """Test item remove without test references doesn't prompt."""
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n")
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: req1\n")

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["item", "remove", "SRS001"])

        assert result.exit_code == 0
        assert "Removed item: SRS001" in result.output
        assert "WARNING" not in result.output

        # Verify item was removed
        assert not (srs_dir / "SRS001.yml").exists()


class TestItemAddWithMock:
    """Tests for item add command (native, no subprocess)."""

    def test_item_add_basic(self, runner, tmp_path, monkeypatch):
        """Test item add creates a new YAML file."""
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n")

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["item", "add", "SRS"])

        assert result.exit_code == 0
        assert "Added item: SRS001" in result.output
        assert (srs_dir / "SRS001.yml").exists()

    def test_item_add_with_count(self, runner, tmp_path, monkeypatch):
        """Test item add with --count option creates multiple items."""
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n")

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["item", "add", "SRS", "--count", "5"])

        assert result.exit_code == 0
        for i in range(1, 6):
            assert (srs_dir / f"SRS00{i}.yml").exists()
        assert "SRS005" in result.output

    def test_item_add_after(self, runner, tmp_path, monkeypatch):
        """Test item add --after inserts after the anchor and shifts."""
        import yaml

        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n")
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: first\nlinks: []\n")
        (srs_dir / "SRS002.yml").write_text("active: true\ntext: second\nlinks: []\n")
        (srs_dir / "SRS003.yml").write_text("active: true\ntext: third\nlinks: []\n")

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["item", "add", "SRS", "--after", "SRS002"])

        assert result.exit_code == 0
        assert "Added item: SRS003" in result.output
        # Old SRS003 shifted to SRS004
        assert (srs_dir / "SRS004.yml").exists()
        data = yaml.safe_load((srs_dir / "SRS004.yml").read_text())
        assert data["text"] == "third"
        # New SRS003 is the inserted blank item
        new_data = yaml.safe_load((srs_dir / "SRS003.yml").read_text())
        assert new_data["text"] == ""

    def test_item_add_before(self, runner, tmp_path, monkeypatch):
        """Test item add --before inserts before the anchor and shifts."""
        import yaml

        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n")
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: first\nlinks: []\n")
        (srs_dir / "SRS002.yml").write_text("active: true\ntext: second\nlinks: []\n")
        (srs_dir / "SRS003.yml").write_text("active: true\ntext: third\nlinks: []\n")

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["item", "add", "SRS", "--before", "SRS002"])

        assert result.exit_code == 0
        assert "Added item: SRS002" in result.output
        # Old SRS002 shifted to SRS003, old SRS003 to SRS004
        assert (srs_dir / "SRS004.yml").exists()
        data = yaml.safe_load((srs_dir / "SRS003.yml").read_text())
        assert data["text"] == "second"
        # New SRS002 is the inserted blank item
        new_data = yaml.safe_load((srs_dir / "SRS002.yml").read_text())
        assert new_data["text"] == ""

    def test_item_add_after_and_before_exclusive(self, runner, tmp_path, monkeypatch):
        """Both --after and --before flags produce an error."""
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n")
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: req\nlinks: []\n")

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["item", "add", "SRS", "--after", "SRS001", "--before", "SRS001"])

        assert result.exit_code == 1
        assert "mutually exclusive" in result.output.lower()

    def test_item_add_after_nonexistent(self, runner, tmp_path, monkeypatch):
        """--after with a nonexistent UID produces an error."""
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n")

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["item", "add", "SRS", "--after", "SRS999"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestItemRemoveWithMock:
    """Tests for item remove command (native, no subprocess)."""

    def test_item_remove(self, runner, tmp_path, monkeypatch):
        """Test item remove deletes the YAML file."""
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n")
        item_path = srs_dir / "SRS001.yml"
        item_path.write_text("active: true\ntext: req\n")

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["item", "remove", "SRS001"])

        assert result.exit_code == 0
        assert not item_path.exists()
        assert "Removed item: SRS001" in result.output


class TestItemEditWithMock:
    """Tests for item edit command (still uses subprocess)."""

    def test_item_edit(self, runner, tmp_path, monkeypatch):
        """Test item edit opens the editor via subprocess."""
        from unittest.mock import MagicMock

        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n")
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: req\n")

        mock_result = MagicMock()
        mock_result.returncode = 0
        captured_cmd = []

        def mock_run(cmd, **kwargs):
            captured_cmd.extend(cmd)
            return mock_result

        monkeypatch.setattr("subprocess.run", mock_run)
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(cli, ["item", "edit", "SRS001"])

        assert result.exit_code == 0
        # Should have called the editor with the item path
        assert len(captured_cmd) == 2
        assert "SRS001.yml" in captured_cmd[1]


class TestLinkCommandsWithMock:
    """Tests for link add/remove commands (native, no subprocess)."""

    def test_link_add(self, runner, tmp_path, monkeypatch):
        """Test link add modifies child YAML to add a link."""
        import yaml

        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  parents:\n  - UN\n  prefix: SRS\n  sep: ''\n")
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: req\n")

        # Also need the UN doc for discovery
        (tmp_path / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: UN\n  sep: ''\n")
        (tmp_path / "UN001.yml").write_text("active: true\ntext: user need\n")

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["link", "add", "SRS001", "UN001"])

        assert result.exit_code == 0
        assert "Linked: SRS001 -> UN001" in result.output

        data = yaml.safe_load((srs_dir / "SRS001.yml").read_text())
        assert "UN001" in data["links"]

    def test_link_remove(self, runner, tmp_path, monkeypatch):
        """Test link remove modifies child YAML to remove a link."""
        import yaml

        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  parents:\n  - UN\n  prefix: SRS\n  sep: ''\n")
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: req\nlinks:\n- UN001\n")

        (tmp_path / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: UN\n  sep: ''\n")

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["link", "remove", "SRS001", "UN001"])

        assert result.exit_code == 0
        assert "Unlinked: SRS001 -> UN001" in result.output

        data = yaml.safe_load((srs_dir / "SRS001.yml").read_text())
        assert data.get("links", []) == []


class TestReviewCommandsWithMock:
    """Tests for review mark command (native, no subprocess)."""

    def test_review_mark(self, runner, tmp_path, monkeypatch):
        """Test review mark writes reviewed hash to item YAML."""
        import yaml

        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n")
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: req\n")

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["review", "mark", "SRS001"])

        assert result.exit_code == 0
        assert "marked item SRS001 as reviewed" in result.output

        data = yaml.safe_load((srs_dir / "SRS001.yml").read_text())
        assert "reviewed" in data
        assert isinstance(data["reviewed"], str)
        assert len(data["reviewed"]) > 0


class TestPublishWithMock:
    """Tests for publish command variants (native markdown publishing)."""

    def test_publish_html(self, runner, tmp_path, monkeypatch):
        """Test publish with --html flag produces real HTML output."""
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n")
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: Software req\nlinks:\n- UN001\n")

        # Also create UN doc for link context
        (tmp_path / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: UN\n  sep: ''\n")
        (tmp_path / "UN001.yml").write_text("active: true\ntext: User need\n")

        output_file = tmp_path / "output.html"
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["publish", "SRS", str(output_file), "--html"])

        assert result.exit_code == 0
        assert output_file.exists()
        content = output_file.read_text()
        assert "<html" in content
        assert "<h1>" in content
        assert "SRS001" in content
        assert "Software req" in content

    def test_publish_html_with_links(self, runner, tmp_path, monkeypatch):
        """Test publish HTML includes hyperlinks for parent and child items."""
        # Create UN (root) and SRS (child) docs
        (tmp_path / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: UN\n  sep: ''\n")
        (tmp_path / "UN001.yml").write_text("active: true\ntext: User need\n")

        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  parents:\n  - UN\n  prefix: SRS\n  sep: ''\n")
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: Software req\nlinks:\n- UN001\n")

        output_file = tmp_path / "output.html"
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["publish", "all", str(output_file), "--html"])

        assert result.exit_code == 0
        content = output_file.read_text()
        # Parent link from SRS001 to UN001
        assert '<a href="#UN001">' in content
        # Child link from UN001 to SRS001
        assert '<a href="#SRS001">' in content

    def test_publish_html_no_child_links(self, runner, tmp_path, monkeypatch):
        """Test publish HTML with --no-links suppresses links."""
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n")
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: req\nlinks:\n- UN001\n")

        output_file = tmp_path / "output.html"
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["publish", "SRS", str(output_file), "--html", "--no-links"])

        assert result.exit_code == 0
        content = output_file.read_text()
        assert "<html" in content
        assert "Links:" not in content
        assert "Linked from:" not in content

    def test_publish_html_all_documents(self, runner, tmp_path, monkeypatch):
        """Test publish all produces HTML with multiple document sections."""
        (tmp_path / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: UN\n  sep: ''\n")
        (tmp_path / "UN001.yml").write_text("active: true\ntext: User need\n")

        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  parents:\n  - UN\n  prefix: SRS\n  sep: ''\n")
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: Software req\nlinks:\n- UN001\n")

        output_file = tmp_path / "all.html"
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["publish", "all", str(output_file), "--html"])

        assert result.exit_code == 0
        content = output_file.read_text()
        assert '<h2 id="doc-UN">' in content
        assert '<h2 id="doc-SRS">' in content

    def test_publish_markdown(self, runner, tmp_path, monkeypatch):
        """Test publish with --markdown flag writes markdown file."""
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n")
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: Software req\n")

        output_file = tmp_path / "output.md"
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["publish", "SRS", str(output_file), "--markdown"])

        assert result.exit_code == 0
        assert output_file.exists()
        content = output_file.read_text()
        assert "SRS001" in content
        assert "Software req" in content

    def test_publish_no_child_links(self, runner, tmp_path, monkeypatch):
        """Test publish with --no-links flag."""
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n")
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: req\n")

        output_file = tmp_path / "output.html"
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["publish", "SRS", str(output_file), "--no-links"])

        assert result.exit_code == 0


class TestInfoErrorHandling:
    """Tests for info command error handling."""

    def test_info_error_handling(self, runner, monkeypatch):
        """Test info command handles exceptions gracefully."""
        from unittest.mock import patch

        with patch(
            "jamb.storage.discover_documents",
            side_effect=ValueError("No documents found"),
        ):
            result = runner.invoke(cli, ["info"])

        assert result.exit_code == 1
        assert "Error" in result.output


class TestCheckWithConfigDocuments:
    """Tests for check command with config.test_documents."""

    def test_check_uses_config_test_documents(self, runner, monkeypatch, tmp_path):
        """Test check command uses test_documents from config."""
        from unittest.mock import MagicMock, patch

        mock_config = MagicMock()
        mock_config.test_documents = ["SRS", "UT"]

        mock_dag = MagicMock()

        mock_graph = MagicMock()
        mock_graph.get_leaf_documents.return_value = ["SRS"]
        mock_graph.get_items_by_document.return_value = []
        mock_graph.items = {}  # Empty dict for unknown UID detection

        with (
            patch("jamb.storage.discover_documents", return_value=mock_dag),
            patch("jamb.storage.build_traceability_graph", return_value=mock_graph),
            patch("jamb.config.loader.load_config", return_value=mock_config),
            patch("jamb.cli.commands._scan_tests_for_requirements", return_value=set()),
        ):
            result = runner.invoke(cli, ["check"])

        assert result.exit_code == 0
        assert "SRS, UT" in result.output

    def test_check_falls_back_to_leaf_documents(self, runner, monkeypatch):
        """Test check command falls back to leaf documents when no config."""
        from unittest.mock import MagicMock, patch

        mock_config = MagicMock()
        mock_config.test_documents = []

        mock_dag = MagicMock()

        mock_graph = MagicMock()
        mock_graph.get_leaf_documents.return_value = ["UT"]
        mock_graph.get_items_by_document.return_value = []
        mock_graph.items = {}  # Empty dict for unknown UID detection

        with (
            patch("jamb.storage.discover_documents", return_value=mock_dag),
            patch("jamb.storage.build_traceability_graph", return_value=mock_graph),
            patch("jamb.config.loader.load_config", return_value=mock_config),
            patch("jamb.cli.commands._scan_tests_for_requirements", return_value=set()),
        ):
            result = runner.invoke(cli, ["check"])

        assert result.exit_code == 0
        assert "UT" in result.output

    def test_check_error_handling(self, runner, monkeypatch):
        """Test check command handles exceptions gracefully."""
        from unittest.mock import patch

        with patch(
            "jamb.storage.discover_documents",
            side_effect=ValueError("No documents found"),
        ):
            result = runner.invoke(cli, ["check"])

        assert result.exit_code == 1
        assert "Error" in result.output


class TestDocListErrorHandling:
    """Tests for doc list command error handling."""

    def test_doc_list_error_handling(self, runner, monkeypatch):
        """Test doc list command handles exceptions gracefully."""
        from unittest.mock import patch

        with patch(
            "jamb.storage.discover_documents",
            side_effect=ValueError("No documents found"),
        ):
            result = runner.invoke(cli, ["doc", "list"])

        assert result.exit_code == 1
        assert "Error" in result.output


class TestExportErrorHandling:
    """Tests for export command error handling."""

    def test_export_error_handling(self, runner, tmp_path, monkeypatch):
        """Test export command handles exceptions gracefully."""
        from unittest.mock import patch

        output_path = tmp_path / "output.yml"

        with patch(
            "jamb.storage.discover_documents",
            side_effect=ValueError("No documents found"),
        ):
            result = runner.invoke(cli, ["export", str(output_path)])

        assert result.exit_code == 1
        assert "Error" in result.output


class TestImportCommandDocuments:
    """Tests for import command document creation."""

    def test_import_shows_would_create_documents(self, runner, tmp_path, monkeypatch):
        """Test import dry-run shows 'Would create X documents'."""
        import yaml

        # Create test YAML file with documents
        yaml_content = {
            "documents": [
                {"prefix": "SRS", "path": "srs"},
                {"prefix": "UT", "path": "ut", "parent": "SRS"},
            ],
            "items": [],
        }
        yaml_file = tmp_path / "import.yml"
        with open(yaml_file, "w") as f:
            yaml.dump(yaml_content, f)

        # Mock _document_exists to return False (documents don't exist)
        from unittest.mock import patch

        with patch("jamb.yaml_io._document_exists", return_value=False):
            result = runner.invoke(cli, ["import", str(yaml_file), "--dry-run"])

        assert result.exit_code == 0
        assert "Would create" in result.output and "document" in result.output

    def test_import_shows_created_documents(self, runner, tmp_path, monkeypatch):
        """Test import shows 'Created X documents'."""
        from unittest.mock import MagicMock, patch

        import yaml

        monkeypatch.chdir(tmp_path)

        # Create test YAML file with documents
        yaml_content = {
            "documents": [
                {"prefix": "SRS", "path": "srs"},
            ],
            "items": [],
        }
        yaml_file = tmp_path / "import.yml"
        with open(yaml_file, "w") as f:
            yaml.dump(yaml_content, f)

        # Mock subprocess.run to succeed
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with (
            patch("jamb.yaml_io._document_exists", return_value=False),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = runner.invoke(cli, ["import", str(yaml_file)])

        assert result.exit_code == 0
        assert "Created" in result.output and "document" in result.output

    def test_import_error_handling(self, runner, tmp_path, monkeypatch):
        """Test import command handles invalid YAML gracefully."""
        # Create invalid YAML file
        yaml_file = tmp_path / "invalid.yml"
        yaml_file.write_text("not: [valid: yaml")

        result = runner.invoke(cli, ["import", str(yaml_file)])

        assert result.exit_code == 1
        assert "Error" in result.output


class TestItemListWithPrefix:
    """Tests for item list command with specific prefix."""

    def test_item_list_with_prefix(self, runner, monkeypatch):
        """Test item list with specific document prefix."""
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        mock_dag = MagicMock()
        mock_dag.document_paths = {"SRS": Path("/fake/srs")}
        mock_dag.topological_sort.return_value = ["SRS"]

        mock_items = [{"uid": "SRS001", "text": "Test requirement text", "active": True}]

        with (
            patch("jamb.storage.discover_documents", return_value=mock_dag),
            patch("jamb.storage.items.read_document_items", return_value=mock_items),
        ):
            result = runner.invoke(cli, ["item", "list", "SRS"])

        assert result.exit_code == 0
        assert "SRS001" in result.output

    def test_item_list_error_handling(self, runner, monkeypatch):
        """Test item list handles errors gracefully."""
        from unittest.mock import patch

        with patch(
            "jamb.storage.discover_documents",
            side_effect=ValueError("No documents found"),
        ):
            result = runner.invoke(cli, ["item", "list"])

        assert result.exit_code == 1
        assert "Error" in result.output


class TestItemShowWithHeader:
    """Tests for item show command showing headers."""

    def test_item_show_with_header(self, runner, monkeypatch):
        """Test item show displays header when present."""
        from pathlib import Path
        from unittest.mock import patch

        mock_data = {
            "uid": "SRS001",
            "document_prefix": "SRS",
            "active": True,
            "type": "requirement",
            "header": "Authentication Requirement",
            "links": [],
            "text": "Test requirement text",
        }

        with (
            patch(
                "jamb.cli.commands._find_item_path",
                return_value=(Path("/fake/SRS001.yml"), "SRS"),
            ),
            patch("jamb.storage.items.read_item", return_value=mock_data),
        ):
            result = runner.invoke(cli, ["item", "show", "SRS001"])

        assert result.exit_code == 0
        assert "Header: Authentication Requirement" in result.output

    def test_item_show_error_handling(self, runner, monkeypatch):
        """Test item show handles errors gracefully."""
        from unittest.mock import patch

        with patch(
            "jamb.storage.discover_documents",
            side_effect=ValueError("Item not found"),
        ):
            result = runner.invoke(cli, ["item", "show", "NONEXISTENT"])

        assert result.exit_code == 1
        assert "Error" in result.output


class TestInitCommand:
    """Tests for jamb init command."""

    def test_init_help(self, runner):
        """Test that init --help works."""
        result = runner.invoke(cli, ["init", "--help"])

        assert result.exit_code == 0
        assert "Initialize" in result.output or "init" in result.output.lower()
        assert "IEC 62304" in result.output

    def test_init_creates_reqs_directory(self, runner, tmp_path, monkeypatch):
        """Test init creates reqs directory with documents."""
        import subprocess

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True,
        )

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["init"], catch_exceptions=False)

        assert result.exit_code == 0
        assert (tmp_path / "reqs").exists()
        assert (tmp_path / "reqs" / "prj").exists()
        assert (tmp_path / "reqs" / "un").exists()
        assert (tmp_path / "reqs" / "sys").exists()
        assert (tmp_path / "reqs" / "srs").exists()
        assert (tmp_path / "reqs" / "haz").exists()
        assert (tmp_path / "reqs" / "rc").exists()
        assert "Created document: PRJ" in result.output
        assert "Created document: UN" in result.output
        assert "Created document: SYS" in result.output
        assert "Created document: SRS" in result.output
        assert "Created document: HAZ" in result.output
        assert "Created document: RC" in result.output

    def test_init_updates_pyproject_toml(self, runner, tmp_path, monkeypatch):
        """Test init adds [tool.jamb] to pyproject.toml."""
        import subprocess

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Create empty pyproject.toml
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n")

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["init"], catch_exceptions=False)

        assert result.exit_code == 0
        content = pyproject.read_text()
        assert "[tool.jamb]" in content
        assert "test_documents" in content
        assert 'trace_to_ignore = ["PRJ"]' in content

    def test_init_skips_existing_jamb_config(self, runner, tmp_path, monkeypatch):
        """Test init skips if [tool.jamb] already exists."""
        import subprocess

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True,
        )

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\n\n[tool.jamb]\ntest_documents = ["UT"]\n')

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["init"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "already has [tool.jamb]" in result.output
        # Original config should be preserved
        content = pyproject.read_text()
        assert '["UT"]' in content

    def test_init_fails_if_documents_exist(self, runner, tmp_path, monkeypatch):
        """Test init fails if documents already exist."""
        import subprocess

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Create existing PRJ document
        reqs_prj = tmp_path / "reqs" / "prj"
        reqs_prj.mkdir(parents=True)
        (reqs_prj / ".jamb.yml").write_text("settings:\n  prefix: PRJ\n")

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["init"])

        assert result.exit_code == 1
        assert "already exist" in result.output

    def test_init_handles_creation_failure(self, runner, tmp_path, monkeypatch):
        """Test init handles creation failure gracefully."""
        from unittest.mock import patch

        monkeypatch.chdir(tmp_path)

        # Mock save_document_config to raise an exception
        with patch(
            "jamb.storage.document_config.save_document_config",
            side_effect=OSError("Permission denied"),
        ):
            result = runner.invoke(cli, ["init"])

        assert result.exit_code == 1
        assert "Failed to create" in result.output

    def test_init_handles_pyproject_update_failure(self, runner, tmp_path, monkeypatch):
        """Test init handles pyproject.toml update failure gracefully."""
        import subprocess

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Create a pyproject.toml that will fail to parse
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("invalid toml [[[")

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["init"], catch_exceptions=False)

        # Should still succeed (warning only) but show warning
        assert "Warning" in result.output or result.exit_code == 0


class TestReviewResetCommand:
    """Tests for review reset command."""

    def test_review_reset_help(self, runner):
        """Test that review reset --help works."""
        result = runner.invoke(cli, ["review", "reset", "--help"])

        assert result.exit_code == 0
        assert "Reset" in result.output or "unreviewed" in result.output.lower()

    def test_review_reset_single_item(self, runner, jamb_project):
        """Test review reset on a single item."""
        import os

        # First mark the item as reviewed
        original_cwd = os.getcwd()
        try:
            os.chdir(jamb_project)
            # Mark as reviewed first
            runner.invoke(cli, ["review", "mark", "SRS001"], catch_exceptions=False)

            # Now reset it
            result = runner.invoke(cli, ["review", "reset", "SRS001"], catch_exceptions=False)
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        # Should indicate item was reset
        assert "reset" in result.output.lower() or "unreviewed" in result.output.lower()

    def test_review_reset_document(self, runner, jamb_project):
        """Test review reset on all items in a document."""
        import os

        # Mark items as reviewed
        srs_file = jamb_project / "srs" / "SRS001.yml"
        content = srs_file.read_text()
        srs_file.write_text(content.replace("active: true", "active: true\nreviewed: abc123"))

        original_cwd = os.getcwd()
        try:
            os.chdir(jamb_project)
            result = runner.invoke(cli, ["review", "reset", "SRS"], catch_exceptions=False)
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0

    def test_review_reset_all(self, runner, jamb_project):
        """Test review reset all."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(jamb_project)
            result = runner.invoke(cli, ["review", "reset", "all"], catch_exceptions=False)
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0

    def test_review_reset_invalid_label(self, runner, jamb_project):
        """Test review reset with invalid label."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(jamb_project)
            result = runner.invoke(cli, ["review", "reset", "NONEXISTENT"])
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 1
        assert "not a valid" in result.output.lower() or "error" in result.output.lower()

    def test_review_reset_strips_link_hashes(self, runner, jamb_project):
        """Test review reset also strips link hashes from items."""
        import os

        import yaml

        # Write an item with reviewed hash and link hashes
        srs_file = jamb_project / "srs" / "SRS001.yml"
        srs_file.write_text("active: true\ntext: Some requirement\nlinks:\n- SYS001: abc123hash\nreviewed: somehash\n")

        original_cwd = os.getcwd()
        try:
            os.chdir(jamb_project)
            result = runner.invoke(cli, ["review", "reset", "SRS001"], catch_exceptions=False)
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        with open(srs_file) as f:
            data = yaml.safe_load(f)
        assert "reviewed" not in data
        # Links should be plain UIDs, not dicts with hashes
        assert data["links"] == ["SYS001"]

    def test_review_reset_no_items_need_reset(self, runner, jamb_project):
        """Test review reset when no items need resetting."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(jamb_project)
            result = runner.invoke(cli, ["review", "reset", "SRS001"], catch_exceptions=False)
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        assert "no items needed resetting" in result.output.lower()

    def test_review_reset_error_handling(self, runner, monkeypatch):
        """Test review reset handles exceptions gracefully."""
        from unittest.mock import patch

        with patch(
            "jamb.storage.discover_documents",
            side_effect=ValueError("Discovery error"),
        ):
            result = runner.invoke(cli, ["review", "reset", "SRS001"])

        assert result.exit_code == 1
        assert "Error" in result.output


class TestReviewClearWithParents:
    """Tests for review clear command with parent arguments (native)."""

    def test_review_clear_help_shows_parents(self, runner):
        """Test that review clear --help shows PARENTS argument."""
        result = runner.invoke(cli, ["review", "clear", "--help"])

        assert result.exit_code == 0
        assert "PARENTS" in result.output

    def test_review_clear_updates_link_hashes(self, runner, tmp_path, monkeypatch):
        """Test review clear updates link hashes in child YAML."""
        import yaml

        # Create UN document with an item
        (tmp_path / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: UN\n  sep: ''\n")
        (tmp_path / "UN001.yml").write_text("active: true\ntext: user need\n")

        # Create SRS document with item linking to UN001
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  parents:\n  - UN\n  prefix: SRS\n  sep: ''\n")
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: req\nlinks:\n- UN001\n")

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["review", "clear", "SRS001", "UN001"])

        assert result.exit_code == 0
        assert "Cleared suspect links on 1 items" in result.output

        # The link should now have a hash
        data = yaml.safe_load((srs_dir / "SRS001.yml").read_text())
        links = data.get("links", [])
        assert len(links) == 1
        # Link should now be a dict with hash
        assert isinstance(links[0], dict)
        assert "UN001" in links[0]


class TestExportWithItemsAndNeighbors:
    """Tests for export command with --items and --neighbors options."""

    def test_export_help_shows_items_option(self, runner):
        """Test that export --help shows --items option."""
        result = runner.invoke(cli, ["export", "--help"])

        assert result.exit_code == 0
        assert "--items" in result.output
        assert "--neighbors" in result.output

    def test_export_specific_items(self, runner, jamb_project):
        """Test export with --items option."""
        output_file = jamb_project / "exported.yml"

        result = runner.invoke(
            cli,
            [
                "export",
                str(output_file),
                "--items",
                "SRS001",
                "--root",
                str(jamb_project),
            ],
        )

        assert result.exit_code == 0
        assert output_file.exists()
        content = output_file.read_text()
        assert "SRS001" in content

    def test_export_with_neighbors(self, runner, jamb_project):
        """Test export with --items and --neighbors options."""
        output_file = jamb_project / "exported.yml"

        result = runner.invoke(
            cli,
            [
                "export",
                str(output_file),
                "--items",
                "SRS001",
                "--neighbors",
                "--root",
                str(jamb_project),
            ],
        )

        assert result.exit_code == 0
        assert output_file.exists()
        content = output_file.read_text()
        # Should include SRS001 and its parent UN001
        assert "SRS001" in content
        assert "UN001" in content

    def test_export_neighbors_requires_items(self, runner, tmp_path):
        """Test that --neighbors requires --items."""
        output_file = tmp_path / "output.yml"

        result = runner.invoke(cli, ["export", str(output_file), "--neighbors"])

        assert result.exit_code == 1
        assert "requires --items" in result.output.lower()


class TestValidateWithFlags:
    """Tests for validate command with various flags (native)."""

    @pytest.fixture
    def validate_project(self, tmp_path, monkeypatch):
        """Create a simple project for validation tests."""
        # Create UN root document
        (tmp_path / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: UN\n  sep: ''\n")
        (tmp_path / "UN001.yml").write_text("active: true\ntext: user need\n")

        # Create SRS child document
        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  parents:\n  - UN\n  prefix: SRS\n  sep: ''\n")
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: Software req\nlinks:\n- UN001\n")

        monkeypatch.chdir(tmp_path)
        return tmp_path

    def test_validate_quiet(self, runner, validate_project):
        """Test validate with --quiet flag."""
        result = runner.invoke(cli, ["validate", "--quiet"])
        # Should accept the flag without error
        assert result.exit_code in (0, 1)

    def test_validate_no_child_check(self, runner, validate_project):
        """Test validate with --no-child-check flag."""
        result = runner.invoke(cli, ["validate", "--no-child-check"])
        assert result.exit_code in (0, 1)

    def test_validate_no_suspect_check(self, runner, validate_project):
        """Test validate with --no-suspect-check flag."""
        result = runner.invoke(cli, ["validate", "--no-suspect-check"])
        assert result.exit_code in (0, 1)

    def test_validate_no_review_check(self, runner, validate_project):
        """Test validate with --no-review-check flag."""
        result = runner.invoke(cli, ["validate", "--no-review-check"])
        assert result.exit_code in (0, 1)

    def test_validate_skip(self, runner, validate_project):
        """Test validate with --skip flag."""
        result = runner.invoke(cli, ["validate", "--skip", "SRS"])
        assert result.exit_code in (0, 1)

    def test_validate_warn_all(self, runner, validate_project):
        """Test validate with --warn-all flag."""
        result = runner.invoke(cli, ["validate", "--warn-all"])
        assert result.exit_code in (0, 1)

    def test_validate_error_all(self, runner, validate_project):
        """Test validate with --error-all flag."""
        result = runner.invoke(cli, ["validate", "--error-all"])
        assert result.exit_code in (0, 1)


class TestItemEditWithTool:
    """Tests for item edit command with --tool option (still uses subprocess)."""

    def test_item_edit_help_shows_tool_option(self, runner):
        """Test that item edit --help shows --tool option."""
        result = runner.invoke(cli, ["item", "edit", "--help"])

        assert result.exit_code == 0
        assert "--tool" in result.output or "-T" in result.output

    def test_item_edit_with_tool(self, runner, tmp_path, monkeypatch):
        """Test item edit with --tool option calls the specified editor."""
        from unittest.mock import MagicMock

        srs_dir = tmp_path / "srs"
        srs_dir.mkdir()
        (srs_dir / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: SRS\n  sep: ''\n")
        (srs_dir / "SRS001.yml").write_text("active: true\ntext: req\n")

        mock_result = MagicMock()
        mock_result.returncode = 0
        captured_cmd = []

        def mock_run(cmd, **kwargs):
            captured_cmd.extend(cmd)
            return mock_result

        monkeypatch.setattr("subprocess.run", mock_run)
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(cli, ["item", "edit", "SRS001", "--tool", "nano"])

        assert result.exit_code == 0
        assert captured_cmd[0] == "nano"
        assert "SRS001.yml" in captured_cmd[1]


class TestScanTestsForRequirements:
    """Tests for _scan_tests_for_requirements function."""

    def test_scan_handles_unparseable_file(self, tmp_path):
        """Test scanning handles files that can't be parsed."""
        from jamb.cli.commands import _scan_tests_for_requirements

        # Create a test directory with an invalid Python file
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        invalid_file = test_dir / "test_invalid.py"
        invalid_file.write_text("def invalid syntax this is not valid python")

        # Should not raise, just skip the file
        result = _scan_tests_for_requirements(tmp_path)
        assert isinstance(result, set)

    def test_is_requirement_marker_returns_false(self):
        """Test _is_requirement_marker returns False for non-requirement markers."""
        import ast

        from jamb.cli.commands import _is_requirement_marker

        # Create an AST node for a different function call
        code = "some_function(arg1, arg2)"
        tree = ast.parse(code)
        call_node = next(node for node in ast.walk(tree) if isinstance(node, ast.Call))

        assert _is_requirement_marker(call_node) is False

    def test_is_requirement_marker_returns_true(self):
        """Test _is_requirement_marker returns True for requirement markers."""
        import ast

        from jamb.cli.commands import _is_requirement_marker

        # Create an AST node for pytest.mark.requirement call
        code = "pytest.mark.requirement('SRS001')"
        tree = ast.parse(code)
        call_node = next(node for node in ast.walk(tree) if isinstance(node, ast.Call))

        assert _is_requirement_marker(call_node) is True


class TestPublishDocx:
    """Tests for publish --docx command."""

    def test_publish_docx_requires_path(self, runner):
        """Test that --docx requires an output path."""
        result = runner.invoke(cli, ["publish", "SRS", "--docx"])

        assert result.exit_code == 1
        assert "requires" in result.output.lower()
        assert "path" in result.output.lower()

    def test_publish_docx_help_shows_option(self, runner):
        """Test that publish --help shows --docx option."""
        result = runner.invoke(cli, ["publish", "--help"])

        assert result.exit_code == 0
        assert "--docx" in result.output or "-d" in result.output
        assert "DOCX" in result.output or "Word" in result.output

    def test_publish_single_document_docx(self, runner, jamb_project):
        """Test publishing a single document as DOCX."""
        import os

        output_file = jamb_project / "output.docx"

        original_cwd = os.getcwd()
        try:
            os.chdir(jamb_project)
            result = runner.invoke(
                cli,
                ["publish", "SRS", str(output_file), "--docx"],
                catch_exceptions=False,
            )
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        assert output_file.exists()
        assert output_file.stat().st_size > 0
        assert "Published" in result.output

    def test_publish_all_documents_docx(self, runner, jamb_project):
        """Test publishing all documents to a single DOCX file."""
        import os

        output_file = jamb_project / "all_requirements.docx"

        original_cwd = os.getcwd()
        try:
            os.chdir(jamb_project)
            result = runner.invoke(
                cli,
                ["publish", "all", str(output_file), "--docx"],
                catch_exceptions=False,
            )
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        assert output_file.exists()
        assert output_file.stat().st_size > 0
        assert "Published" in result.output

    def test_publish_docx_with_no_child_links(self, runner, jamb_project):
        """Test publishing DOCX with --no-links flag."""
        import os

        output_file = jamb_project / "output.docx"

        original_cwd = os.getcwd()
        try:
            os.chdir(jamb_project)
            result = runner.invoke(
                cli,
                ["publish", "SRS", str(output_file), "--docx", "--no-links"],
                catch_exceptions=False,
            )
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        assert output_file.exists()

    def test_publish_docx_nonexistent_document(self, runner, jamb_project):
        """Test publishing DOCX for non-existent document."""
        import os

        output_file = jamb_project / "output.docx"

        original_cwd = os.getcwd()
        try:
            os.chdir(jamb_project)
            result = runner.invoke(
                cli,
                ["publish", "NONEXISTENT", str(output_file), "--docx"],
                catch_exceptions=False,
            )
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 1
        assert "Error" in result.output

    def test_publish_docx_empty_document(self, runner, tmp_path, monkeypatch):
        """Test publishing DOCX when document has no items."""
        # Create empty UN document (no items)
        (tmp_path / ".jamb.yml").write_text("settings:\n  digits: 3\n  prefix: UN\n  sep: ''\n")

        output_file = tmp_path / "output.docx"

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(
            cli,
            ["publish", "UN", str(output_file), "--docx"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1
        assert "No items found" in result.output or "Error" in result.output


class TestMatrixCommand:
    """Tests for the matrix command."""

    @pytest.fixture
    def jamb_file(self, tmp_path):
        """Create a .jamb coverage file for testing."""
        import json

        coverage_data = {
            "version": 1,
            "coverage": {
                "SRS001": {
                    "item": {
                        "uid": "SRS001",
                        "text": "Software requirement",
                        "document_prefix": "SRS",
                        "active": True,
                        "type": "requirement",
                        "header": None,
                        "links": ["SYS001"],
                        "reviewed": None,
                        "derived": False,
                        "testable": True,
                        "custom_attributes": {},
                    },
                    "linked_tests": [
                        {
                            "test_nodeid": "test_srs.py::test_srs001",
                            "item_uid": "SRS001",
                            "test_outcome": "passed",
                            "notes": [],
                            "test_actions": [],
                            "expected_results": [],
                            "actual_results": [],
                            "execution_timestamp": None,
                        }
                    ],
                }
            },
            "graph": {
                "items": {
                    "SYS001": {
                        "uid": "SYS001",
                        "text": "System requirement",
                        "document_prefix": "SYS",
                        "active": True,
                        "type": "requirement",
                        "header": None,
                        "links": [],
                        "reviewed": None,
                        "derived": False,
                        "testable": True,
                        "custom_attributes": {},
                    },
                    "SRS001": {
                        "uid": "SRS001",
                        "text": "Software requirement",
                        "document_prefix": "SRS",
                        "active": True,
                        "type": "requirement",
                        "header": None,
                        "links": ["SYS001"],
                        "reviewed": None,
                        "derived": False,
                        "testable": True,
                        "custom_attributes": {},
                    },
                },
                "item_parents": {"SRS001": ["SYS001"]},
                "item_children": {"SYS001": ["SRS001"]},
                "document_parents": {"SRS": ["SYS"], "SYS": []},
            },
        }

        jamb_path = tmp_path / ".jamb"
        jamb_path.write_text(json.dumps(coverage_data))
        return jamb_path

    def test_matrix_help(self, runner):
        """Test that matrix --help works."""
        result = runner.invoke(cli, ["matrix", "--help"])

        assert result.exit_code == 0
        assert "OUTPUT" in result.output
        assert "--trace-from" in result.output
        assert "--include-ancestors" in result.output
        assert "--test-records" in result.output

    def test_matrix_missing_jamb_file(self, runner, tmp_path):
        """Test matrix command errors on missing .jamb file."""
        output = tmp_path / "matrix.html"

        result = runner.invoke(
            cli,
            ["matrix", str(output), "--input", str(tmp_path / ".jamb")],
        )

        # Exit code 1 for custom error, 2 for click error (file not found)
        assert result.exit_code in (1, 2)
        assert (
            "not found" in result.output.lower()
            or "error" in result.output.lower()
            or "does not exist" in result.output.lower()
        )

    def test_matrix_with_trace_from(self, runner, tmp_path, jamb_file):
        """Test matrix command with --trace-from option."""
        output = tmp_path / "matrix.html"

        result = runner.invoke(
            cli,
            [
                "matrix",
                str(output),
                "--input",
                str(jamb_file),
                "--trace-from",
                "SYS",
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        assert output.exists()
        assert "Generated trace matrix" in result.output

    def test_matrix_with_include_ancestors(self, runner, tmp_path, jamb_file):
        """Test matrix command with --include-ancestors option."""
        output = tmp_path / "matrix.html"

        result = runner.invoke(
            cli,
            [
                "matrix",
                str(output),
                "--input",
                str(jamb_file),
                "--trace-from",
                "SYS",
                "--include-ancestors",
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        assert output.exists()

    def test_matrix_with_test_records(self, runner, tmp_path, jamb_file):
        """Test matrix command with --test-records option."""
        output = tmp_path / "test-records.html"

        result = runner.invoke(
            cli,
            [
                "matrix",
                str(output),
                "--input",
                str(jamb_file),
                "--test-records",
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        assert output.exists()
        assert "test records matrix" in result.output.lower()

    @pytest.mark.parametrize(
        "extension,content_check",
        [
            ("html", lambda c: "<html" in c.lower()),
            ("json", lambda c: '"matrices"' in c or '"items"' in c),
            ("csv", lambda c: "SYS" in c or "Path" in c),
            ("md", lambda c: "# " in c or "|" in c),
        ],
        ids=["html", "json", "csv", "markdown"],
    )
    def test_matrix_format_inference_text(self, runner, tmp_path, jamb_file, extension, content_check):
        """Test that file extension correctly infers text-based output format."""
        output = tmp_path / f"matrix.{extension}"

        result = runner.invoke(
            cli,
            [
                "matrix",
                str(output),
                "--input",
                str(jamb_file),
                "--trace-from",
                "SYS",
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        content = output.read_text()
        assert content_check(content)

    def test_matrix_format_inference_xlsx(self, runner, tmp_path, jamb_file):
        """Test that .xlsx extension infers XLSX format (binary check)."""
        output = tmp_path / "matrix.xlsx"

        result = runner.invoke(
            cli,
            [
                "matrix",
                str(output),
                "--input",
                str(jamb_file),
                "--trace-from",
                "SYS",
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        assert output.exists()
        # XLSX files start with PK (ZIP header)
        content = output.read_bytes()
        assert content[:2] == b"PK"

    def test_matrix_creates_parent_directories(self, runner, tmp_path, jamb_file):
        """Test that matrix command creates parent directories."""
        output = tmp_path / "subdir" / "nested" / "matrix.html"

        result = runner.invoke(
            cli,
            [
                "matrix",
                str(output),
                "--input",
                str(jamb_file),
                "--trace-from",
                "SYS",
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        assert output.exists()

    def test_matrix_with_trace_to_ignore(self, runner, tmp_path, jamb_file):
        """Test matrix command with --trace-to-ignore option."""
        output = tmp_path / "matrix.html"

        result = runner.invoke(
            cli,
            [
                "matrix",
                str(output),
                "--input",
                str(jamb_file),
                "--trace-from",
                "SYS",
                "--trace-to-ignore",
                "PRJ",
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        assert output.exists()

    def test_matrix_corrupt_jamb_file(self, runner, tmp_path):
        """Test matrix command with corrupt .jamb file."""
        # Create corrupt .jamb file
        jamb_path = tmp_path / ".jamb"
        jamb_path.write_text('{"version": 999}')

        output = tmp_path / "matrix.html"

        result = runner.invoke(
            cli,
            ["matrix", str(output), "--input", str(jamb_path)],
        )

        assert result.exit_code == 1
        assert "Error" in result.output

    def test_matrix_unrecognized_extension(self, runner, tmp_path, jamb_file):
        """Test matrix command with unrecognized file extension."""
        output = tmp_path / "matrix.xyz"

        result = runner.invoke(
            cli,
            ["matrix", str(output), "--input", str(jamb_file), "--trace-from", "SYS"],
        )

        assert result.exit_code == 1
        assert "Unrecognized file extension" in result.output
