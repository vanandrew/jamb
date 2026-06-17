"""Locate and invoke the Quarto binary."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


class QuartoNotFoundError(RuntimeError):
    """Raised when no usable Quarto binary can be located."""


class QuartoRenderError(RuntimeError):
    """Raised when a Quarto render invocation fails.

    Attributes:
        returncode: The process exit status, when available.
        stderr: Captured Quarto diagnostic output.
        qmd_path: Path to the ``.qmd`` source that failed to render.
    """

    def __init__(
        self,
        message: str,
        *,
        returncode: int | None = None,
        stderr: str = "",
        qmd_path: str | None = None,
    ) -> None:
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr
        self.qmd_path = qmd_path


def _bundled_quarto() -> str | None:
    """Return the binary shipped with the ``quarto-cli`` package, if present."""
    try:
        import quarto_cli.quarto as bundled
    except ImportError:
        return None

    bin_dir = Path(bundled.__file__).parent / "bin"
    for name in ("quarto", "quarto.cmd", "quarto.exe"):
        candidate = bin_dir / name
        if candidate.exists():
            return str(candidate)
    return None


def find_quarto() -> str:
    """Resolve the Quarto binary to an absolute path.

    Resolution order: the ``JAMB_QUARTO`` environment variable, the binary
    bundled with the ``quarto-cli`` package, then any ``quarto`` on ``PATH``.

    Returns:
        An absolute path to the Quarto binary.

    Raises:
        QuartoNotFoundError: When no binary can be found.
    """
    override = os.environ.get("JAMB_QUARTO")
    if override:
        if Path(override).exists():
            return override
        raise QuartoNotFoundError(f"JAMB_QUARTO points to a missing file: {override}")

    bundled = _bundled_quarto()
    if bundled:
        return bundled

    on_path = shutil.which("quarto")
    if on_path:
        return on_path

    raise QuartoNotFoundError(
        "Quarto is required to render HTML, DOCX, and PDF output but was not found. "
        "Install it with: pip install 'quarto-cli'"
    )


def quarto_version() -> str | None:
    """Return the installed Quarto version string, or ``None`` if unavailable."""
    try:
        executable = find_quarto()
    except QuartoNotFoundError:
        return None
    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def run_quarto(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run the Quarto binary with the given arguments.

    Args:
        args: Arguments passed to Quarto (e.g. ``["render", ...]``).
        cwd: Working directory for the invocation.

    Returns:
        The completed process, with stdout and stderr captured as text.
    """
    executable = find_quarto()
    return subprocess.run([executable, *args], cwd=str(cwd), capture_output=True, text=True)
