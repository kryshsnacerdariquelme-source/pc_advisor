import json
import sys
import threading
import time

import psutil

from database import crear_tabla, guardar_lectura, guardar_recomendacion
from diagnostico import analizar
from guia_solucion import obtener_guia
from hardware import obtener_estado_hardware
from notificaciones import notificar
from logger_config import obtener_logger
from rutas import dir_datos

log = obtener_logger(__name__)

# Lectura viva: una vez por segundo.
INTERVALO_VIVO = 1.0
# SQLite queda como historial y no bloquea el dashboard.
INTERVALO_HISTORIAL = 60.0
MAX_HISTORIAL_VIVO = 60  # 60 puntos = 1 minuto de gráficas en tiempo real

ESTADO_PATH = dir_datos() / "estado_actual.json"

# --- Estado compartido en memoria -------------------------------------
# La app de escritorio corre el monitor en un hilo del mismo proceso, asi
# que lee el estado directo de memoria (sin pasar por un archivo, que en
# Windows puede fallar si alguien lo tiene abierto justo al reemplazarlo).
_estado_actual = None
_candado = threading.Lock()
_detener = threading.Event()


def obtener_estado_actual():
    """Ultimo estado publicado por el monitor (dict) o None si aun no hay."""
    with _candado:
        return _estado_actual


def detener():
    """Pide al monitor que termine su bucle (lo llama la ventana al cerrar)."""
    _detener.set()


def publicar_estado(estado: dict, escribir_archivo: bool = True):
    """Publica el estado en memoria y, opcionalmente, en un JSON (lo usa la
    version web de Streamlit, que corre en otro proceso). El JSON se escribe
    de forma atomica para que nadie lo lea a medio escribir."""
    global _estado_actual
    with _candado:
        _estado_actual = estado

    if not escribir_archivo:
        return
    try:
        temporal = ESTADO_PATH.with_suffix(".tmp")
        temporal.write_text(json.dumps(estado, ensure_ascii=False), encoding="utf-8")
        temporal.replace(ESTADO_PATH)
    except OSError:
        # Archivo ocupado por un lector en ese instante: se reintenta en
        # el siguiente ciclo (1 s), no es un error.
        log.debug("No se pudo escribir estado_actual.json en este ciclo")


def mostrar_estado(estado, diagnosticos):
    print("\n" + "=" * 60)
    print("                     PC ADVISOR")
    print("=" * 60)
    print(f"CPU:             {estado['cpu']:.1f}%")
    print(f"Temperatura CPU: {estado['temperatura_cpu']:.1f} C" if estado['temperatura_cpu'] else "Temperatura CPU: No disponible")
    print(f"RAM:             {estado['ram']:.1f}%")
    print(f"GPU:             {estado['gpu']:.1f}%" if estado['gpu'] is not None else "GPU:             No disponible")
    print(f"GPU:             {estado['gpu_nombre']}")
    print(f"Temperatura GPU: {estado['temperatura_gpu']:.1f} C" if estado['temperatura_gpu'] else "Temperatura GPU: No disponible")
    print(f"VRAM:            {estado['temperatura_vram']:.1f} C" if estado['temperatura_vram'] else "Temperatura VRAM: No disponible")
    print("Discos:")
    for disco in estado.get("discos", []):
        print(f"  {disco['unidad']} -> {disco['uso']:.1f}% ({disco['usado_gb']:.1f}/{disco['total_gb']:.1f} GB)")
    if diagnosticos:
        print("\nALERTAS NUEVAS")
        for d in diagnosticos:
            print(f"- {d['mensaje']}")
    print("=" * 60)


def procesar_diagnosticos(diagnosticos, verbose=False):
    for d in diagnosticos:
        guia = obtener_guia(d["tipo"])
        if guardar_recomendacion(d["tipo"], d["mensaje"], guia):
            notificar("PC Advisor", d["mensaje"])
            if verbose:
                print(f"\n>> Nueva alerta guardada en el historial: {d['tipo']}")


def main(verbose=False, escribir_archivo=True):
    """Bucle del monitor.

    verbose:          imprime el estado en consola cada segundo (solo para
                      cuando se corre `python monitor.py` a mano).
    escribir_archivo: ademas de memoria, escribe data/estado_actual.json
                      (necesario solo para la version web de Streamlit).
    """
    _detener.clear()
    crear_tabla()
    psutil.cpu_percent(interval=None)
    if verbose:
        print("PC Advisor iniciado...")
        print("Lectura de hardware: 1 segundo")
        print("Historial SQLite: 1 minuto")
        print("Presiona CTRL + C para detener.\n")

    ultimo_guardado = None  # monotonic() del ultimo guardado en SQLite
    historial_vivo = []
    errores_seguidos = 0

    log.info("Monitor iniciado")

    while not _detener.is_set():
        inicio = time.monotonic()
        try:
            estado = obtener_estado_hardware()
            estado["timestamp"] = time.time()

            historial_vivo.append({
                "timestamp": estado["timestamp"],
                "cpu": estado["cpu"],
                "ram": estado["ram"],
                "disco": estado["disco"],
                "gpu": estado["gpu"],
            })
            if len(historial_vivo) > MAX_HISTORIAL_VIVO:
                historial_vivo = historial_vivo[-MAX_HISTORIAL_VIVO:]
            # Copia: la ventana lee esta lista desde otro hilo mientras el
            # monitor sigue agregando puntos a la original.
            estado["historial_vivo"] = list(historial_vivo)
            publicar_estado(estado, escribir_archivo)

            ahora = time.monotonic()
            if ultimo_guardado is None or ahora - ultimo_guardado >= INTERVALO_HISTORIAL:
                guardar_lectura(
                    estado["cpu"],
                    estado["ram"],
                    estado["temperatura_cpu"],
                    estado["disco"],
                    estado["gpu"],
                )
                diagnosticos = analizar()
                procesar_diagnosticos(diagnosticos, verbose)
                ultimo_guardado = ahora
            else:
                diagnosticos = []

            if verbose and sys.stdout is not None:
                mostrar_estado(estado, diagnosticos)
            errores_seguidos = 0
        except Exception:
            # Una lectura fallida (sensor caido, WMI ocupado, disco
            # desconectado, etc.) no debe cerrar el monitor completo:
            # se registra en el log y se reintenta en el siguiente ciclo.
            errores_seguidos += 1
            log.exception("Fallo en el ciclo de monitoreo (intento fallido N°%s seguido)", errores_seguidos)
            if errores_seguidos >= 10:
                log.critical(
                    "10 ciclos seguidos han fallado. Puede haber un problema "
                    "persistente (permisos, sensor desconectado, disco lleno)."
                )
                errores_seguidos = 0

        transcurrido = time.monotonic() - inicio
        _detener.wait(max(0.0, INTERVALO_VIVO - transcurrido))

    log.info("Monitor detenido")


if __name__ == "__main__":
    try:
        main(verbose=True)
    except KeyboardInterrupt:
        pass
