"""Generación del reporte de diagnóstico en PDF.

Un solo lugar para armar el PDF, reutilizado tanto por el Frontend
(Streamlit, con st.download_button) como por el Desktop (PySide6, con
un QFileDialog para elegir dónde guardarlo).
"""
from datetime import datetime

from fpdf import FPDF


def _color_a_rgb(color_hex):
    color_hex = color_hex.lstrip("#")
    return tuple(int(color_hex[i:i + 2], 16) for i in (0, 2, 4))


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
    pdf.cell(0, 12, "PC Advisor - Reporte de diagnostico", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 8, f"Generado el {datetime.now().strftime('%d-%m-%Y %H:%M')}", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # --- Puntaje de salud ---
    r, g, b = _color_a_rgb(color_puntaje)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(r, g, b)
    pdf.cell(28, 14, str(puntaje))
    pdf.set_text_color(0, 0, 0)
    pdf.set_xy(pdf.get_x(), pdf.get_y())
    pdf.set_font("Helvetica", "B", 11)
    pdf.multi_cell(0, 6, f"{mensaje_puntaje}\n{detalle_puntaje}")
    pdf.ln(3)

    # --- Mi equipo ---
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Mi equipo", ln=True)
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
            pdf.cell(55, 6, etiqueta)
            pdf.cell(0, 6, str(valor), ln=True)
    pdf.ln(3)

    # --- Estado actual ---
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Estado actual", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(40, 6, f"CPU: {cpu:.0f}%")
    pdf.cell(40, 6, f"RAM: {ram:.0f}%")
    pdf.cell(0, 6, f"GPU: {gpu:.0f}%" if gpu is not None else "GPU: N/D", ln=True)
    disco_texto = ", ".join(
        f"{d.get('unidad', 'Disco')} {d.get('uso', 0):.0f}%" for d in (discos or [])
    )
    pdf.multi_cell(0, 6, f"Disco: {disco_texto or 'N/D'}")
    pdf.ln(3)

    # --- Alertas activas ---
    if alertas:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Alertas activas", ln=True)
        pdf.set_font("Helvetica", "", 10)
        for mensaje in alertas:
            pdf.multi_cell(0, 6, f"- {mensaje}")
        pdf.ln(3)

    # --- Tabla de ultimas lecturas ---
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Ultimas lecturas", ln=True)
    anchos = [45, 45, 45, 45]
    pdf.set_font("Helvetica", "B", 9)
    for titulo, ancho in zip(["CPU", "RAM", "GPU", "Disco"], anchos):
        pdf.cell(ancho, 7, titulo, border=1, align="C")
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    for fila in (lecturas or []):
        cpu_l, ram_l, temperatura_l, disco_l, gpu_l = fila
        valores = [
            f"{cpu_l:.0f}%" if cpu_l is not None else "N/D",
            f"{ram_l:.0f}%" if ram_l is not None else "N/D",
            f"{gpu_l:.0f}%" if gpu_l is not None else "N/D",
            f"{disco_l:.0f}%" if disco_l is not None else "N/D",
        ]
        for valor, ancho in zip(valores, anchos):
            pdf.cell(ancho, 7, valor, border=1, align="C")
        pdf.ln()

    return bytes(pdf.output())
