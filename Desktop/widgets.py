"""Widgets reutilizables de PC Advisor (mismo aspecto que el Frontend web)."""
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QFontMetrics, QPolygonF, QPainterPath,
)
from PySide6.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QHBoxLayout, QWidget, QSizePolicy,
)

from Desktop.theme import (
    COLOR_TARJETA, COLOR_BORDE, COLOR_TEXTO, COLOR_TRACK,
    COLOR_ROJO, EXPLICACION_LIMITE, GLOSARIO, tooltip,
)

A = Qt.AlignmentFlag


def _con_alfa(color, alfa):
    c = QColor(color)
    c.setAlpha(alfa)
    return c


def _num(v):
    try:
        return max(0.0, min(100.0, float(v or 0)))
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------
# Contenedores
# ---------------------------------------------------------------------

class Tarjeta(QFrame):
    """Caja con fondo, borde y (opcional) franja de color a la izquierda,
    como las tarjetas del Frontend."""

    def __init__(self, acento=None, grosor=4, margenes=(20, 16, 20, 12), parent=None):
        super().__init__(parent)
        self.setObjectName("tarjeta")
        self._acento = None
        self._grosor = grosor
        self.set_acento(acento)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(*margenes)
        self.lay.setSpacing(8)

    def set_acento(self, acento):
        if acento == self._acento and self.styleSheet():
            return
        self._acento = acento
        izq = f"border-left:{self._grosor}px solid {acento};" if acento else ""
        self.setStyleSheet(
            f"QFrame#tarjeta {{ background:{COLOR_TARJETA}; border:1px solid {COLOR_BORDE}; "
            f"{izq} border-radius:12px; }}"
        )


class ListaDatos(QWidget):
    """Filas 'etiqueta ........ valor' (los .stat-fila / .mi-equipo-fila del
    Frontend). Reutiliza los widgets entre actualizaciones para no parpadear."""

    def __init__(self, estilo="dashed", borde_ultimo=False, ajustar_texto=False, parent=None):
        super().__init__(parent)
        self._estilo = estilo
        self._borde_ultimo = borde_ultimo
        self._ajustar = ajustar_texto
        self._filas = []  # [frame, izq, der, con_borde]
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(0)

    def _crear_fila(self):
        frame = QFrame()
        frame.setObjectName("fila")
        h = QHBoxLayout(frame)
        h.setContentsMargins(0, 3, 0, 3)
        h.setSpacing(10)
        izq = QLabel()
        izq.setObjectName("stat_izq")
        der = QLabel()
        der.setObjectName("stat_der")
        der.setAlignment(A.AlignRight | A.AlignVCenter)
        if self._ajustar:
            der.setWordWrap(True)
            izq.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
            h.addWidget(izq, 0, A.AlignTop)
            h.addWidget(der, 1)
        else:
            h.addWidget(izq)
            h.addStretch(1)
            h.addWidget(der)
        self._lay.addWidget(frame)
        fila = [frame, izq, der, None]
        self._filas.append(fila)
        return fila

    def set_rows(self, rows):
        """rows: lista de (etiqueta, valor, tooltip_o_None)."""
        while len(self._filas) < len(rows):
            self._crear_fila()
        while len(self._filas) > len(rows):
            frame = self._filas.pop()[0]
            self._lay.removeWidget(frame)
            frame.deleteLater()

        for i, (etiqueta, valor, tip) in enumerate(rows):
            fila = self._filas[i]
            fila[1].setText(str(etiqueta))
            fila[2].setText(str(valor))
            fila[1].setToolTip(tooltip(tip) if tip else "")
            con_borde = self._borde_ultimo or i < len(rows) - 1
            if fila[3] != con_borde:
                fila[3] = con_borde
                linea = "dashed" if self._estilo == "dashed" else "solid"
                borde = f"border-bottom:1px {linea} {COLOR_TRACK};" if con_borde else "border-bottom:0;"
                fila[0].setStyleSheet(f"QFrame#fila {{ background:transparent; border:0; {borde} }}")


# ---------------------------------------------------------------------
# Graficos dibujados a mano
# ---------------------------------------------------------------------

class Anillo(QWidget):
    """Anillo de progreso (equivale a _grafico_anillo del Frontend)."""

    def __init__(self, color, lado=150, tam_texto=26, parent=None):
        super().__init__(parent)
        self.color = color
        self.valor = 0.0
        self.tam_texto = tam_texto
        self.setFixedSize(lado, lado)

    def set_value(self, valor):
        valor = _num(valor)
        if valor != self.valor:
            self.valor = valor
            self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        lado = min(w, h)
        grosor = lado / 2 * 0.28  # hueco central del 72 %, como en Plotly
        rect = QRectF((w - lado) / 2 + grosor / 2, (h - lado) / 2 + grosor / 2,
                      lado - grosor, lado - grosor)
        lapiz = QPen(QColor(COLOR_TRACK), grosor)
        lapiz.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(lapiz)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(rect)
        if self.valor > 0:
            lapiz.setColor(QColor(self.color))
            p.setPen(lapiz)
            p.drawArc(rect, 90 * 16, int(-self.valor / 100 * 360 * 16))
        fuente = QFont("Segoe UI")
        fuente.setPixelSize(self.tam_texto)
        fuente.setBold(True)
        p.setFont(fuente)
        p.setPen(QColor(COLOR_TEXTO))
        p.drawText(QRectF(0, 0, w, h), A.AlignCenter, f"{self.valor:.0f}%")


class MiniBarras(QWidget):
    """Mini barras tipo ecualizador con las ultimas 8 lecturas."""

    def __init__(self, color, umbral=None, parent=None):
        super().__init__(parent)
        self.color = color
        self.umbral = umbral
        self.valores = []
        self.setFixedHeight(70)
        self.setMinimumWidth(60)

    def set_values(self, valores):
        self.valores = [_num(v) for v in list(valores or [])[-8:]]
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        top = 6.0
        alto = h - top
        if self.umbral is not None and len(self.valores) > 1:
            y = top + alto * (1 - self.umbral / 100)
            p.fillRect(QRectF(0, top, w, y - top), _con_alfa(COLOR_ROJO, 31))
        valores = self.valores or [0.0]
        n = len(valores)
        ranura = w / n
        ancho = ranura * 0.65  # bargap 0.35 como en Plotly
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(self.color)))
        for i, v in enumerate(valores):
            barra = alto * v / 100
            p.drawRect(QRectF(i * ranura + (ranura - ancho) / 2, h - barra, ancho, barra))


class Sparkline(QWidget):
    """Linea de tendencia rellena con franja roja sobre el umbral."""

    def __init__(self, color, umbral=None, parent=None):
        super().__init__(parent)
        self.color = color
        self.umbral = umbral
        self.valores = []
        self.setFixedHeight(70)
        self.setMinimumWidth(80)

    def set_values(self, valores):
        self.valores = [_num(v) for v in list(valores or [])]
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        top = 6.0
        alto = h - top

        def y_de(v):
            return top + alto * (1 - v / 100)

        if self.umbral is not None:
            p.fillRect(QRectF(0, top, w, y_de(self.umbral) - top), _con_alfa(COLOR_ROJO, 31))

        n = len(self.valores)
        if n >= 2:
            puntos = [QPointF(i * (w - 1) / (n - 1), y_de(v)) for i, v in enumerate(self.valores)]
            relleno = QPolygonF([QPointF(0, h)] + puntos + [QPointF(w - 1, h)])
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_con_alfa(self.color, 51))
            p.drawPolygon(relleno)
            lapiz = QPen(QColor(self.color), 2)
            lapiz.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(lapiz)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPolyline(QPolygonF(puntos))

        if self.umbral is not None:
            lapiz = QPen(QColor(COLOR_ROJO), 1.5, Qt.PenStyle.DotLine)
            p.setPen(lapiz)
            y = y_de(self.umbral)
            p.drawLine(QPointF(0, y), QPointF(w, y))


class GraficoMultilinea(QWidget):
    """Grafico 'ultimos 60 segundos' con RAM/CPU/Disco/GPU, leyenda arriba,
    cuadricula y etiquetas de hora."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.etiquetas = []
        self.series = []  # (nombre, color, grosor, [valor|None, ...])
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_data(self, etiquetas, series):
        self.etiquetas = list(etiquetas)
        self.series = list(series)
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        izq, der, arriba, abajo = 46.0, 12.0, 34.0, 26.0
        x0, x1 = izq, w - der
        y0, y1 = arriba, h - abajo  # y0 = 100 %, y1 = 0 %

        fuente = QFont("Segoe UI")
        fuente.setPixelSize(11)
        p.setFont(fuente)
        fm = QFontMetrics(fuente)

        # Cuadricula y etiquetas del eje Y
        for pct in range(0, 101, 20):
            y = y1 - (y1 - y0) * pct / 100
            p.setPen(QPen(QColor(COLOR_BORDE), 1))
            p.drawLine(QPointF(x0, y), QPointF(x1, y))
            p.setPen(QColor(COLOR_TEXTO))
            p.drawText(QRectF(0, y - 8, izq - 8, 16), A.AlignRight | A.AlignVCenter, f"{pct}%")

        n = len(self.etiquetas)
        if n >= 2:
            # Etiquetas del eje X (~8 marcas)
            pasos = min(8, n)
            p.setPen(QColor(COLOR_TEXTO))
            for k in range(pasos):
                i = round(k * (n - 1) / (pasos - 1))
                x = x0 + (x1 - x0) * i / (n - 1)
                p.drawText(QRectF(x - 34, y1 + 6, 68, 16), A.AlignCenter, self.etiquetas[i])

            # Lineas de datos (None = hueco, como en Plotly)
            for _nombre, color, grosor, valores in self.series:
                camino = QPainterPath()
                en_trazo = False
                for i, v in enumerate(valores):
                    if v is None:
                        en_trazo = False
                        continue
                    x = x0 + (x1 - x0) * i / (n - 1)
                    y = y1 - (y1 - y0) * _num(v) / 100
                    if en_trazo:
                        camino.lineTo(x, y)
                    else:
                        camino.moveTo(x, y)
                        en_trazo = True
                lapiz = QPen(QColor(color), grosor)
                lapiz.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(lapiz)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(camino)

        # Leyenda horizontal arriba
        x = x0
        for nombre, color, _g, _v in self.series:
            p.setPen(QPen(QColor(color), 3))
            p.drawLine(QPointF(x, 12), QPointF(x + 16, 12))
            p.setPen(QColor(COLOR_TEXTO))
            ancho = fm.horizontalAdvance(nombre)
            p.drawText(QRectF(x + 22, 3, ancho + 4, 18), A.AlignLeft | A.AlignVCenter, nombre)
            x += 22 + ancho + 20


# ---------------------------------------------------------------------
# Tarjeta de metrica (CPU / RAM / GPU / Disco)
# ---------------------------------------------------------------------

class TarjetaMetrica(Tarjeta):
    """Cabecera (titulo + % + modelo), mini-barras, sparkline y datos:
    equivale a render_tarjeta_metrica() del Frontend."""

    def __init__(self, categoria, color, clave_glosario, umbral, parent=None):
        super().__init__(acento=color, grosor=5, margenes=(18, 14, 18, 10), parent=parent)
        self.color = color

        cabecera = QHBoxLayout()
        cabecera.setSpacing(10)
        self.titulo = QLabel(categoria)
        self.titulo.setObjectName("card_titulo")
        self.valor = QLabel("0%")
        self.valor.setStyleSheet(f"color:{color}; font-size:15px; font-weight:700;")
        self.valor.setToolTip(tooltip(GLOSARIO[clave_glosario]))
        self.modelo = QLabel("")
        self.modelo.setObjectName("card_modelo")
        cabecera.addWidget(self.titulo)
        cabecera.addWidget(self.valor)
        cabecera.addWidget(self.modelo, 1)
        self.lay.addLayout(cabecera)

        self.barras = MiniBarras(color, umbral)
        self.spark = Sparkline(color, umbral)
        self.datos = ListaDatos(estilo="dashed")

        col_barras = QVBoxLayout()
        col_barras.setSpacing(2)
        col_barras.addWidget(self.barras)
        etiqueta = QLabel("últimas lecturas")
        etiqueta.setObjectName("mini")
        etiqueta.setAlignment(A.AlignHCenter)
        col_barras.addWidget(etiqueta)
        col_barras.addStretch(1)

        col_spark = QVBoxLayout()
        col_spark.setSpacing(2)
        col_spark.addWidget(self.spark)
        aviso = QLabel("⚠️ franja roja = zona de riesgo")
        aviso.setObjectName("mini")
        aviso.setAlignment(A.AlignHCenter)
        aviso.setToolTip(tooltip(EXPLICACION_LIMITE[clave_glosario]))
        col_spark.addWidget(aviso)
        col_spark.addStretch(1)

        col_datos = QVBoxLayout()
        col_datos.addWidget(self.datos)
        col_datos.addStretch(1)

        cuerpo = QHBoxLayout()
        cuerpo.setSpacing(18)
        cuerpo.addLayout(col_barras, 12)
        cuerpo.addLayout(col_spark, 17)
        cuerpo.addLayout(col_datos, 18)
        self.lay.addLayout(cuerpo)

    def actualizar(self, valor, serie, stats, modelo=None):
        self.valor.setText(f"{float(valor or 0):.0f}%")
        if modelo is not None:
            self.modelo.setText(modelo)
        self.barras.set_values(serie)
        self.spark.set_values(serie)
        self.datos.set_rows(stats)
