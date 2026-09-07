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
            temperatura REAL
        )
    """)

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


def guardar_lectura(cpu, ram, temperatura):
    conn = conectar()
    conn.execute("""
        INSERT INTO lecturas (cpu, ram, temperatura)
        VALUES (?, ?, ?)
    """, (cpu, ram, temperatura))
    conn.commit()
    conn.close()


def obtener_ultimas_lecturas(n=10):
    """Trae las últimas n lecturas para evaluar si el uso fue sostenido,
    no solo un valor puntual."""
    conn = conectar()
    cursor = conn.execute("""
        SELECT cpu, ram, temperatura FROM lecturas
        ORDER BY id DESC LIMIT ?
    """, (n,))
    filas = cursor.fetchall()
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
        SELECT fecha_hora, tipo_diagnostico, mensaje, guia_solucion, estado
        FROM historial_recomendaciones
        ORDER BY id DESC LIMIT ?
    """, (limite,))
    filas = cursor.fetchall()
    conn.close()
    return filas


def marcar_resuelto(id_recomendacion):
    conn = conectar()
    conn.execute("""
        UPDATE historial_recomendaciones SET estado = 'resuelto' WHERE id = ?
    """, (id_recomendacion,))
    conn.commit()
    conn.close()
