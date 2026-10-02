"""Test configuration: isolate the DB to a temp file before app import."""
from __future__ import annotations

import os
import tempfile

# Must be set before any import of app.database.base (engine is built there).
_tmp = tempfile.mkdtemp(prefix="trading-hub-test-")
os.environ.setdefault("TH_DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ.setdefault("TH_MOCK_MODE", "true")
os.environ.setdefault("TH_MONITOR_ENABLED", "false")
