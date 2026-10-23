"""
Muestra el estado de la base de datos. Para la sustentacion: el estado inicial
y como va quedando a medida que se hacen operaciones.
Se ejecuta en la maquina de persistencia, que es donde esta el archivo de la BD.

Uso (desde la raiz del proyecto):
    python -m capa_persistencia.ver_bd                 # solo las fechas con reservas
    python -m capa_persistencia.ver_bd --todas         # las 70 ocurrencias
    python -m capa_persistencia.ver_bd --cada 2        # se refresca cada 2 segundos
    python -m capa_persistencia.ver_bd --verificar     # ocupados = suma de reservas?
"""
import argparse
import time

from capa_persistencia.db import BaseDatos


def main():
    parser = argparse.ArgumentParser(description="Estado de la base de datos del SRB")
    parser.add_argument("--todas", action="store_true", help="mostrar tambien las fechas sin reservas")
    parser.add_argument("--cada", type=float, default=0, help="refrescar cada N segundos")
    parser.add_argument("--verificar", action="store_true",
                        help="comprobar que los ocupados coinciden con las reservas")
    args = parser.parse_args()

    bd = BaseDatos()
    try:
        if args.verificar:
            print("Base de datos consistente" if bd.verificar()
                  else "INCONSISTENTE: hay ocurrencias cuyos ocupados no cuadran con sus reservas")
            return
        while True:
            if args.cada:
                print("\033[2J\033[H", end="")       # limpia la pantalla de la terminal
                print(f"Estado de la BD - {time.strftime('%H:%M:%S')} (Ctrl+C para salir)\n")
            bd.imprimir_estado(solo_ocupadas=not args.todas)
            if not args.cada:
                break
            time.sleep(args.cada)
    except KeyboardInterrupt:
        pass
    finally:
        bd.cerrar()


if __name__ == "__main__":
    main()
