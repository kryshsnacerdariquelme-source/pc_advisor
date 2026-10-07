"""Rutas centrales de PC Advisor.

Cuando la app corre como .exe instalado (por ejemplo en "Program Files"),
la carpeta de instalacion NO es escribible para un usuario normal, asi que
la base de datos y el log no pueden guardarse ahi. Este modulo decide:

- dir_recursos(): donde estan los archivos de solo lectura (assets, etc.).
- dir_datos():    donde se puede escribir (base de datos, log, estado).

  * Ejecutable (.exe):  %LOCALAPPDATA%\\PC Advisor\\data
  * Desde el codigo:    <proyecto>/data   (igual que antes)
  * Se puede forzar con la variable de entorno PC_ADVISOR_DATA.
"""
import os
import sys
from pathlib import Path

NOMBRE_APP = "PC Advisor"


def es_ejecutable() -> bool:
    """True si corre empaquetado con PyInstaller (.exe)."""
    return bool(getattr(sys, "frozen", False))


def dir_recursos() -> Path:
    if es_ejecutable():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def dir_datos() -> Path:
    forzada = os.environ.get("PC_ADVISOR_DATA")
    if forzada:
        ruta = Path(forzada)
    elif es_ejecutable():
        if sys.platform == "win32":
            base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        else:
            base = Path.home() / ".local" / "share"
        ruta = base / NOMBRE_APP / "data"
    else:
        ruta = dir_recursos() / "data"
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def ruta_logo() -> Path:
    return dir_recursos() / "assets" / "logo.png"


def ruta_icono() -> Path:
    ico = dir_recursos() / "assets" / "icon.ico"
    return ico if ico.exists() else ruta_logo()


def dir_legal() -> Path:
    """Carpeta con los terminos y condiciones y la politica de privacidad."""
    return dir_recursos() / "legal"
