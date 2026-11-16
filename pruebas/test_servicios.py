"""
Pruebas unitarias de la logica del Servicio de Persistencia y del RMC, sin red:
el RMC le habla a la persistencia por una llamada directa en lugar de un socket.
"""
import pytest

from config import E_mensaje as m
from capa_negocios.cliente_persistencia import PersistenciaNoDisponible
from capa_negocios.rmc import ServicioRMC
from capa_persistencia.servicio_persistencia import ServicioPersistencia

RESERVA_E1 = {"id_evento": "E1", "fecha": "2026/11/01", "n_asientos": 2}


class PersistenciaDirecta:
    """Hace de ClientePersistencia: entrega la peticion al servicio sin pasar por la red."""

    def __init__(self, servicio):
        self.servicio = servicio
        self.recibidas = []

    def enviar(self, peticion):
        self.recibidas.append(peticion["tipo"])
        return self.servicio.atender(peticion)


@pytest.fixture
def persistencia(bd):
    return PersistenciaDirecta(ServicioPersistencia(bd))


@pytest.fixture
def rmc(persistencia):
    return ServicioRMC(persistencia)


def estado(respuesta):
    return respuesta["estado"], respuesta["motivo"]


# ---------------------------------------------------------------- consulta
def test_consulta_de_un_mes(rmc):
    respuesta = rmc.atender(m.crear_peticion(m.CONSULTA, 1, {"mes": "Noviembre"}))
    assert respuesta["estado"] == m.EXITO and len(respuesta["datos"]["eventos"]) == 70


@pytest.mark.parametrize("mes", ["nobiembre", "", 11, None])
def test_consulta_con_mes_invalido(rmc, mes):
    assert estado(rmc.atender(m.crear_peticion(m.CONSULTA, 1, {"mes": mes}))) == (m.ERROR, m.DATO_INVALIDO)


# ---------------------------------------------------------------- reserva
def test_reserva_sigue_los_pasos_del_enunciado(rmc, persistencia, bd):
    respuesta = rmc.atender(m.crear_peticion(m.RESERVA, 7, RESERVA_E1))
    assert respuesta["estado"] == m.EXITO and respuesta["datos"]["id_reserva"] == 1
    assert persistencia.recibidas == [m.CONSULTA_DISPONIBILIDAD, m.AGREGAR_RESERVA]
    assert bd.disponibilidad("E1", "2026/11/01")["puestos_ocupados"] == 2


def test_reserva_sin_cupo_no_llega_a_escribir(rmc, persistencia, bd):
    respuesta = rmc.atender(m.crear_peticion(m.RESERVA, 7, {**RESERVA_E1, "n_asientos": 101}))
    assert estado(respuesta) == (m.FALLO, m.SIN_CUPO)
    assert persistencia.recibidas == [m.CONSULTA_DISPONIBILIDAD]
    assert bd.resumen()["reservas"] == 0


@pytest.mark.parametrize("n_asientos", [0, -2, "dos", 2.5, True, None])
def test_reserva_con_asientos_invalidos(rmc, bd, n_asientos):
    respuesta = rmc.atender(m.crear_peticion(m.RESERVA, 7, {**RESERVA_E1, "n_asientos": n_asientos}))
    assert estado(respuesta) == (m.ERROR, m.DATO_INVALIDO)
    assert bd.resumen()["reservas"] == 0


@pytest.mark.parametrize("datos, esperado", [
    ({**RESERVA_E1, "id_evento": "E77"}, (m.FALLO, m.NO_EXISTE)),
    ({**RESERVA_E1, "fecha": "2026/11/02"}, (m.FALLO, m.NO_EXISTE)),         # E1 no ocurre ese dia
    ({**RESERVA_E1, "fecha": "02-11-2026"}, (m.ERROR, m.DATO_INVALIDO)),
    ({**RESERVA_E1, "id_evento": 5}, (m.ERROR, m.DATO_INVALIDO)),
    ({**RESERVA_E1, "id_evento": "E1'; DROP TABLE reserva; --"}, (m.FALLO, m.NO_EXISTE)),   # inyeccion SQL
])
def test_reserva_con_datos_que_no_corresponden(rmc, bd, datos, esperado):
    assert estado(rmc.atender(m.crear_peticion(m.RESERVA, 7, datos))) == esperado
    assert bd.resumen()["reservas"] == 0 and len(bd.consultar_mes(11)) == 70


# ---------------------------------------------------------------- idempotencia y reintentos
def test_la_misma_peticion_dos_veces_hace_una_sola_reserva(rmc, bd):
    peticion = m.crear_peticion(m.RESERVA, 7, RESERVA_E1)
    primera, segunda = rmc.atender(peticion), rmc.atender(peticion)
    assert primera == segunda and primera["estado"] == m.EXITO
    assert bd.resumen()["reservas"] == 1 and bd.disponibilidad("E1", "2026/11/01")["puestos_ocupados"] == 2


def test_un_reintento_no_es_rechazado_por_sus_propios_asientos(rmc, persistencia, bd):
    """La reserva lleno la ocurrencia y su respuesta se perdio: el reintento devuelve la misma reserva."""
    peticion = m.crear_peticion(m.RESERVA, 7, {**RESERVA_E1, "n_asientos": 100})
    primera = rmc.atender(peticion)
    persistencia.recibidas.clear()
    reintento = rmc.atender({**peticion, "reintento": True})
    assert reintento == primera and primera["estado"] == m.EXITO
    assert persistencia.recibidas == [m.AGREGAR_RESERVA]           # directo a la escritura
    assert bd.resumen()["reservas"] == 1


def test_un_reintento_de_cambio_de_fecha_no_se_aplica_dos_veces(rmc, bd):
    id_reserva = rmc.atender(m.crear_peticion(m.RESERVA, 7, {**RESERVA_E1, "n_asientos": 100}))["datos"]["id_reserva"]
    peticion = m.crear_peticion(m.MODIFICACION, 7, {"id_reserva": id_reserva, "fecha": "2026/11/15"})
    primera = rmc.atender(peticion)
    reintento = rmc.atender({**peticion, "reintento": True})
    assert reintento == primera and primera["estado"] == m.EXITO
    assert bd.disponibilidad("E1", "2026/11/15")["puestos_ocupados"] == 100
    assert bd.disponibilidad("E1", "2026/11/01")["puestos_ocupados"] == 0


# ---------------------------------------------------------------- modificacion
def test_modificacion_sigue_los_pasos_del_enunciado(rmc, persistencia):
    id_reserva = rmc.atender(m.crear_peticion(m.RESERVA, 7, RESERVA_E1))["datos"]["id_reserva"]
    persistencia.recibidas.clear()
    respuesta = rmc.atender(m.crear_peticion(m.MODIFICACION, 7, {"id_reserva": id_reserva, "n_asientos": 5}))
    assert respuesta["estado"] == m.EXITO and respuesta["datos"]["n_asientos"] == 5
    assert persistencia.recibidas == [m.CONSULTAR_RESERVA, m.CONSULTA_DISPONIBILIDAD, m.MODIFICAR_RESERVA]


@pytest.mark.parametrize("datos, esperado", [
    ({"id_reserva": 99, "n_asientos": 2}, (m.FALLO, m.NO_EXISTE)),            # la reserva no existe
    ({"id_reserva": 1, "n_asientos": 101}, (m.FALLO, m.SIN_CUPO)),
    ({"id_reserva": 1, "n_asientos": 0}, (m.ERROR, m.DATO_INVALIDO)),
    ({"id_reserva": "uno", "n_asientos": 2}, (m.ERROR, m.DATO_INVALIDO)),
    ({"id_reserva": 1, "fecha": "2026/11/16"}, (m.FALLO, m.NO_EXISTE)),       # E30 ocurre una sola vez
    ({"id_reserva": 1, "fecha": "manana"}, (m.ERROR, m.DATO_INVALIDO)),
])
def test_modificacion_rechazada_deja_la_reserva_como_estaba(rmc, bd, datos, esperado):
    rmc.atender(m.crear_peticion(m.RESERVA, 7, {"id_evento": "E30", "fecha": "2026/11/02", "n_asientos": 7}))
    assert estado(rmc.atender(m.crear_peticion(m.MODIFICACION, 7, datos))) == esperado
    reserva = bd.consultar_reserva(1)
    assert (reserva["fecha"], reserva["n_asientos"]) == ("2026/11/02", 7)
    assert bd.disponibilidad("E30", "2026/11/02")["puestos_ocupados"] == 7


# ---------------------------------------------------------------- cancelacion (lado de la persistencia)
def test_liberar_reserva_es_idempotente(persistencia, bd):
    bd.agregar_reserva(7, "E1", "2026/11/01", 4)
    peticion = m.crear_peticion(m.LIBERAR_RESERVA, 7, {"id_reserva": 1})
    primera, segunda = persistencia.enviar(peticion), persistencia.enviar(peticion)
    assert primera == segunda and primera["estado"] == m.EXITO
    assert bd.disponibilidad("E1", "2026/11/01")["puestos_ocupados"] == 0
    otra = persistencia.enviar(m.crear_peticion(m.LIBERAR_RESERVA, 7, {"id_reserva": 1}))
    assert estado(otra) == (m.FALLO, m.NO_EXISTE)                  # otra cancelacion de la misma reserva


# ---------------------------------------------------------------- limites del servicio
def test_la_replica_de_lectura_no_atiende_escrituras(bd):
    replica = ServicioPersistencia(bd, solo_lectura=True)
    assert replica.atender(m.crear_peticion(m.CONSULTA, 1, {"mes": "noviembre"}))["estado"] == m.EXITO
    for tipo in (m.AGREGAR_RESERVA, m.MODIFICAR_RESERVA, m.LIBERAR_RESERVA):
        assert estado(replica.atender(m.crear_peticion(tipo, 1, RESERVA_E1))) == (m.ERROR, m.PETICION_INVALIDA)
    assert bd.resumen()["reservas"] == 0


def test_el_rmc_no_atiende_tipos_que_no_son_suyos(rmc):
    for tipo in (m.CANCELACION, m.AGREGAR_RESERVA, m.LIBERAR_RESERVA):
        assert estado(rmc.atender(m.crear_peticion(tipo, 1, RESERVA_E1))) == (m.ERROR, m.PETICION_INVALIDA)


def test_si_la_persistencia_no_responde_el_rmc_avisa(bd):
    class PersistenciaCaida:
        def enviar(self, peticion):
            raise PersistenciaNoDisponible("la persistencia no respondio")

    respuesta = ServicioRMC(PersistenciaCaida()).atender(m.crear_peticion(m.RESERVA, 7, RESERVA_E1))
    assert estado(respuesta) == (m.ERROR, m.NO_DISPONIBLE)
