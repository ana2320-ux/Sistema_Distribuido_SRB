import zmq
import json
import time
import threading

# IP de la VM de Capa de Negocio (Gestor de Transacciones)
GT_ADDR = "tcp://10.43.100.36:5557"
MI_IP = "10.43.99.237"

def oyente_notificaciones(puerto_notif, id_cliente):
    context = zmq.Context()
    socket_notif = context.socket(zmq.PULL)
    socket_notif.bind(f"tcp://*:{puerto_notif}")
    
    print(f"[{id_cliente}] Escuchando notificaciones asíncronas en puerto {puerto_notif}...")
    
    while True:
        try:
            msg = socket_notif.recv_json()
            print(f"\n========================================")
            print(f" NOTIFICACIÓN ASÍNCRONA RECIBIDA EN CLIENTE [{id_cliente}]:")
            print(f" Status: {msg.get('status')} | Mensaje: {msg.get('mensaje')}")
            print(f"========================================\n")
        except Exception:
            break

def simular_cliente(id_cliente, puerto_notif):
    context = zmq.Context()
    socket_gt = context.socket(zmq.REQ)
    socket_gt.connect(GT_ADDR)

    t_notif = threading.Thread(target=oyente_notificaciones, args=(puerto_notif, id_cliente), daemon=True)
    t_notif.start()

    print(f"\n--- INICIANDO PRUEBAS DESDE VM CLIENTE: {id_cliente} ---")

    # 1. CONSULTA
    print(f"\n1. Enviando CONSULTA a Capa de Negocio ({GT_ADDR})...")
    socket_gt.send_json({"operacion": "CONSULTAR"})
    res = socket_gt.recv_json()
    print(f"   [Respuesta]: Status={res.get('status')}, Total Eventos={len(res.get('data', []))}")

    # 2. RESERVA
    print(f"\n2. Enviando RESERVA de 2 asientos...")
    socket_gt.send_json({
        "operacion": "RESERVAR",
        "payload": {
            "id_cliente": id_cliente,
            "id_ocurrencia": 1,
            "asientos": 2
        }
    })
    res_reserva = socket_gt.recv_json()
    print(f"   [Respuesta]: {res_reserva}")

    # 3. MODIFICACIÓN
    print(f"\n3. Enviando MODIFICACIÓN de reserva...")
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
    print(f"   [Respuesta]: {res_modif}")

    # 4. CANCELACIÓN (Pasa la IP de esta máquina para recibir la respuesta asíncrona)
    print(f"\n4. Enviando CANCELACIÓN (Asíncrona)...")
    socket_gt.send_json({
        "operacion": "CANCELAR",
        "payload": {
            "id_reserva": 1,
            "id_ocurrencia": 2,
            "asientos": 2,
            "endpoint_notificacion": f"tcp://{MI_IP}:{puerto_notif}"
        }
    })
    res_cancel = socket_gt.recv_json()
    print(f"   [Respuesta Inmediata GT]: {res_cancel}")

    time.sleep(3)
    socket_gt.close()
    context.term()

if __name__ == "__main__":
    simular_cliente("Cliente_VM_01", 6001)
