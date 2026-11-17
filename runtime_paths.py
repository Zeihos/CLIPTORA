"""Resolve bundled UI resources and optional external tools in source / .exe mode.

PyInstaller one-directory builds put immutable application resources under
``_internal`` but users may provide FFmpeg next to CLIPTORA.exe in ``tools``.
User video files and local project data are never written here.
"""
import sys
from pathlib import Path


def resource_root():
    """Location of the bundled static web UI and native Rust scanner."""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS).resolve()
    return Path(__file__).resolve().parent


def tool_directories():
    """Prefer user-managed external binaries over the frozen bundle."""
    resource_tools = resource_root() / 'tools'
    if getattr(sys, 'frozen', False):
        external_tools = Path(sys.executable).resolve().parent / 'tools'
        if external_tools != resource_tools:
            return (external_tools, resource_tools)
    return (resource_tools,)
