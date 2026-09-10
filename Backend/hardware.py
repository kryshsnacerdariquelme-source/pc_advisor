"""
Modulo NUEVO: junta todas las lecturas de hardware (CPU, RAM, disco,
temperatura, GPU) y los datos fijos del equipo (SO, modelo de CPU, placa
madre, etc.) en un solo lugar. Antes esto vivia mezclado dentro de
monitor.py; se separa para que la interfaz (Frontend/app.py) tambien
pueda usar estas funciones -por ejemplo para el panel "Mi Equipo"- sin
tener que importar el loop del monitor.
"""

import platform
import subprocess

import psutil


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


def _wmi_valor(clase, propiedad, namespace="root/cimv2"):
    salida = _powershell(f'''
try {{
    Get-CimInstance -Namespace {namespace} -ClassName {clase} -ErrorAction Stop |
    Select-Object -First 1 -ExpandProperty {propiedad}
}} catch {{ }}
''')
    return salida.strip() or None


# ---------------------------------------------------------------------
# Lecturas periodicas (RF-01)
# ---------------------------------------------------------------------

def obtener_cpu():
    return psutil.cpu_percent(interval=1)


def obtener_ram():
    return psutil.virtual_memory().percent


def obtener_disco():
    """% de uso del disco donde vive el sistema operativo. Se agrega para
    completar RF-01 (antes solo se media cpu/ram/temperatura, faltaba
    almacenamiento)."""
    ruta = "C:\\" if platform.system() == "Windows" else "/"
    try:
        return psutil.disk_usage(ruta).percent
    except Exception:
        return 0.0


def _temperatura_hardware_monitor():
    """MSAcpi_ThermalZoneTemperature (el metodo 'nativo' de Windows) no
    funciona en gran parte de los equipos, sobre todo notebooks, porque el
    fabricante no expone el sensor por ahi. LibreHardwareMonitor (y su
    antecesor OpenHardwareMonitor) si leen el sensor real del CPU y lo
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


def obtener_gpu():
    """% de uso de la GPU, via nvidia-smi (viene instalado junto al driver
    de NVIDIA y queda disponible en el PATH). En equipos con GPU AMD o
    Intel, o si falta el driver de NVIDIA, no existe una forma
    multiplataforma confiable de leer esto sin herramientas de terceros
    -mismo caso que la temperatura de CPU-, asi que se devuelve None
    (se muestra 'No disponible', nunca se inventa un valor)."""
    try:
        resultado = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=4,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if resultado.returncode == 0 and resultado.stdout.strip():
            return float(resultado.stdout.strip().splitlines()[0])
    except Exception:
        pass
    return None


def nombre_gpu():
    try:
        resultado = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=4,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if resultado.returncode == 0 and resultado.stdout.strip():
            return resultado.stdout.strip().splitlines()[0]
    except Exception:
        pass
    return None


def plan_energia_activo():
    """Nombre del plan de energia activo en Windows (ej. 'Equilibrado',
    'Ahorro de energia'). Sirve para RF-07: si el equipo esta exigido pero
    tiene activo un plan restrictivo, puede ser un tema de configuracion
    y no de hardware insuficiente."""
    if platform.system() != "Windows":
        return None
    salida = _powershell("powercfg /getactivescheme")
    if not salida:
        return None
    if "(" in salida and ")" in salida:
        return salida.split("(")[-1].split(")")[0].strip()
    return salida


# ---------------------------------------------------------------------
# Datos fijos del equipo, para el panel "Mi Equipo"
# ---------------------------------------------------------------------

def specs_estaticas():
    """Datos que no cambian entre lecturas. Se consultan una sola vez por
    sesion (la interfaz las cachea) para mostrar el panel 'Mi Equipo'."""
    ram_total_gb = round(psutil.virtual_memory().total / (1024 ** 3), 1)
    ruta = "C:\\" if platform.system() == "Windows" else "/"
    try:
        disco_total_gb = round(psutil.disk_usage(ruta).total / (1024 ** 3), 1)
    except Exception:
        disco_total_gb = None

    so = f"{platform.system()} {platform.release()}"
    cpu_modelo = platform.processor() or "No disponible"
    placa_madre = "No disponible"

    if platform.system() == "Windows":
        modelo_cpu_wmi = _wmi_valor("Win32_Processor", "Name")
        if modelo_cpu_wmi:
            cpu_modelo = modelo_cpu_wmi
        fabricante = _wmi_valor("Win32_BaseBoard", "Manufacturer")
        producto = _wmi_valor("Win32_BaseBoard", "Product")
        if fabricante or producto:
            placa_madre = " ".join(x for x in (fabricante, producto) if x)

    gpu = nombre_gpu() or "No detectada (GPU no NVIDIA o falta el driver)"

    return {
        "so": so,
        "cpu_modelo": cpu_modelo,
        "ram_total_gb": ram_total_gb,
        "disco_total_gb": disco_total_gb,
        "placa_madre": placa_madre,
        "gpu": gpu,
    }
