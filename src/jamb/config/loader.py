"""Load jamb configuration from pyproject.toml."""

import re
import warnings
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
        test_matrix_output (str | None): File path for the generated test records
            matrix, or ``None`` to skip generation. Format is inferred from
            file extension (``.html``, ``.json``, ``.csv``, ``.md``, ``.xlsx``).
        trace_matrix_output (str | None): File path for the generated traceability
            matrix, or ``None`` to skip generation. Format is inferred from
            file extension (``.html``, ``.json``, ``.csv``, ``.md``, ``.xlsx``).
        exclude_patterns (list[str]): Glob patterns for documents or items to
            exclude from processing.
        trace_to_ignore (list[str]): Document prefixes to exclude from the
            "Traces To" column in the traceability matrix.
        software_version (str | None): Software version for the traceability matrix.
            If None, auto-parsed from ``[project].version`` in pyproject.toml.
        trace_from (str | None): Starting document prefix for full chain trace
            matrix generation. When set, generates a full chain matrix instead
            of the simple trace matrix.
        include_ancestors (bool): Whether to include a "Traces To" column
            showing ancestors of the starting items in full chain matrices.

    Examples:
        Construct a config with custom settings::

            >>> config = JambConfig(
            ...     test_documents=["SRS"],
            ...     fail_uncovered=True,
            ...     test_matrix_output="test-records.html",
            ... )
            >>> config.test_documents
            ['SRS']
            >>> config.fail_uncovered
            True
    """

    test_documents: list[str] = field(default_factory=list)
    fail_uncovered: bool = False
    require_all_pass: bool = True
    test_matrix_output: str | None = None
    trace_matrix_output: str | None = None
    exclude_patterns: list[str] = field(default_factory=list)
    trace_to_ignore: list[str] = field(default_factory=list)
    software_version: str | None = None
    trace_from: str | None = None
    include_ancestors: bool = False

    def validate(self, available_documents: list[str]) -> list[str]:
        """Validate configuration against available documents.

        Args:
            available_documents: List of document prefixes discovered in the project.

        Returns:
            List of validation warning messages. Empty if no issues found.
        """
        validation_warnings: list[str] = []

        if self.trace_from and self.trace_from not in available_documents:
            validation_warnings.append(
                f"trace_from '{self.trace_from}' not found in documents: {', '.join(sorted(available_documents))}"
            )

        for doc in self.test_documents:
            if doc not in available_documents:
                validation_warnings.append(f"test_documents contains '{doc}' not in available documents")

        for doc in self.trace_to_ignore:
            if doc not in available_documents:
                validation_warnings.append(f"trace_to_ignore contains '{doc}' not in available documents")

        return validation_warnings


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
    version_file = tool.get("hatch", {}).get("build", {}).get("hooks", {}).get("vcs", {}).get("version-file")
    if version_file:
        resolved = (project_root / version_file).resolve()
        if not resolved.is_relative_to(project_root.resolve()):
            pass
        else:
            version = _extract_version_from_file(resolved)
            if version:
                return version

    # Check hatch path-based: [tool.hatch.version].path
    version_file = tool.get("hatch", {}).get("version", {}).get("path")
    if version_file:
        resolved = (project_root / version_file).resolve()
        if not resolved.is_relative_to(project_root.resolve()):
            pass
        else:
            version = _extract_version_from_file(resolved)
            if version:
                return version

    # Check setuptools_scm: [tool.setuptools_scm].write_to
    version_file = tool.get("setuptools_scm", {}).get("write_to")
    if version_file:
        resolved = (project_root / version_file).resolve()
        if not resolved.is_relative_to(project_root.resolve()):
            pass
        else:
            version = _extract_version_from_file(resolved)
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

    RECOGNIZED_KEYS = {
        "test_documents",
        "fail_uncovered",
        "require_all_pass",
        "test_matrix_output",
        "trace_matrix_output",
        "exclude_patterns",
        "trace_to_ignore",
        "software_version",
        "trace_from",
        "include_ancestors",
    }
    unknown = set(jamb_config.keys()) - RECOGNIZED_KEYS
    if unknown:
        warnings.warn(
            f"Unrecognized keys in [tool.jamb]: {', '.join(sorted(unknown))}",
            stacklevel=2,
        )

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
        test_matrix_output=jamb_config.get("test_matrix_output"),
        trace_matrix_output=jamb_config.get("trace_matrix_output"),
        exclude_patterns=jamb_config.get("exclude_patterns", []),
        trace_to_ignore=jamb_config.get("trace_to_ignore", []),
        software_version=software_version,
        trace_from=jamb_config.get("trace_from"),
        include_ancestors=jamb_config.get("include_ancestors", False),
    )
