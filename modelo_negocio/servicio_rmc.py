import zmq

PERSISTENCIA_ADDR = "tcp://localhost:5555"
RMC_PORT = 5556

def procesar_modificacion(socket_persistencia, payload):
    # Solicitud de verificación/actualización para modificaciones
    id_cliente = payload.get("id_cliente")
    id_ocurrencia_actual = payload.get("id_ocurrencia_actual")
    id_ocurrencia_nueva = payload.get("id_ocurrencia_nueva", id_ocurrencia_actual)
    nuevos_asientos = payload.get("asientos")

    # Reenvía la solicitud de modificación estructurada a la persistencia
    req_persistencia = {
        "operacion": "MODIFICAR",
        "payload": {
            "id_cliente": id_cliente,
            "id_ocurrencia_actual": id_ocurrencia_actual,
            "id_ocurrencia_nueva": id_ocurrencia_nueva,
            "asientos": nuevos_asientos
        }
    }
    socket_persistencia.send_json(req_persistencia)
    return socket_persistencia.recv_json()

def iniciar_servicio_rmc():
    context = zmq.Context()
    
    # Socket cliente hacia Persistencia
    socket_persistencia = context.socket(zmq.REQ)
    socket_persistencia.connect(PERSISTENCIA_ADDR)

    # Socket servidor frente al Gestor de Transacciones
    socket_rmc = context.socket(zmq.REP)
    socket_rmc.bind(f"tcp://*:{RMC_PORT}")

    print(f"[SERVICIO RMC] Escuchando operaciones síncronas en tcp://*:{RMC_PORT}...")

    while True:
        try:
            mensaje = socket_rmc.recv_json()
            operacion = mensaje.get("operacion")
            payload = mensaje.get("payload", {})

            if operacion in ["CONSULTAR", "RESERVAR"]:
                # Enrutamiento directo a Persistencia
                socket_persistencia.send_json(mensaje)
                respuesta = socket_persistencia.recv_json()
            elif operacion == "MODIFICAR":
                respuesta = procesar_modificacion(socket_persistencia, payload)
            else:
                respuesta = {"status": "ERROR", "mensaje": "Operación síncrona no válida en RMC"}

            socket_rmc.send_json(respuesta)

        except KeyboardInterrupt:
            print("\n[SERVICIO RMC] Apagando...")
            break
        except Exception as e:
            socket_rmc.send_json({"status": "ERROR", "mensaje": str(e)})

    socket_persistencia.close()
    socket_rmc.close()
    context.term()

if __name__ == "__main__":
    iniciar_servicio_rmc()
