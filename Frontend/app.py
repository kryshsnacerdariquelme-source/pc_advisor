import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "Backend"))

import streamlit as st
import plotly.graph_objects as go
from database import crear_tabla, conectar, obtener_historial

try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=3000, key="pc_advisor_refresh")
except ImportError:
    pass

crear_tabla()
st.set_page_config(page_title="PC Advisor", page_icon="💻", layout="wide")

st.markdown("""
<style>
.stApp { background-color: #0D1321; color: #E8ECF2; }
div[data-testid="stMetric"] { background-color: #151D30; border: 1px solid #28324A; border-radius: 12px; padding: 12px 16px; }
.card { background-color: #151D30; border: 1px solid #28324A; border-radius: 12px; padding: 18px 20px; margin-bottom: 14px; }
.badge-alto { background-color: #4A1414; color: #EF4444; padding: 4px 12px; border-radius: 12px; font-weight: bold; font-size: 13px; }
.badge-ok { background-color: #14351C; color: #22C55E; padding: 4px 12px; border-radius: 12px; font-weight: bold; font-size: 13px; }
</style>
""", unsafe_allow_html=True)

st.title("💻 Estado de tu computador")
st.caption("PC Advisor monitorea RAM, CPU y temperatura")

conn = conectar()
ultima = conn.execute(
    "SELECT cpu, ram, temperatura, fecha_hora FROM lecturas ORDER BY id DESC LIMIT 1"
).fetchone()
filas = conn.execute(
    "SELECT cpu, ram FROM lecturas ORDER BY id DESC LIMIT 40"
).fetchall()
conn.close()

if not ultima:
    st.info("Todavía no hay lecturas. Ejecuta `Backend/monitor.py` y espera unos segundos.")
    st.stop()

cpu, ram, temperatura, fecha = ultima
nivel_ram = "alto" if ram >= 85 else "normal"

col_ram, col_otros = st.columns([1.1, 1])

with col_ram:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    top_l, top_r = st.columns([2, 1])
    top_l.markdown("**Memoria (RAM) en uso**")
    top_r.markdown(
        f'<span class="{"badge-alto" if nivel_ram == "alto" else "badge-ok"}">{"ALTO" if nivel_ram == "alto" else "NORMAL"}</span>',
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
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    st.caption(f"Última lectura: {fecha}")
    st.markdown('</div>', unsafe_allow_html=True)

with col_otros:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("**Otros datos de apoyo**")
    c1, c2 = st.columns(2)
    c1.metric("Procesador (CPU)", f"{cpu:.0f}%")
    c2.metric("Temperatura", f"{temperatura:.0f} °C" if temperatura else "No disponible")
    st.caption("Se usan solo para explicar la causa. La RAM es el dato principal.")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card">', unsafe_allow_html=True)
st.subheader("Cómo se ha comportado tu equipo")
if filas:
    filas_r = list(reversed(filas))
    x = list(range(len(filas_r)))
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=x, y=[f[1] for f in filas_r], mode="lines", name="RAM", line=dict(color="#8B5CF6", width=3)))
    fig2.add_trace(go.Scatter(x=x, y=[f[0] for f in filas_r], mode="lines", name="CPU", line=dict(color="#3B82F6", width=2)))
    fig2.update_layout(
        height=260, margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={"color": "#E8ECF2"},
        yaxis=dict(range=[0, 100], ticksuffix="%", gridcolor="#28324A"),
        xaxis=dict(showticklabels=False, gridcolor="#28324A"),
        legend=dict(orientation="h", y=1.15),
    )
    st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
else:
    st.caption("Aún no hay suficientes datos para el gráfico.")
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card">', unsafe_allow_html=True)
st.subheader("Historial de recomendaciones")
historial = obtener_historial(limite=10)
if not historial:
    st.caption("Todavía no se ha generado ninguna recomendación.")
else:
    for fecha_h, tipo, mensaje, guia, estado in historial:
        emoji = "🟡" if estado == "pendiente" else "🟢"
        with st.expander(f"{emoji} {mensaje[:70]}...  —  {fecha_h}"):
            st.write(mensaje)
            st.markdown("**Cómo solucionarlo:**")
            st.text(guia)
st.markdown('</div>', unsafe_allow_html=True)
