import zmq
import json
import time
import threading
import random

GT_ADDR = "tcp://localhost:5557"

def oyente_notificaciones(puerto_notif, id_cliente):
    """Escucha en segundo plano las notificaciones asíncronas de cancelación."""
    context = zmq.Context()
    socket_notif = context.socket(zmq.PULL)
    socket_notif.bind(f"tcp://*:{puerto_notif}")
    
    print(f"[{id_cliente}] Escuchando notificaciones en puerto {puerto_notif}...")
    
    while True:
        try:
            msg = socket_notif.recv_json()
            print(f"\n========================================")
            print(f" NOTIFICACIÓN ASÍNCRONA PARA [{id_cliente}]:")
            print(f" Status: {msg.get('status')} | Mensaje: {msg.get('mensaje')}")
            print(f"========================================\n")
        except Exception:
            break

def simular_cliente(id_cliente, puerto_notif):
    context = zmq.Context()
    socket_gt = context.socket(zmq.REQ)
    socket_gt.connect(GT_ADDR)

    # Iniciar hilo para recibir notificaciones asíncronas
    t_notif = threading.Thread(target=oyente_notificaciones, args=(puerto_notif, id_cliente), daemon=True)
    t_notif.start()

    print(f"\n--- INICIANDO PRUEBAS DEL CLIENTE: {id_cliente} ---")

    # 1. Petición de CONSULTA (Síncrona)
    print(f"\n1. [{id_cliente}] Enviando CONSULTA de eventos...")
    socket_gt.send_json({"operacion": "CONSULTAR"})
    res = socket_gt.recv_json()
    print(f"   [Respuesta GT]: Status={res.get('status')}, Total Eventos={len(res.get('data', []))}")

    # 2. Petición de RESERVA (Síncrona)
    print(f"\n2. [{id_cliente}] Enviando RESERVA de 2 asientos para la Ocurrencia #1...")
    socket_gt.send_json({
        "operacion": "RESERVAR",
        "payload": {
            "id_cliente": id_cliente,
            "id_ocurrencia": 1,
            "asientos": 2
        }
    })
    res_reserva = socket_gt.recv_json()
    print(f"   [Respuesta GT]: {res_reserva}")

    # 3. Petición de MODIFICACIÓN (Síncrona)
    print(f"\n3. [{id_cliente}] Enviando MODIFICACIÓN de la reserva...")
    socket_gt.send_json({
        "operacion": "MODIFICAR",
        "payload": {
            "id_cliente": id_cliente,
            "id_ocurrencia_actual": 1,
            "id_ocurrencia_nueva": 2,
            "asientos": 2
        }
    })
    res_modif = socket_gt.recv_json()
    print(f"   [Respuesta GT]: {res_modif}")

    # 4. Petición de CANCELACIÓN (Asíncrona)
    print(f"\n4. [{id_cliente}] Enviando CANCELACIÓN (Asíncrona)...")
    socket_gt.send_json({
        "operacion": "CANCELAR",
        "payload": {
            "id_reserva": 1,
            "id_ocurrencia": 1,
            "asientos": 2,
            "endpoint_notificacion": f"tcp://localhost:{puerto_notif}"
        }
    })
    res_cancel = socket_gt.recv_json()
    print(f"   [Respuesta Inmediata GT]: {res_cancel}")

    # Esperar a recibir la notificación asíncrona
    time.sleep(2)
    socket_gt.close()
    context.term()

if __name__ == "__main__":
    simular_cliente("Cliente_Demo_01", 6001)
