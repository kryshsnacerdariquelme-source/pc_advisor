"""Notificaciones al usuario (RF-12).

- Si la interfaz de escritorio registro un manejador (registrar_manejador),
  la notificacion se le entrega a ella: asi se muestra como aviso nativo de
  Windows con el icono de PC Advisor.
- Si no hay manejador (por ejemplo, monitor.py corrido a mano), se usa plyer
  en un hilo aparte, porque en Windows plyer puede quedarse esperando varios
  segundos y no debe frenar las lecturas del monitor.
- Si todo falla, se imprime en consola para no romper el programa.
"""
import threading

_manejador = None


def registrar_manejador(funcion):
    """funcion(titulo, mensaje). Pasar None para quitarlo."""
    global _manejador
    _manejador = funcion


def _con_plyer(titulo, mensaje):
    try:
        from plyer import notification
        notification.notify(title=titulo, message=mensaje, timeout=8)
    except Exception:
        print(f"\n[NOTIFICACION] {titulo}: {mensaje}\n")


def notificar(titulo, mensaje):
    if _manejador is not None:
        try:
            _manejador(titulo, mensaje)
            return
        except Exception:
            pass
    threading.Thread(target=_con_plyer, args=(titulo, mensaje), daemon=True).start()
