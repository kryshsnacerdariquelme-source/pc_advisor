"""Puntaje de salud del equipo (0-100).

Antes esta funcion estaba copiada tanto en el Frontend (Streamlit) como en la
ventana de escritorio. Ahora vive en un solo lugar del Backend.
"""
from diagnostico import UMBRAL_CPU, UMBRAL_RAM

UMBRAL_GPU_REFERENCIA = 90
UMBRAL_DISCO_REFERENCIA = 90


def calcular_puntaje_salud(cpu, ram, gpu, discos):
    """Resume el estado general penalizando cada metrica segun que tan cerca
    esta de su umbral de riesgo. Devuelve (puntaje, color, mensaje, detalle)."""
    disco_max = max((d.get("uso", 0) for d in (discos or [])), default=0)

    def penalizacion(valor, umbral, peso):
        inicio = umbral * 0.5
        if valor is None or valor <= inicio:
            return 0.0
        fraccion = min(1.0, (valor - inicio) / (umbral - inicio))
        return peso * fraccion

    penalizaciones = {
        "CPU": penalizacion(cpu, UMBRAL_CPU, 35),
        "RAM": penalizacion(ram, UMBRAL_RAM, 35),
        "GPU": penalizacion(gpu, UMBRAL_GPU_REFERENCIA, 15),
        "Disco": penalizacion(disco_max, UMBRAL_DISCO_REFERENCIA, 15),
    }
    puntaje = round(max(0, 100 - sum(penalizaciones.values())))
    peor = max(penalizaciones, key=penalizaciones.get)
    hay_problema = penalizaciones[peor] > 5

    if puntaje >= 80:
        color, mensaje = "#22C55E", "Tu equipo está en buen estado."
    elif puntaje >= 50:
        color, mensaje = "#F59E0B", "Rendimiento aceptable, hay algo que vigilar."
    else:
        color, mensaje = "#EF4444", "Tu equipo necesita atención."

    detalle = (
        f"Lo que más influye: {peor} ({penalizaciones[peor]:.0f} pts en contra)."
        if hay_problema else
        "Todas las métricas están dentro de rangos normales."
    )
    return puntaje, color, mensaje, detalle
