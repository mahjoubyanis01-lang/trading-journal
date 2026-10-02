# PyInstaller spec - builds a standalone Trading Hub.exe (run on Windows).
#   pip install pyinstaller
#   pyinstaller trading-hub.spec
# Produces dist/TradingHub(.exe). Bundles the built UI + the MQL bridge EAs.
import os

block_cipher = None

# backend/ is the spec dir; repo root is one level up.
ROOT = os.path.abspath(os.path.join(os.getcwd(), os.pardir))

datas = [
    (os.path.join(ROOT, "frontend", "dist"), os.path.join("frontend", "dist")),
    (os.path.join(ROOT, "assets"), "assets"),
]

hiddenimports = [
    "uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto", "uvicorn.lifespan.on",
    "websockets", "app.main", "app.connectors.registry",
]

a = Analysis(
    ["run_desktop.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name="TradingHub",
    console=False,
    disable_windowed_traceback=False,
    upx=True,
)
