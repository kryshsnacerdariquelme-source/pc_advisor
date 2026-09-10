import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "Backend"))

import streamlit as st
import plotly.graph_objects as go
from database import (
    crear_tabla,
    conectar,
    obtener_historial,
    obtener_alerta_pendiente_mas_reciente,
)
from hardware import specs_estaticas

try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=3000, key="pc_advisor_refresh")
except ImportError:
    pass

crear_tabla()
st.set_page_config(page_title="PC Advisor", page_icon="", layout="wide")

st.markdown("""
<style>
.stApp { background-color: #0D1321; color: #E8ECF2; }
div[data-testid="stMetric"] { background-color: #151D30; border: 1px solid #28324A; border-radius: 12px; padding: 12px 16px; }
.card { background-color: #151D30; border: 1px solid #28324A; border-radius: 12px; padding: 18px 20px; margin-bottom: 14px; }
.badge-alto { background-color: #4A1414; color: #EF4444; padding: 4px 12px; border-radius: 12px; font-weight: bold; font-size: 13px; }
.badge-ok { background-color: #14351C; color: #22C55E; padding: 4px 12px; border-radius: 12px; font-weight: bold; font-size: 13px; }
.term { border-bottom: 1px dotted #8B93A8; cursor: help; }
.mi-equipo-fila { display: flex; justify-content: space-between; font-size: 13px; padding: 3px 0; border-bottom: 1px solid #1D2740; }
.mi-equipo-fila span:first-child { color: #8B93A8; }
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
        ("Memoria RAM", f'{specs["ram_total_gb"]} GB' if specs["ram_total_gb"] else "No disponible"),
        ("Disco", f'{specs["disco_total_gb"]} GB' if specs["disco_total_gb"] else "No disponible"),
        ("Tarjeta gráfica", specs["gpu"]),
        ("Placa madre", specs["placa_madre"]),
    ]
    for etiqueta, valor in filas:
        st.markdown(
            f'<div class="mi-equipo-fila"><span>{etiqueta}</span><span>{valor}</span></div>',
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)


def cargar_datos():
    conn = conectar()
    ultima = conn.execute(
        "SELECT cpu, ram, temperatura, disco, gpu, fecha_hora FROM lecturas ORDER BY id DESC LIMIT 1"
    ).fetchone()
    filas = conn.execute(
        "SELECT cpu, ram, disco, gpu FROM lecturas ORDER BY id DESC LIMIT 40"
    ).fetchall()
    conn.close()
    return ultima, filas


def ir_a_guia(id_diagnostico):
    st.session_state["diagnostico_seleccionado"] = id_diagnostico
    st.switch_page(pagina_guia)


# ---------------------------------------------------------------------
# Página: Resumen
# ---------------------------------------------------------------------

def vista_resumen():
    st.title("💻 Estado de tu computador")
    st.caption("PC Advisor monitorea RAM, CPU, disco, temperatura y GPU")

    ultima, filas = cargar_datos()

    if not ultima:
        st.info("Todavía no hay lecturas. Ejecuta `Backend/monitor.py` y espera unos segundos.")
        return

    cpu, ram, temperatura, disco, gpu, fecha = ultima

    # --- Alerta visual dentro de la app (además de la notificación del SO) ---
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

    nivel_ram = "alto" if ram >= 85 else "normal"

    col_ram, col_otros = st.columns([1.1, 1])

    with col_ram:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        top_l, top_r = st.columns([2, 1])
        top_l.markdown(f"**{term('Memoria (RAM)', 'ram')} en uso**", unsafe_allow_html=True)
        badge_clave = "alto" if nivel_ram == "alto" else "normal"
        top_r.markdown(
            f'<span class="{"badge-alto" if nivel_ram == "alto" else "badge-ok"} term" title="{GLOSARIO[badge_clave]}">'
            f'{"ALTO" if nivel_ram == "alto" else "NORMAL"}</span>',
            unsafe_allow_html=True,
        )
        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=ram,
            number={'suffix': '%', 'font': {'color': '#EF4444' if nivel_ram == 'alto' else '#22C55E', 'size': 34}},
            gauge={'axis': {'range': [0, 100], 'visible': False},
                   'bar': {'color': '#EF4444' if nivel_ram == 'alto' else '#22C55E', 'thickness': 0.3},
                   'bgcolor': "#28324A", 'borderwidth': 0},
        ))
        fig.update_layout(height=160, margin=dict(l=10, r=10, t=10, b=10),
                           paper_bgcolor="rgba(0,0,0,0)", font={'color': "#E8ECF2"})
        st.plotly_chart(fig, config={'displayModeBar': False})
        st.caption(f"Última lectura: {fecha}")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_otros:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**Otros datos de apoyo**")
        c1, c2 = st.columns(2)
        c1.metric("Procesador (CPU)", f"{cpu:.0f}%", help=GLOSARIO["cpu"])
        temp_help = GLOSARIO["temperatura"]
        if not temperatura:
            temp_help += " Ahora mismo no se pudo leer el sensor de tu equipo; en Windows, abrir LibreHardwareMonitor en segundo plano suele solucionarlo."
        c2.metric("Temperatura", f"{temperatura:.0f} °C" if temperatura else "No disponible", help=temp_help)
        c3, c4 = st.columns(2)
        c3.metric("Disco", f"{disco:.0f}%" if disco is not None else "No disponible", help=GLOSARIO["disco"])
        gpu_help = GLOSARIO["gpu"]
        if gpu is None:
            gpu_help += " No se detectó una GPU NVIDIA con nvidia-smi disponible; en tarjetas AMD/Intel no hay una forma multiplataforma confiable de leer esto."
        c4.metric("GPU", f"{gpu:.0f}%" if gpu is not None else "No disponible", help=gpu_help)
        st.caption("Se usan solo para explicar la causa. La RAM es el dato principal.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Cómo se ha comportado tu equipo", help="Muestra las últimas lecturas de CPU, RAM, disco y GPU para ver si el uso alto fue algo puntual o se ha mantenido en el tiempo.")
    if filas:
        filas_r = list(reversed(filas))
        x = list(range(len(filas_r)))
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=x, y=[f[1] for f in filas_r], mode="lines", name="RAM", line=dict(color="#8B5CF6", width=3)))
        fig2.add_trace(go.Scatter(x=x, y=[f[0] for f in filas_r], mode="lines", name="CPU", line=dict(color="#3B82F6", width=2)))
        fig2.add_trace(go.Scatter(x=x, y=[f[2] for f in filas_r], mode="lines", name="Disco", line=dict(color="#F59E0B", width=2)))
        if any(f[3] is not None for f in filas_r):
            fig2.add_trace(go.Scatter(x=x, y=[f[3] for f in filas_r], mode="lines", name="GPU", line=dict(color="#22C55E", width=2)))
        fig2.update_layout(
            height=260, margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={"color": "#E8ECF2"},
            yaxis=dict(range=[0, 100], ticksuffix="%", gridcolor="#28324A"),
            xaxis=dict(showticklabels=False, gridcolor="#28324A"),
            legend=dict(orientation="h", y=1.15),
        )
        st.plotly_chart(fig2, config={"displayModeBar": False})
    else:
        st.caption("Aún no hay suficientes datos para el gráfico.")
    st.markdown('</div>', unsafe_allow_html=True)


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


pagina_resumen = st.Page(vista_resumen, title="Resumen", icon="", default=True)
pagina_historial = st.Page(vista_historial, title="Historial", icon="")
pagina_guia = st.Page(vista_guia, title="Guía solución", icon="")

pg = st.navigation([pagina_resumen, pagina_historial, pagina_guia])
with st.sidebar:
    render_mi_equipo()
pg.run()
