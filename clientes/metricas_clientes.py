"""Métricas de la Tabla 1 a partir de los CSV de los clientes.

Por tipo de operación (consulta, reserva, modificacion, cancelacion, notificacion):
  n, exitosas, tiempo promedio de respuesta (ms), desviación estándar (ms), TPM.
  El tiempo promedio y la desviación usan solo las solicitudes exitosas (ok = 1).

TPM = transacciones por minuto = n / (minutos de la corrida), con la ventana medida
entre la primera y la última solicitud de TODOS los clientes. Ojo: aquí se mide desde
el lado del cliente; el enunciado también acepta medirlo en el GT o la BD (ver README).

Uso:  python metricas_clientes.py resultados/3_clientes
"""
import csv
import glob
import os
import statistics
import sys

TIPOS = ["consulta", "reserva", "modificacion", "cancelacion", "notificacion"]


def calcular(carpeta):
    filas = []
    for ruta in sorted(glob.glob(os.path.join(carpeta, "cliente_*.csv"))):
        with open(ruta, newline="") as f:
            for r in csv.DictReader(f):
                r["cliente"] = os.path.basename(ruta)[8:-4]
                filas.append(r)
    if not filas:
        return {}, 0.0
    ts = [float(r["ts"]) for r in filas if r["tipo"] != "notificacion"]
    minutos = max((max(ts) - min(ts)) / 60.0, 1e-9)
    out = {}
    for t in TIPOS:
        sel = [r for r in filas if r["tipo"] == t]
        if not sel:
            continue
        # El tiempo de respuesta se calcula SOLO con las solicitudes exitosas: un TIMEOUT
        # registra ~timeout_ms sin que haya habido respuesta e inflaría media y desviación.
        # Las fallidas se reportan aparte (columna n vs ok).
        oks = [float(r["latencia_ms"]) for r in sel if r["ok"] == "1"]
        out[t] = {"n": len(sel), "ok": len(oks),
                  "media_ms": statistics.mean(oks) if oks else None,
                  "desv_ms": statistics.stdev(oks) if len(oks) > 1 else (0.0 if oks else None),
                  "tpm": len(sel) / minutos if t != "notificacion" else None,
                  "tpm_ok": len(oks) / minutos if t != "notificacion" else None}
    return out, minutos


def reportar(carpeta, guardar=True):
    out, minutos = calcular(carpeta)
    if not out:
        print("Sin datos en", carpeta)
        return
    print(f"MÉTRICAS ({carpeta}) - ventana {minutos:.2f} min")
    print(f"{'operación':<13}{'n':>7}{'ok':>7}{'media ms':>11}{'desv ms':>10}{'TPM':>9}{'TPM ok':>8}")
    for t, m in out.items():
        tpm = f"{m['tpm']:.1f}" if m["tpm"] is not None else "-"
        tpm_ok = f"{m['tpm_ok']:.1f}" if m["tpm_ok"] is not None else "-"
        media = f"{m['media_ms']:.2f}" if m["media_ms"] is not None else "-"
        desv = f"{m['desv_ms']:.2f}" if m["desv_ms"] is not None else "-"
        print(f"{t:<13}{m['n']:>7}{m['ok']:>7}{media:>11}{desv:>10}{tpm:>9}{tpm_ok:>8}")
    fallidas = sum(m["n"] - m["ok"] for m in out.values())
    if fallidas:
        print(f"\n(media y desv. calculadas solo con las exitosas; {fallidas} solicitudes fallidas no entran)")
    if guardar:
        ruta = os.path.join(carpeta, "resumen.csv")
        with open(ruta, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["operacion", "n", "ok", "media_ms", "desv_ms", "tpm", "tpm_ok"])
            for t, m in out.items():
                w.writerow([t, m["n"], m["ok"],
                            "" if m["media_ms"] is None else f"{m['media_ms']:.3f}",
                            "" if m["desv_ms"] is None else f"{m['desv_ms']:.3f}",
                            "" if m["tpm"] is None else f"{m['tpm']:.2f}",
                            "" if m["tpm_ok"] is None else f"{m['tpm_ok']:.2f}"])
        print(f"\nResumen guardado en {ruta}")


if __name__ == "__main__":
    reportar(sys.argv[1] if len(sys.argv) > 1 else "resultados")
