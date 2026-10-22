"""Cliente del SRB (capa de consumidores).

Cada cliente simula un usuario que envía solicitudes al Gestor de Transacciones (GT):

  * SÍNCRONAS (REQ/REP de ZeroMQ): CONSULTAR, RESERVAR, MODIFICAR
  * ASÍNCRONA: CANCELAR -> el GT responde un ACK inmediato y, cuando la cancelación
    se efectúa de verdad, el servicio de cancelación envía una NOTIFICACIÓN directamente
    a este cliente. Para eso el cliente abre un socket PULL y manda su dirección
    (``endpoint_notificacion``) dentro del mensaje de cancelación.

Formato de mensajes (el mismo del repo: modelo_negocio/ y persistencia/):

    petición  {"operacion": "CONSULTAR|RESERVAR|MODIFICAR|CANCELAR", "payload": {...}}
    respuesta {"status": "OK|RECHAZADO|ERROR", "mensaje": "...", ...}

    RESERVAR   payload: id_cliente, id_ocurrencia, asientos
               (si la respuesta trae id_reserva se guarda; si no, se sigue sin él)
    MODIFICAR  payload: id_cliente, id_ocurrencia_actual, id_ocurrencia_nueva, asientos
               (cambio de fecha: nueva != actual y asientos = los de la reserva;
                cambio de asientos: nueva == actual y asientos = el nuevo número)
    CANCELAR   payload: id_cliente, id_reserva, id_ocurrencia, asientos, endpoint_notificacion
               ACK inmediato del GT con status "ACEPTADO"
    notificación (llega por PULL) {"status": "OK|ERROR", "mensaje": "..."}
               (puede traer id_reserva; si no, se empareja con la cancelación pendiente)

Cada solicitud queda en ``<salida>/cliente_<id>.csv`` con columnas
``ts, tipo, ok, latencia_ms, detalle`` (tipo en minúsculas; las notificaciones se
registran como tipo ``notificacion`` con la latencia desde que se envió la cancelación).

Uso directo (un solo cliente):
    python cliente.py --id C1 --rpm 60 --duracion 120 --pct-consulta 100
"""
import argparse
import csv
import json
import os
import random
import re
import time

import zmq

AQUI = os.path.dirname(os.path.abspath(__file__))


def cargar_config(ruta=None):
    with open(ruta or os.path.join(AQUI, "config_cliente.json"), encoding="utf-8") as f:
        return json.load(f)


class Cliente:
    def __init__(self, id_cliente, cfg, rpm=60, pct_consulta=100, pct_reserva=0,
                 pct_modificacion=0, pct_cancelacion=0, semilla=None,
                 gt=None, salida=None, silencioso=True):
        self.id = id_cliente
        self.cfg = cfg
        self.rpm = rpm
        total = pct_consulta + pct_reserva + pct_modificacion + pct_cancelacion
        if total <= 0:
            raise ValueError("los porcentajes deben sumar más de 0")
        # se normalizan para que siempre sumen 100
        self.p = [pct_consulta * 100 / total, pct_reserva * 100 / total,
                  pct_modificacion * 100 / total, pct_cancelacion * 100 / total]
        self.rnd = random.Random(semilla)
        self.gt = gt or cfg["gt_endpoints"]
        self.salida = salida or cfg.get("carpeta_salida", "resultados")
        self.silencioso = silencioso

        self.ctx = zmq.Context()
        self.sock = self._nuevo_req()
        self.pull = self.ctx.socket(zmq.PULL)       # recibe notificaciones de cancelación
        puerto = self.pull.bind_to_random_port(
            "tcp://*", min_port=cfg["puerto_notif_min"], max_port=cfg["puerto_notif_max"])
        self.endpoint_notif = f"tcp://{cfg['host_notificaciones']}:{puerto}"

        self.ocurrencias = []       # cache de la última consulta
        self.mis_reservas = []      # [{id_reserva (puede ser None), id_ocurrencia, id_evento, asientos}]
        self.pendientes = {}        # clave de la cancelación -> instante en que se envió (orden de envío)
        self.sin_id = 0             # para dar clave a cancelaciones de reservas sin id_reserva
        # operaciones sorteadas que no se pudieron hacer (p. ej. modificar sin tener reservas)
        # y se reemplazaron por una reserva; se reportan para que el cambio no pase en silencio
        self.cambiadas = 0
        os.makedirs(self.salida, exist_ok=True)
        self.f = open(os.path.join(self.salida, f"cliente_{self.id}.csv"), "w", newline="")
        self.w = csv.writer(self.f)
        self.w.writerow(["ts", "tipo", "ok", "latencia_ms", "detalle"])
        self.contadores = {"consulta": 0, "reserva": 0, "modificacion": 0, "cancelacion": 0}

    # ---------------------------------------------------------------- red
    def _nuevo_req(self):
        s = self.ctx.socket(zmq.REQ)
        s.setsockopt(zmq.RCVTIMEO, self.cfg["timeout_ms"])
        s.setsockopt(zmq.SNDTIMEO, self.cfg["timeout_ms"])
        s.setsockopt(zmq.LINGER, 0)
        for ep in self.gt:
            s.connect(ep)
        return s

    def _enviar(self, tipo, operacion, payload, estados_ok=("OK",)):
        """Envía una petición síncrona y registra la latencia. Devuelve (resp, ok, latencia_ms).

        ``estados_ok``: valores de status que cuentan como éxito (la cancelación usa "ACEPTADO").
        """
        t = time.perf_counter()
        try:
            self.sock.send_json({"operacion": operacion, "payload": payload})
            resp = self.sock.recv_json()
            ok = resp.get("status") in estados_ok
            detalle = resp.get("mensaje", resp.get("status", ""))
        except zmq.ZMQError:
            # un REQ queda bloqueado tras un timeout: hay que reconstruirlo
            self.sock.close()
            self.sock = self._nuevo_req()
            resp, ok, detalle = {}, False, "TIMEOUT"
        lat = (time.perf_counter() - t) * 1000
        self.w.writerow([f"{time.time():.6f}", tipo, int(ok), f"{lat:.3f}", str(detalle)[:120]])
        self.contadores[tipo] += 1
        return resp, ok, lat

    def _log(self, texto):
        if not self.silencioso:
            print(f"[{self.id}] {texto}", flush=True)

    # --------------------------------------------------------- operaciones
    def consultar(self):
        resp, ok, lat = self._enviar("consulta", "CONSULTAR",
                                     {"id_cliente": self.id, "mes": self.cfg["mes"], "anio": self.cfg["anio"]})
        if ok and resp.get("data"):
            self.ocurrencias = resp["data"]
        self._log(f"consulta -> {'OK' if ok else 'FALLO'} ({lat:.1f} ms)")

    def reservar(self):
        # La persistencia identifica una reserva por (id_cliente, id_ocurrencia) al modificar,
        # así que se prefiere una ocurrencia donde este cliente aún no tenga reserva: si tuviera
        # dos en la misma, una modificación movería las dos filas y la BD quedaría inconsistente.
        tengo = {r["id_ocurrencia"] for r in self.mis_reservas}
        libres = [o for o in self.ocurrencias if o["id_ocurrencia"] not in tengo]
        o = self.rnd.choice(libres or self.ocurrencias)
        n = self.rnd.randint(self.cfg["asientos_min"], self.cfg["asientos_max"])
        resp, ok, lat = self._enviar("reserva", "RESERVAR",
                                     {"id_cliente": self.id, "id_ocurrencia": o["id_ocurrencia"], "asientos": n})
        # La reserva se guarda aunque la respuesta no traiga id_reserva: el repo modifica y
        # cancela usando id_cliente + id_ocurrencia, así que no hace falta el id para operar.
        if ok:
            self.mis_reservas.append({"id_reserva": resp.get("id_reserva"), "id_ocurrencia": o["id_ocurrencia"],
                                      "id_evento": o["id_evento"], "asientos": n})
        self._log(f"reserva {o['id_evento']} oc{o['id_ocurrencia']} x{n} -> "
                  f"{'OK' if ok else resp.get('mensaje', 'FALLO')} ({lat:.1f} ms)")

    def modificar(self):
        r = self.rnd.choice(self.mis_reservas)
        payload = {"id_cliente": self.id, "id_ocurrencia_actual": r["id_ocurrencia"]}
        if r["id_reserva"] is not None:
            payload["id_reserva"] = r["id_reserva"]
        tengo = {x["id_ocurrencia"] for x in self.mis_reservas}
        otras = [o for o in self.ocurrencias
                 if o["id_evento"] == r["id_evento"] and o["id_ocurrencia"] not in tengo]
        if otras and self.rnd.random() < 0.5:
            # Cambio de fecha (solo eventos con 2 ocurrencias): se mueven TODOS los asientos de la reserva
            payload["id_ocurrencia_nueva"] = otras[0]["id_ocurrencia"]
            payload["asientos"] = r["asientos"]
        else:
            # Cambio de número de asientos, en la misma ocurrencia
            payload["id_ocurrencia_nueva"] = r["id_ocurrencia"]
            payload["asientos"] = self.rnd.randint(self.cfg["asientos_min"], self.cfg["asientos_max"])
        resp, ok, lat = self._enviar("modificacion", "MODIFICAR", payload)
        if ok:
            r["asientos"] = payload["asientos"]
            r["id_ocurrencia"] = payload["id_ocurrencia_nueva"]
        self._log(f"modificacion oc{payload['id_ocurrencia_actual']}->oc{payload['id_ocurrencia_nueva']} "
                  f"x{payload['asientos']} -> {'OK' if ok else resp.get('mensaje', 'FALLO')} ({lat:.1f} ms)")

    def cancelar(self):
        r = self.mis_reservas.pop(self.rnd.randrange(len(self.mis_reservas)))
        if r["id_reserva"] is not None:
            clave = r["id_reserva"]
        else:
            self.sin_id += 1
            clave = f"sin-id-{self.sin_id}"
        self.pendientes[clave] = time.perf_counter()
        resp, ok, lat = self._enviar("cancelacion", "CANCELAR",
                                     {"id_cliente": self.id, "id_reserva": r["id_reserva"],
                                      "id_ocurrencia": r["id_ocurrencia"], "asientos": r["asientos"],
                                      "endpoint_notificacion": self.endpoint_notif},
                                     estados_ok=("OK", "ACEPTADO"))   # el GT responde "ACEPTADO"
        if not ok:
            self.pendientes.pop(clave, None)
        self._log(f"cancelacion oc{r['id_ocurrencia']} x{r['asientos']} -> {'ACK' if ok else 'FALLO'} ({lat:.1f} ms)")

    def _clave_notificacion(self, n):
        """Encuentra a qué cancelación pendiente corresponde una notificación.

        1) por el campo id_reserva, si viene; 2) por el "#<número>" del mensaje
        ("Cancelación de reserva #17 ..."); 3) si no hay forma de saberlo, la más antigua.
        """
        rid = n.get("id_reserva")
        if rid is None:
            m = re.search(r"#(\d+)", str(n.get("mensaje", "")))
            rid = int(m.group(1)) if m else None
        if rid in self.pendientes:
            return rid
        return next(iter(self.pendientes), None)     # los dict conservan el orden de inserción

    def revisar_notificaciones(self):
        while True:
            try:
                n = self.pull.recv_json(zmq.NOBLOCK)
            except zmq.Again:
                return
            clave = self._clave_notificacion(n)
            t0 = self.pendientes.pop(clave, None) if clave is not None else None
            lat = (time.perf_counter() - t0) * 1000 if t0 else 0
            self.w.writerow([f"{time.time():.6f}", "notificacion", int(n.get("status") == "OK"),
                             f"{lat:.3f}", str(n.get("mensaje", ""))[:120]])
            self._log(f"NOTIFICACION {clave}: {n.get('mensaje')} ({lat:.0f} ms)")

    # ------------------------------------------------------------ ejecución
    def _elegir(self):
        """Devuelve la operación a hacer según los porcentajes y lo que sea posible."""
        if not self.ocurrencias:
            return "consulta"          # primero hay que conocer los eventos
        x = self.rnd.random() * 100
        c, r, m, _ = self.p
        if x < c:
            return "consulta"
        if x < c + r:
            return "reserva"
        op = "modificacion" if x < c + r + m else "cancelacion"
        if self.mis_reservas:
            return op
        # Sin reservas no hay nada que modificar o cancelar: se hace una reserva en su lugar
        # (como haría un usuario real) y se cuenta, para que el reemplazo quede reportado.
        self.cambiadas += 1
        self._log(f"{op} sin reservas -> se hace una reserva en su lugar")
        return "reserva"

    def ejecutar(self, duracion):
        intervalo = 60.0 / self.rpm if self.rpm else 0
        fin = time.time() + duracion
        self._log(f"inicio rpm={self.rpm} dur={duracion}s mezcla(c/r/m/x)="
                  f"{'/'.join(f'{v:.0f}' for v in self.p)} notif={self.endpoint_notif}")
        while time.time() < fin:
            t_ini = time.perf_counter()
            getattr(self, {"consulta": "consultar", "reserva": "reservar",
                           "modificacion": "modificar", "cancelacion": "cancelar"}[self._elegir()])()
            self.revisar_notificaciones()
            while time.perf_counter() - t_ini < intervalo:       # pausa, atendiendo notificaciones
                self.revisar_notificaciones()
                time.sleep(0.01)
        espera = time.time() + 5                                  # notificaciones rezagadas
        while self.pendientes and time.time() < espera:
            self.revisar_notificaciones()
            time.sleep(0.05)
        self.f.close()
        self.sock.close()
        self.pull.close()
        self.ctx.term()
        return {**self.contadores, "cambiadas": self.cambiadas, "notif_sin_recibir": len(self.pendientes)}


def main():
    ap = argparse.ArgumentParser(description="Cliente SRB (un solo cliente)")
    ap.add_argument("--id", default="C1")
    ap.add_argument("--rpm", type=float, default=60, help="solicitudes por minuto (mínimo 20 según enunciado)")
    ap.add_argument("--duracion", type=float, default=120, help="segundos")
    ap.add_argument("--pct-consulta", type=float, default=100)
    ap.add_argument("--pct-reserva", type=float, default=0)
    ap.add_argument("--pct-modificacion", type=float, default=0)
    ap.add_argument("--pct-cancelacion", type=float, default=0)
    ap.add_argument("--semilla", type=int, default=None)
    ap.add_argument("--config", default=None)
    ap.add_argument("--gt", default=None, help="endpoint(s) del GT separados por coma (sobrescribe la config)")
    ap.add_argument("--verboso", action="store_true")
    a = ap.parse_args()
    if a.rpm < 20:
        print("AVISO: el enunciado exige al menos 20 solicitudes por minuto por cliente")
    cfg = cargar_config(a.config)
    c = Cliente(a.id, cfg, a.rpm, a.pct_consulta, a.pct_reserva, a.pct_modificacion, a.pct_cancelacion,
                a.semilla, gt=a.gt.split(",") if a.gt else None, silencioso=not a.verboso)
    print(c.ejecutar(a.duracion))


if __name__ == "__main__":
    main()
