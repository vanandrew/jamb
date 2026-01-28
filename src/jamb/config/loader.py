"""Load jamb configuration from pyproject.toml."""

from dataclasses import dataclass, field
from pathlib import Path

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
    """

    test_documents: list[str] = field(default_factory=list)
    fail_uncovered: bool = False
    require_all_pass: bool = True
    matrix_output: str | None = None
    matrix_format: str = "html"
    exclude_patterns: list[str] = field(default_factory=list)
    trace_to_ignore: list[str] = field(default_factory=list)


def load_config(config_path: Path | None = None) -> JambConfig:
    """
    Load jamb configuration from pyproject.toml.

    Looks for [tool.jamb] section.

    Args:
        config_path: Optional path to pyproject.toml. If None, uses cwd.

    Returns:
        JambConfig with loaded values or defaults.
    """
    if config_path is None:
        config_path = Path.cwd() / "pyproject.toml"

    if not config_path.exists():
        return JambConfig()

    with open(config_path, "rb") as f:
        pyproject = tomllib.load(f)

    jamb_config = pyproject.get("tool", {}).get("jamb", {})

    return JambConfig(
        test_documents=jamb_config.get("test_documents", []),
        fail_uncovered=jamb_config.get("fail_uncovered", False),
        require_all_pass=jamb_config.get("require_all_pass", True),
        matrix_output=jamb_config.get("matrix_output"),
        matrix_format=jamb_config.get("matrix_format", "html"),
        exclude_patterns=jamb_config.get("exclude_patterns", []),
        trace_to_ignore=jamb_config.get("trace_to_ignore", []),
    )
