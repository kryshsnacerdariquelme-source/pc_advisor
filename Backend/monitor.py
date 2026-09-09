import platform
import subprocess
import time

import psutil

from database import crear_tabla, guardar_lectura, guardar_recomendacion
from diagnostico import analizar
from guia_solucion import obtener_guia
from notificaciones import notificar

INTERVALO_RAPIDO = 3          # CPU y RAM: se consultan en cada ciclo
CICLOS_PARA_TEMPERATURA = 3   # temperatura: cada 3 ciclos (~9s), es mas lenta de consultar


def _powershell(comando, timeout=6):
    if platform.system() != "Windows":
        return ""
    try:
        resultado = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", comando],
            capture_output=True, text=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return resultado.stdout.strip()
    except Exception:
        return ""


def obtener_temperatura():
    """Primero intenta con psutil (funciona en algunos equipos/Linux).
    Si no hay nada, en Windows recurre a MSAcpi_ThermalZoneTemperature
    (WMI), que suele detectar la temperatura del CPU cuando psutil no
    puede. Si ninguna funciona, devuelve 0 (se muestra 'No disponible',
    nunca se inventa un valor)."""
    try:
        for grupo, sensores in psutil.sensors_temperatures().items():
            for s in sensores:
                if s.current and 0 < s.current <= 130:
                    texto = f"{grupo} {s.label}".lower()
                    if any(x in texto for x in ("cpu", "package", "core", "k10temp")):
                        return s.current
    except Exception:
        pass

    if platform.system() != "Windows":
        return 0.0

    salida = _powershell(r'''
try {
    Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop |
    Select-Object -First 1 -ExpandProperty CurrentTemperature
} catch { }
''')
    try:
        valor_raw = float(salida.strip())
        celsius = (valor_raw / 10.0) - 273.15
        if 0 < celsius <= 130:
            return celsius
    except Exception:
        pass

    return 0.0


def mostrar_estado(cpu, ram, temperatura, diagnosticos):
    print("\n" + "=" * 50)
    print("             PC ADVISOR")
    print("=" * 50)
    print(f"CPU:           {cpu:.1f}%")
    print(f"RAM:           {ram:.1f}%")
    print(f"Temperatura:   {'No disponible' if not temperatura else f'{temperatura:.1f} C'}")

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
    ciclo = 0

    while True:
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent

        if ciclo % CICLOS_PARA_TEMPERATURA == 0:
            temperatura = obtener_temperatura()

        guardar_lectura(cpu, ram, temperatura)

        diagnosticos = analizar()
        mostrar_estado(cpu, ram, temperatura, diagnosticos)
        procesar_diagnosticos(diagnosticos)

        ciclo += 1
        time.sleep(INTERVALO_RAPIDO)


if __name__ == "__main__":
    main()
