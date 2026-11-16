"""
Gestor de Transacciones (GT): la puerta de entrada del sistema.

    clientes (REQ) --> [ROUTER :GT_PUERTO_CLIENTES]  GT  [DEALER :GT_PUERTO_RMC] <-- RMC (REP)
                                                     GT  [PUSH] --> Servicio de Cancelaciones (PULL :GT_PUERTO_CANCELACION)

Canal sincrono (consulta, reserva y modificacion): la peticion va a un RMC y el GT espera
su respuesta para devolverla al cliente. El GT hace bind en los dos lados: los clientes y
los RMC lo buscan a el. Para agregar una replica del RMC basta con arrancarla; el DEALER
reparte las peticiones entre todas.

Canal asincrono (cancelacion): el GT responde ACK de inmediato y pasa la peticion al
Servicio de Cancelaciones por PUSH/PULL. El resultado le llega al cliente despues, como
una notificacion.

Tolerancia a fallas:
  - Si un RMC no responde a tiempo (se cayo), el GT reenvia la peticion con el mismo uuid,
    marcada como reintento, y el DEALER se la entrega a otro RMC.
  - Un segundo GT puede quedar en espera en la misma maquina (ver main.py): toma los
    puertos cuando este proceso se cae. Las peticiones que iban en camino las reenvia el
    cliente con el mismo uuid, y la persistencia no repite las que ya se hicieron.
"""
import time

import zmq

from config import configuracion as config
from config import E_mensaje as m
from capa_negocios.metricas import RegistroMetricas

# Peticiones que van por el canal sincrono (al RMC)
TIPOS_SINCRONOS = {m.CONSULTA, m.RESERVA, m.MODIFICACION}

# Segundos sin respuesta de un RMC antes de reenviar la peticion a otro. Es menos de la
# mitad de lo que espera el cliente, para que el reenvio alcance a responderle.
ESPERA_RMC_S = config.TIMEOUT_MS * 0.4 / 1000
MAX_ENVIOS = 2          # el envio original y un reenvio


def log(texto):
    print(f"[{time.strftime('%H:%M:%S')}] [GT] {texto}", flush=True)


def revisar_peticion(peticion):
    """Devuelve por que la peticion esta mal formada, o None si esta bien."""
    if not isinstance(peticion.get("uuid"), str) or not peticion["uuid"]:
        return "falta el uuid"
    cliente = peticion.get("id_cliente")
    if not isinstance(cliente, int) or isinstance(cliente, bool) or cliente <= 0:
        return f"id_cliente debe ser un entero mayor que 0: {cliente}"
    if not isinstance(peticion.get("datos"), dict):
        return "datos debe ser un objeto"
    return None


class GestorTransacciones:
    def __init__(self, ruta_metricas="resultados/gt_metricas.csv"):
        """Lanza zmq.ZMQError si los puertos ya estan ocupados (hay otro GT activo)."""
        self.contexto = zmq.Context()
        try:
            self.frontend = self.contexto.socket(zmq.ROUTER)      # lado de los clientes
            self.frontend.bind(config.direccion_bind(config.GT_PUERTO_CLIENTES))
            self.backend = self.contexto.socket(zmq.DEALER)       # lado de los RMC
            self.backend.bind(config.direccion_bind(config.GT_PUERTO_RMC))
        except zmq.ZMQError:
            self.contexto.destroy(linger=0)
            raise

        # Hacia el Servicio de Cancelaciones. Como el GT es quien se conecta, si ese servicio
        # esta caido ZeroMQ guarda las cancelaciones y las entrega cuando vuelve.
        self.cancelaciones = self.contexto.socket(zmq.PUSH)
        self.cancelaciones.connect(config.direccion(config.HOST_CAPA_SERVICIOS, config.GT_PUERTO_CANCELACION))

        self.poller = zmq.Poller()
        self.poller.register(self.frontend, zmq.POLLIN)
        self.poller.register(self.backend, zmq.POLLIN)

        # Peticiones enviadas a un RMC que aun no tienen respuesta. uuid -> datos de la peticion
        self.pendientes: dict[str, dict] = {}
        self.metricas = RegistroMetricas(config.RAIZ / ruta_metricas)

    # ------------------------------------------------------------ bucle principal
    def ejecutar(self):
        log(f"clientes en el puerto {config.GT_PUERTO_CLIENTES}, RMC en el puerto {config.GT_PUERTO_RMC}")
        while True:
            eventos = dict(self.poller.poll(200))      # despierta seguido para revisar los pendientes
            if self.frontend in eventos:
                self.atender_cliente()
            if self.backend in eventos:
                self.atender_rmc()
            self.revisar_pendientes()

    # ------------------------------------------------------------ llega algo de un cliente
    def atender_cliente(self):
        frames = self.frontend.recv_multipart()        # [identidad, b"", json]
        try:
            peticion = m.decodificar(frames[-1])
        except ValueError:
            self.responder_directo(frames, m.crear_respuesta(
                {}, m.ERROR, m.PETICION_INVALIDA, {"razon": "el mensaje no es JSON valido"}))
            log("rechazado: mensaje que no es JSON")
            return

        tipo = peticion.get("tipo")
        cliente = peticion.get("id_cliente")
        problema = revisar_peticion(peticion)
        if problema:
            self.responder_directo(frames, m.crear_respuesta(
                peticion, m.ERROR, m.PETICION_INVALIDA, {"razon": problema}))
            log(f"rechazada {tipo} del cliente {cliente}: {problema}")
            return
        if tipo == m.CANCELACION:
            self.atender_cancelacion(frames, peticion)
            return
        if tipo not in TIPOS_SINCRONOS:
            self.responder_directo(frames, m.crear_respuesta(
                peticion, m.ERROR, m.PETICION_INVALIDA, {"razon": f"el GT no acepta peticiones {tipo}"}))
            log(f"rechazada {tipo} del cliente {cliente}")
            return

        if not self.enviar_a_rmc(frames):
            self.responder_directo(frames, m.crear_respuesta(
                peticion, m.ERROR, m.NO_DISPONIBLE, {"razon": "no hay ningun RMC conectado"}))
            log(f"rechazada {tipo} del cliente {cliente}: no hay RMC conectado")
            return
        ahora = time.perf_counter()
        self.pendientes[peticion["uuid"]] = {"inicio": ahora, "enviado": ahora, "envios": 1,
                                             "frames": frames, "peticion": peticion}
        log(f"<- {tipo} del cliente {cliente}")

    def enviar_a_rmc(self, frames):
        """Entrega la peticion a un RMC. False si no hay ninguno conectado."""
        try:
            # NOBLOCK: si no hay ningun RMC conectado, no esperar
            self.backend.send_multipart(frames, flags=zmq.NOBLOCK)   # el sobre viaja intacto
            return True
        except zmq.Again:
            return False

    # ------------------------------------------------------------ cancelacion (canal asincrono)
    def atender_cancelacion(self, frames, peticion):
        datos, cliente = peticion["datos"], peticion["id_cliente"]
        id_reserva, direccion = datos.get("id_reserva"), datos.get("notificar_a")
        if not isinstance(id_reserva, int) or isinstance(id_reserva, bool) or id_reserva <= 0 \
                or not isinstance(direccion, str) or not direccion.startswith("tcp://"):
            self.responder_directo(frames, m.crear_respuesta(
                peticion, m.ERROR, m.DATO_INVALIDO,
                {"razon": "la cancelacion necesita id_reserva (entero) y notificar_a (tcp://host:puerto)"}))
            log(f"rechazada CANCELACION del cliente {cliente}: datos invalidos")
            return
        try:
            self.cancelaciones.send(frames[-1], flags=zmq.NOBLOCK)
        except zmq.Again:                               # demasiadas cancelaciones en espera
            self.responder_directo(frames, m.crear_respuesta(
                peticion, m.ERROR, m.NO_DISPONIBLE, {"razon": "el Servicio de Cancelaciones no esta disponible"}))
            return
        # ACK inmediato: la cancelacion quedo aceptada; el resultado llega por notificacion
        self.responder_directo(frames, m.crear_respuesta(peticion, m.ACK))
        self.metricas.registrar(m.CANCELACION, m.ACK, None, 0.0, cliente, peticion["uuid"])
        log(f"<- CANCELACION de la reserva {id_reserva} del cliente {cliente}: ACK, enviada a Cancelaciones")

    # ------------------------------------------------------------ llega la respuesta de un RMC
    def atender_rmc(self):
        frames = self.backend.recv_multipart()
        try:
            respuesta = m.decodificar(frames[-1])
        except ValueError:
            respuesta = {}
        pendiente = self.pendientes.pop(respuesta.get("uuid"), None)
        if pendiente is None:
            return          # respuesta repetida (la peticion se reenvio) o tardia: ya se respondio
        peticion = pendiente["peticion"]
        tipo, cliente = peticion["tipo"], peticion["id_cliente"]
        ms = (time.perf_counter() - pendiente["inicio"]) * 1000
        motivo = f" {respuesta.get('motivo')}" if respuesta.get("motivo") else ""
        log(f"-> {tipo} al cliente {cliente}: {respuesta.get('estado')}{motivo} ({ms:.1f} ms)")
        self.metricas.registrar(tipo, respuesta.get("estado"), respuesta.get("motivo"),
                                ms, cliente, respuesta.get("uuid"))
        # Se responde a la identidad guardada: si el cliente reenvio la peticion desde un
        # socket nuevo, es la mas reciente.
        self.responder_directo(pendiente["frames"], respuesta)

    # ------------------------------------------------------------ apoyo
    def responder_directo(self, frames, respuesta):
        """Responde al cliente dueno de esos frames."""
        self.frontend.send_multipart(frames[:-1] + [m.codificar(respuesta)])

    def revisar_pendientes(self):
        """Reenvia a otro RMC las peticiones sin respuesta; si tampoco responde, avisa al cliente."""
        ahora = time.perf_counter()
        for uuid, p in list(self.pendientes.items()):
            if ahora - p["enviado"] < ESPERA_RMC_S:
                continue
            peticion = p["peticion"]
            tipo, cliente = peticion["tipo"], peticion["id_cliente"]
            reenvio = p["frames"][:-1] + [m.codificar({**peticion, "reintento": True})]
            if p["envios"] < MAX_ENVIOS and self.enviar_a_rmc(reenvio):
                p["enviado"] = ahora
                p["envios"] += 1
                log(f"sin respuesta del RMC para {tipo} del cliente {cliente}; se reenvia a otro RMC")
            else:
                del self.pendientes[uuid]
                self.responder_directo(p["frames"], m.crear_respuesta(
                    peticion, m.ERROR, m.NO_DISPONIBLE, {"razon": "ningun RMC respondio"}))
                log(f"sin respuesta del RMC para {tipo} del cliente {cliente}; se avisa al cliente")

    def cerrar(self):
        self.metricas.cerrar()
        self.contexto.destroy(linger=0)
