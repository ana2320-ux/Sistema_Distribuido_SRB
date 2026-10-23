"""
Prueba el RMC haciendose pasar por el GT: abre el puerto GT_PUERTO_RMC con un
REQ y le envia peticiones como lo haria un cliente.
Requiere: BD recien cargada, persistencia corriendo y RMC corriendo.
Uso:  python -m pruebas.prueba_rmc
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
    socket.setsockopt(zmq.RCVTIMEO, config.TIMEOUT_MS)
    socket.bind(config.direccion_bind(config.GT_PUERTO_RMC))   # hace de GT: el RMC se conecta aqui

    def pedir(tipo, datos, id_cliente=7):
        peticion = m.crear_peticion(tipo, id_cliente, datos)
        socket.send(m.codificar(peticion))
        respuesta = m.decodificar(socket.recv())
        uuids_correctos.append(respuesta["uuid"] == peticion["uuid"])
        return respuesta

    try:
        r = pedir(m.CONSULTA, {"mes": "noviembre"})
        revisar("consulta de noviembre a traves del RMC: 70 ocurrencias",
                r["estado"] == m.EXITO and len(r["datos"]["eventos"]) == 70)

        r = pedir(m.RESERVA, {"id_evento": "E3", "fecha": "2026/11/03", "n_asientos": 4})
        revisar("reserva valida: EXITO con id de reserva",
                r["estado"] == m.EXITO and "id_reserva" in r["datos"])

        r = pedir(m.RESERVA, {"id_evento": "E3", "fecha": "2026/11/03", "n_asientos": 97})
        revisar("97 asientos con 96 libres: FALLO SIN_CUPO (lo decide el RMC)",
                r["estado"] == m.FALLO and r["motivo"] == m.SIN_CUPO)

        r = pedir(m.RESERVA, {"id_evento": "E3", "fecha": "2026/11/03", "n_asientos": 96})
        revisar("se pueden reservar exactamente los 96 restantes", r["estado"] == m.EXITO)

        r = pedir(m.RESERVA, {"id_evento": "E99", "fecha": "2026/11/03", "n_asientos": 1})
        revisar("evento inexistente: FALLO NO_EXISTE (viene de la persistencia)",
                r["estado"] == m.FALLO and r["motivo"] == m.NO_EXISTE)

        r = pedir(m.RESERVA, {"id_evento": "E3", "fecha": "2026/11/03", "n_asientos": 0})
        revisar("cero asientos: ERROR DATO_INVALIDO, sin preguntar a la persistencia",
                r["estado"] == m.ERROR and r["motivo"] == m.DATO_INVALIDO)

        r = pedir(m.RESERVA, {"id_evento": "E3", "fecha": "3 de noviembre", "n_asientos": 1})
        revisar("fecha mal escrita: ERROR DATO_INVALIDO (viene de la persistencia)",
                r["estado"] == m.ERROR and r["motivo"] == m.DATO_INVALIDO)

        r = pedir(m.AGREGAR_RESERVA, {"id_evento": "E4", "fecha": "2026/11/04", "n_asientos": 1})
        revisar("AGREGAR_RESERVA directo al RMC: ERROR PETICION_INVALIDA",
                r["estado"] == m.ERROR and r["motivo"] == m.PETICION_INVALIDA)

        r = pedir(m.CONSULTA, {"mes": "noviembre"})
        e3 = [e for e in r["datos"]["eventos"] if e["id_evento"] == "E3" and e["fecha"] == "2026/11/03"]
        revisar("al final E3 el 2026/11/03 esta lleno", e3 and e3[0]["libres"] == 0)
        revisar("todas las respuestas traen el uuid de su peticion", all(uuids_correctos))
    except zmq.Again:
        print("Sin respuesta: estan corriendo el RMC y la persistencia?")
    finally:
        socket.close(linger=0)
        contexto.term()

    print(f"\n{sum(resultados)}/{len(resultados)} pruebas pasaron")


if __name__ == "__main__":
    main()