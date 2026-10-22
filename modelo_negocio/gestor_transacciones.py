import zmq

GT_CLIENT_PORT = 5557
RMC_ADDR = "tcp://localhost:5556"
CANCELACIONES_ADDR = "tcp://localhost:5558"

def iniciar_gestor():
    context = zmq.Context()

    socket_frontend = context.socket(zmq.REP)
    socket_frontend.bind(f"tcp://*:{GT_CLIENT_PORT}")

    socket_rmc = context.socket(zmq.REQ)
    socket_rmc.connect(RMC_ADDR)

    socket_cancelaciones = context.socket(zmq.PUSH)
    socket_cancelaciones.connect(CANCELACIONES_ADDR)

    print(f"[GESTOR TRANSACCIONES] Escuchando clientes de red en tcp://*:{GT_CLIENT_PORT}...")

    while True:
        try:
            mensaje = socket_frontend.recv_json()
            operacion = mensaje.get("operacion")

            if operacion in ["CONSULTAR", "RESERVAR", "MODIFICAR"]:
                socket_rmc.send_json(mensaje)
                respuesta = socket_rmc.recv_json()
                socket_frontend.send_json(respuesta)

            elif operacion == "CANCELAR":
                socket_cancelaciones.send_json(mensaje)
                socket_frontend.send_json({
                    "status": "ACEPTADO", 
                    "mensaje": "Solicitud de cancelación recibida. Recibirá una notificación al procesarse."
                })
            else:
                socket_frontend.send_json({"status": "ERROR", "mensaje": "Operación desconocida"})

        except KeyboardInterrupt:
            print("\n[GESTOR TRANSACCIONES] Apagando...")
            break

    socket_frontend.close()
    socket_rmc.close()
    socket_cancelaciones.close()
    context.term()

if __name__ == "__main__":
    iniciar_gestor()
