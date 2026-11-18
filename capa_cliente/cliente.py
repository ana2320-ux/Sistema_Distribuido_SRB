"""
Cliente del SRB: envia peticiones al Gestor de Transacciones y espera la respuesta.

Las cancelaciones son asincronas: el GT responde ACK de inmediato y el resultado llega
despues como una notificacion. Para recibirlas, cada cliente abre un socket PULL en el
puerto PUERTO_BASE_NOTIFICACIONES + su id y envia esa direccion en la cancelacion.
"""
import threading
import time

import zmq

from config import configuracion as config
from config import E_mensaje as m


class Cliente:
    def __init__(self, id_cliente, timeout_ms=config.TIMEOUT_MS, con_hilo=True):
        """con_hilo=False: sin hilo receptor; quien usa el cliente llama a recibir_pendientes()."""
        self.id_cliente = id_cliente
        self.timeout_ms = timeout_ms
        self.direccion = config.direccion(config.HOST_CAPA_SERVICIOS, config.GT_PUERTO_CLIENTES)
        self.contexto = zmq.Context()
        self.contexto.setsockopt(zmq.CONNECT_TIMEOUT, 1000)   # ver GestorTransacciones.__init__
        self.socket = self._nuevo_socket()

        # Notificaciones: llegan a este PULL y las recibe un hilo aparte
        puerto = config.PUERTO_BASE_NOTIFICACIONES + id_cliente
        self.direccion_notificaciones = config.direccion(config.HOST_CAPA_CONSUMIDORES, puerto)
        self.notificaciones: list[dict] = []
        self._entrada = self.contexto.socket(zmq.PULL)
        try:
            self._entrada.bind(config.direccion_bind(puerto))
        except zmq.ZMQError:
            self.contexto.destroy(linger=0)
            raise RuntimeError(f"el puerto {puerto} esta ocupado: ya hay un cliente con el id {id_cliente}")
        self._activo = True
        self._hilo = None
        if con_hilo:
            self._hilo = threading.Thread(target=self._recibir_notificaciones, daemon=True)
            self._hilo.start()

    def _nuevo_socket(self):
        socket = self.contexto.socket(zmq.REQ)
        socket.setsockopt(zmq.LINGER, 0)
        socket.connect(self.direccion)
        return socket

    def _recibir_notificaciones(self):
        while self._activo:
            self.recibir_pendientes(200)

    def recibir_pendientes(self, espera_ms=0):
        """Recibe las notificaciones que ya llegaron; espera hasta espera_ms por la primera."""
        while self._entrada.poll(espera_ms, zmq.POLLIN):
            espera_ms = 0
            try:
                notificacion = m.decodificar(self._entrada.recv())
            except ValueError:
                continue                       # no es JSON: se ignora
            self.notificaciones.append(notificacion)
            datos = notificacion.get("datos", {})
            detalle = (f"reserva {datos.get('id_reserva')} cancelada, {datos.get('n_asientos')} asientos liberados"
                       if notificacion.get("estado") == m.EXITO
                       else f"{notificacion.get('motivo')}: {datos.get('razon', '')}")
            print(f"[{time.strftime('%H:%M:%S')}] [C{self.id_cliente}] NOTIFICACION => "
                  f"{notificacion.get('estado')} ({detalle})", flush=True)

    def esperar_notificaciones(self, cantidad, segundos=None):
        """Espera hasta tener esa cantidad de notificaciones (o hasta el limite). Devuelve cuantas hay."""
        limite = time.time() + (segundos if segundos is not None else 2 * self.timeout_ms / 1000)
        while len(self.notificaciones) < cantidad and time.time() < limite:
            if self._hilo:
                time.sleep(0.05)
            else:
                self.recibir_pendientes(50)
        return len(self.notificaciones)

    def enviar(self, tipo, datos):
        """
        Envia una peticion y devuelve (respuesta, milisegundos que tardo).
        Si el GT no responde a tiempo (por ejemplo, se cayo y entro el de respaldo), la
        peticion se envia una vez mas con el MISMO uuid: el sistema no la repite si ya la
        habia hecho. Si tampoco hay respuesta, devuelve un ERROR NO_DISPONIBLE armado aqui
        mismo: el cliente nunca se queda colgado.
        """
        peticion = m.crear_peticion(tipo, self.id_cliente, datos)
        respuesta = m.crear_respuesta(peticion, m.ERROR, m.NO_DISPONIBLE,
                                      {"razon": f"el GT no respondio en {self.timeout_ms} ms (2 intentos)"})
        inicio = time.perf_counter()
        for _ in range(2):
            self.socket.send(m.codificar(peticion))
            if self.socket.poll(self.timeout_ms, zmq.POLLIN):
                respuesta = m.decodificar(self.socket.recv())
                break
            self.socket.close()                    # este REQ quedo inservible
            self.socket = self._nuevo_socket()
            peticion["reintento"] = True
        ms = (time.perf_counter() - inicio) * 1000
        return respuesta, ms

    def consultar(self, mes):
        return self.enviar(m.CONSULTA, {"mes": mes})

    def reservar(self, id_evento, fecha, n_asientos):
        return self.enviar(m.RESERVA, {"id_evento": id_evento, "fecha": fecha, "n_asientos": n_asientos})

    def modificar(self, id_reserva, n_asientos=None, fecha=None):
        """Cambia el numero de asientos de una reserva, o su fecha (una de las dos cosas)."""
        cambio = {"fecha": fecha} if fecha is not None else {"n_asientos": n_asientos}
        return self.enviar(m.MODIFICACION, {"id_reserva": id_reserva, **cambio})

    def cancelar(self, id_reserva):
        """Pide cancelar una reserva. La respuesta es un ACK; el resultado llega como notificacion."""
        return self.enviar(m.CANCELACION, {"id_reserva": id_reserva,
                                           "notificar_a": self.direccion_notificaciones})

    def cerrar(self):
        self._activo = False
        if self._hilo:
            self._hilo.join()
        self.contexto.destroy(linger=0)
