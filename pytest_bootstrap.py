"""Helpers for making pytest startup reliable in the local dev environment."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import platform
import sys
import types
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any


_READLINE_DISABLE_ENV = "REAL_ESTATE_AGENT_USE_NATIVE_READLINE"


def should_stub_readline(
    *,
    platform_name: str | None = None,
    executable: str | None = None,
    version_info: Any | None = None,
) -> bool:
    """Return whether this interpreter matches the known-bad readline runtime."""

    if os.getenv(_READLINE_DISABLE_ENV):
        return False

    resolved_platform = platform_name or platform.system()
    resolved_executable = executable or sys.executable
    resolved_version = version_info or sys.version_info

    return (
        resolved_platform == "Darwin"
        and str(resolved_executable).startswith("/opt/anaconda3/")
        and tuple(resolved_version[:2]) == (3, 12)
    )


def _noop(*args: Any, **kwargs: Any) -> None:
    return None


def install_safe_readline_stub() -> None:
    """Provide a tiny readline stand-in that keeps pytest startup stable."""

    if "readline" in sys.modules:
        return

    module = types.ModuleType("readline")
    no_op_names = (
        "add_history",
        "clear_history",
        "insert_text",
        "parse_and_bind",
        "read_history_file",
        "redisplay",
        "remove_history_item",
        "replace_history_item",
        "set_auto_history",
        "set_completer",
        "set_completer_delims",
        "set_completion_display_matches_hook",
        "set_history_length",
        "set_pre_input_hook",
        "set_startup_hook",
        "write_history_file",
    )

    for name in no_op_names:
        setattr(module, name, _noop)

    module.get_begidx = lambda: 0
    module.get_completer = lambda: None
    module.get_completer_delims = lambda: ""
    module.get_completion_type = lambda: 0
    module.get_current_history_length = lambda: 0
    module.get_endidx = lambda: 0
    module.get_history_item = lambda index: None
    module.get_history_length = lambda: 0
    module.get_line_buffer = lambda: ""

    def _missing_attr(_name: str) -> Callable[..., None]:
        return _noop

    module.__getattr__ = _missing_attr  # type: ignore[attr-defined]
    sys.modules["readline"] = module


def prepare_pytest_startup() -> None:
    """Install process-wide startup guards before importing the real pytest."""

    if should_stub_readline():
        install_safe_readline_stub()


def load_real_pytest(*, excluded_path: Path) -> ModuleType:
    """Import pytest from site-packages while skipping the project root wrapper."""

    search_path: list[str] = []
    for entry in sys.path:
        if not entry:
            continue
        try:
            resolved_entry = Path(entry).resolve()
        except OSError:
            search_path.append(entry)
            continue
        if resolved_entry == excluded_path:
            continue
        search_path.append(entry)

    spec = importlib.machinery.PathFinder.find_spec("pytest", search_path)
    if spec is None or spec.loader is None:
        raise ImportError("Could not locate the site-packages pytest package")

    module = importlib.util.module_from_spec(spec)
    sys.modules["pytest"] = module
    spec.loader.exec_module(module)
    return module
