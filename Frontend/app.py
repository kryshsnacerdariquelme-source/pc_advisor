import json
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "Backend"))

import psutil
import streamlit as st
import plotly.graph_objects as go
from database import (
    crear_tabla,
    conectar,
    obtener_historial,
    obtener_alerta_pendiente_mas_reciente,
)
from hardware import specs_estaticas
from diagnostico import UMBRAL_CPU, UMBRAL_RAM, UMBRAL_TEMP

# Colores originales de PC Advisor: cada métrica ya tenía un color propio en
# el gráfico comparativo (línea 240 y siguientes). Se reutilizan aquí como
# "color de acento" de cada tarjeta para que todo el panel sea consistente.
COLOR_FONDO = "#0D1321"
COLOR_TARJETA = "#151D30"
COLOR_BORDE = "#28324A"
COLOR_TEXTO = "#E8ECF2"
COLOR_TEXTO_TENUE = "#8B93A8"
COLOR_TRACK_ANILLO = "#1D2740"
ACENTO_CPU = "#3B82F6"
ACENTO_RAM = "#8B5CF6"
ACENTO_DISCO = "#F59E0B"
ACENTO_GPU = "#22C55E"
COLOR_ZONA_LIMITE = "#EF4444"

# GPU y Disco todavía no generan una alerta automática en el Backend (solo
# CPU, RAM y temperatura lo hacen, ver diagnostico.py), así que para esas dos
# tarjetas se usa un nivel de referencia general en vez de un umbral oficial.
UMBRAL_GPU_REFERENCIA = 90
UMBRAL_DISCO_REFERENCIA = 90

# Explicación en lenguaje simple de qué significa cruzar la línea de límite
# en cada gráfico. Se muestra al pasar el mouse por encima de la franja.
EXPLICACION_LIMITE = {
    "cpu": f"Si pasa el {UMBRAL_CPU}% seguido por un rato: el procesador está trabajando al máximo casi todo el tiempo y el equipo puede sentirse lento o trabado.",
    "ram": f"Si pasa el {UMBRAL_RAM}% seguido por un rato: la memoria está casi llena y el equipo empieza a apoyarse en el disco (mucho más lento) para poder seguir funcionando.",
    "gpu": f"Si pasa el {UMBRAL_GPU_REFERENCIA}%: la tarjeta gráfica está trabajando al máximo. Es normal si estás jugando o editando video; si ocurre sin razón aparente, vale la pena revisarlo.",
    "disco": f"Si pasa el {UMBRAL_DISCO_REFERENCIA}%: el disco está casi lleno. Sin espacio libre, Windows no tiene dónde guardar archivos temporales y el equipo se puede volver lento.",
}

st.set_page_config(page_title="PC Advisor", page_icon="💻", layout="wide")

# Actualización automática nativa de Streamlit. Solo se vuelve a ejecutar
# el fragmento de la vista, evitando que el usuario tenga que recargar la página.
if hasattr(st, "fragment"):
    _vista_en_vivo = lambda **kwargs: st.fragment(**kwargs)
else:
    # Compatibilidad con versiones antiguas de Streamlit.
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=1000, key="pc_advisor_refresh_1s")
    except ImportError:
        _vista_en_vivo = lambda **kwargs: (lambda funcion: funcion)

if "_vista_en_vivo" not in globals():
    _vista_en_vivo = lambda **kwargs: (lambda funcion: funcion)

crear_tabla()

st.markdown(f"""
<style>
.stApp {{ background-color: {COLOR_FONDO}; color: {COLOR_TEXTO}; }}
div[data-testid="stMetric"] {{ background-color: {COLOR_TARJETA}; border: 1px solid {COLOR_BORDE}; border-radius: 12px; padding: 12px 16px; }}
.card {{ background-color: {COLOR_TARJETA}; border: 1px solid {COLOR_BORDE}; border-left: 4px solid {ACENTO_DISCO}; border-radius: 12px; padding: 18px 20px; margin-bottom: 14px; }}
.badge-alto {{ background-color: #4A1414; color: #EF4444; padding: 4px 12px; border-radius: 12px; font-weight: bold; font-size: 13px; }}
.badge-ok {{ background-color: #14351C; color: #22C55E; padding: 4px 12px; border-radius: 12px; font-weight: bold; font-size: 13px; }}
.term {{ border-bottom: 1px dotted {COLOR_TEXTO_TENUE}; cursor: help; }}
.mi-equipo-fila {{ display: flex; justify-content: space-between; font-size: 13px; padding: 3px 0; border-bottom: 1px solid {COLOR_TRACK_ANILLO}; }}
.mi-equipo-fila span:first-child {{ color: {COLOR_TEXTO_TENUE}; }}

/* --- Tarjetas de métrica estilo "monitor de sistema" --- */
div[class*="st-key-tarjeta_"] {{
    background-color: {COLOR_TARJETA};
    border: 1px solid {COLOR_BORDE};
    border-left: 5px solid transparent;
    border-radius: 12px;
    padding: 14px 18px 4px 18px;
    margin-bottom: 16px;
}}
div[class*="st-key-tarjeta_cpu"] {{ border-left-color: {ACENTO_CPU}; }}
div[class*="st-key-tarjeta_ram"] {{ border-left-color: {ACENTO_RAM}; }}
div[class*="st-key-tarjeta_gpu"] {{ border-left-color: {ACENTO_GPU}; }}
div[class*="st-key-tarjeta_disco"] {{ border-left-color: {ACENTO_DISCO}; }}

.tarjeta-header {{ display: flex; align-items: baseline; gap: 10px; margin-bottom: 4px; flex-wrap: wrap; }}
.tarjeta-icono {{ font-size: 20px; }}
.tarjeta-titulo {{ font-weight: 700; font-size: 15px; }}
.tarjeta-modelo {{ color: {COLOR_TEXTO_TENUE}; font-size: 13px; }}
.mini-label {{ text-align: center; color: {COLOR_TEXTO_TENUE}; font-size: 11px; margin-top: -14px; }}
.stat-fila {{ display: flex; justify-content: space-between; gap: 10px; font-size: 13px; padding: 3px 0; border-bottom: 1px dashed {COLOR_TRACK_ANILLO}; }}
.stat-fila:last-child {{ border-bottom: none; }}
.stat-fila span:first-child {{ color: {COLOR_TEXTO_TENUE}; }}
.stat-fila strong {{ font-weight: 600; }}
.disco-chip {{ display: flex; justify-content: space-between; align-items: center; background-color: {COLOR_TRACK_ANILLO}; border-radius: 10px; padding: 8px 14px; margin-bottom: 8px; font-size: 13px; }}
.disco-chip span:first-child {{ font-weight: 600; }}
.disco-chip span:last-child {{ color: {COLOR_TEXTO_TENUE}; }}
</style>
""", unsafe_allow_html=True)

# Diccionario con las explicaciones que aparecen al pasar el mouse sobre
# cada término técnico (tooltips).
GLOSARIO = {
    "cpu": "CPU (procesador): ejecuta las instrucciones de tus programas. Un uso alto y sostenido significa que hay procesos exigiendo mucho trabajo al mismo tiempo.",
    "ram": "RAM (memoria): guarda temporalmente los datos que tus programas están usando en este momento. Si se satura, el equipo se vuelve lento porque empieza a apoyarse en el disco, que es mucho más lento.",
    "temperatura": "Temperatura del procesador: sobre los 80°C sostenidos el equipo puede bajar su rendimiento a propósito para protegerse (throttling), o acortar la vida útil del hardware con el tiempo.",
    "disco": "Disco (almacenamiento): cuánto espacio ocupado tiene tu disco. Si está casi lleno, Windows no tiene espacio para archivos temporales y el equipo se puede volver lento aunque la RAM esté bien.",
    "gpu": "GPU (tarjeta gráfica): procesa gráficos y video. Un uso alto es normal jugando o editando video; si sube sin razón aparente puede valer la pena revisarlo.",
    "alto": "ALTO: el valor superó el umbral que se considera riesgoso (85% de uso de RAM).",
    "normal": "NORMAL: el uso está dentro de un rango saludable para el equipo.",
}


def term(texto, clave):
    """Envuelve un texto en un <span> con tooltip nativo del navegador
    (aparece al posicionar el mouse encima), usando la explicación
    definida en GLOSARIO."""
    return f'<span class="term" title="{GLOSARIO[clave]}">{texto}</span>'


@st.cache_data(show_spinner=False)
def _specs_equipo_cacheadas():
    """Las specs fijas (SO, CPU, placa madre, etc.) no cambian mientras
    la app está corriendo, así que se consultan una sola vez por sesión
    en vez de en cada actualización automática."""
    return specs_estaticas()


def render_mi_equipo():
    """Panel fijo en la barra lateral con los datos estáticos del equipo,
    igual al de 'Mi Equipo' del prototipo."""
    specs = _specs_equipo_cacheadas()
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("**💻 Mi Equipo**")
    filas = [
        ("Sistema operativo", specs["so"]),
        ("Procesador", specs["cpu_modelo"]),
        ("Memoria RAM", f'{specs["ram_total_gb"]} GB' if specs["ram_total_gb"] else None),
        ("Disco", f'{specs["disco_total_gb"]} GB' if specs["disco_total_gb"] else None),
        ("Tarjeta gráfica", specs["gpu"]),
        ("Placa madre", specs["placa_madre"]),
    ]
    # Solo se listan los datos que el equipo entrego realmente.
    filas = [(e, v) for e, v in filas if v and str(v).strip().lower() not in ("none", "no disponible")]
    for etiqueta, valor in filas:
        st.markdown(
            f'<div class="mi-equipo-fila"><span>{etiqueta}</span><span>{valor}</span></div>',
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)


def cargar_datos():
    """Lee el estado vivo escrito por Backend/monitor.py.

    SQLite se usa solo como historial; así el resumen no queda limitado por
    el intervalo de guardado de la base de datos.
    """
    estado_path = Path(__file__).resolve().parent.parent / "data" / "estado_actual.json"
    estado = None
    try:
        with estado_path.open("r", encoding="utf-8") as archivo:
            estado = json.load(archivo)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        estado = None

    conn = conectar()
    filas = conn.execute(
        "SELECT cpu, ram, disco, gpu FROM lecturas ORDER BY id DESC LIMIT 40"
    ).fetchall()
    conn.close()
    return estado, filas


def _grafico_anillo(valor_pct, color):
    """Anillo de progreso (como el % circular de la imagen de referencia)."""
    valor_pct = max(0.0, min(100.0, float(valor_pct or 0)))
    fig = go.Figure(go.Pie(
        values=[valor_pct, 100 - valor_pct],
        hole=0.72,
        sort=False,
        direction="clockwise",
        rotation=270,
        marker=dict(colors=[color, COLOR_TRACK_ANILLO], line=dict(width=0)),
        textinfo="none",
        hoverinfo="skip",
    ))
    fig.update_layout(
        showlegend=False,
        margin=dict(l=0, r=0, t=0, b=0),
        height=118,
        paper_bgcolor="rgba(0,0,0,0)",
        annotations=[dict(
            text=f"<b>{valor_pct:.0f}%</b>", x=0.5, y=0.5, showarrow=False,
            font=dict(size=22, color=COLOR_TEXTO),
        )],
    )
    return fig


def _grafico_barras_mini(serie, color, umbral=None):
    """Mini barras tipo ecualizador con las últimas lecturas."""
    valores = [float(v) for v in (serie or [])][-8:]
    if not valores:
        valores = [0]
    fig = go.Figure(go.Bar(
        x=list(range(len(valores))), y=valores,
        marker_color=color, marker_line_width=0,
        hoverinfo="skip",
    ))
    if umbral is not None and len(valores) > 1:
        fig.add_hrect(y0=umbral, y1=100, fillcolor=COLOR_ZONA_LIMITE, opacity=0.12, line_width=0)
    fig.update_layout(
        height=70, margin=dict(l=0, r=0, t=6, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False), yaxis=dict(visible=False, range=[0, 100]),
        bargap=0.35,
    )
    return fig


def _grafico_sparkline(serie, color, umbral=None):
    """Línea de tendencia (últimos segundos) rellena, estilo mini-gráfico.

    Si se indica un umbral, se dibuja una franja roja sobre ese nivel (la
    "zona mala") con una línea punteada en el borde. La explicación de qué
    significa esa franja se muestra aparte, en el textito de abajo (⚠️).
    """
    valores = [float(v) for v in (serie or [])]
    if not valores:
        valores = [0]
    fig = go.Figure(go.Scatter(
        y=valores, mode="lines", line=dict(color=color, width=2),
        fill="tozeroy", fillcolor=color + "33", hoverinfo="skip",
    ))
    if umbral is not None:
        n = max(len(valores), 2)
        fig.add_hrect(y0=umbral, y1=100, fillcolor=COLOR_ZONA_LIMITE, opacity=0.12, line_width=0)
        # Solo la franja + la línea punteada, sin globo de texto al pasar el
        # mouse por encima: la explicación vive únicamente en el textito
        # de abajo (⚠️) para no tapar el gráfico con un recuadro.
        fig.add_trace(go.Scatter(
            x=list(range(n)), y=[umbral] * n, mode="lines",
            line=dict(color=COLOR_ZONA_LIMITE, width=1.5, dash="dot"),
            hoverinfo="skip", name="Límite", showlegend=False,
        ))
    fig.update_layout(
        height=70, margin=dict(l=0, r=0, t=6, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False), yaxis=dict(visible=False, range=[0, 100]),
    )
    return fig


def render_tarjeta_metrica(key, icono, categoria, modelo, valor_pct, color, serie, stats, clave_glosario=None, umbral=None):
    """Tarjeta completa de una métrica: anillo + mini-barras + sparkline + datos,
    mezclando la disposición de la imagen de referencia con los colores y el
    lenguaje simple (tooltips) que ya tenía PC Advisor."""
    texto_umbral = EXPLICACION_LIMITE.get(clave_glosario) if clave_glosario else None
    with st.container(key=key):
        etiqueta_modelo = f'<span class="tarjeta-modelo">{modelo}</span>' if modelo else ""
        st.markdown(
            f'<div class="tarjeta-header"><span class="tarjeta-titulo">{categoria}</span>{etiqueta_modelo}</div>',
            unsafe_allow_html=True,
        )
        col_anillo, col_barras, col_spark, col_datos = st.columns([1.1, 1.2, 1.5, 1.7])
        with col_anillo:
            st.plotly_chart(_grafico_anillo(valor_pct, color), config={"displayModeBar": False}, width="stretch")
            etiqueta = f"USO {categoria.upper()}"
            if clave_glosario:
                st.markdown(f'<div class="mini-label">{term(etiqueta, clave_glosario)}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="mini-label">{etiqueta}</div>', unsafe_allow_html=True)
        with col_barras:
            st.plotly_chart(_grafico_barras_mini(serie, color, umbral=umbral), config={"displayModeBar": False}, width="stretch")
        with col_spark:
            st.plotly_chart(
                _grafico_sparkline(serie, color, umbral=umbral),
                config={"displayModeBar": False}, width="stretch",
            )
            if umbral is not None:
                st.markdown(
                    f'<div class="mini-label">⚠️ <span class="term" title="{texto_umbral}">franja roja = zona de riesgo, pasa el mouse por la línea punteada</span></div>',
                    unsafe_allow_html=True,
                )
        with col_datos:
            for etiqueta_dato, valor_dato, clave_dato in stats:
                texto_etiqueta = term(etiqueta_dato, clave_dato) if clave_dato else etiqueta_dato
                st.markdown(
                    f'<div class="stat-fila"><span>{texto_etiqueta}</span><strong>{valor_dato}</strong></div>',
                    unsafe_allow_html=True,
                )


def ir_a_guia(id_diagnostico):
    st.session_state["diagnostico_seleccionado"] = id_diagnostico
    st.switch_page(pagina_guia)


# ---------------------------------------------------------------------
# Página: Resumen
# ---------------------------------------------------------------------

@_vista_en_vivo(run_every="1s")
def vista_resumen():
    st.title("💻 Estado de tu computador")

    estado, filas = cargar_datos()

    if not estado:
        st.info("Todavía no hay lecturas. Ejecuta `Backend/monitor.py` y espera unos segundos.")
        return

    # El timestamp viene del backend y permite saber que la pantalla está
    # mostrando una lectura nueva, no una copia de SQLite.
    timestamp = float(estado.get("timestamp", 0) or 0)
    actualizado = time.strftime("%H:%M:%S", time.localtime(timestamp)) if timestamp else "--:--:--"
    edad_lectura = max(0, time.time() - timestamp) if timestamp else None
    historial_vivo = estado.get("historial_vivo", []) or []

    cpu = float(estado.get("cpu", 0) or 0)
    ram = float(estado.get("ram", 0) or 0)
    temperatura_cpu = float(estado.get("temperatura_cpu", 0) or 0)
    gpu = estado.get("gpu")
    gpu = float(gpu) if gpu is not None else None
    gpu_nombre = estado.get("gpu_nombre", "No detectada")
    temperatura_gpu = float(estado.get("temperatura_gpu", 0) or 0)
    temperatura_vram = float(estado.get("temperatura_vram", 0) or 0)
    discos = estado.get("discos", []) or []

    if edad_lectura is not None and edad_lectura <= 3:
        st.caption(f"🟢 En vivo · última lectura {actualizado}")
    else:
        st.warning(f"⚠️ Lectura desactualizada · última lectura {actualizado}. Verifica que Backend/monitor.py esté ejecutándose.")

    alerta = obtener_alerta_pendiente_mas_reciente()
    if alerta:
        id_alerta, fecha_alerta, tipo_alerta, mensaje_alerta, guia_alerta = alerta
        if st.session_state.get("alerta_descartada") != id_alerta:
            with st.container(border=True):
                col_msg, col_ver, col_cerrar = st.columns([5, 2, 1])
                col_msg.markdown(f"🔔 **PC Advisor** — {mensaje_alerta}")
                if col_ver.button("Ver qué puedo hacer", key=f"ver_{id_alerta}", width="stretch"):
                    ir_a_guia(id_alerta)
                if col_cerrar.button("Ahora no", key=f"cerrar_{id_alerta}", width="stretch"):
                    st.session_state["alerta_descartada"] = id_alerta
                    st.rerun()

    # Series para las mini-barras y el sparkline de cada tarjeta: se usan las
    # mismas lecturas del historial en vivo que ya alimentaban el gráfico
    # comparativo, solo que ahora cada métrica tiene su propia mini-vista.
    serie_cpu = [float(p.get("cpu", 0) or 0) for p in historial_vivo]
    serie_ram = [float(p.get("ram", 0) or 0) for p in historial_vivo]
    serie_disco = [float(p.get("disco", 0) or 0) for p in historial_vivo]
    serie_gpu = [float(p.get("gpu", 0) or 0) for p in historial_vivo if p.get("gpu") is not None]

    specs = _specs_equipo_cacheadas()

    # --- Tarjeta CPU ---
    stats_cpu = []
    if temperatura_cpu:
        stats_cpu.append(("Temp. CPU", f"{temperatura_cpu:.0f} °C", "temperatura"))
    try:
        hilos = psutil.cpu_count(logical=True)
        nucleos = psutil.cpu_count(logical=False)
        if hilos:
            etiqueta_hilos = f"{nucleos} núcleos / {hilos} hilos" if nucleos and nucleos != hilos else f"{hilos}"
            stats_cpu.append(("Núcleos / hilos", etiqueta_hilos, None))
    except Exception:
        pass
    try:
        frecuencia = psutil.cpu_freq()
        if frecuencia and frecuencia.current:
            stats_cpu.append(("Frecuencia actual", f"{frecuencia.current / 1000:.2f} GHz", None))
    except Exception:
        pass
    render_tarjeta_metrica(
        key="tarjeta_cpu", icono="🧠", categoria="CPU", modelo=specs.get("cpu_modelo"),
        valor_pct=cpu, color=ACENTO_CPU, serie=serie_cpu, stats=stats_cpu, clave_glosario="cpu",
        umbral=UMBRAL_CPU,
    )
    if not temperatura_cpu:
        st.caption(
            "ℹ️ La temperatura del CPU no está disponible. Windows no la expone "
            "directamente: para verla, instala y deja abierto "
            "[Libre Hardware Monitor](https://librehardwaremonitor.org) "
            "(ejecutándolo como administrador)."
        )

    # --- Tarjeta RAM ---
    ram_total_gb = specs.get("ram_total_gb")
    stats_ram = []
    if ram_total_gb:
        stats_ram.append(("En uso", f"{ram_total_gb * ram / 100:.1f} / {ram_total_gb:.1f} GB", None))
    else:
        stats_ram.append(("Uso actual", f"{ram:.1f}%", None))
    render_tarjeta_metrica(
        key="tarjeta_ram", icono="🧩", categoria="RAM", modelo=None,
        valor_pct=ram, color=ACENTO_RAM, serie=serie_ram, stats=stats_ram, clave_glosario="ram",
        umbral=UMBRAL_RAM,
    )

    # --- Tarjeta GPU ---
    if gpu is not None:
        stats_gpu = []
        if temperatura_gpu:
            stats_gpu.append(("Temp. GPU", f"{temperatura_gpu:.0f} °C", None))
        if temperatura_vram:
            stats_gpu.append(("Temp. VRAM", f"{temperatura_vram:.0f} °C",
                               "Temperatura de memoria de la GPU cuando el hardware la expone."))
        render_tarjeta_metrica(
            key="tarjeta_gpu", icono="🎮", categoria="GPU", modelo=gpu_nombre,
            valor_pct=gpu, color=ACENTO_GPU, serie=serie_gpu, stats=stats_gpu, clave_glosario="gpu",
            umbral=UMBRAL_GPU_REFERENCIA,
        )
    else:
        st.caption(f"🎮 Tarjeta gráfica · {gpu_nombre} — no se pudieron leer datos de uso en este momento.")

    # --- Tarjeta Disco principal ---
    disco_principal = float(estado.get("disco", 0) or 0)
    stats_disco = []
    if specs.get("disco_total_gb"):
        stats_disco.append(("Capacidad total", f"{specs['disco_total_gb']:.0f} GB", None))
    render_tarjeta_metrica(
        key="tarjeta_disco", icono="💾", categoria="Disco", modelo="Unidad principal",
        valor_pct=disco_principal, color=ACENTO_DISCO, serie=serie_disco, stats=stats_disco, clave_glosario="disco",
        umbral=UMBRAL_DISCO_REFERENCIA,
    )

    # Otras unidades montadas: sin historial propio, se listan como filas
    # compactas debajo de la tarjeta de disco principal.
    if len(discos) > 1:
        st.caption("Otras unidades detectadas")
        for d in discos:
            temp_txt = f" · {float(d.get('temperatura', 0)):.0f} °C" if d.get("temperatura") else ""
            st.markdown(
                f'<div class="disco-chip"><span>{d.get("unidad", "Disco")}</span>'
                f'<span>{float(d.get("usado_gb", 0)):.1f} / {float(d.get("total_gb", 0)):.1f} GB '
                f'· {float(d.get("uso", 0)):.0f}% usado{temp_txt}</span></div>',
                unsafe_allow_html=True,
            )
    elif not discos:
        st.caption("No se detectaron unidades montadas.")

    st.markdown("---")
    st.subheader("Cómo se ha comportado tu equipo · últimos 60 segundos")
    if historial_vivo:
        datos_grafico = list(historial_vivo)
        x = [time.strftime("%H:%M:%S", time.localtime(float(p.get("timestamp", 0)))) for p in datos_grafico]
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=x, y=[float(p.get("ram", 0) or 0) for p in datos_grafico], mode="lines", name="RAM", line=dict(color="#8B5CF6", width=3)))
        fig2.add_trace(go.Scatter(x=x, y=[float(p.get("cpu", 0) or 0) for p in datos_grafico], mode="lines", name="CPU", line=dict(color="#3B82F6", width=2)))
        fig2.add_trace(go.Scatter(x=x, y=[float(p.get("disco", 0) or 0) for p in datos_grafico], mode="lines", name="Disco", line=dict(color="#F59E0B", width=2)))
        if any(p.get("gpu") is not None for p in datos_grafico):
            fig2.add_trace(go.Scatter(x=x, y=[float(p.get("gpu", 0) or 0) if p.get("gpu") is not None else None for p in datos_grafico], mode="lines", name="GPU", line=dict(color="#22C55E", width=2)))
        fig2.update_layout(
            height=260, margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={"color": "#E8ECF2"},
            yaxis=dict(range=[0, 100], ticksuffix="%", gridcolor="#28324A"),
            xaxis=dict(showticklabels=True, gridcolor="#28324A", nticks=8),
            legend=dict(orientation="h", y=1.15),
        )
        st.plotly_chart(fig2, config={"displayModeBar": False, "responsive": True}, width="stretch")
    elif filas:
        # Compatibilidad con estados generados por una versión anterior del monitor.
        filas_r = list(reversed(filas))
        x = list(range(len(filas_r)))
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=x, y=[f[1] for f in filas_r], mode="lines", name="RAM"))
        fig2.add_trace(go.Scatter(x=x, y=[f[0] for f in filas_r], mode="lines", name="CPU"))
        fig2.add_trace(go.Scatter(x=x, y=[f[2] for f in filas_r], mode="lines", name="Disco"))
        if any(f[3] is not None for f in filas_r):
            fig2.add_trace(go.Scatter(x=x, y=[f[3] for f in filas_r], mode="lines", name="GPU"))
        fig2.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(range=[0, 100], ticksuffix="%"))
        st.plotly_chart(fig2, config={"displayModeBar": False, "responsive": True}, width="stretch")
    else:
        st.caption("Esperando datos del monitor…")


# ---------------------------------------------------------------------
# Página: Historial
# ---------------------------------------------------------------------

def vista_historial():
    st.title("🗂️ Historial")
    st.caption("Diagnósticos y alertas generadas a partir de tus lecturas (RF-04 / RF-16)")

    historial = obtener_historial(limite=15)
    if not historial:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.caption("Todavía no se ha generado ninguna recomendación.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    for id_h, fecha_h, tipo, mensaje, guia, estado in historial:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        col_txt, col_btn = st.columns([4, 1])
        emoji = "🟡" if estado == "pendiente" else "🟢"
        col_txt.markdown(f"{emoji} **{mensaje}**")
        col_txt.caption(fecha_h)
        if col_btn.button("Guía de solución", key=f"guia_{id_h}", width="stretch"):
            ir_a_guia(id_h)
        st.markdown('</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------
# Página: Guía de solución
# ---------------------------------------------------------------------

def vista_guia():
    st.title("✅ Guía de solución")

    id_seleccionado = st.session_state.get("diagnostico_seleccionado")
    conn = conectar()
    if id_seleccionado:
        fila = conn.execute(
            "SELECT tipo_diagnostico, mensaje, guia_solucion, estado FROM historial_recomendaciones WHERE id = ?",
            (id_seleccionado,),
        ).fetchone()
    else:
        fila = conn.execute(
            "SELECT tipo_diagnostico, mensaje, guia_solucion, estado FROM historial_recomendaciones ORDER BY id DESC LIMIT 1"
        ).fetchone()
    conn.close()

    if not fila:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.caption("Todavía no hay ningún diagnóstico generado. Cuando aparezca una alerta, su guía se mostrará acá.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    tipo, mensaje, guia, estado = fila
    st.markdown('<div class="card">', unsafe_allow_html=True)
    col_msg, col_badge = st.columns([4, 1])
    col_msg.markdown(f"### {mensaje}")
    col_badge.markdown(
        f'<span class="{"badge-alto" if estado == "pendiente" else "badge-ok"}">'
        f'{"PENDIENTE" if estado == "pendiente" else "RESUELTO"}</span>',
        unsafe_allow_html=True,
    )
    st.markdown("**Cómo solucionarlo:**")
    for linea in guia.split("\n"):
        st.write(linea)
    st.markdown('</div>', unsafe_allow_html=True)


pagina_resumen = st.Page(vista_resumen, title="Resumen", icon="🏠", default=True)
pagina_historial = st.Page(vista_historial, title="Historial", icon="🗂️")
pagina_guia = st.Page(vista_guia, title="Guía solución", icon="✅")

pg = st.navigation([pagina_resumen, pagina_historial, pagina_guia])
with st.sidebar:
    render_mi_equipo()
pg.run()
