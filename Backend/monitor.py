import json
import platform
import time
from pathlib import Path

from database import crear_tabla, guardar_lectura, guardar_recomendacion
from diagnostico import analizar
from guia_solucion import obtener_guia
from hardware import obtener_estado_hardware
from notificaciones import notificar

# Lectura viva: una vez por segundo.
INTERVALO_VIVO = 1.0
# SQLite queda como historial y no bloquea el dashboard.
INTERVALO_HISTORIAL = 60.0
MAX_HISTORIAL_VIVO = 60  # 60 puntos = 1 minuto de gráficas en tiempo real

BASE_DIR = Path(__file__).resolve().parent.parent
ESTADO_PATH = BASE_DIR / "data" / "estado_actual.json"
ESTADO_PATH.parent.mkdir(parents=True, exist_ok=True)


def publicar_estado(estado: dict):
    """Escribe el estado actual de forma atomica para que Streamlit nunca
    lea un JSON a medio escribir."""
    temporal = ESTADO_PATH.with_suffix(".tmp")
    temporal.write_text(json.dumps(estado, ensure_ascii=False), encoding="utf-8")
    temporal.replace(ESTADO_PATH)


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


def procesar_diagnosticos(diagnosticos):
    for d in diagnosticos:
        guia = obtener_guia(d["tipo"])
        if guardar_recomendacion(d["tipo"], d["mensaje"], guia):
            notificar("PC Advisor", d["mensaje"])
            print(f"\n>> Nueva alerta guardada en el historial: {d['tipo']}")


def main():
    crear_tabla()
    print("PC Advisor iniciado...")
    print("Lectura de hardware: 1 segundo")
    print("Historial SQLite: 1 minuto")
    print("Presiona CTRL + C para detener.\n")

    ultimo_guardado = 0.0
    historial_vivo = []

    while True:
        inicio = time.monotonic()
        estado = obtener_estado_hardware()
        estado["timestamp"] = time.time()

        # Mantiene una ventana corta de datos a 1 Hz. El dashboard la usa
        # directamente, por lo que las gráficas no tienen que esperar al
        # guardado de SQLite (que sigue siendo cada 60 s).
        historial_vivo.append({
            "timestamp": estado["timestamp"],
            "cpu": estado["cpu"],
            "ram": estado["ram"],
            "disco": estado["disco"],
            "gpu": estado["gpu"],
        })
        if len(historial_vivo) > MAX_HISTORIAL_VIVO:
            historial_vivo = historial_vivo[-MAX_HISTORIAL_VIVO:]
        estado["historial_vivo"] = historial_vivo
        publicar_estado(estado)

        # Diagnóstico/historial no condicionan la actualización visual.
        ahora = time.monotonic()
        if ahora - ultimo_guardado >= INTERVALO_HISTORIAL:
            guardar_lectura(
                estado["cpu"],
                estado["ram"],
                estado["temperatura_cpu"],
                estado["disco"],
                estado["gpu"],
            )
            diagnosticos = analizar()
            procesar_diagnosticos(diagnosticos)
            ultimo_guardado = ahora
        else:
            diagnosticos = []

        mostrar_estado(estado, diagnosticos)

        # Mantiene el periodo cercano a 1 segundo, compensando el tiempo de lectura.
        transcurrido = time.monotonic() - inicio
        time.sleep(max(0.0, INTERVALO_VIVO - transcurrido))


if __name__ == "__main__":
    main()
