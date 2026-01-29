"""Tests for jamb.config.loader module."""

import warnings

from jamb.config.loader import (
    JambConfig,
    _extract_version_from_file,
    _get_dynamic_version,
    load_config,
)


class TestJambConfig:
    """Tests for JambConfig dataclass."""

    def test_default_values(self):
        """Test that JambConfig has sensible defaults."""
        config = JambConfig()

        assert config.test_documents == []
        assert config.fail_uncovered is False
        assert config.require_all_pass is True
        assert config.test_matrix_output is None
        assert config.trace_matrix_output is None
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
        assert config.test_matrix_output == "test-records.html"
        assert config.trace_matrix_output == "traceability.html"

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
        assert config.test_matrix_output is None  # Default
        assert config.trace_matrix_output is None  # Default

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
test_matrix_output = "output/test-records.html"
trace_matrix_output = "output/traceability.md"
exclude_patterns = ["**/skip_*.py"]
trace_to_ignore = ["PRJ", "UN"]
"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(content)

        config = load_config(pyproject)

        assert config.test_documents == ["SRS", "SYS", "REQ"]
        assert config.fail_uncovered is True
        assert config.require_all_pass is False
        assert config.test_matrix_output == "output/test-records.html"
        assert config.trace_matrix_output == "output/traceability.md"
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

    def test_unknown_key_warning(self, tmp_path):
        """Unknown keys emit a warning."""
        import warnings

        content = """
[tool.jamb]
unknown_key = "value"
"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(content)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            load_config(pyproject)
            assert len(w) == 1
            assert "Unrecognized keys" in str(w[0].message)

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

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
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


class TestExtractVersionFromFile:
    """Tests for _extract_version_from_file function."""

    def test_extracts_dunder_version_double_quotes(self, tmp_path):
        """Extract __version__ = "1.2.3"."""
        version_file = tmp_path / "_version.py"
        version_file.write_text('__version__ = "1.2.3"\n')
        assert _extract_version_from_file(version_file) == "1.2.3"

    def test_extracts_dunder_version_single_quotes(self, tmp_path):
        """Extract __version__ = '1.2.3'."""
        version_file = tmp_path / "_version.py"
        version_file.write_text("__version__ = '1.2.3'\n")
        assert _extract_version_from_file(version_file) == "1.2.3"

    def test_extracts_version_equals_pattern(self, tmp_path):
        """Extract __version__ = version = '1.2.3'."""
        version_file = tmp_path / "_version.py"
        version_file.write_text("__version__ = version = '1.2.3'\n")
        assert _extract_version_from_file(version_file) == "1.2.3"

    def test_extracts_VERSION_constant(self, tmp_path):
        """Extract VERSION = "1.2.3"."""
        version_file = tmp_path / "_version.py"
        version_file.write_text('VERSION = "1.2.3"\n')
        assert _extract_version_from_file(version_file) == "1.2.3"

    def test_extracts_prerelease_version(self, tmp_path):
        """Extract version with prerelease suffix."""
        version_file = tmp_path / "_version.py"
        version_file.write_text('__version__ = "1.2.3-alpha.1"\n')
        assert _extract_version_from_file(version_file) == "1.2.3-alpha.1"

    def test_extracts_dev_version(self, tmp_path):
        """Extract version with dev suffix."""
        version_file = tmp_path / "_version.py"
        version_file.write_text('__version__ = "1.2.3.dev5+g1234abc"\n')
        assert _extract_version_from_file(version_file) == "1.2.3.dev5+g1234abc"

    def test_returns_none_for_nonexistent_file(self, tmp_path):
        """Return None if file doesn't exist."""
        version_file = tmp_path / "nonexistent.py"
        assert _extract_version_from_file(version_file) is None

    def test_returns_none_for_no_version_pattern(self, tmp_path):
        """Return None if no version pattern found."""
        version_file = tmp_path / "_version.py"
        version_file.write_text("# No version here\nfoo = 'bar'\n")
        assert _extract_version_from_file(version_file) is None

    def test_handles_multiline_file(self, tmp_path):
        """Extract version from multiline file."""
        version_file = tmp_path / "_version.py"
        content = """# Generated by hatch-vcs
__version__ = "0.5.2"
__version_tuple__ = (0, 5, 2)
"""
        version_file.write_text(content)
        assert _extract_version_from_file(version_file) == "0.5.2"


class TestGetDynamicVersion:
    """Tests for _get_dynamic_version function."""

    def test_hatch_vcs_version_file(self, tmp_path):
        """Get version from hatch-vcs version-file."""
        version_file = tmp_path / "src" / "pkg" / "_version.py"
        version_file.parent.mkdir(parents=True)
        version_file.write_text('__version__ = "2.0.0"\n')

        pyproject = {"tool": {"hatch": {"build": {"hooks": {"vcs": {"version-file": "src/pkg/_version.py"}}}}}}
        assert _get_dynamic_version(pyproject, tmp_path) == "2.0.0"

    def test_hatch_version_path(self, tmp_path):
        """Get version from hatch version path."""
        version_file = tmp_path / "mypackage" / "_version.py"
        version_file.parent.mkdir(parents=True)
        version_file.write_text('__version__ = "3.1.0"\n')

        pyproject = {"tool": {"hatch": {"version": {"path": "mypackage/_version.py"}}}}
        assert _get_dynamic_version(pyproject, tmp_path) == "3.1.0"

    def test_setuptools_scm_write_to(self, tmp_path):
        """Get version from setuptools_scm write_to."""
        version_file = tmp_path / "src" / "_version.py"
        version_file.parent.mkdir(parents=True)
        version_file.write_text('__version__ = "4.0.0"\n')

        pyproject = {"tool": {"setuptools_scm": {"write_to": "src/_version.py"}}}
        assert _get_dynamic_version(pyproject, tmp_path) == "4.0.0"

    def test_returns_none_when_no_tool_section(self, tmp_path):
        """Return None if no tool section."""
        pyproject: dict = {}
        assert _get_dynamic_version(pyproject, tmp_path) is None

    def test_returns_none_when_version_file_missing(self, tmp_path):
        """Return None if version file doesn't exist."""
        pyproject = {"tool": {"hatch": {"build": {"hooks": {"vcs": {"version-file": "nonexistent.py"}}}}}}
        assert _get_dynamic_version(pyproject, tmp_path) is None

    def test_first_match_wins(self, tmp_path):
        """First matching config wins."""
        # Create both version files with different versions
        hatch_vcs_file = tmp_path / "hatch_vcs_version.py"
        hatch_vcs_file.write_text('__version__ = "1.0.0"\n')

        hatch_path_file = tmp_path / "hatch_path_version.py"
        hatch_path_file.write_text('__version__ = "2.0.0"\n')

        pyproject = {
            "tool": {
                "hatch": {
                    "build": {"hooks": {"vcs": {"version-file": "hatch_vcs_version.py"}}},
                    "version": {"path": "hatch_path_version.py"},
                }
            }
        }
        # hatch-vcs should be checked first
        assert _get_dynamic_version(pyproject, tmp_path) == "1.0.0"


class TestLoadConfigSoftwareVersion:
    """Tests for software_version loading in load_config."""

    def test_software_version_default_none(self, tmp_path):
        """software_version defaults to None if not set."""
        content = """
[tool.jamb]
test_documents = ["SRS"]
"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(content)
        config = load_config(pyproject)
        assert config.software_version is None

    def test_software_version_from_jamb_config(self, tmp_path):
        """software_version from [tool.jamb] takes priority."""
        content = """
[project]
version = "1.0.0"

[tool.jamb]
software_version = "2.0.0"
"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(content)
        config = load_config(pyproject)
        assert config.software_version == "2.0.0"

    def test_software_version_from_project_version(self, tmp_path):
        """software_version falls back to [project].version."""
        content = """
[project]
name = "mypackage"
version = "1.5.0"

[tool.jamb]
test_documents = ["SRS"]
"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(content)
        config = load_config(pyproject)
        assert config.software_version == "1.5.0"

    def test_software_version_dynamic_hatch_vcs(self, tmp_path):
        """software_version from dynamic hatch-vcs."""
        version_file = tmp_path / "src" / "_version.py"
        version_file.parent.mkdir(parents=True)
        version_file.write_text('__version__ = "3.0.0"\n')

        content = """
[project]
name = "mypackage"
dynamic = ["version"]

[tool.hatch.build.hooks.vcs]
version-file = "src/_version.py"
"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(content)
        config = load_config(pyproject)
        assert config.software_version == "3.0.0"

    def test_software_version_dynamic_not_in_list(self, tmp_path):
        """software_version None if dynamic doesn't include 'version'."""
        content = """
[project]
name = "mypackage"
dynamic = ["readme"]

[tool.hatch.build.hooks.vcs]
version-file = "src/_version.py"
"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(content)
        config = load_config(pyproject)
        assert config.software_version is None


class TestGetDynamicVersionPathEscape:
    """Tests for _get_dynamic_version path escape handling."""

    def test_get_dynamic_version_path_escape_hatch_vcs(self, tmp_path):
        """_get_dynamic_version rejects paths outside project root (hatch-vcs)."""
        # Create a version file outside the project root
        outside_file = tmp_path.parent / "outside_version.py"
        outside_file.write_text('__version__ = "9.9.9"\n')

        pyproject = {"tool": {"hatch": {"build": {"hooks": {"vcs": {"version-file": "../outside_version.py"}}}}}}

        # Should return None because path escapes project root
        result = _get_dynamic_version(pyproject, tmp_path)
        assert result is None

    def test_get_dynamic_version_path_escape_hatch_version(self, tmp_path):
        """_get_dynamic_version rejects paths outside project root (hatch version)."""
        outside_file = tmp_path.parent / "escape_version.py"
        outside_file.write_text('__version__ = "8.8.8"\n')

        pyproject = {"tool": {"hatch": {"version": {"path": "../escape_version.py"}}}}

        result = _get_dynamic_version(pyproject, tmp_path)
        assert result is None

    def test_get_dynamic_version_path_escape_setuptools_scm(self, tmp_path):
        """_get_dynamic_version rejects paths outside project root (setuptools_scm)."""
        outside_file = tmp_path.parent / "scm_version.py"
        outside_file.write_text('__version__ = "7.7.7"\n')

        pyproject = {"tool": {"setuptools_scm": {"write_to": "../scm_version.py"}}}

        result = _get_dynamic_version(pyproject, tmp_path)
        assert result is None


class TestExtractVersionFromFileErrors:
    """Tests for _extract_version_from_file error handling."""

    def test_extract_version_permission_error(self, tmp_path):
        """Extract version handles file permission error gracefully."""
        from unittest.mock import patch

        version_file = tmp_path / "_version.py"
        version_file.write_text('__version__ = "1.0.0"\n')

        # Mock read_text to raise OSError
        with patch.object(type(version_file), "read_text", side_effect=OSError("Permission denied")):
            result = _extract_version_from_file(version_file)
            assert result is None

    def test_extract_version_unicode_error(self, tmp_path):
        """Extract version handles UnicodeDecodeError gracefully."""
        version_file = tmp_path / "_version.py"
        # Write invalid UTF-8 bytes
        version_file.write_bytes(b"\x80\x81\x82invalid")

        result = _extract_version_from_file(version_file)
        assert result is None


class TestJambConfigValidation:
    """Tests for JambConfig.validate method."""

    def test_validate_trace_from_not_in_documents(self):
        """validate returns warning for trace_from not in documents."""
        config = JambConfig(trace_from="MISSING")
        warnings = config.validate(["SRS", "SYS", "UN"])
        assert any("trace_from" in w for w in warnings)
        assert any("MISSING" in w for w in warnings)

    def test_validate_test_documents_not_in_documents(self):
        """validate returns warning for test_documents not in documents."""
        config = JambConfig(test_documents=["SRS", "UNKNOWN"])
        warnings = config.validate(["SRS", "SYS"])
        assert any("test_documents" in w for w in warnings)
        assert any("UNKNOWN" in w for w in warnings)

    def test_validate_trace_to_ignore_not_in_documents(self):
        """validate returns warning for trace_to_ignore not in documents."""
        config = JambConfig(trace_to_ignore=["PRJ", "FAKE"])
        warnings = config.validate(["PRJ", "SRS"])
        assert any("trace_to_ignore" in w for w in warnings)
        assert any("FAKE" in w for w in warnings)

    def test_validate_all_valid(self):
        """validate returns empty list when all config is valid."""
        config = JambConfig(
            test_documents=["SRS"],
            trace_from="UN",
            trace_to_ignore=["PRJ"],
        )
        warnings = config.validate(["UN", "SRS", "PRJ"])
        assert warnings == []
