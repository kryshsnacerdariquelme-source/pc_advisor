# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPEC).parent
BACKEND = ROOT / "Backend"
DESKTOP = ROOT / "Desktop"

backend_modules = [
    "monitor",
    "database",
    "diagnostico",
    "guia_solucion",
    "hardware",
    "notificaciones",
    "logger_config",
]

a = Analysis(
    [str(DESKTOP / "main.py")],
    pathex=[str(ROOT), str(BACKEND)],
    binaries=[],
    datas=[
        (str(BACKEND), "Backend"),
        (str(DESKTOP), "Desktop"),
    ],
    hiddenimports=backend_modules,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["streamlit", "plotly", "altair"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PC Advisor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PC Advisor",
)
