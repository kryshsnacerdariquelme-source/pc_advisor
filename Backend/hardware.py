"""Lecturas de hardware para PC Advisor.

La fuente principal en Windows es Libre Hardware Monitor (LHM) mediante WMI.
Se consulta en una sola llamada por ciclo para evitar que CPU/GPU/temperaturas
se actualicen con distintas edades.  psutil queda como respaldo para CPU/RAM/
discos y nvidia-smi como respaldo de GPU NVIDIA.
"""

import json
import platform
import re
import subprocess
from typing import Any

import psutil


def _powershell(comando: str, timeout: float = 4) -> str:
    if platform.system() != "Windows":
        return ""
    try:
        resultado = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", comando],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return resultado.stdout.strip()
    except Exception:
        return ""


def _wmi_valor(clase: str, propiedad: str, namespace: str = "root/cimv2"):
    salida = _powershell(f'''
try {{
    Get-CimInstance -Namespace {namespace} -ClassName {clase} -ErrorAction Stop |
    Select-Object -First 1 -ExpandProperty {propiedad}
}} catch {{ }}
''')
    return salida.strip() or None


def _leer_sensores_lhm() -> list[dict[str, Any]]:
    """Devuelve todos los sensores WMI de LHM en una sola consulta."""
    if platform.system() != "Windows":
        return []

    for namespace in ("root\\LibreHardwareMonitor", "root\\OpenHardwareMonitor"):
        comando = f'''
try {{
    Get-CimInstance -Namespace {namespace} -ClassName Sensor -ErrorAction Stop |
    Select-Object Name,SensorType,Value,Identifier,Parent,HardwareType |
    ConvertTo-Json -Compress -Depth 4
}} catch {{ }}
'''
        salida = _powershell(comando, timeout=5)
        if not salida:
            continue
        try:
            datos = json.loads(salida)
            if isinstance(datos, dict):
                datos = [datos]
            return [x for x in datos if isinstance(x, dict)]
        except Exception:
            continue
    return []


def _sensor_numero(sensor: dict) -> float | None:
    try:
        valor = float(sensor.get("Value"))
        if valor != valor:  # NaN
            return None
        return valor
    except (TypeError, ValueError):
        return None


def _texto_sensor(sensor: dict) -> str:
    return " ".join(
        str(sensor.get(k, "") or "")
        for k in ("Parent", "Name", "Identifier", "HardwareType")
    ).lower()


def _es_gpu(sensor: dict) -> bool:
    texto = _texto_sensor(sensor)
    return any(x in texto for x in (
        "gpu", "graphics", "radeon", "nvidia", "geforce", "rx ", "rx5700", "display adapter"
    ))


def _nombre_gpu_desde_sensores(sensores: list[dict]) -> str | None:
    """Obtiene el nombre del adaptador, evitando devolver /gpu-amd/0."""
    candidatos = []
    for sensor in sensores:
        texto = _texto_sensor(sensor)
        if not _es_gpu(sensor):
            continue
        for clave in ("Parent", "HardwareType", "Name"):
            valor = str(sensor.get(clave, "") or "").strip()
            if not valor:
                continue
            limpio = re.sub(r"^GPU\s*[-:]?\s*", "", valor, flags=re.I).strip()
            if limpio and not limpio.startswith("/gpu-") and not limpio.lower() in {"gpu", "graphics"}:
                candidatos.append(limpio)

    # Nombres WMI/DXGI son preferibles a nombres de sensores individuales.
    for candidato in candidatos:
        if any(x in candidato.lower() for x in ("radeon", "geforce", "nvidia", "intel", "arc")):
            return candidato
    return candidatos[0] if candidatos else None


def _mejor_sensor(sensores: list[dict], sensor_type: str, palabras: tuple[str, ...],
                  preferidas: tuple[str, ...] = ()) -> float | None:
    candidatos = []
    for sensor in sensores:
        if str(sensor.get("SensorType", "")).lower() != sensor_type.lower():
            continue
        valor = _sensor_numero(sensor)
        if valor is None:
            continue
        texto = _texto_sensor(sensor)
        if palabras and not any(p in texto for p in palabras):
            continue
        prioridad = 0
        for p in preferidas:
            if p in texto:
                prioridad += 10
        candidatos.append((prioridad, valor, texto))
    if not candidatos:
        return None
    candidatos.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidatos[0][1]


def _cpu_temperatura_lhm(sensores: list[dict]) -> float | None:
    candidatos = []
    for sensor in sensores:
        if str(sensor.get("SensorType", "")).lower() != "temperature":
            continue
        valor = _sensor_numero(sensor)
        if valor is None or not 0 < valor <= 130:
            continue
        texto = _texto_sensor(sensor)
        if not any(x in texto for x in ("cpu", "processor", "package", "core", "tdie", "tctl", "ccd")):
            continue
        # CPU Package es la lectura más representativa del procesador completo.
        prioridad = 0
        if "cpu package" in texto:
            prioridad += 100
        if "package" in texto:
            prioridad += 50
        if "tdie" in texto or "tctl" in texto:
            prioridad += 30
        if "core max" in texto:
            prioridad += 20
        candidatos.append((prioridad, valor))
    if not candidatos:
        return None
    candidatos.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidatos[0][1]


def _gpu_temperaturas_lhm(sensores: list[dict]) -> tuple[float | None, float | None]:
    core, vram = [], []
    for sensor in sensores:
        if str(sensor.get("SensorType", "")).lower() != "temperature":
            continue
        valor = _sensor_numero(sensor)
        if valor is None or not 0 < valor <= 130 or not _es_gpu(sensor):
            continue
        texto = _texto_sensor(sensor)
        if any(x in texto for x in ("memory", "mem", "vram", "memory junction", "hbm")):
            vram.append(valor)
        else:
            prioridad = 2 if "gpu core" in texto else 1
            core.append((prioridad, valor))
    core_valor = max(core, key=lambda x: (x[0], x[1]))[1] if core else None
    vram_valor = max(vram) if vram else None
    return core_valor, vram_valor


def _gpu_carga_lhm(sensores: list[dict]) -> float | None:
    candidatos = []
    for sensor in sensores:
        if str(sensor.get("SensorType", "")).lower() != "load" or not _es_gpu(sensor):
            continue
        valor = _sensor_numero(sensor)
        if valor is None or not 0 <= valor <= 100:
            continue
        texto = _texto_sensor(sensor)
        prioridad = 0
        if "gpu core" in texto:
            prioridad += 100
        if "gpu" in texto:
            prioridad += 20
        if "memory" in texto:
            prioridad -= 50
        if "media" in texto or "encode" in texto or "decode" in texto:
            prioridad -= 20
        candidatos.append((prioridad, valor))
    if not candidatos:
        return None
    candidatos.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidatos[0][1]


def _nombre_gpu_wmi() -> str | None:
    """Obtiene el nombre real del adaptador gráfico desde Win32_VideoController.

    LHM puede exponer sensores D3D como "D3D Shared Memory Used"; esos son
    sensores de rendimiento, no el nombre de la tarjeta. WMI es una fuente
    mucho más fiable para identificar el adaptador instalado.
    """
    if platform.system() != "Windows":
        return None

    salida = _powershell(r'''
try {
    Get-CimInstance Win32_VideoController -ErrorAction Stop |
    Where-Object { $_.Name -and $_.Name -notmatch '^(Microsoft Basic Display Adapter|Microsoft Remote Display Adapter)$' } |
    Select-Object -ExpandProperty Name
} catch { }
''')
    nombres = [line.strip() for line in salida.splitlines() if line.strip()]
    if not nombres:
        return None

    for nombre in nombres:
        texto = nombre.lower()
        if any(x in texto for x in (
            "nvidia", "geforce", "quadro", "radeon", "amd", "rx ",
            "intel arc", "intel(r) uhd", "intel(r) iris", "graphics"
        )):
            return nombre
    return nombres[0]


def _gpu_nvidia_smi() -> tuple[str | None, float | None, float | None]:
    try:
        resultado = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if resultado.returncode != 0 or not resultado.stdout.strip():
            return None, None, None
        partes = [x.strip() for x in resultado.stdout.splitlines()[0].split(",")]
        nombre = partes[0] if partes else None
        carga = float(partes[1]) if len(partes) > 1 else None
        temp = float(partes[2]) if len(partes) > 2 else None
        return nombre, carga, temp
    except Exception:
        return None, None, None


def obtener_estado_hardware() -> dict:
    """Una lectura coherente de todo el hardware dinámico."""
    sensores = _leer_sensores_lhm()

    # CPU: psutil es la fuente de carga; el sensor de temperatura es LHM.
    try:
        cpu = float(psutil.cpu_percent(interval=0.15))
    except Exception:
        cpu = 0.0
    ram = float(psutil.virtual_memory().percent)

    temperatura_cpu = _cpu_temperatura_lhm(sensores)
    gpu_nombre_smi, gpu_carga, gpu_temp_smi = _gpu_nvidia_smi()
    gpu_nombre_wmi = _nombre_gpu_wmi()
    gpu_temp, vram_temp = _gpu_temperaturas_lhm(sensores)
    gpu_lhm = _gpu_carga_lhm(sensores)
    gpu_carga = gpu_lhm if gpu_lhm is not None else gpu_carga
    # El nombre del adaptador viene de WMI/nvidia-smi. Nunca usar el nombre
    # de un sensor D3D como "D3D Shared Memory Used" para identificar la GPU.
    gpu_nombre = gpu_nombre_wmi or gpu_nombre_smi
    if not gpu_nombre:
        candidato_lhm = _nombre_gpu_desde_sensores(sensores)
        if candidato_lhm and not re.search(r"d3d|shared memory|memory used|\busage\b|\bload\b", candidato_lhm, re.I):
            gpu_nombre = candidato_lhm
    gpu_temp = gpu_temp if gpu_temp is not None else gpu_temp_smi

    discos = obtener_discos(sensores)

    return {
        "cpu": round(cpu, 1),
        "ram": round(ram, 1),
        "temperatura_cpu": round(temperatura_cpu, 1) if temperatura_cpu is not None else 0.0,
        "gpu": round(gpu_carga, 1) if gpu_carga is not None else None,
        "gpu_nombre": gpu_nombre or "No detectada",
        "temperatura_gpu": round(gpu_temp, 1) if gpu_temp is not None else 0.0,
        "temperatura_vram": round(vram_temp, 1) if vram_temp is not None else 0.0,
        "disco": round(_disco_principal_porcentaje(), 1),
        "discos": discos,
        "timestamp": __import__("time").time(),
    }


def obtener_cpu():
    return obtener_estado_hardware()["cpu"]


def obtener_ram():
    return obtener_estado_hardware()["ram"]


def _disco_principal_porcentaje():
    ruta = "C:\\" if platform.system() == "Windows" else "/"
    try:
        return psutil.disk_usage(ruta).percent
    except Exception:
        return 0.0


def obtener_disco():
    return _disco_principal_porcentaje()


def obtener_discos(sensores: list[dict] | None = None) -> list[dict]:
    """Identifica todas las unidades/particiones montadas y su uso.
    Si LHM entrega temperatura para un disco, se agrega al registro."""
    temperaturas = {}
    for sensor in sensores or []:
        if str(sensor.get("SensorType", "")).lower() != "temperature":
            continue
        valor = _sensor_numero(sensor)
        if valor is None or not 0 < valor <= 130:
            continue
        texto = _texto_sensor(sensor)
        if any(x in texto for x in ("nvme", "ssd", "hdd", "storage", "drive", "hard disk")):
            nombre = str(sensor.get("Parent") or sensor.get("Name") or "Disco")
            temperaturas[nombre.lower()] = (nombre, round(valor, 1))

    resultado = []
    try:
        particiones = psutil.disk_partitions(all=False)
        vistas = set()
        for p in particiones:
            if p.mountpoint in vistas:
                continue
            vistas.add(p.mountpoint)
            try:
                uso = psutil.disk_usage(p.mountpoint)
            except (PermissionError, OSError):
                continue
            temperatura = 0.0
            texto_punto = f"{p.device} {p.mountpoint}".lower()
            for clave, (_, temp) in temperaturas.items():
                if any(token and token in texto_punto for token in re.findall(r"[a-z0-9]+", clave)):
                    temperatura = temp
                    break
            resultado.append({
                "unidad": p.mountpoint,
                "dispositivo": p.device,
                "sistema_archivos": p.fstype,
                "total_gb": round(uso.total / 1024**3, 1),
                "usado_gb": round(uso.used / 1024**3, 1),
                "libre_gb": round(uso.free / 1024**3, 1),
                "uso": round(uso.percent, 1),
                "temperatura": temperatura,
            })
    except Exception:
        pass
    return resultado


def obtener_temperatura():
    return obtener_estado_hardware()["temperatura_cpu"]


def obtener_gpu():
    return obtener_estado_hardware()["gpu"]


def nombre_gpu():
    return obtener_estado_hardware()["gpu_nombre"]


def plan_energia_activo():
    if platform.system() != "Windows":
        return None
    salida = _powershell("powercfg /getactivescheme")
    if not salida:
        return None
    if "(" in salida and ")" in salida:
        return salida.split("(")[-1].split(")")[0].strip()
    return salida


def specs_estaticas():
    ram_total_gb = round(psutil.virtual_memory().total / (1024 ** 3), 1)
    try:
        disco_total_gb = round(sum(
            psutil.disk_usage(p.mountpoint).total for p in psutil.disk_partitions(all=False)
            if p.mountpoint
        ) / (1024 ** 3), 1)
    except Exception:
        disco_total_gb = None

    so = f"{platform.system()} {platform.release()}"
    cpu_modelo = platform.processor() or "No disponible"
    placa_madre = "No disponible"
    if platform.system() == "Windows":
        cpu_wmi = _wmi_valor("Win32_Processor", "Name")
        if cpu_wmi:
            cpu_modelo = cpu_wmi
        fabricante = _wmi_valor("Win32_BaseBoard", "Manufacturer")
        producto = _wmi_valor("Win32_BaseBoard", "Product")
        if fabricante or producto:
            placa_madre = " ".join(x for x in (fabricante, producto) if x)

    sensores = _leer_sensores_lhm()
    gpu = _nombre_gpu_wmi()
    if not gpu:
        gpu, _, _ = _gpu_nvidia_smi()
    if not gpu:
        candidato_lhm = _nombre_gpu_desde_sensores(sensores)
        if candidato_lhm and not re.search(r"d3d|shared memory|memory used|\busage\b|\bload\b", candidato_lhm, re.I):
            gpu = candidato_lhm
    gpu = gpu or "No detectada"

    return {
        "so": so,
        "cpu_modelo": cpu_modelo,
        "ram_total_gb": ram_total_gb,
        "disco_total_gb": disco_total_gb,
        "placa_madre": placa_madre,
        "gpu": gpu,
    }
