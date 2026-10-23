"""
Cliente del SRB: envia peticiones al Gestor de Transacciones y espera la respuesta.
"""
import time

import zmq

from config import configuracion as config
from config import E_mensaje as m


class Cliente:
    def __init__(self, id_cliente, timeout_ms=config.TIMEOUT_MS):
        self.id_cliente = id_cliente
        self.timeout_ms = timeout_ms
        self.direccion = config.direccion(config.HOST_CAPA_SERVICIOS, config.GT_PUERTO_CLIENTES)
        self.contexto = zmq.Context()
        self.socket = self._nuevo_socket()

    def _nuevo_socket(self):
        socket = self.contexto.socket(zmq.REQ)
        socket.setsockopt(zmq.LINGER, 0)
        socket.connect(self.direccion)
        return socket

    def enviar(self, tipo, datos):
        """
        Envia una peticion y devuelve (respuesta, milisegundos que tardo).
        Si el GT no responde a tiempo, la respuesta es un ERROR NO_DISPONIBLE
        armado aqui mismo: el cliente nunca se queda colgado.
        """
        peticion = m.crear_peticion(tipo, self.id_cliente, datos)
        inicio = time.perf_counter()
        self.socket.send(m.codificar(peticion))
        if self.socket.poll(self.timeout_ms, zmq.POLLIN):
            respuesta = m.decodificar(self.socket.recv())
        else:
            self.socket.close()                    # este REQ quedo inservible
            self.socket = self._nuevo_socket()
            respuesta = m.crear_respuesta(peticion, m.ERROR, m.NO_DISPONIBLE,
                                          {"razon": f"el GT no respondio en {self.timeout_ms} ms"})
        ms = (time.perf_counter() - inicio) * 1000
        return respuesta, ms

    def consultar(self, mes):
        return self.enviar(m.CONSULTA, {"mes": mes})

    def reservar(self, id_evento, fecha, n_asientos):
        return self.enviar(m.RESERVA, {"id_evento": id_evento, "fecha": fecha, "n_asientos": n_asientos})

    def cerrar(self):
        self.socket.close(linger=0)
        self.contexto.term()