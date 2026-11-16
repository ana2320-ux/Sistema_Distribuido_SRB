"""
Pruebas de integracion, funcionales, de concurrencia y de seguridad basica, con todos los
procesos en marcha (cliente -> GT -> RMC -> persistencia, y la cancelacion asincrona).
"""
import threading

import zmq

from config import configuracion as config
from config import E_mensaje as m
from capa_cliente.cliente import Cliente
from capa_cliente.script import ejecutar_script


def ocupados(sistema, id_evento, fecha):
    bd = sistema.bd()
    try:
        return bd.disponibilidad(id_evento, fecha)["puestos_ocupados"]
    finally:
        bd.cerrar()


# ---------------------------------------------------------------- integracion y funcionales
def test_caso_basico_deja_la_bd_como_se_espera(sistema):
    """El caso de pruebas/caso_basico.txt: todas las operaciones y el estado final de la BD."""
    cliente = Cliente(1)
    try:
        resumen = ejecutar_script(cliente, config.RAIZ / "pruebas" / "caso_basico.txt")
    finally:
        cliente.cerrar()
    assert resumen == {"EXITO": 8, "FALLO": 6, "ERROR": 2, "ACK": 3, "NOTIFICACIONES": 3}
    estados = sorted(n["estado"] for n in cliente.notificaciones)
    assert estados == ["EXITO", "FALLO", "FALLO"]       # una cancelada, dos rechazadas

    assert ocupados(sistema, "E1", "2026/11/01") == 5
    assert ocupados(sistema, "E1", "2026/11/15") == 100
    assert ocupados(sistema, "E30", "2026/11/02") == 4
    bd = sistema.bd()
    resumen_bd = bd.resumen()
    assert (resumen_bd["ocupados"], resumen_bd["reservas"]) == (109, 3)
    assert bd.verificar()
    bd.cerrar()


def test_consulta_del_mes_lista_los_50_eventos(sistema):
    cliente = Cliente(2)
    try:
        respuesta, _ = cliente.consultar("noviembre")
    finally:
        cliente.cerrar()
    eventos = respuesta["datos"]["eventos"]
    assert respuesta["estado"] == m.EXITO
    assert len({e["id_evento"] for e in eventos}) == 50 and len(eventos) == 70
    assert all(e["libres"] == 100 and e["fecha"].startswith("2026/11/") for e in eventos)


def test_reserva_modificacion_y_cambio_de_fecha(sistema):
    cliente = Cliente(3)
    try:
        reserva, _ = cliente.reservar("E5", "2026/11/05", 4)
        assert reserva["estado"] == m.EXITO and ocupados(sistema, "E5", "2026/11/05") == 4
        id_reserva = reserva["datos"]["id_reserva"]

        respuesta, _ = cliente.reservar("E5", "2026/11/05", 97)          # mas de los libres
        assert (respuesta["estado"], respuesta["motivo"]) == (m.FALLO, m.SIN_CUPO)
        assert ocupados(sistema, "E5", "2026/11/05") == 4                # la BD no cambio

        respuesta, _ = cliente.modificar(id_reserva, n_asientos=10)
        assert respuesta["estado"] == m.EXITO and ocupados(sistema, "E5", "2026/11/05") == 10

        respuesta, _ = cliente.modificar(id_reserva, fecha="2026/11/19")  # E5 ocurre el 05 y el 19
        assert respuesta["estado"] == m.EXITO
        assert ocupados(sistema, "E5", "2026/11/05") == 0                # devueltos en la fecha origen
        assert ocupados(sistema, "E5", "2026/11/19") == 10               # descontados en la destino

        respuesta, _ = cliente.modificar(id_reserva, n_asientos=101)     # rechazada: queda como estaba
        assert (respuesta["estado"], respuesta["motivo"]) == (m.FALLO, m.SIN_CUPO)
        assert ocupados(sistema, "E5", "2026/11/19") == 10
    finally:
        cliente.cerrar()


def test_cancelacion_ack_inmediato_y_notificacion(sistema):
    cliente = Cliente(4)
    try:
        reserva, _ = cliente.reservar("E7", "2026/11/07", 6)
        id_reserva = reserva["datos"]["id_reserva"]

        respuesta, _ = cliente.cancelar(id_reserva)
        assert respuesta["estado"] == m.ACK                              # aceptada de inmediato

        assert cliente.esperar_notificaciones(1) == 1                    # el resultado llega despues
        notificacion = cliente.notificaciones[0]
        assert notificacion["tipo"] == m.NOTIFICACION and notificacion["estado"] == m.EXITO
        assert notificacion["uuid"] == respuesta["uuid"]                 # corresponde a esa cancelacion
        assert notificacion["datos"]["id_reserva"] == id_reserva
        assert ocupados(sistema, "E7", "2026/11/07") == 0                # asientos liberados

        cliente.cancelar(999)                                            # reserva que no existe
        assert cliente.esperar_notificaciones(2) == 2
        assert (cliente.notificaciones[1]["estado"], cliente.notificaciones[1]["motivo"]) == (m.FALLO, m.NO_EXISTE)
    finally:
        cliente.cerrar()


# ---------------------------------------------------------------- concurrencia y consistencia
def test_varios_clientes_compiten_por_los_ultimos_asientos(sistema):
    """8 clientes hacen 150 intentos de 1 asiento sobre una ocurrencia de 100: entran exactamente 100."""
    exitos, otros = [], []

    def comprador(id_cliente, intentos):
        cliente = Cliente(id_cliente)
        try:
            for _ in range(intentos):
                respuesta, _ = cliente.reservar("E2", "2026/11/02", 1)
                (exitos if respuesta["estado"] == m.EXITO else otros).append(respuesta)
        finally:
            cliente.cerrar()

    hilos = [threading.Thread(target=comprador, args=(10 + i, 19 if i < 6 else 18)) for i in range(8)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert len(exitos) == 100 and len(otros) == 50
    assert all((r["estado"], r["motivo"]) == (m.FALLO, m.SIN_CUPO) for r in otros)
    assert len({r["datos"]["id_reserva"] for r in exitos}) == 100        # ninguna reserva repetida
    assert ocupados(sistema, "E2", "2026/11/02") == 100                  # los libres no bajan de 0
    bd = sistema.bd()
    assert bd.verificar()
    bd.cerrar()


# ---------------------------------------------------------------- seguridad basica
def test_mensajes_mal_formados_se_rechazan_sin_tumbar_el_sistema(sistema):
    contexto = zmq.Context()
    socket = contexto.socket(zmq.REQ)
    socket.setsockopt(zmq.RCVTIMEO, config.TIMEOUT_MS)
    socket.connect(config.direccion(config.HOST_CAPA_SERVICIOS, config.GT_PUERTO_CLIENTES))
    reserva = {"id_evento": "E1", "fecha": "2026/11/01", "n_asientos": 1}
    malos = [
        b"esto no es JSON",
        b"[1, 2, 3]",                                                                    # JSON, pero no un objeto
        m.codificar({"tipo": m.RESERVA, "id_cliente": 1, "datos": reserva}),             # sin uuid
        m.codificar({"uuid": "a", "tipo": m.RESERVA, "id_cliente": "uno", "datos": reserva}),
        m.codificar({"uuid": "b", "tipo": m.RESERVA, "id_cliente": 1, "datos": "nada"}),
        m.codificar({"uuid": "c", "tipo": "BORRAR_TODO", "id_cliente": 1, "datos": {}}),
        m.codificar({"uuid": "d", "tipo": m.AGREGAR_RESERVA, "id_cliente": 1, "datos": reserva}),   # tipo interno
        m.codificar({"uuid": "e", "tipo": m.LIBERAR_RESERVA, "id_cliente": 1, "datos": {"id_reserva": 1}}),
        m.codificar({"uuid": "f", "tipo": m.RESERVA, "id_cliente": 1, "datos": {**reserva, "n_asientos": 10**9}}),
        m.codificar({"uuid": "g", "tipo": m.RESERVA, "id_cliente": 1, "datos": {**reserva, "n_asientos": "2"}}),
        m.codificar({"uuid": "h", "tipo": m.RESERVA, "id_cliente": 1,
                     "datos": {**reserva, "id_evento": "E1'; DROP TABLE reserva; --"}}),
        m.codificar({"uuid": "i", "tipo": m.CANCELACION, "id_cliente": 1, "datos": {"id_reserva": 1}}),   # sin direccion
        m.codificar({"uuid": "j", "tipo": m.CANCELACION, "id_cliente": 1,
                     "datos": {"id_reserva": 1, "notificar_a": "archivo.txt"}}),
    ]
    try:
        for mensaje in malos:
            socket.send(mensaje)
            respuesta = m.decodificar(socket.recv())
            assert respuesta["estado"] in (m.ERROR, m.FALLO), mensaje
    finally:
        socket.close(linger=0)
        contexto.term()

    bd = sistema.bd()
    assert bd.resumen()["ocupados"] == 0 and bd.resumen()["reservas"] == 0     # la BD no cambio
    bd.cerrar()
    cliente = Cliente(5)                                                       # y el sistema sigue atendiendo
    try:
        respuesta, _ = cliente.reservar("E1", "2026/11/01", 1)
        assert respuesta["estado"] == m.EXITO
    finally:
        cliente.cerrar()
