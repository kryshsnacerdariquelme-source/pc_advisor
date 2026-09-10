import platform
import subprocess
import time

import psutil

from database import crear_tabla, guardar_lectura, guardar_recomendacion
from diagnostico import analizar
from guia_solucion import obtener_guia
from notificaciones import notificar

INTERVALO_RAPIDO = 3          
CICLOS_PARA_TEMPERATURA = 3   


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


def _temperatura_hardware_monitor():
    """MSAcpi_ThermalZoneTemperature (el metodo 'nativo' de Windows) no
    funciona en gran parte de los equipos, sobre todo notebooks, porque el
    fabricante no expone el sensor por ahi. LibreHardwareMonitor (y su
    antecesor OpenHardwareMonitor) sí leen el sensor real del CPU y lo
    publican en su propio namespace WMI mientras el programa esta abierto
    en segundo plano. Se intenta primero por ser mas confiable; requiere
    tener LibreHardwareMonitor corriendo (gratis, no requiere instalacion)."""
    for namespace in ("root/LibreHardwareMonitor", "root/OpenHardwareMonitor"):
        salida = _powershell(f'''
try {{
    Get-CimInstance -Namespace {namespace} -ClassName Sensor -ErrorAction Stop |
    Where-Object {{ $_.SensorType -eq "Temperature" -and $_.Name -match "CPU" }} |
    Select-Object -First 1 -ExpandProperty Value
}} catch {{ }}
''')
        try:
            valor = float(salida.strip())
            if 0 < valor <= 130:
                return valor
        except Exception:
            continue
    return None


def obtener_temperatura():
    """Intenta varias fuentes de mas a menos confiable:
    1) psutil (funciona en algunos equipos/Linux).
    2) LibreHardwareMonitor / OpenHardwareMonitor via WMI (si el usuario
       los tiene abiertos), que leen el sensor real del CPU.
    3) MSAcpi_ThermalZoneTemperature (WMI nativo de Windows), que en la
       practica falla en muchos equipos pero se deja como ultimo intento.
    Si ninguna funciona, devuelve 0 (se muestra 'No disponible', nunca se
    inventa un valor)."""
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

    valor_hwmonitor = _temperatura_hardware_monitor()
    if valor_hwmonitor is not None:
        return valor_hwmonitor

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
    if not temperatura and platform.system() == "Windows":
        print("               (Tip: abre LibreHardwareMonitor en segundo plano")
        print("                para que se pueda leer el sensor real del CPU)")

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
