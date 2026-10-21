import sqlite3
import json
import zmq

DB_NAME = "reserva_boletos.db"
PORT = 5555

def procesar_consulta(cursor, payload):
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

    cursor.execute("SELECT libres FROM ocurrencias WHERE id_ocurrencia = ?", (id_ocurrencia,))
    resultado = cursor.fetchone()

    if not resultado:
        return {"status": "ERROR", "mensaje": "La ocurrencia especificada no existe."}

    libres_actuales = resultado[0]

    if libres_actuales >= asientos_solicitados:
        cursor.execute("""
            UPDATE ocurrencias
            SET libres = libres - ?, ocupados = ocupados + ?
            WHERE id_ocurrencia = ?
        """, (asientos_solicitados, asientos_solicitados, id_ocurrencia))

        cursor.execute("""
            INSERT INTO reservas (id_cliente, id_ocurrencia, asientos_reservados)
            VALUES (?, ?, ?)
        """, (id_cliente, id_ocurrencia, asientos_solicitados))

        conn.commit()
        return {"status": "OK", "mensaje": "Reserva realizada exitosamente."}
    else:
        return {"status": "RECHAZADO", "mensaje": "No hay suficientes asientos disponibles."}

def procesar_modificacion(conn, cursor, payload):
    id_cliente = payload.get("id_cliente")
    id_ocurrencia_actual = payload.get("id_ocurrencia_actual")
    id_ocurrencia_nueva = payload.get("id_ocurrencia_nueva", id_ocurrencia_actual)
    asientos = payload.get("asientos", 1)

    # Si cambia de fecha / ocurrencia
    if id_ocurrencia_actual != id_ocurrencia_nueva:
        cursor.execute("SELECT libres FROM ocurrencias WHERE id_ocurrencia = ?", (id_ocurrencia_nueva,))
        res_nueva = cursor.fetchone()
        if not res_nueva or res_nueva[0] < asientos:
            return {"status": "RECHAZADO", "mensaje": "No hay disponibilidad en la nueva fecha."}

        cursor.execute("UPDATE ocurrencias SET libres = libres + ?, ocupados = ocupados - ? WHERE id_ocurrencia = ?", 
                       (asientos, asientos, id_ocurrencia_actual))
        cursor.execute("UPDATE ocurrencias SET libres = libres - ?, ocupados = ocupados + ? WHERE id_ocurrencia = ?", 
                       (asientos, asientos, id_ocurrencia_nueva))
        cursor.execute("UPDATE reservas SET id_ocurrencia = ? WHERE id_cliente = ? AND id_ocurrencia = ?", 
                       (id_ocurrencia_nueva, id_cliente, id_ocurrencia_actual))
        conn.commit()
        return {"status": "OK", "mensaje": "Reserva modificada exitosamente."}
    else:
        return {"status": "OK", "mensaje": "Modificación procesada."}

def iniciar_servicio():
    context = zmq.Context()
    socket = context.socket(zmq.REP)
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
            elif operacion == "MODIFICAR":
                respuesta = procesar_modificacion(conn, cursor, payload)
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
