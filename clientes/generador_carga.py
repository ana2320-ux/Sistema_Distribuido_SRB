"""Generador de carga del SRB a partir de un archivo de entrada (escenario JSON).

Lanza un proceso por cliente (multiprocessing), todos a la vez, durante ``duracion_seg``.
El número de solicitudes por minuto (rpm) y el porcentaje de cada operación son
parametrizables por cliente o por grupo de clientes en el archivo de escenario.

Formato del escenario (ver escenarios/*.json):
{
  "nombre": "3_clientes",
  "duracion_seg": 120,
  "grupos": [
    {"prefijo": "CQ", "cantidad": 2, "rpm": 60, "mezcla": {"consulta": 100}},
    {"prefijo": "CR", "cantidad": 1, "rpm": 60, "mezcla": {"consulta": 50, "reserva": 50}}
  ]
}

Uso:
    python generador_carga.py escenarios/escenario_3_clientes.json
    python generador_carga.py escenarios/escenario_8_clientes.json --duracion 150 --rpm 120
    python generador_carga.py escenarios/escenario_5_clientes.json --gt tcp://192.168.1.10:5550
"""
import argparse
import json
import multiprocessing as mp
import os
import shutil
import time

import cliente as cl
import metricas_clientes as mc


def _correr(args):
    cid, cfg, params, duracion, salida, gt, semilla = args
    c = cl.Cliente(cid, cfg, rpm=params["rpm"],
                   pct_consulta=params["mezcla"].get("consulta", 0),
                   pct_reserva=params["mezcla"].get("reserva", 0),
                   pct_modificacion=params["mezcla"].get("modificacion", 0),
                   pct_cancelacion=params["mezcla"].get("cancelacion", 0),
                   semilla=semilla, gt=gt, salida=salida, silencioso=True)
    return cid, c.ejecutar(duracion)


def main():
    ap = argparse.ArgumentParser(description="Generador de carga SRB (archivo de entrada)")
    ap.add_argument("escenario", help="ruta del JSON del escenario")
    ap.add_argument("--config", default=None)
    ap.add_argument("--duracion", type=float, default=None, help="sobrescribe duracion_seg")
    ap.add_argument("--rpm", type=float, default=None, help="sobrescribe las rpm de todos los grupos")
    ap.add_argument("--gt", default=None, help="endpoint(s) GT separados por coma (sobrescribe la config)")
    ap.add_argument("--salida", default=None, help="carpeta de resultados (por defecto resultados/<nombre>)")
    ap.add_argument("--semilla", type=int, default=1)
    a = ap.parse_args()

    with open(a.escenario, encoding="utf-8") as f:
        esc = json.load(f)
    cfg = cl.cargar_config(a.config)
    duracion = a.duracion or esc["duracion_seg"]
    salida = a.salida or os.path.join(cfg.get("carpeta_salida", "resultados"), esc["nombre"])
    if os.path.isdir(salida):
        shutil.rmtree(salida)
    os.makedirs(salida)
    gt = a.gt.split(",") if a.gt else esc.get("gt") or None

    tareas, k = [], 0
    for g in esc["grupos"]:
        g = dict(g)
        if a.rpm:
            g["rpm"] = a.rpm
        if g["rpm"] < 20:
            print(f"AVISO: grupo {g['prefijo']} con rpm={g['rpm']} < 20 (mínimo del enunciado)")
        for i in range(1, g["cantidad"] + 1):
            k += 1
            tareas.append((f"{g['prefijo']}{i}", cfg, g, duracion, salida, gt, a.semilla + k))

    print(f"Escenario '{esc['nombre']}': {len(tareas)} clientes, {duracion:.0f} s, resultados en {salida}", flush=True)
    t0 = time.time()
    with mp.Pool(len(tareas)) as pool:
        res = pool.map(_correr, tareas)
    print(f"Terminado en {time.time() - t0:.1f} s")
    for cid, r in res:
        print(f"  {cid}: {r}")
    cambiadas = sum(r["cambiadas"] for _, r in res)
    if cambiadas:
        print(f"AVISO: {cambiadas} operaciones de modificación/cancelación se reemplazaron por reservas "
              f"porque el cliente no tenía reservas; la mezcla real difiere de la del escenario.")
    print()
    mc.reportar(salida)


if __name__ == "__main__":
    main()
