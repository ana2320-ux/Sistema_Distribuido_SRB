"""
Proceso cliente. Dos modos:

  Caso de prueba (archivo de operaciones):
    python -m capa_cliente.main --id 1 --script pruebas/caso_basico.txt [--detalle]

  Carga continua:
    python -m capa_cliente.main --id 1 --carga --duracion 150 --por-minuto 20 --consultas 70
"""
import argparse

from config import configuracion as config
from capa_cliente.carga import generar_carga
from capa_cliente.cliente import Cliente
from capa_cliente.script import ejecutar_script


def main():
    parser = argparse.ArgumentParser(description="Cliente del Sistema de Reserva de Boletos")
    parser.add_argument("--id", type=int, required=True, help="identificador del cliente (mayor que 0)")
    modo = parser.add_mutually_exclusive_group(required=True)
    modo.add_argument("--script", help="archivo con las operaciones a ejecutar")
    modo.add_argument("--carga", action="store_true", help="generar carga continua")
    parser.add_argument("--detalle", action="store_true",
                        help="(script) en las consultas, mostrar las fechas que tienen reservas")
    parser.add_argument("--duracion", type=float, default=150, help="(carga) segundos, por defecto 150")
    parser.add_argument("--por-minuto", type=float, default=20, help="(carga) peticiones por minuto")
    parser.add_argument("--consultas", type=float, default=70,
                        help="(carga) porcentaje de consultas; el resto son reservas")
    parser.add_argument("--salida", help="(carga) CSV de resultados; por defecto resultados/cliente_<id>.csv")
    parser.add_argument("--semilla", type=int, help="(carga) semilla del azar, para repetir una corrida")
    args = parser.parse_args()

    if args.id <= 0:
        parser.error("--id debe ser un entero mayor que 0")
    if args.carga and args.por_minuto <= 0:
        parser.error("--por-minuto debe ser mayor que 0")
    if args.carga and not 0 <= args.consultas <= 100:
        parser.error("--consultas debe estar entre 0 y 100")

    cliente = Cliente(args.id)
    try:
        if args.script:
            resumen = ejecutar_script(cliente, args.script, args.detalle)
            print(f"[C{args.id}] terminado: {resumen}")
        else:
            salida = args.salida or config.RAIZ / "resultados" / f"cliente_{args.id}.csv"
            print(f"[C{args.id}] carga: {args.por_minuto:g}/min, {args.consultas:g}% consultas, "
                  f"{args.duracion:g} s -> {salida}", flush=True)
            enviadas = generar_carga(cliente, salida, args.duracion, args.por_minuto,
                                     args.consultas, semilla=args.semilla)
            print(f"[C{args.id}] terminado: {enviadas} peticiones", flush=True)
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
