import platform
import time

from database import crear_tabla, guardar_lectura, guardar_recomendacion
from diagnostico import analizar
from guia_solucion import obtener_guia
from hardware import obtener_cpu, obtener_ram, obtener_disco, obtener_temperatura, obtener_gpu
from notificaciones import notificar

INTERVALO_RAPIDO = 3          # CPU, RAM y disco: se consultan en cada ciclo
CICLOS_PARA_TEMPERATURA = 3   # temperatura y GPU: cada 3 ciclos (~9s), son mas lentas de consultar


def mostrar_estado(cpu, ram, temperatura, disco, gpu, diagnosticos):
    print("\n" + "=" * 50)
    print("             PC ADVISOR")
    print("=" * 50)
    print(f"CPU:           {cpu:.1f}%")
    print(f"RAM:           {ram:.1f}%")
    print(f"Disco:         {disco:.1f}%")
    print(f"Temperatura:   {'No disponible' if not temperatura else f'{temperatura:.1f} C'}")
    if not temperatura and platform.system() == "Windows":
        print("               (Tip: abre LibreHardwareMonitor en segundo plano")
        print("                para que se pueda leer el sensor real del CPU)")
    print(f"GPU:           {'No disponible' if gpu is None else f'{gpu:.1f}%'}")

    if not diagnosticos:
        print("\nTodo funciona con normalidad. No hay alertas nuevas.")
    else:
        print("\nALERTAS NUEVAS")
        print("-" * 50)
        for d in diagnosticos:
            print(f"- {d['mensaje']}")
    print("=" * 50)


def procesar_diagnosticos(diagnosticos):
    for d in diagnosticos:
        guia = obtener_guia(d["tipo"])
        if guardar_recomendacion(d["tipo"], d["mensaje"], guia):
            notificar("PC Advisor", d["mensaje"])
            print(f"\n>> Nueva alerta guardada en el historial: {d['tipo']}")
            print(f">> Guia de solucion:\n{guia}")


def main():
    crear_tabla()
    print("PC Advisor iniciado...")
    print("Presiona CTRL + C para detener.\n")

    temperatura = 0.0
    gpu = None
    ciclo = 0

    while True:
        cpu = obtener_cpu()
        ram = obtener_ram()
        disco = obtener_disco()

        if ciclo % CICLOS_PARA_TEMPERATURA == 0:
            temperatura = obtener_temperatura()
            gpu = obtener_gpu()

        guardar_lectura(cpu, ram, temperatura, disco, gpu)

        diagnosticos = analizar()
        mostrar_estado(cpu, ram, temperatura, disco, gpu, diagnosticos)
        procesar_diagnosticos(diagnosticos)

        ciclo += 1
        time.sleep(INTERVALO_RAPIDO)


if __name__ == "__main__":
    main()
