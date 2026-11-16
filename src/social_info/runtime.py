import os
import sys
from pathlib import Path


def configure_runtime():
    if getattr(sys, "frozen", False):
        browsers = Path(sys.executable).parent / "browser"
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers)
        if sys.stdout is None:
            sys.stdout = open(os.devnull, "w", encoding="utf-8")
        if sys.stderr is None:
            sys.stderr = open(os.devnull, "w", encoding="utf-8")
