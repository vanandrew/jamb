"""Load jamb configuration from pyproject.toml."""

from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib  # type: ignore[import-not-found]
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found]


@dataclass
class JambConfig:
    """Configuration schema for jamb."""

    # Which documents represent test specifications
    test_documents: list[str] = field(default_factory=list)

    # Coverage enforcement
    fail_uncovered: bool = False
    require_all_pass: bool = True

    # Matrix output
    matrix_output: str | None = None
    matrix_format: str = "html"

    # Exclusions
    exclude_patterns: list[str] = field(default_factory=list)

    # Document prefixes to exclude from "Traces To" column
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
