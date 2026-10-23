"""
Lanza los escenarios de la Tabla 1 del enunciado. Cada cliente es un proceso aparte.

  Escenario 1: 3 clientes  -> 2 solo consultan, 1 consulta y reserva
  Escenario 2: 5 clientes  -> 3 solo consultan, 2 reservan (*)
  Escenario 3: 8 clientes  -> 4 solo consultan, 4 reservan (*)

  (*) El enunciado dice "reserva y modificacion"; la modificacion llega en la
      segunda entrega, asi que en la arquitectura base esos clientes solo reservan.

Uso (en la maquina de clientes, desde la raiz):
    python -m capa_cliente.escenarios --escenario 1 --etiqueta base
    python -m capa_cliente.escenarios --escenario 3 --etiqueta base --duracion 150 --por-minuto 20
"""
import argparse
import subprocess
import sys

from config import configuracion as config

# escenario -> lista de (cantidad de clientes, porcentaje de consultas)
ESCENARIOS = {
    1: [(2, 100), (1, 50)],
    2: [(3, 100), (2, 0)],
    3: [(4, 100), (4, 0)],
}


def main():
    parser = argparse.ArgumentParser(description="Escenarios de la Tabla 1")
    parser.add_argument("--escenario", type=int, choices=ESCENARIOS, required=True)
    parser.add_argument("--etiqueta", default="base", help="nombre de la corrida: base, escalable...")
    parser.add_argument("--duracion", type=float, default=150, help="segundos (el enunciado pide 2 a 3 min)")
    parser.add_argument("--por-minuto", type=float, default=20, help="peticiones por minuto por cliente")
    args = parser.parse_args()

    total = sum(cantidad for cantidad, _ in ESCENARIOS[args.escenario])
    carpeta = config.RAIZ / "resultados" / f"{args.etiqueta}_{total}clientes"
    carpeta.mkdir(parents=True, exist_ok=True)
    for viejo in carpeta.glob("cliente_*.csv"):
        viejo.unlink()                     # que no se mezclen corridas anteriores

    procesos = []
    id_cliente = 0
    for cantidad, pct_consultas in ESCENARIOS[args.escenario]:
        for _ in range(cantidad):
            id_cliente += 1
            comando = [sys.executable, "-m", "capa_cliente.main", "--id", str(id_cliente), "--carga",
                       "--duracion", str(args.duracion), "--por-minuto", str(args.por_minuto),
                       "--consultas", str(pct_consultas),
                       "--salida", str(carpeta / f"cliente_{id_cliente}.csv")]
            procesos.append(subprocess.Popen(comando, cwd=config.RAIZ))

    print(f"Escenario {args.escenario}: {total} clientes durante {args.duracion:g} s...", flush=True)
    try:
        for p in procesos:
            p.wait()
    except KeyboardInterrupt:
        for p in procesos:
            p.terminate()
        raise
    print(f"Listo. Resultados en {carpeta}")
    print(f"Analizar:  python -m herramientas.analizar_metricas {carpeta} --gt <gt_metricas.csv>")


if __name__ == "__main__":
    main()
