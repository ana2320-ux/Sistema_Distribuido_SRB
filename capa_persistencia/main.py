"""
Proceso del Servicio de Persistencia: socket REP con bind en SP_PUERTO.

Uso (desde la raiz del proyecto):
    python -m capa_persistencia.main            # servicio principal: lecturas y escrituras
    python -m capa_persistencia.main lectura    # replica de lectura, en SP_PUERTO_LECTURA

La replica de lectura es un segundo proceso sobre la misma base de datos (SQLite en modo
WAL): atiende consultas mientras el principal escribe, y asi le quita carga.
"""
import sys

import time

import zmq

from config import configuracion as config
from config import E_mensaje as m
from capa_persistencia.db import BaseDatos
from capa_persistencia.servicio_persistencia import ServicioPersistencia


SOLO_LECTURA = sys.argv[1:] == ["lectura"]
NOMBRE = "PERSISTENCIA-LECTURA" if SOLO_LECTURA else "PERSISTENCIA"
PUERTO = config.SP_PUERTO_LECTURA if SOLO_LECTURA else config.SP_PUERTO


def log(texto):
    print(f"[{time.strftime('%H:%M:%S')}] [{NOMBRE}] {texto}", flush=True)


def main():
    bd = BaseDatos()
    servicio = ServicioPersistencia(bd, solo_lectura=SOLO_LECTURA)

    print("Estado inicial de la base de datos:")
    bd.imprimir_estado(solo_ocupadas=True)

    contexto = zmq.Context()
    socket = contexto.socket(zmq.REP)
    socket.bind(config.direccion_bind(PUERTO))
    log(f"escuchando en el puerto {PUERTO}")

    try:
        while True:
            mensaje = socket.recv()
            peticion = {}
            try:
                peticion = m.decodificar(mensaje)
                respuesta = servicio.atender(peticion)
            except ValueError:
                respuesta = m.crear_respuesta(peticion, m.ERROR, m.PETICION_INVALIDA,
                                              {"razon": "el mensaje no es JSON valido"})
            except Exception as e:          # pase lo que pase, el REP SIEMPRE responde
                respuesta = m.crear_respuesta(peticion, m.ERROR, m.NO_DISPONIBLE,
                                              {"razon": f"error inesperado: {e}"})

            motivo = f" {respuesta['motivo']}" if respuesta["motivo"] else ""
            log(f"{peticion.get('tipo', 'mensaje no valido')} {peticion.get('datos', '')} "
                f"=> {respuesta['estado']}{motivo}")
            socket.send(m.codificar(respuesta))
    except KeyboardInterrupt:
        log("detenido")
        print("Estado final de la base de datos:")
        bd.imprimir_estado(solo_ocupadas=True)
    finally:
        socket.close(linger=0)
        contexto.term()
        bd.cerrar()


if __name__ == "__main__":
    main()