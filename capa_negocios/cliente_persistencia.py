"""
Cliente de la persistencia: los sockets REQ con los que el RMC y el Servicio de
Cancelaciones le hablan al Servicio de Persistencia, con limite de espera y reintento.

Con replica de lectura (arquitectura escalable), las consultas van a la replica y las
escrituras al servicio principal. Si la replica no responde, la consulta se reintenta
en el principal.
"""
import zmq

from config import configuracion as config
from config import E_mensaje as m

# Peticiones que no cambian datos: las puede atender la replica de lectura
LECTURAS = {m.CONSULTA, m.CONSULTA_DISPONIBILIDAD, m.CONSULTAR_RESERVA}


class PersistenciaNoDisponible(Exception):
    """La persistencia no respondio a tiempo."""


class ClientePersistencia:
    def __init__(self, contexto, timeout_ms, usar_replica=False):
        self.contexto = contexto
        self.timeout_ms = timeout_ms
        self.principal = config.direccion(config.HOST_CAPA_PERSISTENCIA, config.SP_PUERTO)
        self.lecturas = (config.direccion(config.HOST_CAPA_PERSISTENCIA, config.SP_PUERTO_LECTURA)
                         if usar_replica else self.principal)
        self.sockets: dict[str, zmq.Socket] = {}       # direccion -> socket REQ

    def _socket(self, direccion):
        if direccion not in self.sockets:
            socket = self.contexto.socket(zmq.REQ)
            socket.setsockopt(zmq.LINGER, 0)
            socket.connect(direccion)
            self.sockets[direccion] = socket
        return self.sockets[direccion]

    def enviar(self, peticion):
        """
        Envia una peticion y devuelve la respuesta. Si no hay respuesta la envia una vez mas:
        no hay riesgo de repetir una escritura, porque la persistencia reconoce el uuid.
        """
        direccion = self.lecturas if peticion["tipo"] in LECTURAS else self.principal
        for _ in range(2):
            socket = self._socket(direccion)
            socket.send(m.codificar(peticion))
            if socket.poll(self.timeout_ms, zmq.POLLIN):
                return m.decodificar(socket.recv())
            # Sin respuesta: este REQ quedo esperando un recv que nunca llegara.
            # No se puede volver a usar; se cierra y se crea uno nuevo al reintentar.
            socket.close()
            del self.sockets[direccion]
            # Si fallo la replica, el reintento y las consultas siguientes van al principal.
            # shortcut: no vuelve a usar la replica hasta reiniciar este proceso; revisar si la replica se cae seguido
            direccion = self.lecturas = self.principal
        raise PersistenciaNoDisponible(f"la persistencia no respondio ({direccion})")

    def cerrar(self):
        for socket in self.sockets.values():
            socket.close(linger=0)
