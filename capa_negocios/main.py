"""
Arranca un proceso de la capa de negocio.

Uso (desde la raiz del proyecto):
    python -m capa_negocios.main rmc
"""
import sys
import time

import zmq

from config import configuracion as config
from config import E_mensaje as m
from capa_negocios.cliente_persistencia import ClientePersistencia
from capa_negocios.rmc import ServicioRMC
from capa_negocios.gestor_transacciones import GestorTransacciones


def log(quien, texto):
    print(f"[{time.strftime('%H:%M:%S')}] [{quien}] {texto}", flush=True)

def arrancar_gt():
    gt = GestorTransacciones()
    try:
        gt.ejecutar()
    except KeyboardInterrupt:
        log("GT", "detenido")
    finally:
        gt.cerrar()

def arrancar_rmc():
    contexto = zmq.Context()

    # El RMC se CONECTA al GT: el GT tiene la direccion fija y reparte el trabajo
    socket_gt = contexto.socket(zmq.REP)
    direccion_gt = config.direccion(config.HOST_CAPA_SERVICIOS, config.GT_PUERTO_RMC)
    socket_gt.connect(direccion_gt)

    # El limite hacia la persistencia es menor que el del cliente: si la
    # persistencia no responde, el RMC alcanza a avisarle al cliente con un ERROR.
    persistencia = ClientePersistencia(contexto, timeout_ms=config.TIMEOUT_MS // 3)
    servicio = ServicioRMC(persistencia)
    log("RMC", f"conectado al GT en {direccion_gt}; persistencia en {persistencia.direccion}")

    try:
        while True:
            recibido = socket_gt.recv()
            peticion = {}
            try:
                peticion = m.decodificar(recibido)
                respuesta = servicio.atender(peticion)
            except ValueError:
                respuesta = m.crear_respuesta(peticion, m.ERROR, m.PETICION_INVALIDA,
                                              {"razon": "el mensaje no es JSON valido"})
            except Exception as e:          # pase lo que pase, el REP SIEMPRE responde
                respuesta = m.crear_respuesta(peticion, m.ERROR, m.NO_DISPONIBLE,
                                              {"razon": f"error inesperado: {e}"})

            motivo = f" {respuesta['motivo']}" if respuesta["motivo"] else ""
            log("RMC", f"{peticion.get('tipo', 'mensaje no valido')} {peticion.get('datos', '')} "
                       f"=> {respuesta['estado']}{motivo}")
            socket_gt.send(m.codificar(respuesta))
    except KeyboardInterrupt:
        log("RMC", "detenido")
    finally:
        persistencia.cerrar()
        socket_gt.close(linger=0)
        contexto.term()

if __name__ == "__main__":
    procesos = {"gt": arrancar_gt, "rmc": arrancar_rmc}
    if len(sys.argv) != 2 or sys.argv[1] not in procesos:
        print("uso: python -m capa_negocios.main [gt|rmc]")
        sys.exit(1)
    procesos[sys.argv[1]]()
