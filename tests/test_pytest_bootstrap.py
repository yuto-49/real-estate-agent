"""Regression coverage for Python test bootstrap behavior."""

from __future__ import annotations

import sys

from config import Settings
from pytest_bootstrap import install_safe_readline_stub, should_stub_readline


def test_settings_ignore_unrelated_environment_keys():
    settings = Settings(
        environment="test",
        supabase_url="https://example.supabase.co",
        vite_supabase_url="https://example.supabase.co",
        vite_supabase_publishable_key="publishable-key",
    )

    assert settings.environment == "test"
    assert "supabase_url" not in settings.model_dump()
    assert "vite_supabase_url" not in settings.model_dump()


def test_should_stub_readline_for_known_broken_anaconda_runtime(monkeypatch):
    monkeypatch.delenv("REAL_ESTATE_AGENT_USE_NATIVE_READLINE", raising=False)

    assert should_stub_readline(
        platform_name="Darwin",
        executable="/opt/anaconda3/bin/python3",
        version_info=(3, 12, 4),
    )
    assert not should_stub_readline(
        platform_name="Linux",
        executable="/opt/anaconda3/bin/python3",
        version_info=(3, 12, 4),
    )


def test_install_safe_readline_stub_registers_module(monkeypatch):
    monkeypatch.setitem(sys.modules, "readline", None)
    sys.modules.pop("readline", None)

    install_safe_readline_stub()

    readline_module = sys.modules["readline"]

    assert readline_module.get_line_buffer() == ""
    assert readline_module.get_history_length() == 0
    assert readline_module.parse_and_bind("tab: complete") is None
