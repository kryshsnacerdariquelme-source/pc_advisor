import psutil
from database import obtener_ultimas_lecturas, obtener_promedios_diarios_ram
from hardware import plan_energia_activo

UMBRAL_CPU = 90
UMBRAL_RAM = 85
UMBRAL_TEMP = 80
PORCENTAJE_SOSTENIDO = 0.7  # el 70% de las últimas lecturas debe superar el umbral

# RF-07: planes de energía de Windows que limitan el rendimiento a propósito.
PLANES_RESTRICTIVOS = ("ahorro de energía", "ahorro de energia", "energy saver", "battery saver")

# RF-08: no proyectar con pocos datos, y umbral considerado critico a futuro.
DIAS_MINIMOS_PROYECCION = 5
UMBRAL_RAM_PROYECTADO = 90


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


def _causa_configuracion(cpus, rams):
    """RF-07: si el equipo esta exigido pero el plan de energia activo es
    restrictivo, el problema puede ser de configuracion y no de hardware
    insuficiente. Es una unica revision (no requiere historial de dias)."""
    if not (_es_sostenido(cpus, UMBRAL_CPU) or _es_sostenido(rams, UMBRAL_RAM)):
        return None
    plan = plan_energia_activo()
    if plan and any(p in plan.lower() for p in PLANES_RESTRICTIVOS):
        return {
            "tipo": "configuracion_plan_energia",
            "mensaje": f"Tu equipo esta exigido pero el plan de energia activo es "
                       f"'{plan}', que limita el rendimiento a proposito. Antes de "
                       f"pensar en un problema de hardware, vale la pena revisar "
                       f"la configuracion de energia.",
        }
    return None


def _proyeccion_capacidad_ram():
    """RF-08: evalua si la tendencia diaria de uso de RAM viene en aumento
    y, de ser asi, estima en cuantos dias podria acercarse a un umbral
    critico si la tendencia se mantiene. Es una proyeccion simple (regresion
    lineal sobre el promedio diario), no una prediccion exacta: sirve para
    dar una alerta temprana, no una fecha garantizada."""
    datos = obtener_promedios_diarios_ram(dias=30)
    if len(datos) < DIAS_MINIMOS_PROYECCION:
        return None

    xs = list(range(len(datos)))
    ys = [d[1] for d in datos]
    n = len(xs)
    prom_x = sum(xs) / n
    prom_y = sum(ys) / n
    denominador = sum((x - prom_x) ** 2 for x in xs) or 1
    pendiente = sum((xs[i] - prom_x) * (ys[i] - prom_y) for i in range(n)) / denominador

    if pendiente <= 0.05:  # sin tendencia al alza relevante
        return None

    interseccion = prom_y - pendiente * prom_x
    dias_para_umbral = (UMBRAL_RAM_PROYECTADO - interseccion) / pendiente - xs[-1]

    if not (0 < dias_para_umbral <= 365):
        return None

    return {
        "tipo": "capacidad_futura_ram",
        "mensaje": f"Tu uso promedio de RAM viene subiendo dia a dia. Si la "
                   f"tendencia se mantiene, en unos {round(dias_para_umbral)} "
                   f"dias podria estar cerca del limite de forma constante.",
    }


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

    causa_config = _causa_configuracion(cpus, rams)
    if causa_config:
        diagnosticos.append(causa_config)

    proyeccion = _proyeccion_capacidad_ram()
    if proyeccion:
        diagnosticos.append(proyeccion)

    return diagnosticos
