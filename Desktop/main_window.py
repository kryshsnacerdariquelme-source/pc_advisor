import json
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QPixmap, QIcon
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QGridLayout, QStackedWidget, QScrollArea, QMessageBox, QSizePolicy
)

ROOT = Path(__file__).resolve().parent.parent
def ruta_logo():
    base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else ROOT
    return base / "assets" / "logo.png"

LOGO_PATH = ruta_logo()
BACKEND = ROOT / "Backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from Desktop.hardware_reader import read_state, read_specs
from database import obtener_historial, conectar, obtener_alerta_pendiente_mas_reciente

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

UMBRAL_GPU = 90
UMBRAL_DISCO = 90

GLOSARIO = {
    "cpu": "CPU (procesador): ejecuta las instrucciones de tus programas. Un uso alto y sostenido significa que hay procesos exigiendo mucho trabajo al mismo tiempo.",
    "ram": "RAM (memoria): guarda temporalmente los datos que tus programas están usando. Si se satura, el equipo empieza a apoyarse en el disco.",
    "gpu": "GPU (tarjeta gráfica): procesa gráficos y video. Un uso alto es normal jugando o editando video; si sube sin razón aparente, vale la pena revisarlo.",
    "disco": "Disco (almacenamiento): cuánto espacio está ocupado. Si está casi lleno, Windows tiene menos espacio para archivos temporales.",
}


def estado_uso(valor, umbral=90):
    valor = float(valor or 0)
    if valor >= umbral:
        return "Muy alto", COLOR_ROJO
    if valor >= 70:
        return "Alto", "#F59E0B"
    return "Normal", COLOR_VERDE


def temperatura_estado(valor):
    valor = float(valor or 0)
    if valor >= 90:
        return "Muy alta", COLOR_ROJO
    if valor >= 80:
        return "Elevada", "#F59E0B"
    return "Normal", COLOR_VERDE


class RingWidget(QWidget):
    def __init__(self, color):
        super().__init__()
        self.value = 0.0
        self.color = color
        self.setMinimumSize(120, 120)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def set_value(self, value):
        self.value = max(0.0, min(100.0, float(value or 0)))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = min(self.width(), self.height()) - 14
        rect = QRectF((self.width()-r)/2, (self.height()-r)/2, r, r)
        pen = QPen(QColor(COLOR_TRACK), 11)
        p.setPen(pen)
        p.drawArc(rect, 0, 360*16)
        pen.setColor(QColor(self.color))
        p.setPen(pen)
        p.drawArc(rect, 90*16, int(-360*16*self.value/100))
        p.setPen(QColor(COLOR_TEXTO))
        p.setFont(QFont("Segoe UI", 20, QFont.Bold))
        p.drawText(rect, Qt.AlignCenter, f"{self.value:.0f}%")


class Sparkline(QWidget):
    def __init__(self, color, threshold=None):
        super().__init__()
        self.values = []
        self.color = color
        self.threshold = threshold
        self.setMinimumHeight(80)

    def set_values(self, values):
        self.values = [max(0.0, min(100.0, float(v or 0))) for v in values[-60:]]
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(COLOR_TARJETA))
        if self.threshold is not None:
            y = h - (self.threshold / 100) * h
            pen = QPen(QColor(COLOR_ROJO), 1, Qt.DashLine)
            p.setPen(pen)
            p.drawLine(0, int(y), w, int(y))
        if len(self.values) < 2:
            return
        pen = QPen(QColor(self.color), 2)
        p.setPen(pen)
        pts = []
        for i, v in enumerate(self.values):
            x = i * (w-4) / max(1, len(self.values)-1) + 2
            y = h - (v / 100) * (h-6) - 3
            pts.append(QPointF(x, y))
        for a, b in zip(pts, pts[1:]):
            p.drawLine(a, b)


class MetricCard(QFrame):
    def __init__(self, title, model, color, glossary_key, threshold):
        super().__init__()
        self.setObjectName("metricCard")
        self.setProperty("accent", color)
        self.title = QLabel(title)
        self.title.setObjectName("cardTitle")
        self.model = QLabel(model or "")
        self.model.setObjectName("cardModel")
        self.ring = RingWidget(color)
        self.chart = Sparkline(color, threshold)
        self.usage_label = QLabel(f"USO {title.upper()}")
        self.usage_label.setObjectName("miniLabel")
        self.status = QLabel("Normal")
        self.status.setObjectName("statusLabel")
        self.stats = QVBoxLayout()
        self.stats.setSpacing(3)

        header = QHBoxLayout()
        header.addWidget(self.title)
        header.addWidget(self.model)
        header.addStretch()

        left = QVBoxLayout()
        left.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        left.addWidget(self.ring, 0, Qt.AlignHCenter)
        left.addWidget(self.usage_label, 0, Qt.AlignHCenter)

        middle = QVBoxLayout()
        middle.addWidget(self.chart)
        middle.addWidget(self.status)

        body = QHBoxLayout()
        body.addLayout(left)
        body.addLayout(middle, 1)
        body.addLayout(self.stats, 1)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 12, 18, 12)
        root.addLayout(header)
        root.addLayout(body)

        self.setToolTip(GLOSARIO.get(glossary_key, ""))

    def update_card(self, value, series, stats):
        self.ring.set_value(value)
        self.chart.set_values(series)
        text, color = estado_uso(value, self.chart.threshold or 90)
        self.status.setText(text)
        self.status.setStyleSheet(f"color:{color}; font-weight:600;")
        while self.stats.count():
            item = self.stats.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for label, value_text in stats:
            row = QWidget()
            lay = QHBoxLayout(row)
            lay.setContentsMargins(0, 0, 0, 0)
            a = QLabel(label)
            a.setObjectName("statLabel")
            b = QLabel(value_text)
            b.setObjectName("statValue")
            b.setAlignment(Qt.AlignRight)
            lay.addWidget(a)
            lay.addWidget(b)
            self.stats.addWidget(row)


class TempCard(QFrame):
    def __init__(self, title):
        super().__init__()
        self.setObjectName("tempCard")
        self.title = QLabel(title)
        self.title.setObjectName("tempTitle")
        self.value = QLabel("-- °C")
        self.value.setObjectName("tempValue")
        self.status = QLabel("Esperando datos")
        self.status.setObjectName("statusLabel")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.addWidget(self.title)
        lay.addWidget(self.value)
        lay.addWidget(self.status)

    def set_value(self, value):
        if not value:
            self.value.setText("No disponible")
            self.status.setText("Sin lectura")
            return
        self.value.setText(f"{value:.0f} °C")
        text, color = temperatura_estado(value)
        self.status.setText(text)
        self.status.setStyleSheet(f"color:{color}; font-weight:600;")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PC Advisor")
        self.resize(1400, 850)
        self.setMinimumSize(1100, 700)
        self.specs = read_specs()
        self._monitor_thread = None
        self._monitor_module = None
        self.history_series = {"cpu": [], "ram": [], "gpu": [], "disco": []}
        self.build_ui()
        self.start_monitor()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)
        self.refresh()

    def build_ui(self):
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = self.build_sidebar()
        root.addWidget(self.sidebar)

        self.pages = QStackedWidget()
        self.summary_page = self.build_summary()
        self.history_page = self.build_history()
        self.guide_page = self.build_guide()
        self.pages.addWidget(self.summary_page)
        self.pages.addWidget(self.history_page)
        self.pages.addWidget(self.guide_page)
        root.addWidget(self.pages, 1)

        self.setCentralWidget(central)

    def build_sidebar(self):
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(270)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(18, 20, 18, 18)

        title_row = QHBoxLayout()
        if LOGO_PATH.exists():
            logo_lbl = QLabel()
            logo_lbl.setPixmap(QPixmap(str(LOGO_PATH)).scaledToHeight(28, Qt.SmoothTransformation))
            title_row.addWidget(logo_lbl)
        title = QLabel("PC Advisor")
        title.setObjectName("appTitle")
        title_row.addWidget(title)
        title_row.addStretch()
        lay.addLayout(title_row)

        self.nav_buttons = []
        for text in ("🏠  Resumen", "🗂️  Historial", "✅  Guía solución"):
            b = QPushButton(text)
            b.setObjectName("navButton")
            b.setCheckable(True)
            b.clicked.connect(lambda checked=False, i=len(self.nav_buttons): self.switch_page(i))
            self.nav_buttons.append(b)
            lay.addWidget(b)

        lay.addSpacing(15)
        mi = QFrame()
        mi.setObjectName("miEquipo")
        ml = QVBoxLayout(mi)
        ml.setContentsMargins(14, 12, 14, 12)
        h_row = QHBoxLayout()
        if LOGO_PATH.exists():
            h_logo = QLabel()
            h_logo.setPixmap(QPixmap(str(LOGO_PATH)).scaledToHeight(16, Qt.SmoothTransformation))
            h_row.addWidget(h_logo)
        h = QLabel("Mi Equipo")
        h.setObjectName("miTitulo")
        h_row.addWidget(h)
        h_row.addStretch()
        ml.addLayout(h_row)
        filas = [
            ("Sistema operativo", self.specs.get("so")),
            ("Procesador", self.specs.get("cpu_modelo")),
            ("Memoria RAM", f"{self.specs.get('ram_total_gb')} GB" if self.specs.get("ram_total_gb") else None),
            ("Disco", f"{self.specs.get('disco_total_gb')} GB" if self.specs.get("disco_total_gb") else None),
            ("Tarjeta gráfica", self.specs.get("gpu")),
            ("Placa madre", self.specs.get("placa_madre")),
        ]
        for a, b in filas:
            if not b or str(b).lower() in ("none", "no disponible"):
                continue
            row = QHBoxLayout()
            la = QLabel(a)
            la.setObjectName("muted")
            lb = QLabel(str(b))
            lb.setWordWrap(True)
            lb.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(la, 1)
            row.addWidget(lb, 1)
            ml.addLayout(row)
        lay.addWidget(mi)
        lay.addStretch()

        self.connection = QLabel("● Iniciando monitor...")
        self.connection.setObjectName("connection")
        lay.addWidget(self.connection)

        self.nav_buttons[0].setChecked(True)
        return side

    def build_summary(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(28, 22, 28, 22)
        outer.setSpacing(14)

        title_row = QHBoxLayout()
        if LOGO_PATH.exists():
            page_logo = QLabel()
            page_logo.setPixmap(QPixmap(str(LOGO_PATH)).scaledToHeight(32, Qt.SmoothTransformation))
            title_row.addWidget(page_logo)
        title = QLabel("Estado de tu computador")
        title.setObjectName("pageTitle")
        title_row.addWidget(title)
        title_row.addStretch()
        outer.addLayout(title_row)

        self.live_label = QLabel("🟡 Esperando lectura...")
        self.live_label.setObjectName("liveLabel")
        outer.addWidget(self.live_label)

        self.alert_frame = QFrame()
        self.alert_frame.setObjectName("alertFrame")
        al = QHBoxLayout(self.alert_frame)
        self.alert_text = QLabel("")
        self.alert_text.setWordWrap(True)
        self.alert_button = QPushButton("Ver qué puedo hacer")
        self.alert_button.clicked.connect(lambda: self.switch_page(2))
        al.addWidget(self.alert_text, 1)
        al.addWidget(self.alert_button)
        self.alert_frame.hide()
        outer.addWidget(self.alert_frame)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)
        self.cpu_card = MetricCard("CPU", self.specs.get("cpu_modelo"), ACENTO_CPU, "cpu", 90)
        self.ram_card = MetricCard("RAM", None, ACENTO_RAM, "ram", 85)
        self.gpu_card = MetricCard("GPU", self.specs.get("gpu"), ACENTO_GPU, "gpu", UMBRAL_GPU)
        self.disk_card = MetricCard("Disco", "Unidad principal", ACENTO_DISCO, "disco", UMBRAL_DISCO)
        grid.addWidget(self.cpu_card, 0, 0)
        grid.addWidget(self.ram_card, 0, 1)
        grid.addWidget(self.gpu_card, 1, 0)
        grid.addWidget(self.disk_card, 1, 1)
        outer.addLayout(grid)

        temp_row = QHBoxLayout()
        self.cpu_temp = TempCard("🌡️ Temperatura del procesador")
        self.gpu_temp = TempCard("🎮 Temperatura de la tarjeta gráfica")
        temp_row.addWidget(self.cpu_temp)
        temp_row.addWidget(self.gpu_temp)
        outer.addLayout(temp_row)

        self.disks_frame = QFrame()
        self.disks_frame.setObjectName("card")
        self.disks_layout = QVBoxLayout(self.disks_frame)
        self.disks_title = QLabel("💾 Unidades detectadas")
        self.disks_title.setObjectName("sectionTitle")
        self.disks_layout.addWidget(self.disks_title)
        outer.addWidget(self.disks_frame)

        chart_frame = QFrame()
        chart_frame.setObjectName("card")
        cl = QVBoxLayout(chart_frame)
        chart_title = QLabel("Cómo se ha comportado tu equipo · últimos 60 segundos")
        chart_title.setObjectName("sectionTitle")
        cl.addWidget(chart_title)
        self.live_chart = Sparkline("#5DA9FF")
        self.live_chart.setMinimumHeight(120)
        cl.addWidget(self.live_chart)
        outer.addWidget(chart_frame)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(page)
        return scroll

    def build_history(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 22, 28, 22)
        title = QLabel("🗂️ Historial")
        title.setObjectName("pageTitle")
        lay.addWidget(title)
        sub = QLabel("Diagnósticos y alertas generadas a partir de tus lecturas.")
        sub.setObjectName("muted")
        lay.addWidget(sub)
        self.history_container = QVBoxLayout()
        lay.addLayout(self.history_container)
        lay.addStretch()
        return page

    def build_guide(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 22, 28, 22)
        title = QLabel("✅ Guía de solución")
        title.setObjectName("pageTitle")
        lay.addWidget(title)
        self.guide_text = QLabel("Todavía no hay ningún diagnóstico generado.")
        self.guide_text.setWordWrap(True)
        self.guide_text.setObjectName("guideText")
        lay.addWidget(self.guide_text)
        lay.addStretch()
        return page

    def switch_page(self, index):
        self.pages.setCurrentIndex(index)
        for i, b in enumerate(self.nav_buttons):
            b.setChecked(i == index)
        if index == 1:
            self.refresh_history()
        elif index == 2:
            self.refresh_guide()

    def start_monitor(self):
        def worker():
            try:
                import monitor
                self._monitor_module = monitor
                monitor.main()
            except Exception as exc:
                self._monitor_module = None
                print(f"PC Advisor: error del monitor: {exc}")

        self._monitor_thread = threading.Thread(target=worker, name="PCAdvisorMonitor", daemon=True)
        self._monitor_thread.start()

    def refresh(self):
        state = read_state()
        if not state:
            self.connection.setText("● Esperando al monitor...")
            self.connection.setStyleSheet(f"color:{'#F59E0B'};")
            return

        timestamp = float(state.get("timestamp", 0) or 0)
        age = max(0, time.time() - timestamp) if timestamp else 999
        stamp = time.strftime("%H:%M:%S", time.localtime(timestamp)) if timestamp else "--:--:--"
        if age <= 3:
            self.connection.setText("● Monitor activo")
            self.connection.setStyleSheet(f"color:{COLOR_VERDE};")
            self.live_label.setText(f"🟢 En vivo · última lectura {stamp}")
        else:
            self.connection.setText("● Lectura desactualizada")
            self.connection.setStyleSheet(f"color:{COLOR_ROJO};")
            self.live_label.setText(f"⚠️ Lectura desactualizada · última lectura {stamp}")

        cpu = float(state.get("cpu", 0) or 0)
        ram = float(state.get("ram", 0) or 0)
        gpu_raw = state.get("gpu")
        gpu = float(gpu_raw) if gpu_raw is not None else 0
        disco = float(state.get("disco", 0) or 0)
        t_cpu = float(state.get("temperatura_cpu", 0) or 0)
        t_gpu = float(state.get("temperatura_gpu", 0) or 0)
        gpu_name = state.get("gpu_nombre") or self.specs.get("gpu") or "No detectada"

        self.history_series["cpu"] = [float(x.get("cpu", 0) or 0) for x in state.get("historial_vivo", [])]
        self.history_series["ram"] = [float(x.get("ram", 0) or 0) for x in state.get("historial_vivo", [])]
        self.history_series["gpu"] = [float(x.get("gpu", 0) or 0) for x in state.get("historial_vivo", []) if x.get("gpu") is not None]
        self.history_series["disco"] = [float(x.get("disco", 0) or 0) for x in state.get("historial_vivo", [])]
        self.live_chart.set_values(self.history_series["cpu"])

        self.cpu_card.model.setText(self.specs.get("cpu_modelo") or "")
        self.ram_card.update_card(ram, self.history_series["ram"], [
            ("En uso", f"{(self.specs.get('ram_total_gb') or 0) * ram / 100:.1f} / {self.specs.get('ram_total_gb'):.1f} GB" if self.specs.get("ram_total_gb") else f"{ram:.1f}%")
        ])
        self.cpu_card.update_card(cpu, self.history_series["cpu"], [
            ("Temp. CPU", f"{t_cpu:.0f} °C" if t_cpu else "No disponible"),
            ("Núcleos / hilos", self.cpu_threads()),
            ("Frecuencia actual", self.cpu_frequency()),
        ])
        self.gpu_card.model.setText(gpu_name)
        if gpu_raw is not None:
            self.gpu_card.update_card(gpu, self.history_series["gpu"], [
                ("Temp. GPU", f"{t_gpu:.0f} °C" if t_gpu else "No disponible"),
                ("Temp. VRAM", f"{float(state.get('temperatura_vram', 0) or 0):.0f} °C" if state.get("temperatura_vram") else "No disponible"),
            ])
        else:
            self.gpu_card.update_card(0, self.history_series["gpu"], [("Uso", "No disponible")])
            self.gpu_card.status.setText("No disponible")
            self.gpu_card.status.setStyleSheet(f"color:{COLOR_TEXTO_TENUE};")
        self.disk_card.update_card(disco, self.history_series["disco"], [
            ("Capacidad total", f"{self.specs.get('disco_total_gb'):.0f} GB" if self.specs.get("disco_total_gb") else "No disponible")
        ])
        self.cpu_temp.set_value(t_cpu)
        self.gpu_temp.set_value(t_gpu)
        self.update_disks(state.get("discos", []))
        self.update_alert()
        if self.pages.currentIndex() == 1:
            self.refresh_history()

    def cpu_threads(self):
        try:
            import psutil
            a = psutil.cpu_count(logical=False)
            b = psutil.cpu_count(logical=True)
            return f"{a} núcleos / {b} hilos" if a and b and a != b else str(b or "No disponible")
        except Exception:
            return "No disponible"

    def cpu_frequency(self):
        try:
            import psutil
            f = psutil.cpu_freq()
            return f"{f.current/1000:.2f} GHz" if f and f.current else "No disponible"
        except Exception:
            return "No disponible"

    def update_disks(self, disks):
        while self.disks_layout.count() > 1:
            item = self.disks_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        if not disks:
            self.disks_layout.addWidget(QLabel("No se detectaron unidades montadas."))
            return
        for d in disks:
            row = QFrame()
            row.setObjectName("diskChip")
            l = QHBoxLayout(row)
            unit = QLabel(str(d.get("unidad", "Disco")))
            unit.setObjectName("diskUnit")
            used = QLabel(f"{float(d.get('usado_gb',0)):.1f} / {float(d.get('total_gb',0)):.1f} GB · {float(d.get('uso',0)):.0f}% usado")
            used.setObjectName("muted")
            temp = float(d.get("temperatura", 0) or 0)
            if temp:
                used.setText(used.text() + f" · {temp:.0f} °C")
            l.addWidget(unit)
            l.addWidget(used, 1, Qt.AlignRight)
            self.disks_layout.addWidget(row)

    def update_alert(self):
        try:
            alerta = obtener_alerta_pendiente_mas_reciente()
        except Exception:
            alerta = None
        if alerta:
            _, _, _, mensaje, _ = alerta
            self.alert_text.setText(f"🔔 PC Advisor — {mensaje}")
            self.alert_frame.show()
        else:
            self.alert_frame.hide()

    def refresh_history(self):
        while self.history_container.count():
            item = self.history_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        try:
            rows = obtener_historial(limite=15)
        except Exception:
            rows = []
        if not rows:
            self.history_container.addWidget(QLabel("Todavía no se ha generado ninguna recomendación."))
            return
        for row in rows:
            id_h, fecha, tipo, mensaje, guia, estado = row
            card = QFrame()
            card.setObjectName("card")
            l = QHBoxLayout(card)
            emoji = "🟡" if estado == "pendiente" else "🟢"
            text = QLabel(f"{emoji}  {mensaje}\n{fecha}")
            text.setWordWrap(True)
            button = QPushButton("Guía de solución")
            button.clicked.connect(lambda checked=False, g=guia, m=mensaje, s=estado: self.show_guide(m, g, s))
            l.addWidget(text, 1)
            l.addWidget(button)
            self.history_container.addWidget(card)

    def show_guide(self, message, guide, state):
        self.guide_text.setText(
            f"<h2>{message}</h2>"
            f"<p><b>{'PENDIENTE' if state == 'pendiente' else 'RESUELTO'}</b></p>"
            f"<p>{str(guide).replace(chr(10), '<br>')}</p>"
        )
        self.switch_page(2)

    def refresh_guide(self):
        try:
            conn = conectar()
            row = conn.execute(
                "SELECT mensaje, guia_solucion, estado FROM historial_recomendaciones ORDER BY id DESC LIMIT 1"
            ).fetchone()
            conn.close()
        except Exception:
            row = None
        if row:
            self.show_guide(*row)

    def closeEvent(self, event):
        self.timer.stop()
        try:
            if self._monitor_module and hasattr(self._monitor_module, "detener"):
                self._monitor_module.detener()
        except Exception:
            pass
        event.accept()


STYLE = f"""
QMainWindow, QWidget {{ background:{COLOR_FONDO}; color:{COLOR_TEXTO}; font-family:'Segoe UI'; }}
#sidebar {{ background:{COLOR_FONDO}; border-right:1px solid {COLOR_BORDE}; }}
#appTitle {{ font-size:24px; font-weight:700; padding-bottom:12px; }}
#pageTitle {{ font-size:30px; font-weight:700; }}
#navButton {{ background:{COLOR_FONDO}; color:{COLOR_TEXTO_TENUE}; border:0; border-radius:9px; padding:12px 14px; text-align:left; font-size:14px; }}
#navButton:hover, #navButton:checked {{ background:{COLOR_TARJETA}; color:{COLOR_TEXTO}; }}
#miEquipo, #card, #metricCard, #tempCard {{ background:{COLOR_TARJETA}; border:1px solid {COLOR_BORDE}; border-radius:12px; }}
#metricCard[accent="{ACENTO_CPU}"] {{ border-left:5px solid {ACENTO_CPU}; }}
#metricCard[accent="{ACENTO_RAM}"] {{ border-left:5px solid {ACENTO_RAM}; }}
#metricCard[accent="{ACENTO_GPU}"] {{ border-left:5px solid {ACENTO_GPU}; }}
#metricCard[accent="{ACENTO_DISCO}"] {{ border-left:5px solid {ACENTO_DISCO}; }}
#cardTitle {{ font-size:15px; font-weight:700; }}
#cardModel {{ color:{COLOR_TEXTO_TENUE}; font-size:13px; }}
#miniLabel, #muted, #statLabel {{ color:{COLOR_TEXTO_TENUE}; font-size:12px; }}
#statValue {{ font-weight:600; }}
#statusLabel {{ font-size:13px; padding:2px 0; }}
#tempTitle {{ color:{COLOR_TEXTO_TENUE}; font-size:13px; }}
#tempValue {{ font-size:25px; font-weight:700; }}
#sectionTitle {{ font-size:15px; font-weight:700; }}
#diskChip {{ background:{COLOR_TRACK}; border-radius:10px; padding:5px; }}
#diskUnit {{ font-weight:600; }}
#connection {{ font-size:12px; }}
#liveLabel {{ color:{COLOR_TEXTO_TENUE}; }}
#alertFrame {{ background:#241D13; border:1px solid #6B4D18; border-radius:10px; padding:4px; }}
QPushButton {{ background:{COLOR_TARJETA}; color:{COLOR_TEXTO}; border:1px solid {COLOR_BORDE}; border-radius:8px; padding:9px 12px; }}
QPushButton:hover {{ background:#263653; }}
#guideText {{ background:{COLOR_TARJETA}; border:1px solid {COLOR_BORDE}; border-radius:12px; padding:20px; font-size:15px; }}
QScrollArea {{ border:0; }}
"""

def apply_style(app):
    app.setStyleSheet(STYLE)
