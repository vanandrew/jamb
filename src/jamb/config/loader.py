"""Load jamb configuration from pyproject.toml."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib  # type: ignore[import-not-found]
except ImportError:
    import tomli as tomllib


@dataclass
class JambConfig:
    """Configuration schema for jamb.

    Attributes:
        test_documents (list[str]): Document prefixes that represent test
            specifications.
        fail_uncovered (bool): Fail the pytest session when any normative item
            lacks test coverage.
        require_all_pass (bool): Require all linked tests to pass for an item
            to be considered covered.
        matrix_output (str | None): File path for the generated traceability matrix,
            or ``None`` to skip generation.
        matrix_format (str): Output format for the traceability matrix
            (``"html"``, ``"markdown"``, ``"json"``, ``"csv"``, or
            ``"xlsx"``).
        exclude_patterns (list[str]): Glob patterns for documents or items to
            exclude from processing.
        trace_to_ignore (list[str]): Document prefixes to exclude from the
            "Traces To" column in the traceability matrix.
        software_version (str | None): Software version for the traceability matrix.
            If None, auto-parsed from ``[project].version`` in pyproject.toml.

    Examples:
        Construct a config with custom settings::

            >>> config = JambConfig(
            ...     test_documents=["SRS"],
            ...     fail_uncovered=True,
            ...     matrix_output="matrix.html",
            ... )
            >>> config.test_documents
            ['SRS']
            >>> config.fail_uncovered
            True
    """

    test_documents: list[str] = field(default_factory=list)
    fail_uncovered: bool = False
    require_all_pass: bool = True
    matrix_output: str | None = None
    matrix_format: str = "html"
    exclude_patterns: list[str] = field(default_factory=list)
    trace_to_ignore: list[str] = field(default_factory=list)
    software_version: str | None = None


def _extract_version_from_file(version_file: Path) -> str | None:
    """Extract version string from a Python version file.

    Looks for patterns like:
    - __version__ = "1.2.3"
    - __version__ = '1.2.3'
    - __version__ = version = '1.2.3'
    - VERSION = "1.2.3"

    Args:
        version_file: Path to the version file.

    Returns:
        The version string if found, None otherwise.
    """
    if not version_file.exists():
        return None

    try:
        content = version_file.read_text()
        # Match __version__ = "..." or __version__ = version = "..." or VERSION = "..."
        # The pattern captures the quoted version string at the end
        pattern = (
            r"""(?:__version__|VERSION)\s*=\s*"""
            r"""(?:version\s*=\s*)?['"]([\d.]+(?:[-+.a-zA-Z0-9]+)?)['"]\s*$"""
        )
        match = re.search(pattern, content, re.MULTILINE)
        if match:
            return match.group(1)
    except (OSError, UnicodeDecodeError):
        pass

    return None


def _get_dynamic_version(pyproject: dict[str, Any], project_root: Path) -> str | None:
    """Get version from dynamic version file configurations.

    Checks common build tool configurations:
    - [tool.hatch.build.hooks.vcs].version-file (hatch-vcs)
    - [tool.hatch.version].path (hatch path-based)
    - [tool.setuptools_scm].write_to (setuptools_scm)

    Args:
        pyproject: Parsed pyproject.toml content.
        project_root: Root directory of the project.

    Returns:
        The version string if found, None otherwise.
    """
    tool = pyproject.get("tool", {})

    # Check hatch-vcs: [tool.hatch.build.hooks.vcs].version-file
    version_file = (
        tool.get("hatch", {})
        .get("build", {})
        .get("hooks", {})
        .get("vcs", {})
        .get("version-file")
    )
    if version_file:
        version = _extract_version_from_file(project_root / version_file)
        if version:
            return version

    # Check hatch path-based: [tool.hatch.version].path
    version_file = tool.get("hatch", {}).get("version", {}).get("path")
    if version_file:
        version = _extract_version_from_file(project_root / version_file)
        if version:
            return version

    # Check setuptools_scm: [tool.setuptools_scm].write_to
    version_file = tool.get("setuptools_scm", {}).get("write_to")
    if version_file:
        version = _extract_version_from_file(project_root / version_file)
        if version:
            return version

    return None


def load_config(config_path: Path | None = None) -> JambConfig:
    """
    Load jamb configuration from pyproject.toml.

    Looks for [tool.jamb] section. Also auto-parses software version from
    [project].version if not explicitly set in [tool.jamb].

    Args:
        config_path: Optional path to pyproject.toml. If None, uses cwd.

    Returns:
        JambConfig with loaded values or defaults.

    Examples:
        Load configuration from the default path (``pyproject.toml`` in
        the current working directory)::

            >>> config = load_config()
            >>> config.matrix_format
            'html'

        Load from a specific path::

            >>> from pathlib import Path
            >>> config = load_config(Path("myproject/pyproject.toml"))
    """
    if config_path is None:
        config_path = Path.cwd() / "pyproject.toml"

    if not config_path.exists():
        return JambConfig()

    with open(config_path, "rb") as f:
        pyproject = tomllib.load(f)

    jamb_config = pyproject.get("tool", {}).get("jamb", {})

    # Get software_version with fallback chain:
    # 1. [tool.jamb].software_version (explicit override)
    # 2. [project].version (static version)
    # 3. Dynamic version file (hatch-vcs, setuptools_scm, etc.)
    software_version = jamb_config.get("software_version")
    if software_version is None:
        software_version = pyproject.get("project", {}).get("version")
    if software_version is None:
        # Check if version is dynamic and try to read from version file
        dynamic = pyproject.get("project", {}).get("dynamic", [])
        if "version" in dynamic:
            software_version = _get_dynamic_version(pyproject, config_path.parent)

    return JambConfig(
        test_documents=jamb_config.get("test_documents", []),
        fail_uncovered=jamb_config.get("fail_uncovered", False),
        require_all_pass=jamb_config.get("require_all_pass", True),
        matrix_output=jamb_config.get("matrix_output"),
        matrix_format=jamb_config.get("matrix_format", "html"),
        exclude_patterns=jamb_config.get("exclude_patterns", []),
        trace_to_ignore=jamb_config.get("trace_to_ignore", []),
        software_version=software_version,
    )
