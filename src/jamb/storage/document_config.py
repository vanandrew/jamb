"""Document configuration for jamb's native storage layer."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class DocumentConfig:
    """Configuration for a requirements document.

    Attributes:
        prefix (str): Unique identifier prefix for items in this document
            (e.g. ``"REQ"``).
        parents (list[str]): Prefixes of parent documents in the document DAG.
        digits (int): Number of zero-padded digits in generated UIDs
            (e.g. ``3`` produces ``REQ001``).
        sep (str): Separator between the prefix and numeric part of a UID
            (e.g. ``"-"`` produces ``REQ-001``).
    """

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
    with open(path, encoding="utf-8") as f:
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
    settings: dict[str, Any] = {
        "prefix": config.prefix,
        "digits": config.digits,
        "sep": config.sep,
    }
    if config.parents:
        settings["parents"] = config.parents

    data = {"settings": settings}

    directory.mkdir(parents=True, exist_ok=True)
    config_path = directory / ".jamb.yml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
