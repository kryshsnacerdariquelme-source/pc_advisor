"""Aceptacion de Terminos y Condiciones y Politica de Privacidad.

Al abrir la app por primera vez (o cuando cambia VERSION_LEGAL) se muestra
un dialogo que obliga a aceptar ambos documentos. Si la persona no acepta,
la app se cierra sin iniciar el monitor ni guardar nada.

La aceptacion queda registrada en  <dir_datos>/consentimiento.json
"""
import json
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QTextEdit, QVBoxLayout,
)

from logger_config import obtener_logger
from rutas import dir_datos, dir_legal

log = obtener_logger(__name__)

# Sube este numero cada vez que cambies los textos de legal/ de forma
# importante: a todos los usuarios se les volvera a pedir la aceptacion.
VERSION_LEGAL = 1

ARCHIVO_TERMINOS = "TERMINOS_Y_CONDICIONES.txt"
ARCHIVO_PRIVACIDAD = "POLITICA_DE_PRIVACIDAD.txt"


def _ruta_registro():
    return dir_datos() / "consentimiento.json"


def leer_texto(nombre_archivo: str) -> str:
    try:
        return (dir_legal() / nombre_archivo).read_text(encoding="utf-8-sig")
    except OSError:
        log.exception("No se pudo leer el documento legal %s", nombre_archivo)
        return ("No se pudo cargar este documento. Reinstala PC Advisor o "
                "contacta al titular del programa.")


def consentimiento_vigente() -> bool:
    """True si ya se aceptaron los documentos en su version actual."""
    try:
        datos = json.loads(_ruta_registro().read_text(encoding="utf-8"))
        return bool(datos.get("aceptado")) and datos.get("version") == VERSION_LEGAL
    except (OSError, ValueError):
        return False


def registrar_consentimiento() -> bool:
    try:
        _ruta_registro().write_text(json.dumps({
            "aceptado": True,
            "version": VERSION_LEGAL,
            "fecha": datetime.now().isoformat(timespec="seconds"),
        }, indent=2), encoding="utf-8")
        return True
    except OSError:
        log.exception("No se pudo guardar el registro de aceptacion")
        return False


def _visor(texto: str) -> QTextEdit:
    v = QTextEdit()
    v.setReadOnly(True)
    v.setPlainText(texto)
    return v


class DialogoLegal(QDialog):
    """Dialogo de aceptacion (modo_lectura=False) o de consulta (True)."""

    def __init__(self, parent=None, modo_lectura=False):
        super().__init__(parent)
        self.setWindowTitle("PC Advisor - Términos y privacidad")
        self.setModal(True)
        self.resize(760, 640)
        # Sin boton "cerrar" de la barra: se debe elegir Aceptar / No acepto.
        if not modo_lectura:
            self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 18)
        lay.setSpacing(12)

        titulo = QLabel("Antes de empezar" if not modo_lectura else "Términos y privacidad")
        titulo.setObjectName("subtitulo")
        lay.addWidget(titulo)

        intro = QLabel(
            "Lee los siguientes documentos. Para usar PC Advisor necesitas aceptar "
            "ambos. Todos tus datos se quedan en tu computador."
            if not modo_lectura else
            "Estos son los documentos que aceptaste al empezar a usar PC Advisor.")
        intro.setObjectName("caption")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        tabs = QTabWidget()
        tabs.addTab(_visor(leer_texto(ARCHIVO_TERMINOS)), "Términos y condiciones")
        tabs.addTab(_visor(leer_texto(ARCHIVO_PRIVACIDAD)), "Política de privacidad")
        lay.addWidget(tabs, 1)

        botones = QHBoxLayout()
        botones.addStretch(1)

        if modo_lectura:
            cerrar = QPushButton("Cerrar")
            cerrar.clicked.connect(self.accept)
            botones.addWidget(cerrar)
            lay.addLayout(botones)
            return

        self.chk_terminos = QCheckBox("He leído y acepto los Términos y condiciones de uso")
        self.chk_privacidad = QCheckBox("He leído y acepto la Política de privacidad")
        lay.addWidget(self.chk_terminos)
        lay.addWidget(self.chk_privacidad)

        self.btn_rechazar = QPushButton("No acepto (salir)")
        self.btn_rechazar.clicked.connect(self.reject)
        self.btn_aceptar = QPushButton("Aceptar y continuar")
        self.btn_aceptar.setEnabled(False)
        self.btn_aceptar.setDefault(True)
        self.btn_aceptar.clicked.connect(self.accept)
        botones.addWidget(self.btn_rechazar)
        botones.addWidget(self.btn_aceptar)
        lay.addLayout(botones)

        self.chk_terminos.toggled.connect(self._actualizar_boton)
        self.chk_privacidad.toggled.connect(self._actualizar_boton)

    def _actualizar_boton(self):
        self.btn_aceptar.setEnabled(
            self.chk_terminos.isChecked() and self.chk_privacidad.isChecked())

    def reject(self):
        # Esc o "No acepto": equivale a rechazar
        super().reject()


def solicitar_consentimiento() -> bool:
    """Muestra el dialogo si hace falta. Devuelve True si se puede continuar."""
    if consentimiento_vigente():
        return True
    dialogo = DialogoLegal()
    if dialogo.exec() != QDialog.DialogCode.Accepted:
        log.info("El usuario no acepto los terminos: se cierra la aplicacion")
        return False
    if not registrar_consentimiento():
        # Sin poder guardarlo se volveria a preguntar cada vez, pero la
        # persona si acepto en esta sesion: se deja continuar.
        log.warning("Aceptado en esta sesion, pero no quedo registrado")
    return True
