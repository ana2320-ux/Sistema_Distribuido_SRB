import zmq

CANCEL_PORT = 5558
PERSISTENCIA_ADDR = "tcp://10.43.99.246:5555"

def procesar_cancelacion(payload):
    id_reserva = payload.get("id_reserva")
    id_ocurrencia = payload.get("id_ocurrencia")
    asientos = payload.get("asientos")
    endpoint_notificacion = payload.get("endpoint_notificacion")

    context = zmq.Context()
    socket_persistencia = context.socket(zmq.REQ)
    socket_persistencia.connect(PERSISTENCIA_ADDR)

    # Reenvía la liberación a la capa de persistencia remota
    req_cancel = {
        "operacion": "MODIFICAR",
        "payload": {
            "id_ocurrencia_actual": id_ocurrencia,
            "id_ocurrencia_nueva": id_ocurrencia,
            "asientos": -asientos # Suma de regreso los cupos
        }
    }
    
    try:
        socket_persistencia.send_json(req_cancel)
        res_pers = socket_persistencia.recv_json()
        exito = (res_pers.get("status") == "OK")
        msg = f"Cancelación de reserva #{id_reserva} procesada exitosamente."
    except Exception as e:
        exito = False
        msg = f"Falla en cancelación: {str(e)}"
    finally:
        socket_persistencia.close()

    # Enviar notificación asíncrona a la IP de la VM Clientes (10.43.99.237)
    if endpoint_notificacion:
        s_notif = context.socket(zmq.PUSH)
        try:
            s_notif.connect(endpoint_notificacion)
            s_notif.send_json({"status": "OK" if exito else "ERROR", "mensaje": msg})
        except Exception as e:
            print(f"[CANCELACIONES] No se pudo enviar notificación: {e}")
        finally:
            s_notif.close()
            
    context.term()

def iniciar_servicio_cancelaciones():
    context = zmq.Context()
    socket_pull = context.socket(zmq.PULL)
    socket_pull.bind(f"tcp://*:{CANCEL_PORT}")

    print(f"[SERVICIO CANCELACIONES] Escuchando solicitudes en tcp://*:{CANCEL_PORT}...")

    while True:
        try:
            mensaje = socket_pull.recv_json()
            payload = mensaje.get("payload", {})
            procesar_cancelacion(payload)
        except KeyboardInterrupt:
            print("\n[SERVICIO CANCELACIONES] Apagando...")
            break

    socket_pull.close()
    context.term()

if __name__ == "__main__":
    iniciar_servicio_cancelaciones()
