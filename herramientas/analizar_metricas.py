"""
Calcula las metricas de desempeno de la Tabla 1 del enunciado a partir de los CSV de las corridas.

Lee, dentro de la carpeta de resultados, las carpetas <etiqueta>_<N>clientes (las crea
capa_cliente.escenarios), con una subcarpeta por corrida, y el CSV del Gestor de
Transacciones. Para cada arquitectura (etiqueta), numero de clientes y operacion calcula:

  - tiempo de respuesta: promedio, desviacion estandar y percentil 95, en milisegundos
    (medido en el cliente: desde que envia la peticion hasta que recibe la respuesta)
  - transacciones por minuto (TPM), contadas en el Gestor de Transacciones
  - tasa de error: porcentaje de peticiones que terminaron en ERROR

Las filas del GT se asocian a cada corrida por el uuid de la peticion, asi que no importa
que el CSV del GT tenga otras corridas ni que los relojes de las maquinas no coincidan.
Si no hay CSV del GT, las TPM se cuentan con las respuestas que recibieron los clientes.

Uso (desde la raiz del proyecto):
    python -m herramientas.analizar_metricas                              # resultados/ y resultados/gt_metricas.csv
    python -m herramientas.analizar_metricas resultados --gt gt_base.csv gt_escalable.csv

Deja resultados/resumen.csv y, si esta matplotlib, los graficos en resultados/graficos/.
"""
import argparse
import csv
import re
import statistics
from pathlib import Path

from config import configuracion as config

OPERACIONES = ["CONSULTA", "RESERVA", "MODIFICACION", "CANCELACION"]
COLUMNAS = ["arquitectura", "clientes", "operacion", "corridas", "peticiones", "promedio_ms",
            "desviacion_ms", "p95_ms", "tpm", "tasa_error_pct", "tpm_medidas_en"]


def leer_csv(ruta):
    with open(ruta, newline="", encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def percentil_95(valores):
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, round(0.95 * (len(ordenados) - 1)))]


def analizar(carpeta, rutas_gt):
    """Devuelve una lista de filas (diccionarios con las COLUMNAS), una por arquitectura, clientes y operacion."""
    uuids_gt = {fila["uuid"] for ruta in rutas_gt for fila in leer_csv(ruta)}
    filas = []
    for carpeta_escenario in sorted(Path(carpeta).iterdir()):
        nombre = re.fullmatch(r"(.+)_(\d+)clientes", carpeta_escenario.name)
        if not carpeta_escenario.is_dir() or not nombre:
            continue
        arquitectura, clientes = nombre.group(1), int(nombre.group(2))

        # Una corrida = una subcarpeta con los CSV de sus clientes (o los CSV sueltos, si no hay subcarpetas)
        corridas = [c for c in sorted(carpeta_escenario.iterdir()) if c.is_dir()] or [carpeta_escenario]
        peticiones = {op: [] for op in OPERACIONES}          # operacion -> filas de todas las corridas
        tpm = {op: [] for op in OPERACIONES}                 # operacion -> TPM de cada corrida
        for corrida in corridas:
            filas_corrida = [f for ruta in sorted(corrida.glob("cliente_*.csv")) for f in leer_csv(ruta)]
            if not filas_corrida:
                continue
            envios = [float(f["hora_envio"]) for f in filas_corrida]
            minutos = (max(envios) - min(envios)) / 60 or 1 / 60
            for op in OPERACIONES:
                de_la_operacion = [f for f in filas_corrida if f["tipo"] == op]
                peticiones[op] += de_la_operacion
                if uuids_gt:
                    procesadas = sum(1 for f in de_la_operacion if f["uuid"] in uuids_gt)
                else:
                    procesadas = sum(1 for f in de_la_operacion if f["estado"] != "ERROR")
                tpm[op].append(procesadas / minutos)

        for op in OPERACIONES:
            if not peticiones[op]:
                continue
            # tiempos de las peticiones que si tuvieron respuesta del sistema
            tiempos = [float(f["ms"]) for f in peticiones[op] if f["estado"] != "ERROR"]
            errores = len(peticiones[op]) - len(tiempos)
            filas.append({
                "arquitectura": arquitectura, "clientes": clientes, "operacion": op,
                "corridas": len(tpm[op]), "peticiones": len(peticiones[op]),
                "promedio_ms": round(statistics.mean(tiempos), 2) if tiempos else "",
                "desviacion_ms": round(statistics.stdev(tiempos), 2) if len(tiempos) > 1 else 0.0,
                "p95_ms": round(percentil_95(tiempos), 2) if tiempos else "",
                "tpm": round(statistics.mean(tpm[op]), 1),
                "tasa_error_pct": round(100 * errores / len(peticiones[op]), 2),
                "tpm_medidas_en": "GT" if uuids_gt else "cliente",
            })
    return filas


def imprimir(filas):
    print(f"{'arquitectura':<14}{'clientes':>8}  {'operacion':<13}{'peticiones':>10}{'promedio ms':>13}"
          f"{'desv. ms':>10}{'p95 ms':>9}{'TPM':>8}{'error %':>9}")
    for f in filas:
        print(f"{f['arquitectura']:<14}{f['clientes']:>8}  {f['operacion']:<13}{f['peticiones']:>10}"
              f"{f['promedio_ms']:>13}{f['desviacion_ms']:>10}{f['p95_ms']:>9}{f['tpm']:>8}{f['tasa_error_pct']:>9}")


def graficar(filas, carpeta):
    """Un grafico por metrica y operacion: la metrica en funcion del numero de clientes, una linea por arquitectura."""
    import matplotlib
    matplotlib.use("Agg")                    # sin ventana: solo guarda los archivos
    import matplotlib.pyplot as plt

    carpeta.mkdir(parents=True, exist_ok=True)
    metricas = [("promedio_ms", "Tiempo promedio de respuesta (ms)", "tiempo_promedio"),
                ("p95_ms", "Percentil 95 del tiempo de respuesta (ms)", "percentil_95"),
                ("tpm", "Transacciones por minuto (TPM)", "tpm"),
                ("tasa_error_pct", "Tasa de error (%)", "tasa_error")]
    marcadores = "osD^v"
    for op in OPERACIONES:
        de_la_operacion = [f for f in filas if f["operacion"] == op and f["promedio_ms"] != ""]
        if not de_la_operacion:
            continue
        for columna, titulo, archivo in metricas:
            figura, ejes = plt.subplots(figsize=(6.4, 4))
            for i, arquitectura in enumerate(sorted({f["arquitectura"] for f in de_la_operacion})):
                puntos = sorted((f for f in de_la_operacion if f["arquitectura"] == arquitectura),
                                key=lambda f: f["clientes"])
                x = [f["clientes"] for f in puntos]
                y = [f[columna] for f in puntos]
                barras = [f["desviacion_ms"] for f in puntos] if columna == "promedio_ms" else None
                ejes.errorbar(x, y, yerr=barras, marker=marcadores[i % len(marcadores)], capsize=4,
                              linewidth=1.8, label=f"Arquitectura {arquitectura}")
            ejes.set_title(f"{titulo}\n{op.capitalize()}" +
                           (" (barras: desviación estándar)" if columna == "promedio_ms" else ""), fontsize=11)
            ejes.set_xlabel("Número de clientes simultáneos")
            ejes.set_ylabel(titulo)
            ejes.set_xticks(sorted({f["clientes"] for f in de_la_operacion}))
            ejes.set_ylim(bottom=0)
            ejes.grid(alpha=0.3)
            ejes.legend()
            figura.tight_layout()
            figura.savefig(carpeta / f"{archivo}_{op.lower()}.png", dpi=150)
            plt.close(figura)


def main():
    parser = argparse.ArgumentParser(description="Metricas de desempeno de las corridas del SRB")
    parser.add_argument("carpeta", nargs="?", default=config.RAIZ / "resultados", type=Path,
                        help="carpeta con las corridas (por defecto resultados/)")
    parser.add_argument("--gt", nargs="*", type=Path,
                        help="CSV del Gestor de Transacciones (por defecto <carpeta>/gt_metricas.csv)")
    args = parser.parse_args()

    rutas_gt = args.gt if args.gt is not None else [r for r in [args.carpeta / "gt_metricas.csv"] if r.exists()]
    filas = analizar(args.carpeta, rutas_gt)
    if not filas:
        print(f"No hay corridas en {args.carpeta} (carpetas <etiqueta>_<N>clientes)")
        return
    imprimir(filas)
    print("TPM medidas en:", "el Gestor de Transacciones" if rutas_gt else
          "los clientes (no se encontro el CSV del GT; indicarlo con --gt)")

    with open(args.carpeta / "resumen.csv", "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS)
        escritor.writeheader()
        escritor.writerows(filas)
    print(f"Tabla guardada en {args.carpeta / 'resumen.csv'}")
    try:
        graficar(filas, args.carpeta / "graficos")
        print(f"Graficos guardados en {args.carpeta / 'graficos'}")
    except ImportError:
        print("Sin graficos: falta matplotlib (pip install matplotlib)")


if __name__ == "__main__":
    main()
