import sqlite3
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "pc_advisor.db"
DB_PATH.parent.mkdir(exist_ok=True)


def conectar():
    return sqlite3.connect(DB_PATH)


def crear_tabla():
    conn = conectar()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS lecturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
            cpu REAL,
            ram REAL,
            temperatura REAL,
            disco REAL,
            gpu REAL
        )
    """)

    # Migracion para bases de datos creadas antes de agregar disco/gpu
    # (RF-01 completo: antes solo se guardaba cpu/ram/temperatura).
    columnas_existentes = {fila[1] for fila in conn.execute("PRAGMA table_info(lecturas)")}
    for columna in ("disco", "gpu"):
        if columna not in columnas_existentes:
            conn.execute(f"ALTER TABLE lecturas ADD COLUMN {columna} REAL")

    # NUEVO: historial de diagnósticos/alertas (RF-16), separado de las
    # lecturas crudas. Cada fila es un diagnóstico ya procesado, con su
    # guía de solución asociada y un estado que se puede actualizar.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS historial_recomendaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
            tipo_diagnostico TEXT,
            mensaje TEXT,
            guia_solucion TEXT,
            estado TEXT DEFAULT 'pendiente'
        )
    """)

    conn.commit()
    conn.close()


def guardar_lectura(cpu, ram, temperatura, disco=None, gpu=None):
    conn = conectar()
    conn.execute("""
        INSERT INTO lecturas (cpu, ram, temperatura, disco, gpu)
        VALUES (?, ?, ?, ?, ?)
    """, (cpu, ram, temperatura, disco, gpu))
    conn.commit()
    conn.close()


def obtener_ultimas_lecturas(n=10):
    """Trae las últimas n lecturas para evaluar si el uso fue sostenido,
    no solo un valor puntual."""
    conn = conectar()
    cursor = conn.execute("""
        SELECT cpu, ram, temperatura, disco, gpu FROM lecturas
        ORDER BY id DESC LIMIT ?
    """, (n,))
    filas = cursor.fetchall()
    conn.close()
    return filas


def obtener_promedios_diarios_ram(dias=30):
    """Promedio diario de RAM de los últimos `dias` días. Se usa para
    proyectar si la tendencia de uso va en aumento (RF-08: evaluar
    capacidad futura)."""
    conn = conectar()
    filas = conn.execute("""
        SELECT date(fecha_hora) AS dia, AVG(ram)
        FROM lecturas
        WHERE fecha_hora >= date('now', ?)
        GROUP BY dia
        ORDER BY dia ASC
    """, (f'-{dias} days',)).fetchall()
    conn.close()
    return filas


def guardar_recomendacion(tipo_diagnostico, mensaje, guia_solucion):
    """Guarda un diagnóstico en el historial, evitando duplicar el mismo
    tipo de alerta si ya hay una pendiente reciente (para no spamear)."""
    conn = conectar()
    ya_existe = conn.execute("""
        SELECT id FROM historial_recomendaciones
        WHERE tipo_diagnostico = ? AND estado = 'pendiente'
        ORDER BY id DESC LIMIT 1
    """, (tipo_diagnostico,)).fetchone()

    if ya_existe:
        conn.close()
        return False  # ya hay una alerta igual pendiente, no duplicar

    conn.execute("""
        INSERT INTO historial_recomendaciones (tipo_diagnostico, mensaje, guia_solucion)
        VALUES (?, ?, ?)
    """, (tipo_diagnostico, mensaje, guia_solucion))
    conn.commit()
    conn.close()
    return True


def obtener_historial(limite=20):
    conn = conectar()
    cursor = conn.execute("""
        SELECT id, fecha_hora, tipo_diagnostico, mensaje, guia_solucion, estado
        FROM historial_recomendaciones
        ORDER BY id DESC LIMIT ?
    """, (limite,))
    filas = cursor.fetchall()
    conn.close()
    return filas


def obtener_alerta_pendiente_mas_reciente():
    """Trae la alerta pendiente mas reciente, para mostrarla como aviso
    dentro de la propia app (ademas de la notificacion del sistema
    operativo que ya se dispara al generarla)."""
    conn = conectar()
    fila = conn.execute("""
        SELECT id, fecha_hora, tipo_diagnostico, mensaje, guia_solucion
        FROM historial_recomendaciones
        WHERE estado = 'pendiente'
        ORDER BY id DESC LIMIT 1
    """).fetchone()
    conn.close()
    return fila


def marcar_resuelto(id_recomendacion):
    conn = conectar()
    conn.execute("""
        UPDATE historial_recomendaciones SET estado = 'resuelto' WHERE id = ?
    """, (id_recomendacion,))
    conn.commit()
    conn.close()
