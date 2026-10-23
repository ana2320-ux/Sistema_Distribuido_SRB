"""
Cliente de la persistencia: el socket REQ con el que el RMC le pregunta cosas
al Servicio de Persistencia, con limite de espera y reintento.
"""
import zmq

from config import configuracion as config
from config import E_mensaje as m


class PersistenciaNoDisponible(Exception):
    """La persistencia no respondio a tiempo."""


class ClientePersistencia:
    def __init__(self, contexto, timeout_ms, reintentos=1):
        self.contexto = contexto
        self.direccion = config.direccion(config.HOST_CAPA_PERSISTENCIA, config.SP_PUERTO)
        self.timeout_ms = timeout_ms
        self.reintentos = reintentos
        self.socket = self._nuevo_socket()

    def _nuevo_socket(self):
        socket = self.contexto.socket(zmq.REQ)
        socket.setsockopt(zmq.LINGER, 0)
        socket.connect(self.direccion)
        return socket

    def enviar(self, peticion, reintentar=True):
        """
        Envia una peticion y devuelve la respuesta.
        reintentar=False para operaciones que cambian datos: si la primera llego
        pero su respuesta se perdio, reintentar haria la reserva dos veces.
        """
        intentos = 1 + (self.reintentos if reintentar else 0)
        for _ in range(intentos):
            self.socket.send(m.codificar(peticion))
            if self.socket.poll(self.timeout_ms, zmq.POLLIN):
                return m.decodificar(self.socket.recv())
            # Sin respuesta: este REQ quedo esperando un recv que nunca llegara.
            # No se puede volver a usar; se cierra y se crea uno nuevo.
            self.socket.close()
            self.socket = self._nuevo_socket()
        raise PersistenciaNoDisponible(f"la persistencia no respondio ({self.direccion})")

    def cerrar(self):
        self.socket.close(linger=0)