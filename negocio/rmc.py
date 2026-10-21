import os
import zmq
from dotenv import load_dotenv

# 1. Cargar variables del .env (está en la raíz del proyecto, una carpeta arriba)
RUTA_ENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
load_dotenv(RUTA_ENV)

PUERTO_RMC = os.getenv("GT_PUERTO_RMC", "5556")
HOST_PERSISTENCIA = os.getenv("HOST_CAPA_PERSISTENCIA", "localhost")
PUERTO_PERSISTENCIA = os.getenv("PERSISTENCIA", "5558")


def iniciar_rmc():
    # 2. Un solo contexto por proceso; de él salen todos los sockets
    context = zmq.Context()

    # 3. Socket REP: el RMC actúa como SERVIDOR frente al GT
    socket_gt = context.socket(zmq.REP)
    socket_gt.bind(f"tcp://*:{PUERTO_RMC}")

    # 4. Socket REQ: el RMC actúa como CLIENTE frente a Persistencia
    socket_persistencia = context.socket(zmq.REQ)
    socket_persistencia.connect(f"tcp://{HOST_PERSISTENCIA}:{PUERTO_PERSISTENCIA}")

    print(f"[RMC] Escuchando al GT en tcp://*:{PUERTO_RMC}")
    print(f"[RMC] Conectado a Persistencia en tcp://{HOST_PERSISTENCIA}:{PUERTO_PERSISTENCIA}")

    while True:
        try:
            # 5. Esperar una petición del GT (recv bloquea hasta que llegue algo)
            peticion = socket_gt.recv_json()
            print(f"[RMC] Petición recibida: {peticion}")

            # 6. Reenviarla tal cual a Persistencia y esperar su respuesta
            socket_persistencia.send_json(peticion)
            respuesta = socket_persistencia.recv_json()
            print(f"[RMC] Respuesta de Persistencia: {respuesta.get('status')}")

            # 7. Devolver la respuesta al GT (cierra el ciclo REQ/REP)
            socket_gt.send_json(respuesta)

        except KeyboardInterrupt:
            print("\n[RMC] Apagando el servicio...")
            break

    socket_gt.close()
    socket_persistencia.close()
    context.term()


if __name__ == "__main__":
    iniciar_rmc()

