"""Tests for jamb.config.loader module."""

from jamb.config.loader import JambConfig, load_config


class TestJambConfig:
    """Tests for JambConfig dataclass."""

    def test_default_values(self):
        """Test that JambConfig has sensible defaults."""
        config = JambConfig()

        assert config.test_documents == []
        assert config.fail_uncovered is False
        assert config.require_all_pass is True
        assert config.matrix_output is None
        assert config.matrix_format == "html"
        assert config.exclude_patterns == []
        assert config.trace_to_ignore == []


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_missing_file(self, tmp_path):
        """Test that missing config file returns defaults."""
        config = load_config(tmp_path / "nonexistent.toml")

        assert config.test_documents == []
        assert config.fail_uncovered is False

    def test_load_config_empty_jamb_section(self, empty_pyproject):
        """Test loading config without [tool.jamb] section."""
        config = load_config(empty_pyproject)

        assert config.test_documents == []
        assert config.fail_uncovered is False

    def test_load_config_with_all_options(self, sample_pyproject):
        """Test loading config with all options set."""
        config = load_config(sample_pyproject)

        assert config.test_documents == ["SRS", "SYS"]
        assert config.fail_uncovered is True
        assert config.matrix_output == "matrix.html"
        assert config.matrix_format == "html"

    def test_load_config_partial_options(self, tmp_path):
        """Test loading config with partial options."""
        content = """
[tool.jamb]
test_documents = ["UT"]
"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(content)

        config = load_config(pyproject)

        assert config.test_documents == ["UT"]
        assert config.fail_uncovered is False  # Default
        assert config.matrix_format == "html"  # Default

    def test_load_config_default_path(self, tmp_path, monkeypatch):
        """Test loading from default pyproject.toml in cwd."""
        content = """
[tool.jamb]
test_documents = ["SRS"]
"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(content)

        monkeypatch.chdir(tmp_path)
        config = load_config()

        assert config.test_documents == ["SRS"]

    def test_load_config_with_exclude_patterns(self, tmp_path):
        """Test loading config with exclude_patterns."""
        content = """
[tool.jamb]
test_documents = ["SRS"]
exclude_patterns = ["test_*.py", "*_test.py"]
"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(content)

        config = load_config(pyproject)

        assert config.exclude_patterns == ["test_*.py", "*_test.py"]

    def test_load_config_with_require_all_pass_false(self, tmp_path):
        """Test loading config with require_all_pass set to false."""
        content = """
[tool.jamb]
require_all_pass = false
"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(content)

        config = load_config(pyproject)

        assert config.require_all_pass is False

    def test_load_config_all_fields(self, tmp_path):
        """Test loading config with all fields populated."""
        content = """
[tool.jamb]
test_documents = ["SRS", "SYS", "REQ"]
fail_uncovered = true
require_all_pass = false
matrix_output = "output/matrix.html"
matrix_format = "markdown"
exclude_patterns = ["**/skip_*.py"]
trace_to_ignore = ["PRJ", "UN"]
"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(content)

        config = load_config(pyproject)

        assert config.test_documents == ["SRS", "SYS", "REQ"]
        assert config.fail_uncovered is True
        assert config.require_all_pass is False
        assert config.matrix_output == "output/matrix.html"
        assert config.matrix_format == "markdown"
        assert config.exclude_patterns == ["**/skip_*.py"]
        assert config.trace_to_ignore == ["PRJ", "UN"]

    def test_load_config_with_trace_to_ignore(self, tmp_path):
        """Test loading config with trace_to_ignore."""
        content = """
[tool.jamb]
test_documents = ["SRS"]
trace_to_ignore = ["PRJ", "UN"]
"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(content)

        config = load_config(pyproject)

        assert config.trace_to_ignore == ["PRJ", "UN"]

    def test_load_config_wrong_type_test_documents(self, tmp_path):
        """9a: test_documents as string instead of list — documents behavior."""
        content = """
[tool.jamb]
test_documents = "SRS"
"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(content)

        config = load_config(pyproject)
        # TOML parser returns "SRS" as a string, load_config passes it through
        assert config.test_documents == "SRS"


class TestLoadConfigTypeEdgeCases:
    """Document current behavior: no type validation on config values."""

    def test_test_documents_as_dict(self, tmp_path):
        """test_documents = {SRS = true} passes through as dict."""
        content = """
[tool.jamb]
test_documents = {SRS = true}
"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(content)

        config = load_config(pyproject)
        assert config.test_documents == {"SRS": True}

    def test_fail_uncovered_as_string(self, tmp_path):
        """fail_uncovered = 'yes' passes through as string."""
        content = """
[tool.jamb]
fail_uncovered = "yes"
"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(content)

        config = load_config(pyproject)
        assert config.fail_uncovered == "yes"

    def test_matrix_format_as_int(self, tmp_path):
        """matrix_format = 42 passes through as int."""
        content = """
[tool.jamb]
matrix_format = 42
"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(content)

        config = load_config(pyproject)
        assert config.matrix_format == 42

    def test_exclude_patterns_as_string(self, tmp_path):
        """exclude_patterns = '*.py' passes through as string."""
        content = """
[tool.jamb]
exclude_patterns = "*.py"
"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(content)

        config = load_config(pyproject)
        assert config.exclude_patterns == "*.py"

    def test_trace_to_ignore_as_dict(self, tmp_path):
        """trace_to_ignore = {PRJ = true} passes through as dict."""
        content = """
[tool.jamb]
trace_to_ignore = {PRJ = true}
"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(content)

        config = load_config(pyproject)
        assert config.trace_to_ignore == {"PRJ": True}

    def test_extra_unknown_keys_ignored(self, tmp_path):
        """Unknown keys don't break loading."""
        content = """
[tool.jamb]
test_documents = ["SRS"]
totally_unknown_key = "hello"
another_fake = 99
"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(content)

        config = load_config(pyproject)
        assert config.test_documents == ["SRS"]
        assert not hasattr(config, "totally_unknown_key")

    def test_malformed_toml_raises(self, tmp_path):
        """Invalid TOML syntax raises an exception."""
        import pytest

        content = """
[tool.jamb
test_documents = ["SRS"
"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(content)

        with pytest.raises(Exception):  # noqa: B017
            load_config(pyproject)
