"""
Prueba el sistema completo a traves del Gestor de Transacciones, como lo haran
los clientes. Requiere: BD recien cargada, persistencia, al menos un RMC y el GT.
Uso:  python -m pruebas.prueba_gt
"""
import threading

import zmq

from config import configuracion as config
from config import E_mensaje as m

resultados: list[bool] = []


def revisar(nombre, condicion):
    resultados.append(condicion)
    print(f"[{'PASA' if condicion else 'FALLA'}] {nombre}")


class ClientePrueba:
    """Un cliente minimo: un REQ hacia el GT con limite de espera."""

    def __init__(self, contexto, id_cliente):
        self.id_cliente = id_cliente
        self.socket = contexto.socket(zmq.REQ)
        self.socket.setsockopt(zmq.RCVTIMEO, config.TIMEOUT_MS)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.connect(config.direccion(config.HOST_CAPA_SERVICIOS, config.GT_PUERTO_CLIENTES))

    def pedir(self, tipo, datos):
        peticion = m.crear_peticion(tipo, self.id_cliente, datos)
        self.socket.send(m.codificar(peticion))
        respuesta = m.decodificar(self.socket.recv())
        if respuesta["uuid"] != peticion["uuid"]:
            raise AssertionError("la respuesta no corresponde a la peticion")
        return respuesta

    def cerrar(self):
        self.socket.close()


def main():
    contexto = zmq.Context()
    c = ClientePrueba(contexto, 1)
    try:
        r = c.pedir(m.CONSULTA, {"mes": "noviembre"})
        revisar("consulta a traves del GT: 70 ocurrencias",
                r["estado"] == m.EXITO and len(r["datos"]["eventos"]) == 70)

        r = c.pedir(m.RESERVA, {"id_evento": "E1", "fecha": "2026/11/01", "n_asientos": 2})
        revisar("reserva a traves del GT: EXITO", r["estado"] == m.EXITO)

        r = c.pedir(m.MODIFICACION, {})
        revisar("MODIFICACION: el GT la rechaza con NO_IMPLEMENTADO",
                r["estado"] == m.ERROR and r["motivo"] == m.NO_IMPLEMENTADO)

        r = c.pedir(m.AGREGAR_RESERVA, {"id_evento": "E1", "fecha": "2026/11/01", "n_asientos": 1})
        revisar("AGREGAR_RESERVA desde un cliente: el GT la rechaza",
                r["estado"] == m.ERROR and r["motivo"] == m.NO_IMPLEMENTADO)

        c.socket.send(b"esto no es JSON")
        r = m.decodificar(c.socket.recv())
        revisar("mensaje que no es JSON: ERROR PETICION_INVALIDA",
                r["estado"] == m.ERROR and r["motivo"] == m.PETICION_INVALIDA)

        # --- 8 clientes a la vez compiten por E2 el 2026/11/02 (100 asientos)
        exitos: list[int] = []
        errores: list[str] = []

        def comprador(id_cliente, intentos):
            cliente = ClientePrueba(contexto, id_cliente)
            ok = 0
            try:
                for _ in range(intentos):
                    r = cliente.pedir(m.RESERVA, {"id_evento": "E2", "fecha": "2026/11/02", "n_asientos": 1})
                    ok += r["estado"] == m.EXITO
            except Exception as e:
                errores.append(f"cliente {id_cliente}: {e}")
            finally:
                cliente.cerrar()
            exitos.append(ok)

        hilos = [threading.Thread(target=comprador, args=(10 + i, 19 if i < 6 else 18))
                 for i in range(8)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        revisar("8 clientes a la vez: cada uno recibio sus propias respuestas", not errores)
        revisar(f"sin sobreventa a traves de todo el sistema: {sum(exitos)} de 150",
                sum(exitos) == 100)

        r = c.pedir(m.CONSULTA, {"mes": "noviembre"})
        e2 = [e for e in r["datos"]["eventos"] if e["id_evento"] == "E2" and e["fecha"] == "2026/11/02"]
        revisar("E2 el 2026/11/02 quedo lleno", bool(e2) and e2[0]["libres"] == 0)
        for e in errores:
            print("   ", e)
    except zmq.Again:
        print("Sin respuesta: estan corriendo el GT, el RMC y la persistencia?")
    finally:
        c.cerrar()
        contexto.term()

    print(f"\n{sum(resultados)}/{len(resultados)} pruebas pasaron")


if __name__ == "__main__":
    main()