import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Base de données et réglages dans un répertoire temporaire pour les tests.
os.environ["BACKTESTER_DATA_DIR"] = tempfile.mkdtemp(prefix="backtester-tests-")
