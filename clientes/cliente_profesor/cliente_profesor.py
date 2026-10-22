"""Cliente para el CASO DE PRUEBA del profesor (sustentación).

A diferencia de generador_carga.py (operaciones al azar para medir rendimiento), este
script ejecuta una lista EXACTA de operaciones, en el orden de un archivo de texto, y
muestra el estado de los eventos involucrados ANTES y DESPUÉS, para comparar la BD con
el resultado que espera el profesor.

Formato del archivo (una operación por línea; lo que va después de # es comentario):

    # cliente  OPERACION  datos...                          => resultado esperado (opcional)
    C1  CONSULTAR
    C1  RESERVAR   E5  1  4                                 => OK
    C2  RESERVAR   E5  1  96
    C3  RESERVAR   E5  1  1                                 => RECHAZADO
    C1  MODIFICAR  E1  1  2  4      # de la ocurrencia 1 a la 2, con 4 asientos
    C1  CANCELAR   E1  2  4         # cancela la reserva de 4 asientos en la ocurrencia 2

  * Los eventos se escriben como E5 (o 5) y la ocurrencia como 1 o 2: es la 1.a o 2.a
    fecha del evento en el mes. El script la traduce al id_ocurrencia de la BD con una
    consulta inicial, así el archivo se escribe con los datos que da el profesor.
  * RESERVAR  evento ocurrencia asientos
    MODIFICAR evento ocurrencia_actual ocurrencia_nueva asientos
              (cambio de fecha: nueva distinta; cambio de asientos: nueva = actual)
    CANCELAR  evento ocurrencia asientos
  * "=> OK", "=> RECHAZADO", "=> ERROR" o "=> ACEPTADO" al final de la línea es opcional:
    si está, el script compara el resultado real con el esperado.

Las operaciones se envían una tras otra (aunque sean de clientes distintos) para que el
resultado sea predecible. Cada una queda también en resultados/caso_profesor/cliente_PROFESOR.csv.

Ubicación: clientes/cliente_profesor/cliente_profesor.py, con los casos en
clientes/cliente_profesor/casos/. Usa cliente.py y config_cliente.json de clientes/.

Uso (desde la carpeta clientes/):
    python cliente_profesor/cliente_profesor.py caso_ejemplo.txt
    python cliente_profesor/cliente_profesor.py caso_ejemplo.txt --gt tcp://10.43.100.36:5557
  (si se da solo el nombre, el archivo se busca en cliente_profesor/casos/; también acepta una ruta)
"""
import argparse
import os
import sys
import time

import zmq

# Este script vive en clientes/cliente_profesor/, pero usa cliente.py y config_cliente.json,
# que están en clientes/. Python solo busca imports en la carpeta del script que se ejecuta,
# así que se agrega la carpeta de arriba (clientes/) a la ruta de búsqueda antes del import.
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))

import cliente as cl  # noqa: E402  (debe ir después de ajustar sys.path)

OPERACIONES = {
    # nombre: (tipo para el CSV, cantidad de datos después de la operación)
    "CONSULTAR": ("consulta", 0),
    "RESERVAR": ("reserva", 3),
    "MODIFICAR": ("modificacion", 4),
    "CANCELAR": ("cancelacion", 3),
}
ESTADOS = {"OK", "RECHAZADO", "ERROR", "ACEPTADO"}


class ErrorCaso(Exception):
    pass


# ----------------------------------------------------------------- lectura del caso
def leer_caso(ruta):
    """Lee y valida el archivo completo ANTES de enviar nada al sistema."""
    pasos = []
    with open(ruta, encoding="utf-8") as f:
        for num, linea in enumerate(f, 1):
            texto = linea.split("#", 1)[0].strip()
            if not texto:
                continue
            esperado = None
            if "=>" in texto:
                texto, esperado = (p.strip() for p in texto.split("=>", 1))
                esperado = esperado.upper()
                if esperado not in ESTADOS:
                    raise ErrorCaso(f"línea {num}: resultado esperado '{esperado}' no válido "
                                    f"(use {', '.join(sorted(ESTADOS))})")
            partes = texto.split()
            if len(partes) < 2:
                raise ErrorCaso(f"línea {num}: falta la operación -> '{linea.strip()}'")
            id_cliente, op, datos = partes[0], partes[1].upper(), partes[2:]
            if op not in OPERACIONES:
                raise ErrorCaso(f"línea {num}: operación '{partes[1]}' desconocida "
                                f"(use {', '.join(OPERACIONES)})")
            if len(datos) != OPERACIONES[op][1]:
                raise ErrorCaso(f"línea {num}: {op} lleva {OPERACIONES[op][1]} datos y tiene {len(datos)}")
            if datos:
                evento = datos[0].upper()
                evento = evento if evento.startswith("E") else f"E{evento}"
                try:
                    numeros = [int(x) for x in datos[1:]]
                except ValueError:
                    raise ErrorCaso(f"línea {num}: ocurrencias y asientos deben ser números")
                if numeros[-1] <= 0:
                    raise ErrorCaso(f"línea {num}: los asientos deben ser mayores que 0")
            else:
                evento, numeros = None, []
            pasos.append({"linea": num, "cliente": id_cliente, "op": op, "evento": evento,
                          "numeros": numeros, "esperado": esperado})
    if not pasos:
        raise ErrorCaso("el archivo no tiene operaciones")
    return pasos


# ------------------------------------------------------- traducción evento -> ocurrencia
def mapa_ocurrencias(data):
    """{'E5': [ocurrencia1, ocurrencia2]} ordenadas por fecha (1.a y 2.a fecha del evento)."""
    mapa = {}
    for o in data:
        mapa.setdefault(o["id_evento"], []).append(o)
    for lista in mapa.values():
        lista.sort(key=lambda o: (o["fecha"], o["id_ocurrencia"]))
    return mapa


def ocurrencia(mapa, evento, k, linea):
    if evento not in mapa:
        raise ErrorCaso(f"línea {linea}: el evento {evento} no existe en la BD")
    if not 1 <= k <= len(mapa[evento]):
        raise ErrorCaso(f"línea {linea}: {evento} tiene {len(mapa[evento])} ocurrencia(s), no existe la #{k}")
    return mapa[evento][k - 1]


# ------------------------------------------------------------------- presentación
def tabla_estado(titulo, mapa, involucradas, antes=None):
    print(f"\n{titulo}")
    print(f"  {'evento':<7}{'#':>2}  {'fecha':<11}{'id_oc':>6}{'ocupados':>10}{'libres':>8}"
          + ("    cambio" if antes else ""))
    for evento, k in involucradas:
        o = mapa[evento][k - 1]
        fila = (f"  {evento:<7}{k:>2}  {o['fecha']:<11}{o['id_ocurrencia']:>6}"
                f"{o['ocupados']:>10}{o['libres']:>8}")
        if antes:
            d = o["ocupados"] - antes[evento][k - 1]["ocupados"]
            fila += f"    {d:+d} ocupados" if d else "    sin cambio"
        print(fila)


def consultar(c, quien="PROFESOR"):
    resp, ok, lat = c._enviar("consulta", "CONSULTAR",
                              {"id_cliente": quien, "mes": c.cfg["mes"], "anio": c.cfg["anio"]})
    if not ok or not resp.get("data"):
        raise ErrorCaso(f"la consulta al GT falló: {resp.get('mensaje', 'sin respuesta (¿GT encendido?)')}")
    return resp, lat


def validar_eventos(pasos, cfg, gt):
    """Valida eventos y ocurrencias del caso contra la BD ANTES de crear el Cliente.

    El Cliente abre cliente_PROFESOR.csv en modo "w" al crearse, así que si la validación
    se hiciera con él, un caso inválido borraría el CSV de la corrida anterior. Por eso
    esta consulta va por un socket REQ aparte que no escribe nada.
    """
    ctx = zmq.Context()
    s = ctx.socket(zmq.REQ)
    s.setsockopt(zmq.RCVTIMEO, cfg["timeout_ms"])
    s.setsockopt(zmq.SNDTIMEO, cfg["timeout_ms"])
    s.setsockopt(zmq.LINGER, 0)
    for ep in gt:
        s.connect(ep)
    try:
        s.send_json({"operacion": "CONSULTAR",
                     "payload": {"id_cliente": "PROFESOR", "mes": cfg["mes"], "anio": cfg["anio"]}})
        resp = s.recv_json()
    except zmq.ZMQError:
        resp = {}
    finally:
        s.close()
        ctx.term()
    if resp.get("status") != "OK" or not resp.get("data"):
        raise ErrorCaso(f"la consulta al GT falló: {resp.get('mensaje', 'sin respuesta (¿GT encendido?)')}")
    mapa = mapa_ocurrencias(resp["data"])
    for p in pasos:
        for k in p["numeros"][:-1]:          # todos los números menos el último son ocurrencias
            ocurrencia(mapa, p["evento"], k, p["linea"])


# -------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Ejecuta el caso de prueba del profesor (operaciones exactas)")
    ap.add_argument("caso", help="archivo de texto con las operaciones")
    ap.add_argument("--gt", default=None, help="endpoint(s) del GT separados por coma (sobrescribe la config)")
    ap.add_argument("--config", default=None)
    # Por defecto clientes/resultados/caso_profesor, sin importar desde qué carpeta se ejecute
    ap.add_argument("--salida", default=os.path.join(os.path.dirname(AQUI), "resultados", "caso_profesor"),
                    help="carpeta del CSV")
    ap.add_argument("--pausa", type=float, default=0, help="segundos de espera entre operaciones")
    ap.add_argument("--espera-notif", type=float, default=5,
                    help="segundos máximos de espera por notificaciones de cancelación al final")
    a = ap.parse_args()

    # Si se da solo el nombre del archivo (p. ej. caso_ejemplo.txt), se busca en cliente_profesor/casos/
    if not os.path.exists(a.caso) and os.path.exists(os.path.join(AQUI, "casos", a.caso)):
        a.caso = os.path.join(AQUI, "casos", a.caso)

    try:
        pasos = leer_caso(a.caso)
    except (OSError, ErrorCaso) as e:
        print(f"Error en el archivo del caso: {e}")
        sys.exit(1)

    cfg = cl.cargar_config(a.config)
    gt = a.gt.split(",") if a.gt else cfg["gt_endpoints"]
    print(f"Caso: {a.caso} ({len(pasos)} operaciones) | GT: {', '.join(gt)}")
    try:
        validar_eventos(pasos, cfg, gt)
    except ErrorCaso as e:
        print(f"\nError: {e}")
        sys.exit(1)

    c = cl.Cliente("PROFESOR", cfg, gt=gt, salida=a.salida)
    try:
        # 1) Estado inicial (los eventos/ocurrencias ya se validaron arriba)
        resp, _ = consultar(c)
        antes = mapa_ocurrencias(resp["data"])
        involucradas = []
        for p in pasos:
            if p["evento"] is None:
                continue
            for k in p["numeros"][:-1]:          # todos los números menos el último son ocurrencias
                ocurrencia(antes, p["evento"], k, p["linea"])
                if (p["evento"], k) not in involucradas:
                    involucradas.append((p["evento"], k))
        if involucradas:
            tabla_estado("ESTADO INICIAL (eventos del caso)", antes, involucradas)

        # 2) Ejecutar las operaciones en orden
        print("\nOPERACIONES")
        coinciden = no_coinciden = 0
        cancelaciones = []
        for i, p in enumerate(pasos, 1):
            op, ev, n = p["op"], p["evento"], p["numeros"]
            if op == "CONSULTAR":
                resp, lat = consultar(c, p["cliente"])
                desc = "CONSULTAR"
                status, detalle = resp.get("status"), f"{len(resp['data'])} ocurrencias"
            else:
                tipo = OPERACIONES[op][0]
                o = ocurrencia(antes, ev, n[0], p["linea"])
                if op == "RESERVAR":
                    desc = f"RESERVAR  {ev} #{n[0]} x{n[1]}"
                    payload = {"id_cliente": p["cliente"], "id_ocurrencia": o["id_ocurrencia"], "asientos": n[1]}
                    estados_ok = ("OK",)
                elif op == "MODIFICAR":
                    nueva = ocurrencia(antes, ev, n[1], p["linea"])
                    desc = f"MODIFICAR {ev} #{n[0]} -> #{n[1]} x{n[2]}"
                    payload = {"id_cliente": p["cliente"], "id_ocurrencia_actual": o["id_ocurrencia"],
                               "id_ocurrencia_nueva": nueva["id_ocurrencia"], "asientos": n[2]}
                    estados_ok = ("OK",)
                else:  # CANCELAR
                    desc = f"CANCELAR  {ev} #{n[0]} x{n[1]}"
                    payload = {"id_cliente": p["cliente"], "id_reserva": None,
                               "id_ocurrencia": o["id_ocurrencia"], "asientos": n[1],
                               "endpoint_notificacion": c.endpoint_notif}
                    estados_ok = ("OK", "ACEPTADO")
                    cancelaciones.append((time.perf_counter(), p["cliente"], desc))
                resp, ok, lat = c._enviar(tipo, op, payload, estados_ok=estados_ok)
                status = resp.get("status", "SIN_RESPUESTA")
                detalle = resp.get("mensaje", "TIMEOUT" if not resp else "")

            marca = ""
            if p["esperado"]:
                if status == p["esperado"]:
                    coinciden += 1
                    marca = "   [coincide]"
                else:
                    no_coinciden += 1
                    marca = f"   [NO COINCIDE: se esperaba {p['esperado']}]"
            print(f"  {i:>3}. [{p['cliente']}] {desc:<28} -> {status}: {detalle} ({lat:.1f} ms){marca}")
            if a.pausa:
                time.sleep(a.pausa)

        # 3) Notificaciones de cancelación (llegan después, por el socket PULL)
        if cancelaciones:
            print("\nNOTIFICACIONES DE CANCELACIÓN")
            fin = time.time() + a.espera_notif
            recibidas = 0
            while recibidas < len(cancelaciones) and time.time() < fin:
                try:
                    msg = c.pull.recv_json(zmq.NOBLOCK)
                except zmq.Again:
                    time.sleep(0.05)
                    continue
                t0, quien, desc = cancelaciones[recibidas]
                recibidas += 1
                print(f"  [{quien}] {desc}: {msg.get('status')} - {msg.get('mensaje')} "
                      f"({(time.perf_counter() - t0) * 1000:.0f} ms después de enviarla)")
            if recibidas < len(cancelaciones):
                print(f"  Faltan {len(cancelaciones) - recibidas} notificaciones (revise host_notificaciones en config_cliente.json)")
            time.sleep(0.5)   # margen para que la BD refleje las cancelaciones antes de la consulta final

        # 4) Estado final
        if involucradas:
            resp, _ = consultar(c)
            despues = mapa_ocurrencias(resp["data"])
            tabla_estado("ESTADO FINAL (eventos del caso)", despues, involucradas, antes=antes)

        if coinciden or no_coinciden:
            print(f"\nResultados esperados: {coinciden} coinciden, {no_coinciden} no coinciden")
        print(f"\nDetalle guardado en {a.salida}/cliente_PROFESOR.csv")
    except ErrorCaso as e:
        print(f"\nError: {e}")
        sys.exit(1)
    finally:
        c.f.close()
        c.sock.close()
        c.pull.close()
        c.ctx.term()


if __name__ == "__main__":
    main()