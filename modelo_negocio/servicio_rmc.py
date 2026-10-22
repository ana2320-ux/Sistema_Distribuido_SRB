import zmq

# IP de la VM de Persistencia
PERSISTENCIA_ADDR = "tcp://10.43.99.246:5555"
RMC_PORT = 5556

def iniciar_servicio_rmc():
    context = zmq.Context()
    
    socket_persistencia = context.socket(zmq.REQ)
    socket_persistencia.connect(PERSISTENCIA_ADDR)

    socket_rmc = context.socket(zmq.REP)
    socket_rmc.bind(f"tcp://*:{RMC_PORT}")

    print(f"[SERVICIO RMC] Escuchando operaciones síncronas en tcp://*:{RMC_PORT}...")
    print(f"[SERVICIO RMC] Conectado a Persistencia en {PERSISTENCIA_ADDR}")

    while True:
        try:
            mensaje = socket_rmc.recv_json()
            # Enruta las operaciones síncronas hacia la Capa de Persistencia
            socket_persistencia.send_json(mensaje)
            respuesta = socket_persistencia.recv_json()
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
