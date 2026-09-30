"""
Modulo NUEVO: logging centralizado para todo PC Advisor.

Antes, los fallos de sensores, WMI, base de datos, etc. se tragaban con
`except Exception: pass` y desaparecian sin dejar rastro. Eso hacia
imposible diagnosticar un problema reportado por un usuario ("no me
muestra la temperatura", "se cerro solo") porque no quedaba ningun
registro de que fallo ni por que.

Este modulo entrega un logger ya configurado que:
- Escribe en `pc_advisor.log` (carpeta de datos, ver rutas.py) (rotando cada 1 MB, se guardan 3
  respaldos) para no crecer indefinidamente.
- Tambien imprime en consola cuando se corre `monitor.py` a mano.
- Se importa una sola vez por proceso (logging cachea por nombre).

Uso tipico en cualquier modulo del backend:

    from logger_config import obtener_logger
    log = obtener_logger(__name__)
    ...
    try:
        algo_riesgoso()
    except Exception:
        log.exception("No se pudo leer X")   # guarda el traceback completo
"""

import logging
import logging.handlers
import sys

from rutas import dir_datos

LOG_PATH = dir_datos() / "pc_advisor.log"

_FORMATO = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_CONFIGURADO = False


def _configurar_raiz():
    global _CONFIGURADO
    if _CONFIGURADO:
        return
    raiz = logging.getLogger("pc_advisor")
    raiz.setLevel(logging.INFO)

    manejador_archivo = logging.handlers.RotatingFileHandler(
        LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    manejador_archivo.setFormatter(logging.Formatter(_FORMATO))
    raiz.addHandler(manejador_archivo)

    # En el .exe sin consola (modo ventana) sys.stderr es None: no se
    # agrega el manejador de consola porque fallaria en cada mensaje.
    if sys.stderr is not None:
        manejador_consola = logging.StreamHandler()
        manejador_consola.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        manejador_consola.setLevel(logging.WARNING)  # la consola solo muestra lo importante
        raiz.addHandler(manejador_consola)

    _CONFIGURADO = True


def obtener_logger(nombre: str) -> logging.Logger:
    """Devuelve un logger hijo de 'pc_advisor', ya listo para usar.

    `nombre` normalmente es `__name__` del modulo que lo pide, asi las
    lineas del log dicen de donde vino cada mensaje
    (ej: 'pc_advisor.hardware').
    """
    _configurar_raiz()
    if not nombre.startswith("pc_advisor"):
        nombre = f"pc_advisor.{nombre}"
    return logging.getLogger(nombre)
