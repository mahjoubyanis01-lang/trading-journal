#!/usr/bin/env bash
# ============================================================
#  Trading Hub - launcher for macOS / Linux
#  First run installs everything; afterwards it just opens.
#  Prerequisite: Python 3.11+.
# ============================================================
set -e
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

if [ ! -x "backend/.venv/bin/python" ]; then
  echo "[Trading Hub] First-time setup..."
  "$PY" -m venv backend/.venv
fi
# shellcheck disable=SC1091
. backend/.venv/bin/activate

python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r backend/requirements.txt
python -m pip install --quiet pywebview || true   # optional native window

# Rebuild the UI only if missing and npm is available.
if [ ! -f frontend/dist/index.html ] && command -v npm >/dev/null 2>&1; then
  echo "[Trading Hub] Building the interface..."
  ( cd frontend && npm install && npm run build )
fi

cd backend
exec python -m app.desktop
