import zmq

GT_CLIENT_PORT = 5557
RMC_ADDR = "tcp://localhost:5556"
CANCELACIONES_ADDR = "tcp://localhost:5558"

def iniciar_gestor():
    context = zmq.Context()

    # Socket para recibir peticiones de Clientes (Router/Rep)
    socket_frontend = context.socket(zmq.REP)
    socket_frontend.bind(f"tcp://*:{GT_CLIENT_PORT}")

    # Socket para canal síncrono con RMC
    socket_rmc = context.socket(zmq.REQ)
    socket_rmc.connect(RMC_ADDR)

    # Socket para canal asíncrono con Servicio de Cancelaciones (Push)
    socket_cancelaciones = context.socket(zmq.PUSH)
    socket_cancelaciones.connect(CANCELACIONES_ADDR)

    print(f"[GESTOR TRANSACCIONES] Escuchando clientes en tcp://*:{GT_CLIENT_PORT}...")

    while True:
        try:
            mensaje = socket_frontend.recv_json()
            operacion = mensaje.get("operacion")

            if operacion in ["CONSULTAR", "RESERVAR", "MODIFICAR"]:
                # Canal Síncrono
                socket_rmc.send_json(mensaje)
                respuesta = socket_rmc.recv_json()
                socket_frontend.send_json(respuesta)

            elif operacion == "CANCELAR":
                # Canal Asíncrono: Responde de inmediato al cliente
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
