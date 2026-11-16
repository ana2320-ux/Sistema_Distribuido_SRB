"""
Pruebas de tolerancia a fallas: se mata un proceso mientras el sistema trabaja y se
comprueba que el cliente no ve errores, que no se pierde ninguna operacion y que
ninguna se hace dos veces.
"""
import threading
import time

import zmq

from config import configuracion as config
from config import E_mensaje as m
from capa_cliente.cliente import Cliente
from capa_negocios.cliente_persistencia import ClientePersistencia


def rmc_que_se_cae(recibidas, antes_de_caer=None):
    """Un RMC falso: recibe UNA peticion del GT y se cae sin responderla."""
    contexto = zmq.Context()
    socket = contexto.socket(zmq.REP)
    socket.connect(config.direccion(config.HOST_CAPA_SERVICIOS, config.GT_PUERTO_RMC))
    peticion = m.decodificar(socket.recv())
    if antes_de_caer:
        antes_de_caer(contexto, peticion)
    recibidas.append(peticion)
    contexto.destroy(linger=0)


def test_rmc_se_cae_antes_de_atender_la_reserva(sistema):
    """El GT reenvia la peticion a otro RMC: el cliente recibe EXITO y la reserva queda una sola vez."""
    recibidas = []
    hilo = threading.Thread(target=rmc_que_se_cae, args=(recibidas,))
    hilo.start()
    time.sleep(0.5)                                  # que el RMC falso alcance a conectarse al GT
    cliente = Cliente(20)
    try:
        respuestas = [cliente.reservar("E3", "2026/11/03", 1)[0] for _ in range(6)]
    finally:
        cliente.cerrar()
    hilo.join(timeout=5)

    assert len(recibidas) == 1                       # una de las seis le toco al RMC que se cayo
    assert [r["estado"] for r in respuestas] == [m.EXITO] * 6
    assert "se reenvia a otro RMC" in sistema.log("gt")
    bd = sistema.bd()
    assert bd.disponibilidad("E3", "2026/11/03")["puestos_ocupados"] == 6     # ni una menos ni una de mas
    assert bd.verificar()
    bd.cerrar()


def test_rmc_se_cae_despues_de_guardar_la_reserva(sistema):
    """
    El RMC alcanzo a guardar la reserva pero se cayo antes de responder. El otro RMC recibe
    el reintento y la persistencia reconoce el uuid: devuelve la misma reserva, sin
    duplicarla y sin rechazarla por los asientos que ella misma ocupo.
    """
    def guardar_y_caer(contexto, peticion):
        persistencia = ClientePersistencia(contexto, timeout_ms=config.TIMEOUT_MS)
        persistencia.enviar(m.crear_peticion(m.AGREGAR_RESERVA, peticion["id_cliente"],
                                             peticion["datos"], peticion["uuid"]))

    recibidas = []
    hilo = threading.Thread(target=rmc_que_se_cae, args=(recibidas, guardar_y_caer))
    hilo.start()
    time.sleep(0.5)
    cliente = Cliente(21)
    try:
        # cada reserva llena por completo una ocurrencia distinta (E21 a E26, 100 asientos)
        respuestas = [cliente.reservar(f"E{i}", f"2026/11/{i - 14:02d}", 100)[0] for i in range(21, 27)]
    finally:
        cliente.cerrar()
    hilo.join(timeout=5)

    assert len(recibidas) == 1
    assert [r["estado"] for r in respuestas] == [m.EXITO] * 6
    assert len({r["datos"]["id_reserva"] for r in respuestas}) == 6
    bd = sistema.bd()
    resumen = bd.resumen()
    assert (resumen["ocupados"], resumen["reservas"]) == (600, 6)
    assert bd.verificar()
    bd.cerrar()


def test_se_cae_el_gt_y_entra_el_de_respaldo(sistema):
    """Se mata el GT en plena carga: el de respaldo toma el control y no se pierde ni se repite nada."""
    sistema.arrancar("gt_respaldo", "capa_negocios.main", "gt")
    time.sleep(1.5)
    assert "en espera como respaldo" in sistema.log("gt_respaldo")

    respuestas = []

    def cargar():
        cliente = Cliente(22)
        try:
            for _ in range(90):
                respuestas.append(cliente.reservar("E4", "2026/11/04", 1)[0])
        finally:
            cliente.cerrar()

    hilo = threading.Thread(target=cargar)
    hilo.start()
    while len(respuestas) < 20:                      # con la carga ya en marcha...
        time.sleep(0.01)
    sistema.matar("gt")                              # ...cae el GT activo, con peticiones en camino
    hilo.join()

    assert len(respuestas) == 90
    assert "toma el control" in sistema.log("gt_respaldo")
    assert [r["estado"] for r in respuestas] == [m.EXITO] * 90          # el cliente no vio ningun error
    assert len({r["datos"]["id_reserva"] for r in respuestas}) == 90
    bd = sistema.bd()
    assert bd.disponibilidad("E4", "2026/11/04")["puestos_ocupados"] == 90
    assert bd.verificar()
    bd.cerrar()


def test_cancelacion_pendiente_se_procesa_cuando_vuelve_el_servicio(sistema):
    cliente = Cliente(23)
    try:
        reserva, _ = cliente.reservar("E6", "2026/11/06", 5)
        sistema.matar("cancelaciones")

        respuesta, _ = cliente.cancelar(reserva["datos"]["id_reserva"])
        assert respuesta["estado"] == m.ACK                              # el GT la acepta igual
        assert cliente.esperar_notificaciones(1, segundos=1) == 0        # pero nadie la procesa todavia
        bd = sistema.bd()
        assert bd.disponibilidad("E6", "2026/11/06")["puestos_ocupados"] == 5

        sistema.arrancar("cancelaciones", "capa_negocios.main", "cancelaciones")
        assert cliente.esperar_notificaciones(1, segundos=10) == 1       # al volver, la procesa y notifica
        assert cliente.notificaciones[0]["estado"] == m.EXITO
        assert bd.disponibilidad("E6", "2026/11/06")["puestos_ocupados"] == 0
        bd.cerrar()
    finally:
        cliente.cerrar()


def test_se_cae_la_replica_de_lectura(sistema):
    """Sin la replica, las consultas las atiende el servicio principal."""
    sistema.matar("lectura")
    cliente = Cliente(24)
    try:
        for _ in range(4):
            respuesta, _ = cliente.consultar("noviembre")
            assert respuesta["estado"] == m.EXITO
        respuesta, _ = cliente.reservar("E8", "2026/11/08", 2)
        assert respuesta["estado"] == m.EXITO
    finally:
        cliente.cerrar()
