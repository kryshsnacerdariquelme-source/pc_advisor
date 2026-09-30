"""Colores, textos y estilos de la app de escritorio.

Los valores salen del Frontend (Frontend/app.py, la version en Streamlit)
para que ambas interfaces se vean igual.
"""
import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "Backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from diagnostico import UMBRAL_CPU, UMBRAL_RAM  # noqa: E402
from puntaje import UMBRAL_GPU_REFERENCIA, UMBRAL_DISCO_REFERENCIA  # noqa: E402

COLOR_FONDO = "#0D1321"
COLOR_TARJETA = "#151D30"
COLOR_BORDE = "#28324A"
COLOR_TEXTO = "#E8ECF2"
COLOR_TEXTO_TENUE = "#8B93A8"
COLOR_TRACK = "#1D2740"
ACENTO_CPU = "#3B82F6"
ACENTO_RAM = "#8B5CF6"
ACENTO_DISCO = "#F59E0B"
ACENTO_GPU = "#22C55E"
COLOR_ROJO = "#EF4444"
COLOR_VERDE = "#22C55E"
COLOR_LINEA_GRAFICO = {"RAM": "#8B5CF6", "CPU": "#3B82F6", "Disco": "#F59E0B", "GPU": "#22C55E"}

GLOSARIO = {
    "cpu": "CPU (procesador): ejecuta las instrucciones de tus programas. Un uso alto y sostenido significa que hay procesos exigiendo mucho trabajo al mismo tiempo.",
    "ram": "RAM (memoria): guarda temporalmente los datos que tus programas están usando en este momento. Si se satura, el equipo se vuelve lento porque empieza a apoyarse en el disco, que es mucho más lento.",
    "temperatura": "Temperatura del procesador: sobre los 80°C sostenidos el equipo puede bajar su rendimiento a propósito para protegerse (throttling), o acortar la vida útil del hardware con el tiempo.",
    "disco": "Disco (almacenamiento): cuánto espacio ocupado tiene tu disco. Si está casi lleno, Windows no tiene espacio para archivos temporales y el equipo se puede volver lento aunque la RAM esté bien.",
    "gpu": "GPU (tarjeta gráfica): procesa gráficos y video. Un uso alto es normal jugando o editando video; si sube sin razón aparente puede valer la pena revisarlo.",
    "vram": "Temperatura de memoria de la GPU cuando el hardware la expone.",
}

EXPLICACION_LIMITE = {
    "cpu": f"Si pasa el {UMBRAL_CPU}% seguido por un rato: el procesador está trabajando al máximo casi todo el tiempo y el equipo puede sentirse lento o trabado.",
    "ram": f"Si pasa el {UMBRAL_RAM}% seguido por un rato: la memoria está casi llena y el equipo empieza a apoyarse en el disco (mucho más lento) para poder seguir funcionando.",
    "gpu": f"Si pasa el {UMBRAL_GPU_REFERENCIA}%: la tarjeta gráfica está trabajando al máximo. Es normal si estás jugando o editando video; si ocurre sin razón aparente, vale la pena revisarlo.",
    "disco": f"Si pasa el {UMBRAL_DISCO_REFERENCIA}%: el disco está casi lleno. Sin espacio libre, Windows no tiene dónde guardar archivos temporales y el equipo se puede volver lento.",
}


def tooltip(texto):
    """Tooltip con ancho acotado (Qt no ajusta el texto plano a varias lineas)."""
    return f'<table width="300"><tr><td>{html.escape(texto)}</td></tr></table>'


STYLE = f"""
QWidget {{ color:{COLOR_TEXTO}; font-family:'Segoe UI'; font-size:13px; }}
QMainWindow, #raiz, #pagina {{ background:{COLOR_FONDO}; }}
QLabel {{ background:transparent; }}
QScrollArea {{ background:transparent; border:0; }}

#barra_lateral {{ background:{COLOR_FONDO}; border-right:1px solid {COLOR_BORDE}; }}
#nav {{ background:transparent; color:{COLOR_TEXTO}; border:0; border-radius:8px;
        padding:9px 12px; text-align:left; font-size:14px; }}
#nav:hover {{ background:rgba(255,255,255,0.06); }}
#nav:checked {{ background:rgba(255,255,255,0.12); font-weight:600; }}

#titulo_pagina {{ font-size:34px; font-weight:700; }}
#subtitulo {{ font-size:22px; font-weight:700; }}
#seccion {{ font-size:17px; font-weight:700; }}
#caption {{ color:{COLOR_TEXTO_TENUE}; font-size:13px; }}
#mini {{ color:{COLOR_TEXTO_TENUE}; font-size:11px; }}
#stat_izq {{ color:{COLOR_TEXTO_TENUE}; font-size:13px; }}
#stat_der {{ font-size:13px; font-weight:600; }}
#card_titulo {{ font-size:15px; font-weight:700; }}
#card_modelo {{ color:{COLOR_TEXTO_TENUE}; font-size:13px; }}
#aviso_info {{ background:#10243D; color:#A8D1FF; border-radius:8px; padding:12px 14px; }}
#aviso_warning {{ background:#25281F; color:#FFFFC2; border-radius:8px; padding:12px 14px; }}
#divisor {{ background:{COLOR_BORDE}; }}
#badge_pendiente {{ background:#4A1414; color:#EF4444; padding:4px 12px; border-radius:12px;
                    font-weight:700; font-size:13px; }}
#badge_resuelto {{ background:#14351C; color:#22C55E; padding:4px 12px; border-radius:12px;
                   font-weight:700; font-size:13px; }}

QPushButton {{ background:{COLOR_TARJETA}; color:{COLOR_TEXTO}; border:1px solid {COLOR_BORDE};
               border-radius:8px; padding:8px 14px; }}
QPushButton:hover {{ border-color:#5B6B91; color:#FFFFFF; }}
QPushButton:pressed {{ background:{COLOR_TRACK}; }}

QToolTip {{ background:{COLOR_TARJETA}; color:{COLOR_TEXTO}; border:1px solid {COLOR_BORDE};
            border-radius:8px; padding:8px 10px; font-size:12px; }}

QScrollBar:vertical {{ background:{COLOR_FONDO}; width:10px; margin:0; }}
QScrollBar::handle:vertical {{ background:{COLOR_BORDE}; border-radius:5px; min-height:30px; }}
QScrollBar::handle:vertical:hover {{ background:#3A4766; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:transparent; }}
"""


def apply_style(app):
    app.setStyleSheet(STYLE)
