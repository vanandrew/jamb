"""Filesystem discovery for jamb document trees."""

import logging
from pathlib import Path

import yaml

from jamb.storage.document_config import load_document_config
from jamb.storage.document_dag import DocumentDAG

logger = logging.getLogger("jamb")


def discover_documents(root: Path | None = None) -> DocumentDAG:
    """Walk filesystem for .jamb.yml files and build a DAG.

    Args:
        root: Root directory to search. Defaults to current working directory.

    Returns:
        DocumentDAG containing all discovered documents.

    Raises:
        FileNotFoundError: If root directory does not exist.
    """
    if root is None:
        root = Path.cwd()

    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Root directory not found: {root}")

    dag = DocumentDAG()

    for config_path in _find_config_files(root):
        try:
            config = load_document_config(config_path)
        except (ValueError, yaml.YAMLError, OSError) as e:
            logger.debug("Skipping %s: %s", config_path, e)
            continue

        dag.documents[config.prefix] = config
        dag.document_paths[config.prefix] = config_path.parent

    return dag


def _find_config_files(root: Path) -> list[Path]:
    """Find all .jamb.yml files under root.

    Args:
        root: The directory to search recursively.

    Returns:
        A list of config file paths sorted alphabetically.
    """
    return sorted(root.rglob(".jamb.yml"))
