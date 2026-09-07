"""
Modulo NUEVO: cubre RF-04 (consultar historial) de forma simple, en
consola, antes de tener la interfaz grafica lista. Ejecutalo con:
    python ver_historial.py
"""
from database import obtener_historial


def main():
    historial = obtener_historial(limite=20)

    if not historial:
        print("Todavia no hay recomendaciones registradas.")
        return

    print("\nHISTORIAL DE RECOMENDACIONES")
    print("=" * 60)
    for fecha, tipo, mensaje, guia, estado in historial:
        print(f"\n[{estado.upper()}] {fecha}")
        print(f"  {mensaje}")
        print(f"  Guia:\n" + "\n".join(f"    {l}" for l in guia.split("\n")))
    print("=" * 60)


if __name__ == "__main__":
    main()
