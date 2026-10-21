import zmq

context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect("tcp://localhost:5555")

print("--- 1. Enviando petición de CONSULTA ---")
socket.send_json({"operacion": "CONSULTAR"})
respuesta = socket.recv_json()
print(f"Estado: {respuesta.get('status')}")
print(f"Total eventos recibidos: {len(respuesta.get('data', []))}")
print(f"Ejemplo evento 1: {respuesta.get('data', [])[0] if respuesta.get('data') else 'N/A'}")

print("\n--- 2. Enviando petición de RESERVA ---")
socket.send_json({
    "operacion": "RESERVAR",
    "payload": {
        "id_cliente": "ClientePrueba_01",
        "id_ocurrencia": 1,
        "asientos": 2
    }
})
respuesta_reserva = socket.recv_json()
print(f"Respuesta Reserva: {respuesta_reserva}")

socket.close()
context.term()
