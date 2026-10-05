"""Generación del reporte de diagnóstico en PDF.

Un solo lugar para armar el PDF, reutilizado tanto por el Frontend
(Streamlit, con st.download_button) como por el Desktop (PySide6, con
un QFileDialog para elegir dónde guardarlo).

Requiere fpdf2 (pip install fpdf2).
"""
from datetime import datetime

from fpdf import FPDF
from fpdf.enums import XPos, YPos


def _color_a_rgb(color_hex):
    color_hex = color_hex.lstrip("#")
    return tuple(int(color_hex[i:i + 2], 16) for i in (0, 2, 4))


def _t(texto):
    """La fuente base (Helvetica) solo admite latin-1: los caracteres que no
    entren (emojis, simbolos raros en nombres de procesos, etc.) se cambian
    por '?' en vez de hacer fallar todo el reporte."""
    return str(texto).encode("latin-1", "replace").decode("latin-1")


def _linea(pdf, ancho, alto, texto, **kwargs):
    """Celda que termina con salto de linea (vuelve al margen izquierdo)."""
    pdf.cell(ancho, alto, _t(texto), new_x=XPos.LMARGIN, new_y=YPos.NEXT, **kwargs)


def _celda(pdf, ancho, alto, texto, **kwargs):
    """Celda que deja el cursor a su derecha (para poner otra al lado)."""
    pdf.cell(ancho, alto, _t(texto), new_x=XPos.RIGHT, new_y=YPos.TOP, **kwargs)


def _parrafo(pdf, alto, texto, ancho=0):
    """Texto multilinea que deja el cursor en el margen izquierdo, abajo."""
    pdf.multi_cell(ancho, alto, _t(texto), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def generar_reporte_pdf(specs, puntaje, color_puntaje, mensaje_puntaje, detalle_puntaje,
                         cpu, ram, gpu, discos, lecturas, alertas=None):
    """Arma el PDF y devuelve los bytes listos para guardar o descargar.

    - specs: dict como el que devuelve Backend/hardware.py (specs_estaticas()).
    - lecturas: lista de tuplas (cpu, ram, temperatura, disco, gpu), más
      reciente primero (mismo formato que obtener_ultimas_lecturas()).
    - alertas: lista de mensajes de recomendaciones pendientes (opcional).
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    _linea(pdf, 0, 12, "PC Advisor - Reporte de diagnostico")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(120, 120, 120)
    _linea(pdf, 0, 8, f"Generado el {datetime.now().strftime('%d-%m-%Y %H:%M')}")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # --- Puntaje de salud ---
    r, g, b = _color_a_rgb(color_puntaje)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(r, g, b)
    _celda(pdf, 28, 14, str(puntaje))
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 11)
    _parrafo(pdf, 6, f"{mensaje_puntaje}\n{detalle_puntaje}")
    pdf.ln(3)

    # --- Mi equipo ---
    pdf.set_font("Helvetica", "B", 13)
    _linea(pdf, 0, 8, "Mi equipo")
    pdf.set_font("Helvetica", "", 10)
    filas_equipo = [
        ("Sistema operativo", specs.get("so")),
        ("Procesador", specs.get("cpu_modelo")),
        ("Memoria RAM", f"{specs.get('ram_total_gb')} GB" if specs.get("ram_total_gb") else None),
        ("Disco", f"{specs.get('disco_total_gb')} GB" if specs.get("disco_total_gb") else None),
        ("Tarjeta grafica", specs.get("gpu")),
        ("Placa madre", specs.get("placa_madre")),
    ]
    for etiqueta, valor in filas_equipo:
        if valor and str(valor).strip().lower() not in ("none", "no disponible"):
            _celda(pdf, 55, 6, etiqueta)
            _linea(pdf, 0, 6, str(valor))
    pdf.ln(3)

    # --- Estado actual ---
    pdf.set_font("Helvetica", "B", 13)
    _linea(pdf, 0, 8, "Estado actual")
    pdf.set_font("Helvetica", "", 10)
    _celda(pdf, 40, 6, f"CPU: {cpu:.0f}%")
    _celda(pdf, 40, 6, f"RAM: {ram:.0f}%")
    _linea(pdf, 0, 6, f"GPU: {gpu:.0f}%" if gpu is not None else "GPU: N/D")
    disco_texto = ", ".join(
        f"{d.get('unidad', 'Disco')} {d.get('uso', 0):.0f}%" for d in (discos or [])
    )
    _parrafo(pdf, 6, f"Disco: {disco_texto or 'N/D'}")
    pdf.ln(3)

    # --- Alertas activas ---
    if alertas:
        pdf.set_font("Helvetica", "B", 13)
        _linea(pdf, 0, 8, "Alertas activas")
        pdf.set_font("Helvetica", "", 10)
        for mensaje in alertas:
            _parrafo(pdf, 6, f"- {mensaje}")
        pdf.ln(3)

    # --- Tabla de ultimas lecturas ---
    pdf.set_font("Helvetica", "B", 13)
    _linea(pdf, 0, 8, "Ultimas lecturas")
    anchos = [45, 45, 45, 45]
    pdf.set_font("Helvetica", "B", 9)
    for titulo, ancho in zip(["CPU", "RAM", "GPU", "Disco"], anchos):
        _celda(pdf, ancho, 7, titulo, border=1, align="C")
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    for fila in (lecturas or []):
        cpu_l, ram_l, _temperatura_l, disco_l, gpu_l = fila
        valores = [
            f"{cpu_l:.0f}%" if cpu_l is not None else "N/D",
            f"{ram_l:.0f}%" if ram_l is not None else "N/D",
            f"{gpu_l:.0f}%" if gpu_l is not None else "N/D",
            f"{disco_l:.0f}%" if disco_l is not None else "N/D",
        ]
        for valor, ancho in zip(valores, anchos):
            _celda(pdf, ancho, 7, valor, border=1, align="C")
        pdf.ln()

    return bytes(pdf.output())
