import sqlite3
import json
import zmq

DB_NAME = "reserva_boletos.db"
PORT = 5555

def procesar_consulta(cursor, payload):
    # Consulta de eventos del mes
    cursor.execute("""
        SELECT e.id_evento, e.nombre, o.id_ocurrencia, o.fecha, o.capacidad, o.ocupados, o.libres 
        FROM eventos e 
        JOIN ocurrencias o ON e.id_evento = o.id_evento
    """)
    filas = cursor.fetchall()
    
    eventos = []
    for f in filas:
        eventos.append({
            "id_evento": f[0],
            "nombre": f[1],
            "id_ocurrencia": f[2],
            "fecha": f[3],
            "capacidad": f[4],
            "ocupados": f[5],
            "libres": f[6]
        })
    return {"status": "OK", "data": eventos}

def procesar_reserva(conn, cursor, payload):
    id_cliente = payload.get("id_cliente")
    id_ocurrencia = payload.get("id_ocurrencia")
    asientos_solicitados = payload.get("asientos", 1)

    # Verificar disponibilidad en tiempo real
    cursor.execute("SELECT libres FROM ocurrencias WHERE id_ocurrencia = ?", (id_ocurrencia,))
    resultado = cursor.fetchone()

    if not resultado:
        return {"status": "ERROR", "mensaje": "La ocurrencia especificada no existe."}

    libres_actuales = resultado[0]

    if libres_actuales >= asientos_solicitados:
        # Descontar libres y aumentar ocupados
        cursor.execute("""
            UPDATE ocurrencias 
            SET libres = libres - ?, ocupados = ocupados + ? 
            WHERE id_ocurrencia = ?
        """, (asientos_solicitados, asientos_solicitados, id_ocurrencia))

        # Registrar la reserva en la tabla de reservas
        cursor.execute("""
            INSERT INTO reservas (id_cliente, id_ocurrencia, asientos_reservados)
            VALUES (?, ?, ?)
        """, (id_cliente, id_ocurrencia, asientos_solicitados))

        conn.commit()
        return {"status": "OK", "mensaje": "Reserva realizada exitosamente."}
    else:
        return {"status": "RECHAZADO", "mensaje": "No hay suficientes asientos disponibles."}

def iniciar_servicio():
    context = zmq.Context()
    socket = context.socket(zmq.REP)  # Patrón Request/Reply (REPLY)
    socket.bind(f"tcp://*:{PORT}")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    print(f"[SERVICIO PERSISTENCIA] Escuchando peticiones en tcp://*:{PORT}...")

    while True:
        try:
            mensaje = socket.recv_json()
            operacion = mensaje.get("operacion")
            payload = mensaje.get("payload", {})

            if operacion == "CONSULTAR":
                respuesta = procesar_consulta(cursor, payload)
            elif operacion == "RESERVAR":
                respuesta = procesar_reserva(conn, cursor, payload)
            else:
                respuesta = {"status": "ERROR", "mensaje": "Operación no soportada."}

            socket.send_json(respuesta)

        except KeyboardInterrupt:
            print("\n[SERVICIO PERSISTENCIA] Apagando el servicio...")
            break
        except Exception as e:
            socket.send_json({"status": "ERROR", "mensaje": str(e)})

    conn.close()
    socket.close()
    context.term()

if __name__ == "__main__":
    iniciar_servicio()
