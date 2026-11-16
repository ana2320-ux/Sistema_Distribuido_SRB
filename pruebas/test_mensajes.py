"""Pruebas unitarias del protocolo: armado y validacion de los mensajes JSON."""
import pytest

from config import E_mensaje as m
from capa_cliente.script import interpretar_linea
from capa_negocios.gestor_transacciones import revisar_peticion


def test_peticion_valida_ida_y_vuelta():
    peticion = m.crear_peticion(m.RESERVA, 7, {"id_evento": "E1", "fecha": "2026/11/01", "n_asientos": 2})
    assert peticion["uuid"] and peticion["tipo"] == m.RESERVA
    assert m.decodificar(m.codificar(peticion)) == peticion
    assert revisar_peticion(peticion) is None


def test_cada_peticion_tiene_un_uuid_distinto():
    uuids = {m.crear_peticion(m.CONSULTA, 1, {"mes": "noviembre"})["uuid"] for _ in range(100)}
    assert len(uuids) == 100


@pytest.mark.parametrize("tipo, id_cliente", [("BORRAR", 1), (m.RESERVA, 0), (m.RESERVA, -3), (m.RESERVA, "7")])
def test_peticion_con_tipo_o_cliente_invalido_se_rechaza(tipo, id_cliente):
    with pytest.raises(ValueError):
        m.crear_peticion(tipo, id_cliente, {})


def test_la_respuesta_lleva_el_uuid_de_la_peticion():
    peticion = m.crear_peticion(m.CONSULTA, 1, {"mes": "noviembre"})
    respuesta = m.crear_respuesta(peticion, m.FALLO, m.SIN_CUPO, {"libres": 1})
    assert respuesta["uuid"] == peticion["uuid"] and respuesta["motivo"] == m.SIN_CUPO
    assert m.crear_respuesta(peticion, m.EXITO, "sobra")["motivo"] is None      # un exito no lleva motivo


def test_un_fallo_o_error_exige_un_motivo_valido():
    with pytest.raises(ValueError):
        m.crear_respuesta({}, m.FALLO)
    with pytest.raises(ValueError):
        m.crear_respuesta({}, "QUIZAS")


@pytest.mark.parametrize("texto", [b"esto no es JSON", b"[1, 2]", b'"hola"', b"12"])
def test_decodificar_solo_acepta_objetos_json(texto):
    with pytest.raises(ValueError):
        m.decodificar(texto)


@pytest.mark.parametrize("cambio", [{"uuid": None}, {"uuid": ""}, {"id_cliente": "uno"}, {"id_cliente": True},
                                    {"id_cliente": 0}, {"datos": "nada"}, {"datos": None}])
def test_el_gt_rechaza_peticiones_mal_formadas(cambio):
    peticion = {**m.crear_peticion(m.CONSULTA, 1, {"mes": "noviembre"}), **cambio}
    assert revisar_peticion(peticion) is not None


def test_lineas_de_un_caso_de_prueba():
    assert interpretar_linea("CONSULTA noviembre") == ("CONSULTA", "noviembre")
    assert interpretar_linea("reserva E1 2026/11/01 2") == ("RESERVA", "E1", "2026/11/01", 2)
    assert interpretar_linea("MODIFICACION 3 5") == ("MODIFICACION", 3, 5, None)
    assert interpretar_linea("MODIFICACION 3 2026/11/15") == ("MODIFICACION", 3, None, "2026/11/15")
    assert interpretar_linea("CANCELACION 3") == ("CANCELACION", 3)
    assert interpretar_linea("ESPERAR 1.5") == ("ESPERAR", 1.5)
    for mala in ("RESERVA E2 2026/11/02", "RESERVA E2 2026/11/02 dos", "BORRAR 1"):
        with pytest.raises(ValueError):
            interpretar_linea(mala)
