"""
Gestor de Transacciones (GT): la puerta de entrada del sistema.

    clientes (REQ) --> [ROUTER :GT_PUERTO_CLIENTES]  GT  [DEALER :GT_PUERTO_RMC] <-- RMC (REP)

El GT hace bind en los dos lados: los clientes y los RMC lo buscan a el.
Para agregar una replica del RMC basta con arrancarla; el GT no cambia.
"""
import time

import zmq

from config import configuracion as config
from config import E_mensaje as m
from capa_negocios.metricas import RegistroMetricas

# Peticiones que el canal sincrono acepta en la primera entrega
TIPOS_SINCRONOS = {m.CONSULTA, m.RESERVA}


def log(texto):
    print(f"[{time.strftime('%H:%M:%S')}] [GT] {texto}", flush=True)


class GestorTransacciones:
    def __init__(self, ruta_metricas="resultados/gt_metricas.csv"):
        self.contexto = zmq.Context()

        self.frontend = self.contexto.socket(zmq.ROUTER)      # lado de los clientes
        self.frontend.bind(config.direccion_bind(config.GT_PUERTO_CLIENTES))

        self.backend = self.contexto.socket(zmq.DEALER)       # lado de los RMC
        self.backend.bind(config.direccion_bind(config.GT_PUERTO_RMC))

        self.poller = zmq.Poller()
        self.poller.register(self.frontend, zmq.POLLIN)
        self.poller.register(self.backend, zmq.POLLIN)

        # uuid -> (hora de entrada, tipo, id_cliente)
        self.pendientes: dict[str, tuple[float, str, int]] = {}
        self.metricas = RegistroMetricas(config.RAIZ / ruta_metricas)

    # ------------------------------------------------------------ bucle principal
    def ejecutar(self):
        log(f"clientes en el puerto {config.GT_PUERTO_CLIENTES}, RMC en el puerto {config.GT_PUERTO_RMC}")
        while True:
            eventos = dict(self.poller.poll(1000))     # despierta al menos cada segundo
            if self.frontend in eventos:
                self.atender_cliente()
            if self.backend in eventos:
                self.atender_rmc()
            self.limpiar_pendientes()

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
        if tipo not in TIPOS_SINCRONOS:
            motivo = m.NO_IMPLEMENTADO if tipo in m.TIPOS else m.PETICION_INVALIDA
            self.responder_directo(frames, m.crear_respuesta(
                peticion, m.ERROR, motivo, {"razon": f"el GT no acepta peticiones {tipo}"}))
            log(f"rechazada {tipo} del cliente {cliente} ({motivo})")
            return

        try:
            # NOBLOCK: si no hay ningun RMC conectado, no esperar; avisar al cliente
            self.backend.send_multipart(frames, flags=zmq.NOBLOCK)   # el sobre viaja intacto
        except zmq.Again:
            self.responder_directo(frames, m.crear_respuesta(
                peticion, m.ERROR, m.NO_DISPONIBLE, {"razon": "no hay ningun RMC conectado"}))
            log(f"rechazada {tipo} del cliente {cliente}: no hay RMC conectado")
            return
        self.pendientes[peticion.get("uuid")] = (time.perf_counter(), tipo, cliente)
        log(f"<- {tipo} del cliente {cliente}")

    # ------------------------------------------------------------ llega la respuesta de un RMC
    def atender_rmc(self):
        frames = self.backend.recv_multipart()
        try:
            respuesta = m.decodificar(frames[-1])
        except ValueError:
            respuesta = {}
        inicio, tipo, cliente = self.pendientes.pop(respuesta.get("uuid"), (None, "?", "?"))
        ms = (time.perf_counter() - inicio) * 1000 if inicio is not None else 0.0
        motivo = f" {respuesta.get('motivo')}" if respuesta.get("motivo") else ""
        log(f"-> {tipo} al cliente {cliente}: {respuesta.get('estado')}{motivo} ({ms:.1f} ms)")
        if inicio is not None:
            self.metricas.registrar(tipo, respuesta.get("estado"), respuesta.get("motivo"),
                                    ms, cliente, respuesta.get("uuid"))
        self.frontend.send_multipart(frames)           # el ROUTER lo entrega al cliente correcto

    # ------------------------------------------------------------ apoyo
    def responder_directo(self, frames, respuesta):
        """Responde al cliente desde el GT, sin pasar por el RMC."""
        self.frontend.send_multipart(frames[:-1] + [m.codificar(respuesta)])

    def limpiar_pendientes(self):
        """Olvida las peticiones cuya respuesta ya no llegara (p. ej. se cayo el RMC)."""
        limite = time.perf_counter() - 2 * config.TIMEOUT_MS / 1000
        vencidas = [u for u, (inicio, _, _) in self.pendientes.items() if inicio < limite]
        for u in vencidas:
            _, tipo, cliente = self.pendientes.pop(u)
            log(f"sin respuesta del RMC para {tipo} del cliente {cliente}; se descarta")

    def cerrar(self):
        self.metricas.cerrar()
        self.frontend.close(linger=0)
        self.backend.close(linger=0)
        self.contexto.term()
