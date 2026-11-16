"""Pruebas unitarias de la base de datos (capa_persistencia/db.py), sin red."""
import threading

import pytest

from capa_persistencia.db import BaseDatos, NoExiste, SinCupo

E1_DIA_1 = ("E1", "2026/11/01")       # E1 ocurre el 01 y el 15
E1_DIA_15 = ("E1", "2026/11/15")
E30_DIA_2 = ("E30", "2026/11/02")     # E30 ocurre una sola vez


def test_carga_inicial_del_enunciado(bd):
    noviembre = bd.consultar_mes(11)
    assert len(noviembre) == 70 and len({o["id_evento"] for o in noviembre}) == 50
    assert all(o["capacidad"] == 100 and o["libres"] == 100 for o in noviembre)
    assert bd.consultar_mes(10) == []
    assert bd.resumen() == {"eventos": 50, "ocurrencias": 70, "capacidad": 7000, "ocupados": 0, "reservas": 0}


def test_tras_una_reserva_libres_mas_ocupados_es_la_capacidad(bd):
    reserva = bd.agregar_reserva(7, *E1_DIA_1, 10)
    assert reserva["id_reserva"] == 1
    d = bd.disponibilidad(*E1_DIA_1)
    assert (d["puestos_ocupados"], d["libres"]) == (10, 90)
    assert d["libres"] + d["puestos_ocupados"] == d["capacidad"] and d["libres"] >= 0


def test_reservar_mas_de_los_libres_no_cambia_nada(bd):
    bd.agregar_reserva(7, *E1_DIA_1, 10)
    with pytest.raises(SinCupo):
        bd.agregar_reserva(8, *E1_DIA_1, 91)
    assert bd.disponibilidad(*E1_DIA_1)["libres"] == 90
    bd.agregar_reserva(8, *E1_DIA_1, 90)              # exactamente los que quedan si se puede
    assert bd.disponibilidad(*E1_DIA_1)["libres"] == 0


def test_evento_o_fecha_inexistente(bd):
    with pytest.raises(NoExiste):
        bd.disponibilidad("E99", "2026/11/01")
    with pytest.raises(NoExiste):
        bd.agregar_reserva(7, "E30", "2026/11/16", 1)
    assert bd.resumen()["reservas"] == 0


def test_modificar_el_numero_de_asientos(bd):
    id_reserva = bd.agregar_reserva(7, *E1_DIA_1, 3)["id_reserva"]
    assert bd.modificar_reserva(id_reserva, n_asientos=8)["n_asientos"] == 8
    assert bd.disponibilidad(*E1_DIA_1)["puestos_ocupados"] == 8
    bd.modificar_reserva(id_reserva, n_asientos=2)
    assert bd.disponibilidad(*E1_DIA_1)["puestos_ocupados"] == 2
    with pytest.raises(SinCupo):                      # rechazada: la reserva queda como estaba
        bd.modificar_reserva(id_reserva, n_asientos=101)
    assert bd.consultar_reserva(id_reserva)["n_asientos"] == 2
    assert bd.verificar()


def test_cambiar_la_fecha_en_un_evento_de_dos_ocurrencias(bd):
    id_reserva = bd.agregar_reserva(7, *E1_DIA_1, 4)["id_reserva"]
    reserva = bd.modificar_reserva(id_reserva, fecha="2026/11/15")
    assert (reserva["fecha"], reserva["n_asientos"]) == ("2026/11/15", 4)
    assert bd.disponibilidad(*E1_DIA_1)["puestos_ocupados"] == 0      # devueltos en la fecha origen
    assert bd.disponibilidad(*E1_DIA_15)["puestos_ocupados"] == 4     # descontados en la destino
    assert bd.verificar()


def test_un_evento_de_una_sola_ocurrencia_no_admite_cambio_de_fecha(bd):
    id_reserva = bd.agregar_reserva(7, *E30_DIA_2, 5)["id_reserva"]
    with pytest.raises(NoExiste):
        bd.modificar_reserva(id_reserva, fecha="2026/11/16")
    assert bd.consultar_reserva(id_reserva)["fecha"] == "2026/11/02"
    assert bd.disponibilidad(*E30_DIA_2)["puestos_ocupados"] == 5
    assert bd.modificar_reserva(id_reserva, n_asientos=6)["n_asientos"] == 6     # asientos si


def test_cambio_de_fecha_sin_cupo_deja_todo_como_estaba(bd):
    id_reserva = bd.agregar_reserva(7, *E1_DIA_1, 4)["id_reserva"]
    bd.agregar_reserva(8, *E1_DIA_15, 98)
    with pytest.raises(SinCupo):
        bd.modificar_reserva(id_reserva, fecha="2026/11/15")
    assert bd.disponibilidad(*E1_DIA_1)["puestos_ocupados"] == 4      # no se alcanzo a liberar el origen
    assert bd.disponibilidad(*E1_DIA_15)["puestos_ocupados"] == 98
    assert bd.verificar()


def test_liberar_una_reserva_devuelve_los_asientos(bd):
    id_reserva = bd.agregar_reserva(7, *E1_DIA_1, 6)["id_reserva"]
    liberada = bd.liberar_reserva(id_reserva)
    assert liberada["n_asientos"] == 6
    assert bd.disponibilidad(*E1_DIA_1)["puestos_ocupados"] == 0
    assert bd.resumen()["reservas"] == 0
    for operacion in (bd.liberar_reserva, bd.consultar_reserva):       # ya no existe como reserva activa
        with pytest.raises(NoExiste):
            operacion(id_reserva)
    with pytest.raises(NoExiste):
        bd.modificar_reserva(id_reserva, n_asientos=2)
    assert bd.verificar()


def test_una_escritura_queda_registrada_por_su_uuid(bd):
    assert bd.operacion_hecha("abc") is None
    reserva = bd.agregar_reserva(7, *E1_DIA_1, 2, uuid="abc")
    assert bd.operacion_hecha("abc") == reserva
    with pytest.raises(SinCupo):
        bd.agregar_reserva(7, *E1_DIA_1, 500, uuid="xyz")
    assert bd.operacion_hecha("xyz") is None           # una operacion rechazada no queda registrada


def test_varias_conexiones_a_la_vez_no_sobrevenden(bd):
    """8 hilos, cada uno con su conexion, hacen 150 intentos de 1 asiento sobre 100."""
    exitos = []

    def comprador(id_cliente, intentos):
        mi_bd = BaseDatos(bd.ruta)
        aceptadas = 0
        for _ in range(intentos):
            try:
                mi_bd.agregar_reserva(id_cliente, "E2", "2026/11/02", 1)
                aceptadas += 1
            except SinCupo:
                pass
        mi_bd.cerrar()
        exitos.append(aceptadas)

    hilos = [threading.Thread(target=comprador, args=(100 + i, 19 if i < 6 else 18)) for i in range(8)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert sum(exitos) == 100
    assert bd.disponibilidad("E2", "2026/11/02")["libres"] == 0
    assert bd.verificar()
