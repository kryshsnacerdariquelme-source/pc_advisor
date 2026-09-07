import psutil
from database import obtener_ultimas_lecturas

UMBRAL_CPU = 90
UMBRAL_RAM = 85
UMBRAL_TEMP = 80
PORCENTAJE_SOSTENIDO = 0.7  # el 70% de las últimas lecturas debe superar el umbral


def _es_sostenido(valores, umbral):
    """Evita falsas alarmas por un solo pico: solo cuenta como problema
    si la mayoría de las últimas lecturas superó el umbral, no una sola."""
    if len(valores) < 3:
        return False
    sobre_umbral = sum(1 for v in valores if v >= umbral)
    return (sobre_umbral / len(valores)) >= PORCENTAJE_SOSTENIDO


def _procesos_que_mas_consumen(top_n=2):
    """Identifica qué procesos son responsables del uso alto de RAM,
    en vez de solo decir 'cierra programas' de forma generica (RF-07)."""
    procesos = []
    for p in psutil.process_iter(['name', 'memory_percent']):
        try:
            procesos.append((p.info['name'], p.info['memory_percent'] or 0))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procesos.sort(key=lambda x: x[1], reverse=True)
    return procesos[:top_n]


def analizar():
    """Revisa el HISTORIAL reciente (no una sola lectura) y clasifica el
    diagnostico en un tipo concreto, para poder mapearlo a una guia de
    solucion especifica."""
    lecturas = obtener_ultimas_lecturas(n=10)
    if not lecturas:
        return []

    cpus = [f[0] for f in lecturas]
    rams = [f[1] for f in lecturas]
    temps = [f[2] for f in lecturas]

    diagnosticos = []

    if _es_sostenido(rams, UMBRAL_RAM):
        top_procesos = _procesos_que_mas_consumen()
        nombres = ", ".join(f"{n} ({p:.0f}%)" for n, p in top_procesos if n)
        diagnosticos.append({
            "tipo": "ram_alta_sostenida",
            "mensaje": f"Tu memoria se ha mantenido muy alta por un rato. "
                       f"Los que mas estan pidiendo memoria ahora son: {nombres or 'no identificados'}.",
        })

    if _es_sostenido(cpus, UMBRAL_CPU):
        diagnosticos.append({
            "tipo": "cpu_alta_sostenida",
            "mensaje": "Tu procesador ha estado trabajando al limite de forma seguida.",
        })

    if _es_sostenido(temps, UMBRAL_TEMP):
        diagnosticos.append({
            "tipo": "temperatura_alta",
            "mensaje": "La temperatura de tu equipo ha estado elevada por un rato.",
        })

    return diagnosticos
