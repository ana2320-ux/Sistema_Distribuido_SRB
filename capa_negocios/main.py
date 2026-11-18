"""
Arranca un proceso de la capa de negocio.

Uso (desde la raiz del proyecto, en la maquina de servicios):
    python -m capa_negocios.main gt                  # Gestor de Transacciones
    python -m capa_negocios.main rmc                 # un RMC (se pueden arrancar varios)
    python -m capa_negocios.main rmc --con-replica   # RMC que consulta en la replica de lectura
    python -m capa_negocios.main cancelaciones       # Servicio de Cancelaciones y Notificaciones

GT de respaldo: se arranca un segundo "gt". Encuentra los puertos ocupados y queda en
espera; cuando el GT activo se cae, toma los puertos y sigue atendiendo.
"""
import sys
import time

import zmq

from config import configuracion as config
from config import E_mensaje as m
from capa_negocios.cliente_persistencia import ClientePersistencia, PersistenciaNoDisponible
from capa_negocios.rmc import ServicioRMC
from capa_negocios.gestor_transacciones import GestorTransacciones


def log(quien, texto):
    print(f"[{time.strftime('%H:%M:%S')}] [{quien}] {texto}", flush=True)


def arrancar_gt():
    en_espera = False
    try:
        while True:
            try:
                gt = GestorTransacciones()
                break
            except zmq.ZMQError:             # puertos ocupados: ya hay un GT activo
                if not en_espera:
                    log("GT", "hay otro GT activo; en espera como respaldo")
                    en_espera = True
                time.sleep(1)                # se vuelve a intentar cada segundo
    except KeyboardInterrupt:
        log("GT", "detenido")
        return
    if en_espera:
        log("GT", "el GT activo se cayo; este GT toma el control")
    try:
        gt.ejecutar()
    except KeyboardInterrupt:
        log("GT", "detenido")
    finally:
        gt.cerrar()


def arrancar_rmc():
    contexto = zmq.Context()
    contexto.setsockopt(zmq.CONNECT_TIMEOUT, 1000)   # ver GestorTransacciones.__init__

    # El RMC se CONECTA al GT: el GT tiene la direccion fija y reparte el trabajo
    socket_gt = contexto.socket(zmq.REP)
    direccion_gt = config.direccion(config.HOST_CAPA_SERVICIOS, config.GT_PUERTO_RMC)
    socket_gt.connect(direccion_gt)

    # El limite hacia la persistencia es menor que el del cliente: si la
    # persistencia no responde, el RMC alcanza a avisarle al cliente con un ERROR.
    persistencia = ClientePersistencia(contexto, timeout_ms=config.TIMEOUT_MS // 3,
                                       usar_replica="--con-replica" in sys.argv)
    servicio = ServicioRMC(persistencia)
    log("RMC", f"conectado al GT en {direccion_gt}; escrituras en {persistencia.principal}, "
               f"consultas en {persistencia.lecturas}")

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
            reintento = " (reintento)" if peticion.get("reintento") else ""
            log("RMC", f"{peticion.get('tipo', 'mensaje no valido')}{reintento} {peticion.get('datos', '')} "
                       f"=> {respuesta['estado']}{motivo}")
            socket_gt.send(m.codificar(respuesta))
    except KeyboardInterrupt:
        log("RMC", "detenido")
    finally:
        persistencia.cerrar()
        socket_gt.close(linger=0)
        contexto.term()


def arrancar_cancelaciones():
    """
    Servicio de Cancelaciones y Notificaciones: recibe del GT las cancelaciones ya aceptadas,
    le pide a la persistencia liberar los asientos y le notifica el resultado al cliente,
    directamente a la direccion que el cliente envio en su peticion.
    """
    contexto = zmq.Context()
    contexto.setsockopt(zmq.CONNECT_TIMEOUT, 1000)   # ver GestorTransacciones.__init__
    entrada = contexto.socket(zmq.PULL)
    entrada.bind(config.direccion_bind(config.GT_PUERTO_CANCELACION))
    persistencia = ClientePersistencia(contexto, timeout_ms=config.TIMEOUT_MS // 3)
    log("CANCELACIONES", f"esperando cancelaciones en el puerto {config.GT_PUERTO_CANCELACION}")

    try:
        while True:
            try:
                peticion = m.decodificar(entrada.recv())
                datos = peticion["datos"]
                liberar = m.crear_peticion(m.LIBERAR_RESERVA, peticion["id_cliente"],
                                           {"id_reserva": datos["id_reserva"]}, peticion["uuid"])
                destino = datos["notificar_a"]
            except (ValueError, KeyError, TypeError) as e:     # el GT ya la valido; por si acaso
                log("CANCELACIONES", f"cancelacion mal formada, se descarta: {e}")
                continue
            try:
                respuesta = persistencia.enviar(liberar)       # mismo uuid: no se libera dos veces
            except PersistenciaNoDisponible as e:
                respuesta = m.crear_respuesta(peticion, m.ERROR, m.NO_DISPONIBLE, {"razon": str(e)})

            motivo = f" {respuesta['motivo']}" if respuesta["motivo"] else ""
            log("CANCELACIONES", f"reserva {datos['id_reserva']} del cliente {peticion['id_cliente']} "
                                 f"=> {respuesta['estado']}{motivo}; notificacion a {destino}")
            salida = contexto.socket(zmq.PUSH)
            salida.setsockopt(zmq.LINGER, config.TIMEOUT_MS)   # al cerrar, dar tiempo a que salga el mensaje
            try:
                salida.connect(destino)
                salida.send(m.codificar({**respuesta, "tipo": m.NOTIFICACION}))
            except zmq.ZMQError as e:
                log("CANCELACIONES", f"no se pudo notificar a {destino}: {e}")
            finally:
                salida.close()
    except KeyboardInterrupt:
        log("CANCELACIONES", "detenido")
    finally:
        persistencia.cerrar()
        entrada.close(linger=0)
        contexto.term()


if __name__ == "__main__":
    procesos = {"gt": arrancar_gt, "rmc": arrancar_rmc, "cancelaciones": arrancar_cancelaciones}
    if len(sys.argv) < 2 or sys.argv[1] not in procesos:
        print("uso: python -m capa_negocios.main [gt | rmc [--con-replica] | cancelaciones]")
        sys.exit(1)
    procesos[sys.argv[1]]()
