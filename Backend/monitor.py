import psutil
import time

from database import crear_tabla, guardar_lectura, guardar_recomendacion
from diagnostico import analizar
from guia_solucion import obtener_guia
from notificaciones import notificar


def obtener_temperatura():
    try:
        temperaturas = psutil.sensors_temperatures()
        if not temperaturas:
            return 0
        for nombre, sensores in temperaturas.items():
            for sensor in sensores:
                if sensor.current:
                    return sensor.current
    except Exception:
        pass
    return 0


def mostrar_estado(cpu, ram, temperatura, diagnosticos):
    print("\n" + "=" * 50)
    print("             PC ADVISOR")
    print("=" * 50)
    print(f"CPU:           {cpu:.1f}%")
    print(f"RAM:           {ram:.1f}%")
    print(f"Temperatura:   {'No disponible' if temperatura == 0 else f'{temperatura:.1f} C'}")

    if not diagnosticos:
        print("\nTodo funciona con normalidad. No hay alertas nuevas.")
    else:
        print("\nALERTAS NUEVAS")
        print("-" * 50)
        for d in diagnosticos:
            print(f"- {d['mensaje']}")
    print("=" * 50)


def procesar_diagnosticos(diagnosticos):
    """Por cada diagnostico sostenido detectado: arma la guia de
    solucion, lo guarda en el historial (si no habia uno igual pendiente)
    y dispara la notificacion nativa solo cuando es realmente nuevo."""
    for d in diagnosticos:
        guia = obtener_guia(d["tipo"])
        es_nuevo = guardar_recomendacion(d["tipo"], d["mensaje"], guia)

        if es_nuevo:
            notificar("PC Advisor", d["mensaje"])
            print(f"\n>> Nueva alerta guardada en el historial: {d['tipo']}")
            print(f">> Guia de solucion:\n{guia}")


def main():
    crear_tabla()
    print("PC Advisor iniciado...")
    print("Presiona CTRL + C para detener.\n")

    while True:
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        temperatura = obtener_temperatura()

        guardar_lectura(cpu, ram, temperatura)

        diagnosticos = analizar()
        mostrar_estado(cpu, ram, temperatura, diagnosticos)
        procesar_diagnosticos(diagnosticos)

        time.sleep(3)


if __name__ == "__main__":
    main()
