import zmq
import sqlite3
import os

CANCEL_PORT = 5558
# Apuntar a la base de datos real ubicada en la carpeta persistencia
DB_NAME = "/home/estudiante/SRB/Sistema_Distribuido_SRB/persistencia/reserva_boletos.db"

def procesar_cancelacion(payload):
    id_reserva = payload.get("id_reserva")
    id_ocurrencia = payload.get("id_ocurrencia")
    asientos = payload.get("asientos")
    endpoint_notificacion = payload.get("endpoint_notificacion")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        # Liberación de asientos en persistencia
        cursor.execute("""
            UPDATE ocurrencias
            SET libres = libres + ?, ocupados = ocupados - ?
            WHERE id_ocurrencia = ?
        """, (asientos, asientos, id_ocurrencia))

        cursor.execute("DELETE FROM reservas WHERE id_reserva = ?", (id_reserva,))
        conn.commit()
        exito = True
        msg = f"Cancelación de reserva #{id_reserva} procesada exitosamente."
    except Exception as e:
        exito = False
        msg = f"Falla en cancelación: {str(e)}"
    finally:
        conn.close()

    # Notificación asíncrona directa al cliente
    if endpoint_notificacion:
        ctx = zmq.Context()
        s_notif = ctx.socket(zmq.PUSH)
        try:
            s_notif.connect(endpoint_notificacion)
            s_notif.send_json({"status": "OK" if exito else "ERROR", "mensaje": msg})
        except Exception as e:
            print(f"[CANCELACIONES] No se pudo enviar notificación: {e}")
        finally:
            s_notif.close()
            ctx.term()

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
