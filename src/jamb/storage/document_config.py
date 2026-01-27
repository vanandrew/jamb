"""Document configuration for jamb's native storage layer."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class DocumentConfig:
    """Configuration for a requirements document."""

    prefix: str
    parents: list[str] = field(default_factory=list)
    digits: int = 3
    sep: str = ""


def load_document_config(path: Path) -> DocumentConfig:
    """Load document config from a .jamb.yml file.

    Args:
        path: Path to the config file (.jamb.yml).

    Returns:
        DocumentConfig parsed from the file.

    Raises:
        ValueError: If the config file is missing required fields.
    """
    with open(path) as f:
        data = yaml.safe_load(f)

    if not data or "settings" not in data:
        raise ValueError(f"Invalid config file: {path}")

    settings = data["settings"]
    prefix = settings.get("prefix")
    if not prefix:
        raise ValueError(f"Config file missing 'prefix': {path}")

    parents: list[str] = []
    if "parents" in settings:
        raw = settings["parents"]
        if isinstance(raw, list):
            parents = [str(p) for p in raw]
        elif raw is not None:
            parents = [str(raw)]

    return DocumentConfig(
        prefix=prefix,
        parents=parents,
        digits=settings.get("digits", 3),
        sep=settings.get("sep", ""),
    )


def save_document_config(config: DocumentConfig, directory: Path) -> None:
    """Save document config as .jamb.yml in the given directory.

    Args:
        config: The document configuration to save.
        directory: The directory to write .jamb.yml into.
    """
    settings: dict = {
        "prefix": config.prefix,
        "digits": config.digits,
        "sep": config.sep,
    }
    if config.parents:
        settings["parents"] = config.parents

    data = {"settings": settings}

    directory.mkdir(parents=True, exist_ok=True)
    config_path = directory / ".jamb.yml"
    with open(config_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
