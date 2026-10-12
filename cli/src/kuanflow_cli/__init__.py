"""Kuanflow CLI."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("kuanflow-cli")
except PackageNotFoundError:  # pragma: no cover - only when running from an uninstalled tree
    __version__ = "0+unknown"

__all__ = ["__version__"]
