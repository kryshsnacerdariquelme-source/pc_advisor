"""Generación del informe técnico del equipo en PDF.

Pensado para entregarlo a un servicio técnico: identifica el equipo
(fabricante, modelo, componentes), muestra su estado medido y lista los
hallazgos con la mejora sugerida. Un solo lugar para armar el PDF,
reutilizado por el Frontend (Streamlit, st.download_button) y por el
Desktop (PySide6, QFileDialog).

Requiere fpdf2 (pip install fpdf2).
"""
from datetime import datetime

from fpdf import FPDF
from fpdf.enums import TableBordersLayout, TableCellFillMode, XPos, YPos
from fpdf.fonts import FontFace

# Mismos umbrales que usa la app
UMBRAL_CPU = 90
UMBRAL_RAM = 85
UMBRAL_GPU = 90
UMBRAL_DISCO = 90
UMBRAL_TEMP = 80
MARGEN_ATENCION_PCT = 15   # a partir de (umbral - 15) se marca "Atención"
MARGEN_ATENCION_TEMP = 10

AZUL_OSCURO = (13, 19, 33)
AZUL = (59, 130, 246)
GRIS_TEXTO = (90, 96, 110)
GRIS_FILA = (244, 246, 250)
VERDE = (22, 130, 70)
AMBAR = (176, 105, 0)
ROJO = (190, 30, 45)

COLOR_ESTADO = {"Normal": VERDE, "Atención": AMBAR, "Crítico": ROJO, "N/D": GRIS_TEXTO}


def _t(texto):
    """La fuente base (Helvetica) solo admite latin-1: los caracteres que no
    entren (emojis, símbolos raros en nombres de procesos, etc.) se cambian
    por '?' en vez de hacer fallar todo el reporte."""
    return str(texto).encode("latin-1", "replace").decode("latin-1")


def _logo():
    try:
        from rutas import ruta_logo
        ruta = ruta_logo()
        return str(ruta) if ruta.exists() else None
    except Exception:
        return None


class _Informe(FPDF):
    def header(self):
        self.set_fill_color(*AZUL_OSCURO)
        self.rect(0, 0, 210, 18, "F")
        x_texto = 15
        logo = _logo()
        if logo:
            try:
                self.image(logo, x=14, y=3, h=12)
                x_texto = 29
            except Exception:
                pass
        self.set_xy(x_texto, 5)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(255, 255, 255)
        self.cell(60, 8, "PC Advisor")
        self.set_text_color(0, 0, 0)
        self.set_y(26)

    def footer(self):
        self.set_y(-17)
        self.set_text_color(*GRIS_TEXTO)
        self.set_font("Helvetica", "I", 7.5)
        self.cell(0, 4, _t("Informe generado automáticamente por PC Advisor. Valores referenciales; "
                           "no reemplazan una revisión técnica presencial."),
                  align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Helvetica", "", 8)
        self.cell(0, 5, _t(f"Página {self.page_no()} de {{nb}}"), align="C")


def _seccion(pdf, titulo, espacio_minimo=35):
    """Si no queda lugar para el título y al menos una fila de tabla, pasa a
    la página siguiente (evita títulos huérfanos al final de la página)."""
    if pdf.get_y() + espacio_minimo > pdf.h - pdf.b_margin:
        pdf.add_page()
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*AZUL_OSCURO)
    pdf.cell(0, 7, _t(titulo), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1.5)


def _nota(pdf, texto):
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*GRIS_TEXTO)
    pdf.multi_cell(0, 4.5, _t(texto), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)


def _tabla(pdf, anchos, filas, encabezados=None, alineacion=None):
    """filas: lista de listas; cada celda es texto o (texto, FontFace)."""
    pdf.set_font("Helvetica", "", 9)
    pdf.set_draw_color(*AZUL)
    pdf.set_line_width(0.2)
    estilo_enc = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=AZUL_OSCURO)
    with pdf.table(
        col_widths=anchos,
        text_align=alineacion or tuple("LEFT" for _ in anchos),
        first_row_as_headings=bool(encabezados),
        headings_style=estilo_enc,
        borders_layout=TableBordersLayout.HORIZONTAL_LINES,
        cell_fill_color=GRIS_FILA,
        cell_fill_mode=TableCellFillMode.ROWS,
        line_height=5.5,
        padding=1.0,
        v_align="MIDDLE",
    ) as tabla:
        if encabezados:
            fila = tabla.row()
            for h in encabezados:
                fila.cell(_t(h))
        for datos in filas:
            fila = tabla.row()
            for celda in datos:
                if isinstance(celda, tuple):
                    fila.cell(_t(celda[0]), style=celda[1])
                else:
                    fila.cell(_t(celda))


def _valido(v):
    return v is not None and str(v).strip().lower() not in ("", "none", "no disponible", "no detectada")


def _estado(valor, umbral, margen):
    if valor is None:
        return "N/D"
    if valor >= umbral:
        return "Crítico"
    if valor >= umbral - margen:
        return "Atención"
    return "Normal"


def _celda_estado(estado):
    return (estado, FontFace(emphasis="BOLD", color=COLOR_ESTADO[estado]))


def _pct(v):
    return f"{v:.0f}%" if v is not None else "N/D"


def _estadisticas(valores):
    """(promedio, maximo) o (None, None) si no hay datos."""
    v = [x for x in valores if x is not None]
    return (sum(v) / len(v), max(v)) if v else (None, None)


def _hallazgos(specs, cpu, ram, gpu, discos, stats, temp_max, alertas):
    """Devuelve lista de (hallazgo, mejora, prioridad) según lo medido."""
    h = []
    ram_total = specs.get("ram_total_gb")

    ram_ref = max(x for x in (ram, stats["ram"][0]) if x is not None)
    if ram_ref >= UMBRAL_RAM:
        h.append((
            f"Uso de memoria RAM elevado (actual {ram:.0f}%, promedio reciente {_pct(stats['ram'][0])}).",
            "Cerrar programas en segundo plano y revisar los que más memoria usan. Si es recurrente, "
            f"evaluar ampliar la RAM{f' (hoy {ram_total} GB)' if ram_total else ''}.",
            "Alta"))
    elif ram_ref >= UMBRAL_RAM - MARGEN_ATENCION_PCT:
        h.append((
            f"Uso de memoria RAM moderado-alto (actual {ram:.0f}%, promedio reciente {_pct(stats['ram'][0])}).",
            "Vigilar el consumo; si sube con el uso normal, considerar ampliar la RAM.",
            "Media"))

    cpu_ref = max(x for x in (cpu, stats["cpu"][0]) if x is not None)
    if cpu_ref >= UMBRAL_CPU:
        h.append((
            f"Uso de procesador elevado (actual {cpu:.0f}%, promedio reciente {_pct(stats['cpu'][0])}).",
            "Revisar procesos que consumen CPU y descartar software malicioso. Verificar la refrigeración "
            "y el plan de energía.",
            "Alta"))
    elif cpu_ref >= UMBRAL_CPU - MARGEN_ATENCION_PCT:
        h.append((
            f"Uso de procesador moderado-alto (actual {cpu:.0f}%, promedio reciente {_pct(stats['cpu'][0])}).",
            "Vigilar el consumo y los programas que arrancan con el sistema.",
            "Media"))

    if gpu is not None and gpu >= UMBRAL_GPU:
        h.append((f"Uso de tarjeta gráfica elevado ({gpu:.0f}%).",
                  "Revisar la carga gráfica, actualizar controladores y verificar la refrigeración.",
                  "Media"))

    if temp_max is not None:
        if temp_max >= UMBRAL_TEMP:
            h.append((f"Temperatura elevada (máxima registrada {temp_max:.0f} °C).",
                      "Limpieza interna, revisión de ventiladores y disipador, y evaluar cambio de pasta térmica.",
                      "Alta"))
        elif temp_max >= UMBRAL_TEMP - MARGEN_ATENCION_TEMP:
            h.append((f"Temperatura moderada-alta (máxima registrada {temp_max:.0f} °C).",
                      "Mantener ventilación libre y considerar una limpieza preventiva.",
                      "Media"))

    for d in discos or []:
        uso = d.get("uso")
        if uso is None:
            continue
        unidad = d.get("unidad", "Disco")
        libre = d.get("libre_gb")
        extra = f", libres {libre} GB" if libre is not None else ""
        if uso >= UMBRAL_DISCO:
            h.append((f"Unidad {unidad} casi llena ({uso:.0f}% usado{extra}).",
                      "Liberar espacio (archivos temporales, descargas, programas sin uso) o ampliar/migrar "
                      "el almacenamiento, idealmente a una unidad SSD.",
                      "Alta"))
        elif uso >= UMBRAL_DISCO - MARGEN_ATENCION_PCT:
            h.append((f"Unidad {unidad} con poco espacio libre ({uso:.0f}% usado{extra}).",
                      "Planificar una limpieza o ampliación de almacenamiento.",
                      "Media"))

    for mensaje in alertas or []:
        h.append((f"Alerta registrada por PC Advisor: {mensaje}",
                  "Seguir la guía de solución indicada en la aplicación.",
                  "Media"))
    return h


def generar_reporte_pdf(specs, puntaje, color_puntaje, mensaje_puntaje, detalle_puntaje,
                         cpu, ram, gpu, discos, lecturas, alertas=None):
    """Arma el PDF y devuelve los bytes listos para guardar o descargar.

    - specs: dict como el que devuelve Backend/hardware.py (specs_estaticas()).
    - lecturas: lista de tuplas (cpu, ram, temperatura, disco, gpu), más
      reciente primero (mismo formato que obtener_ultimas_lecturas()).
    - alertas: lista de mensajes de recomendaciones pendientes (opcional).
    - puntaje, color_puntaje, mensaje_puntaje y detalle_puntaje se mantienen
      por compatibilidad con quienes llaman a esta función, pero el informe
      ya no muestra el puntaje: lo que importa es el estado medido.
    """
    specs = specs or {}
    discos = discos or []
    lecturas = lecturas or []
    cpu = float(cpu or 0)
    ram = float(ram or 0)

    stats = {
        "cpu": _estadisticas([f[0] for f in lecturas]),
        "ram": _estadisticas([f[1] for f in lecturas]),
        "disco": _estadisticas([f[3] for f in lecturas]),
        "gpu": _estadisticas([f[4] for f in lecturas]),
        "temp": _estadisticas([f[2] for f in lecturas if f[2] is not None and f[2] > 0]),
    }
    temp_prom, temp_max = stats["temp"]
    ahora = datetime.now()

    pdf = _Informe(format="A4")
    pdf.alias_nb_pages()
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_title("PC Advisor - Informe técnico del equipo")
    pdf.set_creator("PC Advisor")
    pdf.add_page()

    # --- Título ---
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*AZUL_OSCURO)
    pdf.cell(0, 10, _t("Informe técnico del equipo"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*GRIS_TEXTO)
    pdf.cell(0, 6, _t(f"Fecha y hora del informe: {ahora.strftime('%d-%m-%Y %H:%M')}"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)

    # --- 1. Identificación del equipo ---
    _seccion(pdf, "Identificación del equipo")
    etiqueta = FontFace(emphasis="BOLD", color=GRIS_TEXTO)
    fabricante, modelo = specs.get("fabricante_equipo"), specs.get("modelo_equipo")
    filas = [
        ("Fabricante", fabricante if _valido(fabricante) else "No detectado (ver etiqueta del equipo)"),
        ("Modelo", modelo if _valido(modelo) else "No detectado (ver etiqueta del equipo)"),
        ("Sistema operativo", specs.get("so")),
        ("Procesador", specs.get("cpu_modelo")),
    ]
    if specs.get("nucleos") or specs.get("hilos"):
        filas.append(("Núcleos / hilos", f"{specs.get('nucleos') or '?'} núcleos / {specs.get('hilos') or '?'} hilos"))
    filas += [
        ("Memoria RAM", f"{specs.get('ram_total_gb')} GB" if specs.get("ram_total_gb") else None),
        ("Almacenamiento total", f"{specs.get('disco_total_gb')} GB" if specs.get("disco_total_gb") else None),
        ("Tarjeta gráfica", specs.get("gpu")),
        ("Placa madre", specs.get("placa_madre")),
        ("Versión de BIOS", specs.get("bios_version")),
    ]
    _tabla(pdf, (48, 132), [[(e, etiqueta), str(v)] for e, v in filas if _valido(v) or e in ("Fabricante", "Modelo")])

    # --- 2. Almacenamiento ---
    if discos:
        _seccion(pdf, "Unidades de almacenamiento")
        filas = []
        for d in discos:
            uso = d.get("uso")
            filas.append([
                str(d.get("unidad", "Disco")),
                str(d.get("sistema_archivos") or "-"),
                f"{d['total_gb']} GB" if d.get("total_gb") is not None else "N/D",
                f"{d['usado_gb']} GB" if d.get("usado_gb") is not None else "N/D",
                f"{d['libre_gb']} GB" if d.get("libre_gb") is not None else "N/D",
                _pct(uso),
                _celda_estado(_estado(uso, UMBRAL_DISCO, MARGEN_ATENCION_PCT)),
            ])
        _tabla(pdf, (26, 24, 26, 26, 26, 24, 28), filas,
               encabezados=["Unidad", "Formato", "Total", "Usado", "Libre", "Uso", "Estado"],
               alineacion=("LEFT", "LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "CENTER"))

    # --- 3. Estado de componentes ---
    _seccion(pdf, "Estado de los componentes")
    disco_actual = max((d.get("uso") for d in discos if d.get("uso") is not None), default=None)
    filas = [
        ["Procesador (CPU)", _pct(cpu), _pct(stats["cpu"][0]), _pct(stats["cpu"][1]),
         _celda_estado(_estado(cpu, UMBRAL_CPU, MARGEN_ATENCION_PCT))],
        ["Memoria RAM", _pct(ram), _pct(stats["ram"][0]), _pct(stats["ram"][1]),
         _celda_estado(_estado(ram, UMBRAL_RAM, MARGEN_ATENCION_PCT))],
        ["Tarjeta gráfica (GPU)", _pct(gpu), _pct(stats["gpu"][0]), _pct(stats["gpu"][1]),
         _celda_estado(_estado(gpu, UMBRAL_GPU, MARGEN_ATENCION_PCT))],
        ["Disco (unidad más usada)", _pct(disco_actual), _pct(stats["disco"][0]), _pct(stats["disco"][1]),
         _celda_estado(_estado(disco_actual, UMBRAL_DISCO, MARGEN_ATENCION_PCT))],
        ["Temperatura",
         "N/D" if temp_max is None else "-",
         "N/D" if temp_prom is None else f"{temp_prom:.0f} °C",
         "N/D" if temp_max is None else f"{temp_max:.0f} °C",
         _celda_estado(_estado(temp_max, UMBRAL_TEMP, MARGEN_ATENCION_TEMP))],
    ]
    _tabla(pdf, (52, 28, 32, 32, 36), filas,
           encabezados=["Componente", "Valor actual", "Promedio", "Máximo", "Estado"],
           alineacion=("LEFT", "RIGHT", "RIGHT", "RIGHT", "CENTER"))

    # --- 4. Hallazgos y mejoras ---
    _seccion(pdf, "Hallazgos y mejoras recomendadas")
    hallazgos = _hallazgos(specs, cpu, ram, gpu, discos, stats, temp_max, alertas)
    orden = {"Alta": 0, "Media": 1, "Baja": 2}
    hallazgos.sort(key=lambda x: orden.get(x[2], 3))
    if hallazgos:
        filas = [[str(i), hallazgo, mejora]
                 for i, (hallazgo, mejora, _prio) in enumerate(hallazgos, 1)]
    else:
        filas = [["1", "Sin hallazgos: los valores medidos están dentro de rangos normales.",
                  "No se requiere intervención por ahora. Mantener revisiones periódicas."]]
    _tabla(pdf, (10, 80, 90), filas,
           encabezados=["N°", "Hallazgo", "Mejora sugerida"],
           alineacion=("CENTER", "LEFT", "LEFT"))

    return bytes(pdf.output())
