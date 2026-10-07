import html
import threading
import time

import psutil
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QScrollArea, QMessageBox, QFileDialog, QSystemTrayIcon,
)

from Desktop.theme import (
    ACENTO_CPU, ACENTO_RAM, ACENTO_DISCO, ACENTO_GPU, COLOR_TEXTO_TENUE,
    COLOR_LINEA_GRAFICO, GLOSARIO, tooltip,
    UMBRAL_CPU, UMBRAL_RAM, UMBRAL_GPU_REFERENCIA, UMBRAL_DISCO_REFERENCIA,
)
from Desktop.widgets import (
    Tarjeta, ListaDatos, Anillo, GraficoMultilinea, TarjetaMetrica,
)
from Desktop.hardware_reader import read_state, read_specs
from Desktop.consentimiento import DialogoLegal

import monitor
from database import (
    crear_tabla, obtener_historial, obtener_alerta_pendiente_mas_reciente,
    obtener_ultimas_lecturas, obtener_recomendacion,
)
from logger_config import obtener_logger
from notificaciones import registrar_manejador
from puntaje import calcular_puntaje_salud
from reporte_pdf import generar_reporte_pdf
from rutas import ruta_logo

log = obtener_logger(__name__)

A = Qt.AlignmentFlag
URL_LHM = "https://librehardwaremonitor.org"


def _etiqueta(texto="", nombre=None, ajustar=False, alineacion=None, plano=False):
    """plano=True: el texto se muestra tal cual (sin interpretar HTML)."""
    lb = QLabel(texto)
    if plano:
        lb.setTextFormat(Qt.TextFormat.PlainText)
    if nombre:
        lb.setObjectName(nombre)
    if ajustar:
        lb.setWordWrap(True)
    if alineacion is not None:
        lb.setAlignment(alineacion)
    return lb


def _logo_label(alto):
    ruta = ruta_logo()
    if not ruta.exists():
        return None
    lb = QLabel()
    lb.setPixmap(QPixmap(str(ruta)).scaledToHeight(alto, Qt.TransformationMode.SmoothTransformation))
    return lb


class MainWindow(QMainWindow):
    # Se emiten desde otros hilos y se atienden en el hilo de la interfaz.
    specs_listas = Signal(dict)
    notificacion = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PC Advisor")
        self.resize(1400, 850)
        self.setMinimumSize(1100, 700)

        self.specs = None            # se llena en segundo plano
        self.alerta_descartada = None
        self.diagnostico_sel = None  # id elegido para la Guia
        self._firma_historial = None

        crear_tabla()  # antes de que la interfaz consulte la base de datos
        self._construir_ui()
        self._iniciar_tray()

        self.specs_listas.connect(self._on_specs)
        threading.Thread(target=lambda: self.specs_listas.emit(read_specs()),
                         name="PCAdvisorSpecs", daemon=True).start()

        self._iniciar_monitor()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refrescar)
        self.timer.start(1000)
        self.refrescar()

    # ------------------------------------------------------------------
    # Construccion de la interfaz
    # ------------------------------------------------------------------

    def _construir_ui(self):
        central = QWidget()
        central.setObjectName("raiz")
        raiz = QHBoxLayout(central)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        raiz.addWidget(self._construir_barra_lateral())

        self.paginas = QStackedWidget()
        self.paginas.addWidget(self._construir_resumen())
        self.paginas.addWidget(self._construir_historial())
        self.paginas.addWidget(self._construir_guia())
        raiz.addWidget(self.paginas, 1)
        self.setCentralWidget(central)

    def _construir_barra_lateral(self):
        barra = QFrame()
        barra.setObjectName("barra_lateral")
        barra.setFixedWidth(290)
        lay = QVBoxLayout(barra)
        lay.setContentsMargins(16, 20, 16, 16)
        lay.setSpacing(4)

        self.botones_nav = []
        for i, texto in enumerate(("🏠  Resumen", "🗂️  Historial", "✅  Guía solución")):
            b = QPushButton(texto)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, idx=i: self.ir_a_pagina(idx))
            self.botones_nav.append(b)
            lay.addWidget(b)
        self.botones_nav[0].setChecked(True)

        lay.addSpacing(16)

        # Panel "Mi Equipo"
        self.mi_equipo = Tarjeta(acento=ACENTO_DISCO, margenes=(18, 16, 18, 10))
        cab = QHBoxLayout()
        logo = _logo_label(28)
        if logo is not None:
            cab.addWidget(logo)
        cab.addWidget(_etiqueta("Mi Equipo", "card_titulo"))
        cab.addStretch(1)
        self.mi_equipo.lay.addLayout(cab)
        self.mi_equipo_datos = ListaDatos(estilo="solid", borde_ultimo=True, ajustar_texto=True)
        self.mi_equipo_datos.set_rows([("Sistema", "Leyendo datos del equipo…", None)])
        self.mi_equipo.lay.addWidget(self.mi_equipo_datos)
        lay.addWidget(self.mi_equipo)
        lay.addStretch(1)

        btn_legal = QPushButton("📄  Términos y privacidad")
        btn_legal.setObjectName("nav")
        btn_legal.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_legal.clicked.connect(lambda: DialogoLegal(self, modo_lectura=True).exec())
        lay.addWidget(btn_legal)
        return barra

    def _pagina_con_scroll(self, construir):
        """Crea una pagina desplazable con margenes estandar."""
        pagina = QWidget()
        pagina.setObjectName("pagina")
        lay = QVBoxLayout(pagina)
        lay.setContentsMargins(36, 28, 36, 28)
        lay.setSpacing(14)
        construir(lay)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(pagina)
        return scroll

    # --- Pagina: Resumen ----------------------------------------------

    def _construir_resumen(self):
        return self._pagina_con_scroll(self._llenar_resumen)

    def _llenar_resumen(self, lay):
        fila_titulo = QHBoxLayout()
        fila_titulo.setSpacing(14)
        logo = _logo_label(48)
        if logo is not None:
            fila_titulo.addWidget(logo)
        fila_titulo.addWidget(_etiqueta("Estado de tu computador", "titulo_pagina"))
        fila_titulo.addStretch(1)
        lay.addLayout(fila_titulo)

        self.aviso_sin_datos = _etiqueta(
            "Todavía no hay lecturas. El monitor arranca solo: espera unos segundos…",
            "aviso_info", ajustar=True)
        lay.addWidget(self.aviso_sin_datos)

        # Todo lo demas aparece cuando llega la primera lectura
        self.contenido = QWidget()
        cl = QVBoxLayout(self.contenido)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(14)
        lay.addWidget(self.contenido)
        lay.addStretch(1)
        self.contenido.hide()

        self.lbl_en_vivo = _etiqueta("", "caption")
        self.lbl_desactualizada = _etiqueta("", "aviso_warning", ajustar=True, plano=True)
        self.lbl_desactualizada.hide()
        cl.addWidget(self.lbl_en_vivo)
        cl.addWidget(self.lbl_desactualizada)

        # Aviso de alerta pendiente
        self.banner_alerta = Tarjeta(margenes=(16, 10, 16, 10))
        fila = QHBoxLayout()
        self.lbl_alerta = _etiqueta("", ajustar=True)
        self.lbl_alerta.setTextFormat(Qt.TextFormat.RichText)
        self.btn_ver_alerta = QPushButton("Ver qué puedo hacer")
        self.btn_ver_alerta.clicked.connect(lambda: self.ir_a_guia(self._id_alerta_actual))
        self.btn_cerrar_alerta = QPushButton("Ahora no")
        self.btn_cerrar_alerta.clicked.connect(self._descartar_alerta)
        fila.addWidget(self.lbl_alerta, 1)
        fila.addWidget(self.btn_ver_alerta)
        fila.addWidget(self.btn_cerrar_alerta)
        self.banner_alerta.lay.addLayout(fila)
        self.banner_alerta.hide()
        self._id_alerta_actual = None
        cl.addWidget(self.banner_alerta)

        # Puntaje de salud
        self.tarjeta_puntaje = Tarjeta(acento=ACENTO_DISCO, margenes=(20, 16, 20, 16))
        fila = QHBoxLayout()
        fila.setSpacing(18)
        self.lbl_puntaje = _etiqueta("--")
        fila.addWidget(self.lbl_puntaje)
        col = QVBoxLayout()
        col.setSpacing(2)
        self.lbl_puntaje_msg = _etiqueta("")
        self.lbl_puntaje_msg.setStyleSheet("font-size:15px; font-weight:600;")
        self.lbl_puntaje_det = _etiqueta("", ajustar=True)
        self.lbl_puntaje_det.setStyleSheet(f"font-size:12.5px; color:{COLOR_TEXTO_TENUE};")
        col.addWidget(self.lbl_puntaje_msg)
        col.addWidget(self.lbl_puntaje_det)
        fila.addLayout(col, 1)
        self.tarjeta_puntaje.lay.addLayout(fila)
        cl.addWidget(self.tarjeta_puntaje)

        self.btn_pdf = QPushButton("Descargar reporte en PDF")
        self.btn_pdf.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pdf.clicked.connect(self.exportar_pdf)
        cl.addWidget(self.btn_pdf, 0, A.AlignLeft)

        # Panel general: 2 anillos + lista de datos
        self.panel_general = Tarjeta(acento=ACENTO_CPU, margenes=(20, 18, 20, 12))
        fila = QHBoxLayout()
        fila.setSpacing(20)
        self.anillo_cpu = Anillo(ACENTO_CPU, 150, 26)
        self.anillo_gpu = Anillo(ACENTO_GPU, 150, 26)
        self.lbl_anillo_gpu = _etiqueta("USO DE GPU", "mini", alineacion=A.AlignHCenter)
        for anillo, texto, clave, lbl in (
            (self.anillo_cpu, "USO DE CPU", "cpu", None),
            (self.anillo_gpu, "USO DE GPU", "gpu", self.lbl_anillo_gpu),
        ):
            col = QVBoxLayout()
            col.setSpacing(4)
            col.setAlignment(A.AlignTop | A.AlignHCenter)
            col.addWidget(anillo, 0, A.AlignHCenter)
            lb = lbl or _etiqueta(texto, "mini", alineacion=A.AlignHCenter)
            lb.setToolTip(tooltip(GLOSARIO[clave]))
            col.addWidget(lb)
            fila.addLayout(col, 10)
        self.lista_general = ListaDatos(estilo="dashed")
        col = QVBoxLayout()
        col.addWidget(self.lista_general)
        col.addStretch(1)
        fila.addLayout(col, 16)
        self.panel_general.lay.addLayout(fila)
        cl.addWidget(self.panel_general)

        cl.addWidget(_etiqueta("Detalle por componente", "seccion"))

        self.tarjeta_cpu = TarjetaMetrica("CPU", ACENTO_CPU, "cpu", UMBRAL_CPU)
        cl.addWidget(self.tarjeta_cpu)
        self.lbl_sin_temp = _etiqueta(
            "ℹ️ La temperatura del CPU no está disponible. Windows no la expone "
            f"directamente: para verla, instala y deja abierto "
            f"<a href=\"{URL_LHM}\" style=\"color:#5DA9FF;\">Libre Hardware Monitor</a> "
            "(ejecutándolo como administrador).", "caption", ajustar=True)
        self.lbl_sin_temp.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_sin_temp.setOpenExternalLinks(True)
        cl.addWidget(self.lbl_sin_temp)

        self.tarjeta_ram = TarjetaMetrica("RAM", ACENTO_RAM, "ram", UMBRAL_RAM)
        cl.addWidget(self.tarjeta_ram)

        self.tarjeta_gpu = TarjetaMetrica("GPU", ACENTO_GPU, "gpu", UMBRAL_GPU_REFERENCIA)
        cl.addWidget(self.tarjeta_gpu)
        self.lbl_sin_gpu = _etiqueta("", "caption", ajustar=True, plano=True)
        cl.addWidget(self.lbl_sin_gpu)

        self.tarjeta_disco = TarjetaMetrica("Disco", ACENTO_DISCO, "disco", UMBRAL_DISCO_REFERENCIA)
        self.tarjeta_disco.modelo.setText("Unidad principal")
        cl.addWidget(self.tarjeta_disco)

        # Otras unidades
        self.caja_unidades = QWidget()
        ul = QVBoxLayout(self.caja_unidades)
        ul.setContentsMargins(0, 0, 0, 0)
        ul.setSpacing(8)
        ul.addWidget(_etiqueta("Otras unidades detectadas", "caption"))
        self.unidades_lay = QVBoxLayout()
        self.unidades_lay.setSpacing(8)
        ul.addLayout(self.unidades_lay)
        cl.addWidget(self.caja_unidades)
        self.lbl_sin_unidades = _etiqueta("No se detectaron unidades montadas.", "caption")
        cl.addWidget(self.lbl_sin_unidades)

        divisor = QFrame()
        divisor.setObjectName("divisor")
        divisor.setFixedHeight(1)
        cl.addSpacing(8)
        cl.addWidget(divisor)
        cl.addSpacing(4)
        cl.addWidget(_etiqueta("Cómo se ha comportado tu equipo · últimos 60 segundos", "subtitulo"))
        self.grafico = GraficoMultilinea()
        cl.addWidget(self.grafico)
        self.lbl_sin_grafico = _etiqueta("Esperando datos del monitor…", "caption")
        cl.addWidget(self.lbl_sin_grafico)

    # --- Pagina: Historial --------------------------------------------

    def _construir_historial(self):
        return self._pagina_con_scroll(self._llenar_historial)

    def _llenar_historial(self, lay):
        lay.addWidget(_etiqueta("🗂️ Historial", "titulo_pagina"))
        lay.addWidget(_etiqueta("Diagnósticos y alertas generadas a partir de tus lecturas (RF-04 / RF-16)", "caption"))
        self.historial_lay = QVBoxLayout()
        self.historial_lay.setSpacing(14)
        lay.addLayout(self.historial_lay)
        lay.addStretch(1)

    # --- Pagina: Guia de solucion -------------------------------------

    def _construir_guia(self):
        return self._pagina_con_scroll(self._llenar_guia)

    def _llenar_guia(self, lay):
        lay.addWidget(_etiqueta("✅ Guía de solución", "titulo_pagina"))
        self.guia_lay = QVBoxLayout()
        lay.addLayout(self.guia_lay)
        lay.addStretch(1)

    # ------------------------------------------------------------------
    # Monitor, tray y specs
    # ------------------------------------------------------------------

    def _iniciar_monitor(self):
        def trabajo():
            try:
                # Sin archivo JSON: la ventana lee el estado directo de memoria.
                monitor.main(verbose=False, escribir_archivo=False)
            except Exception:
                log.exception("El monitor termino con un error")

        self._hilo_monitor = threading.Thread(target=trabajo, name="PCAdvisorMonitor", daemon=True)
        self._hilo_monitor.start()

    def _iniciar_tray(self):
        """Icono en la bandeja: se usa para mostrar avisos nativos de Windows."""
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip("PC Advisor")
        self.tray.messageClicked.connect(self._al_hacer_clic_aviso)
        self.tray.show()
        self.notificacion.connect(self._mostrar_aviso)
        registrar_manejador(lambda titulo, mensaje: self.notificacion.emit(titulo, mensaje))

    def _mostrar_aviso(self, titulo, mensaje):
        if self.tray is not None and self.tray.isVisible():
            self.tray.showMessage(titulo, mensaje, self.windowIcon(), 8000)

    def _al_hacer_clic_aviso(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.ir_a_guia(None)

    def _on_specs(self, specs):
        self.specs = specs
        filas = [
            ("Sistema operativo", specs.get("so")),
            ("Procesador", specs.get("cpu_modelo")),
            ("Memoria RAM", f"{specs.get('ram_total_gb')} GB" if specs.get("ram_total_gb") else None),
            ("Disco", f"{specs.get('disco_total_gb')} GB" if specs.get("disco_total_gb") else None),
            ("Tarjeta gráfica", specs.get("gpu")),
            ("Placa madre", specs.get("placa_madre")),
        ]
        filas = [(e, v, None) for e, v in filas if v and str(v).strip().lower() not in ("none", "no disponible")]
        self.mi_equipo_datos.set_rows(filas)
        self.tarjeta_cpu.modelo.setText(specs.get("cpu_modelo") or "")
        self.refrescar()

    # ------------------------------------------------------------------
    # Navegacion
    # ------------------------------------------------------------------

    def ir_a_pagina(self, indice):
        self.paginas.setCurrentIndex(indice)
        for i, b in enumerate(self.botones_nav):
            b.setChecked(i == indice)
        if indice == 1:
            self.actualizar_historial(forzar=True)
        elif indice == 2:
            self.actualizar_guia()

    def ir_a_guia(self, id_diagnostico):
        self.diagnostico_sel = id_diagnostico
        self.ir_a_pagina(2)

    def _descartar_alerta(self):
        self.alerta_descartada = self._id_alerta_actual
        self.banner_alerta.hide()

    # ------------------------------------------------------------------
    # Actualizacion periodica (cada segundo)
    # ------------------------------------------------------------------

    def refrescar(self):
        try:
            self._refrescar_resumen()
            if self.paginas.currentIndex() == 1:
                self.actualizar_historial()
        except Exception:
            log.exception("Error al refrescar la interfaz")

    def _refrescar_resumen(self):
        estado = read_state()
        if not estado:
            self.aviso_sin_datos.show()
            self.contenido.hide()
            return
        self.aviso_sin_datos.hide()
        self.contenido.show()

        specs = self.specs or {}
        timestamp = float(estado.get("timestamp", 0) or 0)
        actualizado = time.strftime("%H:%M:%S", time.localtime(timestamp)) if timestamp else "--:--:--"
        edad = max(0, time.time() - timestamp) if timestamp else None
        if edad is not None and edad <= 3:
            self.lbl_en_vivo.setText(f"🟢 En vivo · última lectura {actualizado}")
            self.lbl_en_vivo.show()
            self.lbl_desactualizada.hide()
        else:
            self.lbl_desactualizada.setText(
                f"⚠️ Lectura desactualizada · última lectura {actualizado}. "
                "El monitor no está enviando datos; si sigue así, cierra y vuelve a abrir la app.")
            self.lbl_desactualizada.show()
            self.lbl_en_vivo.hide()

        historial = estado.get("historial_vivo", []) or []
        cpu = float(estado.get("cpu", 0) or 0)
        ram = float(estado.get("ram", 0) or 0)
        temp_cpu = float(estado.get("temperatura_cpu", 0) or 0)
        gpu_raw = estado.get("gpu")
        gpu = float(gpu_raw) if gpu_raw is not None else None
        gpu_nombre = estado.get("gpu_nombre") or specs.get("gpu") or "No detectada"
        temp_gpu = float(estado.get("temperatura_gpu", 0) or 0)
        temp_vram = float(estado.get("temperatura_vram", 0) or 0)
        discos = estado.get("discos", []) or []
        disco_principal = float(estado.get("disco", 0) or 0)

        serie_cpu = [float(p.get("cpu", 0) or 0) for p in historial]
        serie_ram = [float(p.get("ram", 0) or 0) for p in historial]
        serie_disco = [float(p.get("disco", 0) or 0) for p in historial]
        serie_gpu = [float(p.get("gpu", 0) or 0) for p in historial if p.get("gpu") is not None]

        self._actualizar_alerta()

        # Puntaje
        puntaje, color, mensaje, detalle = calcular_puntaje_salud(cpu, ram, gpu, discos)
        self.lbl_puntaje.setText(str(puntaje))
        self.lbl_puntaje.setStyleSheet(f"font-size:40px; font-weight:800; color:{color};")
        self.lbl_puntaje_msg.setText(mensaje)
        self.lbl_puntaje_det.setText(detalle)
        self.tarjeta_puntaje.set_acento(color)

        # Panel general
        self.anillo_cpu.set_value(cpu)
        self.anillo_gpu.set_value(gpu if gpu is not None else 0)
        self.lbl_anillo_gpu.setText("USO DE GPU" if gpu is not None else "GPU no disponible")
        filas = [("Uso de RAM", f"{ram:.0f}%", None)]
        frecuencia = self._frecuencia_cpu()
        if frecuencia:
            filas.append(("Frecuencia CPU", frecuencia, None))
        if temp_cpu:
            filas.append(("Temperatura CPU", f"{temp_cpu:.0f} °C", None))
        if temp_gpu:
            filas.append(("Temperatura GPU", f"{temp_gpu:.0f} °C", None))
        for d in discos[:3]:
            filas.append((
                d.get("unidad", "Disco"),
                f"{d.get('usado_gb', 0):.0f} / {d.get('total_gb', 0):.0f} GB · {d.get('uso', 0):.0f}%",
                None,
            ))
        self.lista_general.set_rows(filas)

        # Tarjeta CPU
        stats = []
        if temp_cpu:
            stats.append(("Temp. CPU", f"{temp_cpu:.0f} °C", GLOSARIO["temperatura"]))
        nucleos = self._nucleos_hilos()
        if nucleos:
            stats.append(("Núcleos / hilos", nucleos, None))
        if frecuencia:
            stats.append(("Frecuencia actual", frecuencia, None))
        self.tarjeta_cpu.actualizar(cpu, serie_cpu, stats, modelo=specs.get("cpu_modelo") or "")
        self.lbl_sin_temp.setVisible(not temp_cpu)

        # Tarjeta RAM
        ram_total = specs.get("ram_total_gb")
        if ram_total:
            stats = [("En uso", f"{ram_total * ram / 100:.1f} / {ram_total:.1f} GB", None)]
        else:
            stats = [("Uso actual", f"{ram:.1f}%", None)]
        self.tarjeta_ram.actualizar(ram, serie_ram, stats)

        # Tarjeta GPU
        if gpu is not None:
            stats = []
            if temp_gpu:
                stats.append(("Temp. GPU", f"{temp_gpu:.0f} °C", None))
            if temp_vram:
                stats.append(("Temp. VRAM", f"{temp_vram:.0f} °C", GLOSARIO["vram"]))
            self.tarjeta_gpu.actualizar(gpu, serie_gpu, stats, modelo=gpu_nombre)
            self.tarjeta_gpu.show()
            self.lbl_sin_gpu.hide()
        else:
            self.tarjeta_gpu.hide()
            self.lbl_sin_gpu.setText(f"🎮 Tarjeta gráfica · {gpu_nombre} — no se pudieron leer datos de uso en este momento.")
            self.lbl_sin_gpu.show()

        # Tarjeta Disco
        stats = []
        if specs.get("disco_total_gb"):
            stats.append(("Capacidad total", f"{specs['disco_total_gb']:.0f} GB", None))
        self.tarjeta_disco.actualizar(disco_principal, serie_disco, stats)

        self._actualizar_unidades(discos)
        self._actualizar_grafico(historial)

    def _frecuencia_cpu(self):
        try:
            f = psutil.cpu_freq()
            return f"{f.current / 1000:.2f} GHz" if f and f.current else None
        except Exception:
            return None

    def _nucleos_hilos(self):
        try:
            fisicos = psutil.cpu_count(logical=False)
            hilos = psutil.cpu_count(logical=True)
            if not hilos:
                return None
            return f"{fisicos} núcleos / {hilos} hilos" if fisicos and fisicos != hilos else f"{hilos}"
        except Exception:
            return None

    def _actualizar_alerta(self):
        try:
            alerta = obtener_alerta_pendiente_mas_reciente()
        except Exception:
            alerta = None
        if alerta and alerta[0] != self.alerta_descartada:
            self._id_alerta_actual = alerta[0]
            self.lbl_alerta.setText(f"<b>PC Advisor</b> — {html.escape(alerta[3])}")
            self.banner_alerta.show()
        else:
            self._id_alerta_actual = alerta[0] if alerta else None
            self.banner_alerta.hide()

    def _actualizar_unidades(self, discos):
        # Se reconstruye solo si cambia la lista (la mayoria de segundos no cambia).
        firma = tuple((d.get("unidad"), round(float(d.get("uso", 0) or 0)), d.get("temperatura")) for d in discos)
        if firma == getattr(self, "_firma_unidades", None):
            return
        self._firma_unidades = firma
        while self.unidades_lay.count():
            item = self.unidades_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.caja_unidades.setVisible(len(discos) > 1)
        self.lbl_sin_unidades.setVisible(not discos)
        if len(discos) <= 1:
            return
        for d in discos:
            chip = QFrame()
            chip.setStyleSheet("QFrame#chip { background:#1D2740; border-radius:10px; }")
            chip.setObjectName("chip")
            h = QHBoxLayout(chip)
            h.setContentsMargins(14, 8, 14, 8)
            nombre = _etiqueta(str(d.get("unidad", "Disco")))
            nombre.setStyleSheet("font-weight:600;")
            temp = f" · {float(d.get('temperatura', 0)):.0f} °C" if d.get("temperatura") else ""
            detalle = _etiqueta(
                f"{float(d.get('usado_gb', 0)):.1f} / {float(d.get('total_gb', 0)):.1f} GB "
                f"· {float(d.get('uso', 0)):.0f}% usado{temp}")
            detalle.setStyleSheet(f"color:{COLOR_TEXTO_TENUE};")
            h.addWidget(nombre)
            h.addStretch(1)
            h.addWidget(detalle)
            self.unidades_lay.addWidget(chip)

    def _actualizar_grafico(self, historial):
        if not historial:
            self.grafico.hide()
            self.lbl_sin_grafico.show()
            return
        self.grafico.show()
        self.lbl_sin_grafico.hide()
        etiquetas = [time.strftime("%H:%M:%S", time.localtime(float(p.get("timestamp", 0)))) for p in historial]
        series = [
            ("RAM", COLOR_LINEA_GRAFICO["RAM"], 3, [float(p.get("ram", 0) or 0) for p in historial]),
            ("CPU", COLOR_LINEA_GRAFICO["CPU"], 2, [float(p.get("cpu", 0) or 0) for p in historial]),
            ("Disco", COLOR_LINEA_GRAFICO["Disco"], 2, [float(p.get("disco", 0) or 0) for p in historial]),
        ]
        if any(p.get("gpu") is not None for p in historial):
            series.append(("GPU", COLOR_LINEA_GRAFICO["GPU"], 2,
                           [float(p["gpu"]) if p.get("gpu") is not None else None for p in historial]))
        self.grafico.set_data(etiquetas, series)

    # ------------------------------------------------------------------
    # Historial
    # ------------------------------------------------------------------

    def actualizar_historial(self, forzar=False):
        try:
            filas = obtener_historial(limite=15)
        except Exception:
            log.exception("No se pudo leer el historial")
            filas = []
        firma = tuple((f[0], f[5]) for f in filas)
        if not forzar and firma == self._firma_historial:
            return
        self._firma_historial = firma

        while self.historial_lay.count():
            item = self.historial_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not filas:
            tarjeta = Tarjeta(acento=ACENTO_DISCO, margenes=(20, 18, 20, 18))
            tarjeta.lay.addWidget(_etiqueta("Todavía no se ha generado ninguna recomendación.", "caption"))
            self.historial_lay.addWidget(tarjeta)
            return

        for id_h, fecha, _tipo, mensaje, _guia, estado in filas:
            tarjeta = Tarjeta(acento=ACENTO_DISCO, margenes=(20, 16, 20, 16))
            fila = QHBoxLayout()
            fila.setSpacing(16)
            col = QVBoxLayout()
            col.setSpacing(4)
            emoji = "🟡" if estado == "pendiente" else "🟢"
            texto = _etiqueta(f"{emoji} <b>{html.escape(mensaje)}</b>", ajustar=True)
            texto.setTextFormat(Qt.TextFormat.RichText)
            col.addWidget(texto)
            col.addWidget(_etiqueta(str(fecha), "caption", plano=True))
            fila.addLayout(col, 4)
            boton = QPushButton("Guía de solución")
            boton.setCursor(Qt.CursorShape.PointingHandCursor)
            boton.clicked.connect(lambda _=False, i=id_h: self.ir_a_guia(i))
            fila.addWidget(boton, 1, A.AlignVCenter)
            tarjeta.lay.addLayout(fila)
            self.historial_lay.addWidget(tarjeta)

    # ------------------------------------------------------------------
    # Guia de solucion
    # ------------------------------------------------------------------

    def actualizar_guia(self):
        while self.guia_lay.count():
            item = self.guia_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        try:
            fila = obtener_recomendacion(self.diagnostico_sel)
        except Exception:
            log.exception("No se pudo leer la guía de solución")
            fila = None

        tarjeta = Tarjeta(acento=ACENTO_DISCO, margenes=(20, 18, 20, 18))
        if not fila:
            tarjeta.lay.addWidget(_etiqueta(
                "Todavía no hay ningún diagnóstico generado. Cuando aparezca una alerta, su guía se mostrará acá.",
                "caption", ajustar=True))
            self.guia_lay.addWidget(tarjeta)
            return

        _tipo, mensaje, guia, estado = fila
        pendiente = estado == "pendiente"
        cab = QHBoxLayout()
        cab.setSpacing(16)
        titulo = _etiqueta(mensaje, "subtitulo", ajustar=True, plano=True)
        titulo.setStyleSheet("font-size:20px; font-weight:700;")
        badge = _etiqueta("PENDIENTE" if pendiente else "RESUELTO",
                          "badge_pendiente" if pendiente else "badge_resuelto")
        cab.addWidget(titulo, 1)
        cab.addWidget(badge, 0, A.AlignTop)
        tarjeta.lay.addLayout(cab)
        tarjeta.lay.addWidget(_etiqueta("<b>Cómo solucionarlo:</b>"))
        for linea in str(guia).split("\n"):
            tarjeta.lay.addWidget(_etiqueta(linea, ajustar=True, plano=True))
        self.guia_lay.addWidget(tarjeta)

    # ------------------------------------------------------------------
    # Reporte PDF
    # ------------------------------------------------------------------

    def exportar_pdf(self):
        estado = read_state() or {}
        cpu = float(estado.get("cpu", 0) or 0)
        ram = float(estado.get("ram", 0) or 0)
        gpu_raw = estado.get("gpu")
        gpu = float(gpu_raw) if gpu_raw is not None else None
        discos = estado.get("discos", []) or []
        puntaje, color, mensaje, detalle = calcular_puntaje_salud(cpu, ram, gpu, discos)

        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar reporte",
            f"pc_advisor_reporte_{time.strftime('%Y%m%d_%H%M')}.pdf",
            "Archivos PDF (*.pdf)")
        if not ruta:
            return
        try:
            try:
                lecturas = obtener_ultimas_lecturas(15)
            except Exception:
                lecturas = []
            alerta = obtener_alerta_pendiente_mas_reciente()
            alertas = [alerta[3]] if alerta and alerta[0] != self.alerta_descartada else []
            pdf_bytes = generar_reporte_pdf(
                self.specs or {}, puntaje, color, mensaje, detalle,
                cpu, ram, gpu, discos, lecturas, alertas)
            with open(ruta, "wb") as f:
                f.write(pdf_bytes)
            QMessageBox.information(self, "PC Advisor", "Reporte guardado correctamente.")
        except Exception as e:
            log.exception("No se pudo generar el PDF")
            QMessageBox.warning(self, "PC Advisor", f"No se pudo generar el PDF:\n{e}")

    # ------------------------------------------------------------------

    def closeEvent(self, event):
        self.timer.stop()
        registrar_manejador(None)
        try:
            monitor.detener()
        except Exception:
            pass
        if self.tray is not None:
            self.tray.hide()
        event.accept()

