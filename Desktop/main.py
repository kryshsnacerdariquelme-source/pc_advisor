"""Punto de entrada de PC Advisor (aplicacion de escritorio con PySide6).

Uso desde el codigo:   python Desktop/main.py
Como ejecutable:       PC_Advisor.exe   (se genera con build_exe.bat)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "Backend"
for ruta in (ROOT, BACKEND):
    if str(ruta) not in sys.path:
        sys.path.insert(0, str(ruta))

from PySide6.QtCore import Qt, QTimer, QLockFile
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from Desktop.theme import apply_style
from Desktop.main_window import MainWindow
from Desktop.consentimiento import solicitar_consentimiento
from logger_config import obtener_logger
from rutas import dir_datos, ruta_logo

log = obtener_logger("main")


def _registrar_errores(tipo, valor, traza):
    """Deja en el log cualquier error no controlado (en el .exe no hay
    consola donde verlo)."""
    log.critical("Excepcion no controlada", exc_info=(tipo, valor, traza))


def main():
    sys.excepthook = _registrar_errores

    if sys.platform == "win32":
        # Identidad propia para que Windows muestre el icono de PC Advisor
        # en la barra de tareas (y no el de python.exe).
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PCAdvisor.Desktop")
        except Exception:
            pass

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("PC Advisor")
    app.setOrganizationName("PC Advisor")
    if ruta_logo().exists():
        app.setWindowIcon(QIcon(str(ruta_logo())))
    apply_style(app)

    # Una sola instancia: dos monitores escribiendo en la misma base de
    # datos solo generarian lecturas duplicadas.
    bloqueo = QLockFile(str(dir_datos() / "pc_advisor.lock"))
    if not bloqueo.tryLock(300):
        QMessageBox.information(None, "PC Advisor", "PC Advisor ya está abierto.")
        return 0

    # Terminos y privacidad: se piden en el primer uso (y cuando cambian los
    # textos). Sin aceptarlos no se inicia el monitor ni se guarda nada.
    # La prueba automatica (--smoke-test) no tiene a nadie que haga clic.
    if "--smoke-test" not in sys.argv and not solicitar_consentimiento():
        bloqueo.unlock()
        return 0

    ventana = MainWindow()
    pantalla = app.primaryScreen().availableGeometry()
    ventana.resize(min(ventana.width(), pantalla.width() - 40),
                   min(ventana.height(), pantalla.height() - 40))
    ventana.show()

    if "--smoke-test" in sys.argv:
        # Prueba automatica (la usa la compilacion en GitHub Actions):
        # tras unos segundos comprueba que el monitor ya entrego datos.
        def verificar():
            import monitor
            app.exit(0 if monitor.obtener_estado_actual() else 1)
        QTimer.singleShot(12000, verificar)

    codigo = app.exec()
    bloqueo.unlock()
    return codigo


if __name__ == "__main__":
    sys.exit(main())
