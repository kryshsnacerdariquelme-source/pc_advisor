# -*- mode: python ; coding: utf-8 -*-
#
# Genera dist/PC_Advisor/PC_Advisor.exe  (carpeta "onedir": arranque rapido
# y menos falsos positivos de antivirus que un .exe de un solo archivo).
#
# Compilar:  build_exe.bat      (o:  pyinstaller --noconfirm --clean PC_Advisor.spec)

from pathlib import Path

ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / "Desktop" / "main.py")],
    pathex=[str(ROOT), str(ROOT / "Backend")],
    binaries=[],
    datas=[(str(ROOT / "assets"), "assets"), (str(ROOT / "legal"), "legal")],
    hiddenimports=[
        # Modulos del Backend (se importan "planos", PyInstaller no siempre los ve)
        "monitor", "database", "diagnostico", "guia_solucion", "hardware",
        "notificaciones", "logger_config", "reporte_pdf", "puntaje", "rutas",
        # plyer elige su plataforma en tiempo de ejecucion
        "plyer.platforms.win.notification",
        "plyer.platforms.win.libs.balloontip",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Version web: no se necesita en el escritorio
        "streamlit", "plotly", "altair", "pandas", "numpy", "pyarrow",
        # Cosas pesadas que no se usan
        "tkinter", "matplotlib", "IPython", "pytest",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.Qt3DCore",
        "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PC_Advisor",
    icon=str(ROOT / "assets" / "icon.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,        # UPX corrompe a veces las DLL de Qt: mejor desactivado
    console=False,    # aplicacion de ventana: NO abre consola ni navegador
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PC_Advisor",
)
