"""
Inicializa la base de datos con el caso del enunciado o con un archivo JSON.

Uso (desde la raiz del proyecto):
    python -m capa_persistencia.cargar_datos                       # 50 eventos de noviembre 2026
    python -m capa_persistencia.cargar_datos pruebas/caso.json      # caso del profesor
"""
import json
import sys

from capa_persistencia.db import BaseDatos

TIPOS_EVENTO = ["concierto", "teatro", "futbol", "cine", "danza"]


def generar_eventos(anio=2026, mes=11, cantidad=50, dobles=20, capacidad=100):
    """
    El caso del enunciado: 50 eventos en un mes; los primeros 20 ocurren dos veces.
    E1 cae el dia 1 y el 15, E2 el 2 y el 16 ... los demas una sola vez.
    """
    eventos = []
    for i in range(1, cantidad + 1):
        dia = (i - 1) % 14 + 1 # dias 1 a 14
        fechas = [f"{anio}/{mes:02d}/{dia:02d}"]
        if i <= dobles:
            fechas.append(f"{anio}/{mes:02d}/{dia + 14:02d}") # dias 15 a 28
        tipo = TIPOS_EVENTO[(i - 1) % len(TIPOS_EVENTO)]
        eventos.append({"id": f"E{i}", "nombre": f"{tipo.capitalize()} {i}",
                        "tipo_evento": tipo, "fechas": fechas, "capacidad": capacidad})
    return eventos


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as archivo:
            eventos = json.load(archivo)
        origen = sys.argv[1]
    else:
        eventos = generar_eventos()
        origen = "caso del enunciado"

    bd = BaseDatos()
    bd.reiniciar()
    bd.cargar_eventos(eventos)
    print(f"[CARGA] {len(eventos)} eventos cargados ({origen}) en {bd.ruta}")
    bd.imprimir_estado()
    bd.cerrar()


if __name__ == "__main__":
    main()