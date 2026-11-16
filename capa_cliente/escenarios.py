"""
Lanza los escenarios de la Tabla 1 del enunciado. Cada cliente es un proceso aparte.

  Escenario 1: 3 clientes  -> 2 solo consultan, 1 consulta y reserva
  Escenario 2: 5 clientes  -> 3 solo consultan, 2 reservan y modifican
  Escenario 3: 8 clientes  -> 4 solo consultan, 4 reservan y modifican

Uso (en la maquina de clientes, desde la raiz):
    python -m capa_cliente.escenarios --escenario 1 --etiqueta base
    python -m capa_cliente.escenarios --escenario 3 --etiqueta base --duracion 150 --por-minuto 20
    python -m capa_cliente.escenarios --escenario 1 --etiqueta escalable --corrida 2

Cada corrida queda en resultados/<etiqueta>_<N>clientes/corrida_<n>/, un CSV por cliente.
La semilla del azar de cada cliente depende de la corrida y de su id: la misma corrida
envia las mismas operaciones en la arquitectura base y en la escalable.
"""
import argparse
import subprocess
import sys

from config import configuracion as config

# escenario -> lista de (cantidad de clientes, % de consultas, % de las escrituras que son modificaciones)
ESCENARIOS = {
    1: [(2, 100, 0), (1, 50, 0)],
    2: [(3, 100, 0), (2, 0, 50)],
    3: [(4, 100, 0), (4, 0, 50)],
}


def main():
    parser = argparse.ArgumentParser(description="Escenarios de la Tabla 1")
    parser.add_argument("--escenario", type=int, choices=ESCENARIOS, required=True)
    parser.add_argument("--etiqueta", default="base", help="nombre de la corrida: base, escalable...")
    parser.add_argument("--duracion", type=float, default=150, help="segundos (el enunciado pide 2 a 3 min)")
    parser.add_argument("--por-minuto", type=float, default=20, help="peticiones por minuto por cliente")
    parser.add_argument("--corrida", type=int, default=1, help="numero de la repeticion (1, 2, 3...)")
    args = parser.parse_args()

    total = sum(cantidad for cantidad, _, _ in ESCENARIOS[args.escenario])
    carpeta = config.RAIZ / "resultados" / f"{args.etiqueta}_{total}clientes" / f"corrida_{args.corrida}"
    carpeta.mkdir(parents=True, exist_ok=True)
    for viejo in carpeta.glob("cliente_*.csv"):
        viejo.unlink()                     # que no se mezclen corridas anteriores

    procesos = []
    id_cliente = 0
    for cantidad, pct_consultas, pct_modificaciones in ESCENARIOS[args.escenario]:
        for _ in range(cantidad):
            id_cliente += 1
            comando = [sys.executable, "-m", "capa_cliente.main", "--id", str(id_cliente), "--carga",
                       "--duracion", str(args.duracion), "--por-minuto", str(args.por_minuto),
                       "--consultas", str(pct_consultas), "--modificaciones", str(pct_modificaciones),
                       "--semilla", str(args.corrida * 100 + id_cliente),
                       "--salida", str(carpeta / f"cliente_{id_cliente}.csv")]
            procesos.append(subprocess.Popen(comando, cwd=config.RAIZ))

    print(f"Escenario {args.escenario}, corrida {args.corrida}: {total} clientes durante {args.duracion:g} s...",
          flush=True)
    try:
        for p in procesos:
            p.wait()
    except KeyboardInterrupt:
        for p in procesos:
            p.terminate()
        raise
    print(f"Listo. Resultados en {carpeta}")
    print("Analizar:  python -m herramientas.analizar_metricas")


if __name__ == "__main__":
    main()
