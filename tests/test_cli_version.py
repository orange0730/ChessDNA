import subprocess
import sys

import chessdna


def test_cli_version_flag():
    # Use python -m to avoid depending on console_script installation.
    out = subprocess.check_output(
        [sys.executable, "-m", "chessdna", "--version"],
        text=True,
    ).strip()
    assert out == f"chessdna {chessdna.__version__}"
