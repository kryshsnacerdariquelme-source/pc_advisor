"""
Modulo NUEVO: traduce cada tipo de diagnostico en pasos concretos y
accionables (RF-15). Esto es lo que le faltaba al MVP: antes solo se
decia "cierra programas" de forma generica; ahora cada diagnostico
tiene su propia guia paso a paso.
"""

GUIAS = {
    "ram_alta_sostenida": [
        "Presiona Ctrl + Shift + Esc para abrir el Administrador de tareas.",
        "Ordena la lista por 'Memoria' y revisa qué programa está usando más.",
        "Cierra las pestañas o programas que no estés usando en este momento.",
    ],
    "cpu_alta_sostenida": [
        "Abre el Administrador de tareas (Ctrl + Shift + Esc).",
        "Revisa si hay algún programa usando el procesador sin que lo hayas abierto tú.",
        "Si no reconoces el programa, ciérralo y observa si el uso baja.",
    ],
    "temperatura_alta": [
        "Revisa que las rejillas de ventilación del equipo no estén tapadas.",
        "Si usas el equipo sobre la cama o un cojín, cámbialo a una superficie dura.",
        "Deja que el equipo descanse unos minutos si el ventilador suena muy fuerte.",
    ],
}


def obtener_guia(tipo_diagnostico):
    pasos = GUIAS.get(tipo_diagnostico, ["No hay una guía específica para este caso todavía."])
    return "\n".join(f"{i}. {paso}" for i, paso in enumerate(pasos, start=1))
