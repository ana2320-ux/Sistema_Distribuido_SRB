"""
Proceso cliente para casos de prueba (archivo de operaciones):

    python -m capa_cliente.main --id 1 --script pruebas/caso_basico.txt [--detalle]

La carga continua de los escenarios la genera Locust: capa_cliente/locustfile.py.
"""
import argparse
import sys

from capa_cliente.cliente import Cliente
from capa_cliente.script import ejecutar_script


def main():
    parser = argparse.ArgumentParser(description="Cliente del Sistema de Reserva de Boletos")
    parser.add_argument("--id", type=int, required=True, help="identificador del cliente (mayor que 0)")
    parser.add_argument("--script", required=True, help="archivo con las operaciones a ejecutar")
    parser.add_argument("--detalle", action="store_true",
                        help="en las consultas, mostrar las fechas que tienen reservas")
    args = parser.parse_args()

    if args.id <= 0:
        parser.error("--id debe ser un entero mayor que 0")

    try:
        cliente = Cliente(args.id)
    except RuntimeError as e:
        sys.exit(f"[C{args.id}] {e}")
    try:
        resumen = ejecutar_script(cliente, args.script, args.detalle)
        print(f"[C{args.id}] terminado: {resumen}")
    except FileNotFoundError:
        print(f"No existe el archivo {args.script}")
    except RuntimeError as e:
        print(f"[C{args.id}] {e}")
    except KeyboardInterrupt:
        print(f"[C{args.id}] interrumpido")
    finally:
        cliente.cerrar()


if __name__ == "__main__":
    main()
