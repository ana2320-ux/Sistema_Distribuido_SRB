"""GT FALSO para probar la capa de cliente sin los demás servicios.

Se comporta como el Gestor de Transacciones + RMC + Cancelación + Persistencia, todo en
memoria y con los mismos datos de init_bd.py (50 eventos, 20 con 2 ocurrencias,
100 asientos por ocurrencia). NO es parte del sistema final: solo sirve para validar
que el cliente cumple el contrato de mensajes.

Uso (desde la carpeta clientes/):
    python pruebas/probar_cliente.py                 # escucha en tcp://*:5550
    python pruebas/probar_cliente.py --puerto 5551 --retardo-ms 5
"""
import argparse
import json
import queue
import threading
import time

import zmq


def crear_datos(mes, anio):
    ocs, id_oc = [], 0
    for i in range(1, 51):
        n = 2 if i <= 20 else 1
        for k in range(n):
            id_oc += 1
            ocs.append({"id_evento": f"E{i}", "nombre": f"Evento {i}", "id_ocurrencia": id_oc,
                        "fecha": f"{anio}-{mes:02d}-{(i + 10 * k) % 28 + 1:02d}",
                        "capacidad": 100, "ocupados": 0, "libres": 100})
    return {o["id_ocurrencia"]: o for o in ocs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--puerto", type=int, default=5550)
    ap.add_argument("--mes", type=int, default=10)
    ap.add_argument("--anio", type=int, default=2026)
    ap.add_argument("--retardo-ms", type=float, default=0, help="latencia simulada por petición")
    ap.add_argument("--retardo-notif", type=float, default=0.3, help="segundos hasta enviar la notificación")
    a = ap.parse_args()

    ocs = crear_datos(a.mes, a.anio)
    reservas, sig = {}, [0]
    cola = queue.Queue()
    ctx = zmq.Context()

    def hilo_notificaciones():
        """Servicio de cancelación: espera, 'libera' y notifica DIRECTO al cliente (PUSH)."""
        while True:
            t, endpoint, msg = cola.get()
            time.sleep(max(0, t - time.time()))
            p = ctx.socket(zmq.PUSH)
            p.setsockopt(zmq.LINGER, 1000)
            p.connect(endpoint)
            p.send_json(msg)
            p.close()

    threading.Thread(target=hilo_notificaciones, daemon=True).start()

    def buscar_reserva(p, id_ocurrencia):
        """Por id_reserva si viene; si no, por (id_cliente, id_ocurrencia), como hace el repo."""
        if p.get("id_reserva") is not None:
            return reservas.get(p["id_reserva"])
        for rv in reservas.values():
            if rv["id_cliente"] == p.get("id_cliente") and rv["id_ocurrencia"] == id_ocurrencia:
                return rv
        return None

    rep = ctx.socket(zmq.REP)
    rep.bind(f"tcp://*:{a.puerto}")
    print(f"[GT-FALSO] escuchando en tcp://*:{a.puerto}  ({len(ocs)} ocurrencias)", flush=True)

    while True:
        try:
            m = json.loads(rep.recv())
            op, p = m["operacion"], m["payload"]
        except (ValueError, KeyError, TypeError):
            rep.send_json({"status": "ERROR", "mensaje": "MENSAJE_INVALIDO"})
            continue
        if a.retardo_ms:
            time.sleep(a.retardo_ms / 1000)

        if op == "CONSULTAR":
            fecha = f"{p.get('anio', a.anio)}-{int(p.get('mes', a.mes)):02d}"
            r = {"status": "OK", "data": [o for o in ocs.values() if o["fecha"].startswith(fecha)]}
        elif op == "RESERVAR":
            o, n = ocs.get(p.get("id_ocurrencia")), p.get("asientos", 0)
            if o is None or n <= 0:
                r = {"status": "ERROR", "mensaje": "DATOS_INVALIDOS"}
            elif o["libres"] < n:
                r = {"status": "RECHAZADO", "mensaje": "SIN_DISPONIBILIDAD"}
            else:
                o["libres"] -= n
                o["ocupados"] += n
                sig[0] += 1
                reservas[sig[0]] = {"id_cliente": p["id_cliente"], "id_ocurrencia": o["id_ocurrencia"], "asientos": n}
                r = {"status": "OK", "mensaje": "Reserva confirmada", "id_reserva": sig[0]}
        elif op == "MODIFICAR":
            # Mismo payload que el repo: id_cliente, id_ocurrencia_actual, id_ocurrencia_nueva, asientos
            rv = buscar_reserva(p, p.get("id_ocurrencia_actual"))
            nueva = ocs.get(p.get("id_ocurrencia_nueva", p.get("id_ocurrencia_actual")))
            if rv is None or nueva is None:
                r = {"status": "ERROR", "mensaje": "RESERVA_NO_EXISTE"}
            else:
                nuevo_o = nueva
                nuevo_n = p.get("asientos", rv["asientos"])
                viejo = ocs[rv["id_ocurrencia"]]
                disp = viejo["libres"] + rv["asientos"] if nuevo_o is viejo else nuevo_o["libres"]
                if nuevo_n > disp:
                    r = {"status": "RECHAZADO", "mensaje": "SIN_DISPONIBILIDAD"}
                else:
                    viejo["libres"] += rv["asientos"]; viejo["ocupados"] -= rv["asientos"]
                    nuevo_o["libres"] -= nuevo_n; nuevo_o["ocupados"] += nuevo_n
                    rv["id_ocurrencia"], rv["asientos"] = nuevo_o["id_ocurrencia"], nuevo_n
                    r = {"status": "OK", "mensaje": "Reserva modificada"}
        elif op == "CANCELAR":
            # Mismo payload que el repo: id_reserva, id_ocurrencia, asientos, endpoint_notificacion
            rv = buscar_reserva(p, p.get("id_ocurrencia"))
            if rv is None or "endpoint_notificacion" not in p:
                r = {"status": "ERROR", "mensaje": "RESERVA_NO_EXISTE_O_SIN_ENDPOINT"}
            else:
                rid = next(k for k, v in reservas.items() if v is rv)
                del reservas[rid]
                o = ocs[rv["id_ocurrencia"]]
                o["libres"] += rv["asientos"]; o["ocupados"] -= rv["asientos"]
                # Notificación con el mismo formato del servicio_cancelaciones del repo (sin campo id_reserva)
                cola.put((time.time() + a.retardo_notif, p["endpoint_notificacion"],
                          {"status": "OK", "mensaje": f"Cancelación de reserva #{rid} procesada exitosamente."}))
                # ACK inmediato, igual que el gestor_transacciones del repo
                r = {"status": "ACEPTADO",
                     "mensaje": "Solicitud de cancelación recibida. Recibirá una notificación al procesarse."}
        else:
            r = {"status": "ERROR", "mensaje": "OPERACION_DESCONOCIDA"}
        rep.send_json(r)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
