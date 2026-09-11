import json
import sys
import time
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

st.set_page_config(page_title="PC Advisor", page_icon="", layout="wide")

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

  
    # Fila principal solicitada: CPU, temperatura CPU, RAM y % real de GPU.
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("CPU", f"{cpu:.1f}%", help=GLOSARIO["cpu"])
    c2.metric("Temperatura CPU", f"{temperatura_cpu:.1f} °C" if temperatura_cpu else "No disponible", help=GLOSARIO["temperatura"])
    c3.metric("RAM", f"{ram:.1f}%", help=GLOSARIO["ram"])

    st.markdown("---")
    st.subheader(f"🎮 Tarjeta gráfica · {gpu_nombre}")
    g1, g2, g3 = st.columns(3)
    # Se elimina 'GPU identificada' de las métricas: el nombre queda como
    # información secundaria y la métrica principal es el % de uso real.
    g1.metric("Uso GPU", f"{gpu:.1f}%" if gpu is not None else "No disponible", help=GLOSARIO["gpu"])
    g2.metric("Temperatura GPU", f"{temperatura_gpu:.1f} °C" if temperatura_gpu else "No disponible")
    g3.metric("Temperatura VRAM", f"{temperatura_vram:.1f} °C" if temperatura_vram else "No disponible", help="Temperatura de memoria de la GPU cuando el hardware la expone.")
    st.markdown("---")


    st.subheader("💾 Discos detectados")
    if discos:
        columnas = st.columns(min(4, len(discos)))
        for i, d in enumerate(discos):
            with columnas[i % len(columnas)]:
                st.metric(d.get("unidad", "Disco"), f"{float(d.get('uso', 0)):.1f}% usado")
                st.caption(
                    f"{float(d.get('usado_gb', 0)):.1f} / {float(d.get('total_gb', 0)):.1f} GB"
                    + (f" · {float(d.get('temperatura', 0)):.1f} °C" if d.get("temperatura") else "")
                )
    else:
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
        st.plotly_chart(fig2, config={"displayModeBar": False}, use_container_width=True)
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
        st.plotly_chart(fig2, config={"displayModeBar": False}, use_container_width=True)
    else:
        st.caption("Esperando datos del monitor…")
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


pagina_resumen = st.Page(vista_resumen, title="Resumen", default=True)
pagina_historial = st.Page(vista_historial, title="Historial")
pagina_guia = st.Page(vista_guia, title="Guía solución")

pg = st.navigation([pagina_resumen, pagina_historial, pagina_guia])
with st.sidebar:
    render_mi_equipo()
pg.run()
