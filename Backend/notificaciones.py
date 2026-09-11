"""
Modulo NUEVO: dispara una notificacion nativa del sistema operativo
(RF-12), en vez de que la alerta solo se vea si tienes la consola abierta.
Si plyer falla (por ejemplo, corriendo en un entorno sin soporte), cae
de vuelta a imprimir en consola para no romper el programa.
"""

def notificar(titulo, mensaje):
    try:
        from plyer import notification
        notification.notify(
            title=titulo,
            message=mensaje,
            timeout=8,
        )
    except Exception:
        print(f"\n[NOTIFICACION] {titulo}: {mensaje}\n")
