"""PyInstaller entry point. Also usable directly: `python run_desktop.py`."""
from __future__ import annotations

import os
import sys


def _prepare() -> None:
    # When frozen, keep writable data (DB, MT5 instances) in a real user folder.
    if getattr(sys, "frozen", False) and not os.environ.get("TH_DATA_DIR"):
        from app.paths import user_data_dir

        os.environ["TH_DATA_DIR"] = str(user_data_dir())


if __name__ == "__main__":
    _prepare()
    from app.desktop import main

    main()
