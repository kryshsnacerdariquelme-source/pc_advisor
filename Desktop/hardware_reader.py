import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "Backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from hardware import specs_estaticas

STATE_PATH = ROOT / "data" / "estado_actual.json"


def read_state():
    try:
        with STATE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def read_specs():
    try:
        return specs_estaticas()
    except Exception:
        return {
            "so": "No disponible",
            "cpu_modelo": "No disponible",
            "ram_total_gb": None,
            "disco_total_gb": None,
            "placa_madre": "No disponible",
            "gpu": "No detectada",
        }
