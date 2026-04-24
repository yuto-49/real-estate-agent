"""Project-local pytest entrypoint.

Running ``python3 -m pytest`` from this repository first passes through this
module, which installs the readline guard for the known-bad Anaconda runtime and
then delegates to the real site-packages pytest package.
"""

from __future__ import annotations

from pathlib import Path

from pytest_bootstrap import load_real_pytest, prepare_pytest_startup


_IS_MAIN = __name__ == "__main__"
prepare_pytest_startup()
_REAL_PYTEST = load_real_pytest(excluded_path=Path(__file__).resolve().parent)

globals().update(_REAL_PYTEST.__dict__)


if _IS_MAIN:
    raise SystemExit(_REAL_PYTEST.console_main())
