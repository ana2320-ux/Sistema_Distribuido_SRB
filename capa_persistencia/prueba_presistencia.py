"""
Prueba el Servicio de Persistencia por la red, como lo hara el RMC.
Requiere: BD recien cargada (python -m capa_persistencia.cargar_datos)
          y el servicio corriendo (python -m capa_persistencia.main)
Uso:  python -m pruebas.prueba_persistencia
"""
import zmq

from config import configuracion as config
from config import E_mensaje as m

resultados: list[bool] = []
uuids_correctos: list[bool] = []


def revisar(nombre, condicion):
    resultados.append(condicion)
    print(f"[{'PASA' if condicion else 'FALLA'}] {nombre}")


def main():
    contexto = zmq.Context()
    socket = contexto.socket(zmq.REQ)
    socket.setsockopt(zmq.RCVTIMEO, config.TIMEOUT_MS)   # no esperar para siempre
    socket.connect(config.direccion(config.HOST_CAPA_PERSISTENCIA, config.SP_PUERTO))

    def pedir(tipo, datos):
        peticion = m.crear_peticion(tipo, 7, datos)
        socket.send(m.codificar(peticion))
        respuesta = m.decodificar(socket.recv())
        uuids_correctos.append(respuesta["uuid"] == peticion["uuid"])
        return respuesta

    try:
        r = pedir(m.CONSULTA, {"mes": "noviembre"})
        revisar("consulta de noviembre: 70 ocurrencias",
                r["estado"] == m.EXITO and len(r["datos"]["eventos"]) == 70)

        r = pedir(m.CONSULTA, {"mes": "Noviembre "})
        revisar("el mes se acepta con mayusculas y espacios", r["estado"] == m.EXITO)

        r = pedir(m.CONSULTA, {"mes": "noviembr"})
        revisar("mes mal escrito: ERROR DATO_INVALIDO",
                r["estado"] == m.ERROR and r["motivo"] == m.DATO_INVALIDO)

        r = pedir(m.CONSULTA_DISPONIBILIDAD, {"id_evento": "E1", "fecha": "2026/11/01"})
        revisar("disponibilidad de E1 el 2026/11/01: 100 libres",
                r["estado"] == m.EXITO and r["datos"]["libres"] == 100)

        r = pedir(m.AGREGAR_RESERVA, {"id_evento": "E1", "fecha": "2026/11/1", "n_asientos": 3})
        revisar("reserva con fecha '2026/11/1' (sin cero) funciona",
                r["estado"] == m.EXITO and r["datos"]["fecha"] == "2026/11/01")

        r = pedir(m.AGREGAR_RESERVA, {"id_evento": "E1", "fecha": "2026/11/01", "n_asientos": 98})
        revisar("98 asientos con 97 libres: FALLO SIN_CUPO",
                r["estado"] == m.FALLO and r["motivo"] == m.SIN_CUPO)

        r = pedir(m.AGREGAR_RESERVA, {"id_evento": "E99", "fecha": "2026/11/01", "n_asientos": 1})
        revisar("evento inexistente: FALLO NO_EXISTE",
                r["estado"] == m.FALLO and r["motivo"] == m.NO_EXISTE)

        r = pedir(m.AGREGAR_RESERVA, {"id_evento": "E1", "fecha": "01-11-2026", "n_asientos": 1})
        revisar("fecha con otro formato: ERROR DATO_INVALIDO",
                r["estado"] == m.ERROR and r["motivo"] == m.DATO_INVALIDO)

        r = pedir(m.AGREGAR_RESERVA, {"id_evento": "E1", "fecha": "2026/11/01", "n_asientos": "2"})
        revisar("n_asientos como texto: ERROR DATO_INVALIDO",
                r["estado"] == m.ERROR and r["motivo"] == m.DATO_INVALIDO)

        r = pedir(m.RESERVA, {"id_evento": "E1", "fecha": "2026/11/01", "n_asientos": 1})
        revisar("RESERVA no es para la persistencia: ERROR PETICION_INVALIDA",
                r["estado"] == m.ERROR and r["motivo"] == m.PETICION_INVALIDA)

        socket.send(b"esto no es JSON")
        r = m.decodificar(socket.recv())
        revisar("mensaje que no es JSON: ERROR PETICION_INVALIDA, y el servicio sigue vivo",
                r["estado"] == m.ERROR and r["motivo"] == m.PETICION_INVALIDA)

        r = pedir(m.CONSULTA_DISPONIBILIDAD, {"id_evento": "E1", "fecha": "2026/11/01"})
        revisar("al final E1 el 2026/11/01 tiene 97 libres", r["datos"]["libres"] == 97)
        revisar("todas las respuestas traen el uuid de su peticion", all(uuids_correctos))
    except zmq.Again:
        print("Sin respuesta: el servicio de persistencia esta corriendo?")
    finally:
        socket.close(linger=0)
        contexto.term()

    print(f"\n{sum(resultados)}/{len(resultados)} pruebas pasaron")


if __name__ == "__main__":
    main()