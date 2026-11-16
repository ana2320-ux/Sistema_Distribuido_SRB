"""
Generador de carga continua: un cliente envia peticiones a un ritmo fijo
durante un tiempo, con un porcentaje configurable de consultas, reservas,
modificaciones y cancelaciones (de sus propias reservas), y guarda cada resultado
en un CSV.
"""
import csv
import random
import time
from pathlib import Path

from config import E_mensaje as m

COLUMNAS = ["hora_envio", "id_cliente", "tipo", "estado", "motivo", "ms", "uuid"]


def obtener_catalogo(cliente, mes):
    """Consulta el mes una vez para saber que (evento, fecha) existen."""
    respuesta, _ = cliente.consultar(mes)
    if respuesta["estado"] != m.EXITO:
        raise RuntimeError(f"no se pudo obtener el catalogo: {respuesta['motivo']}")
    return [(e["id_evento"], e["fecha"]) for e in respuesta["datos"]["eventos"]]


def generar_carga(cliente, ruta_csv, duracion_s, por_minuto, pct_consultas, pct_modificaciones=0,
                  pct_cancelaciones=0, mes="noviembre", max_asientos=3, semilla=None):
    """
    Envia peticiones durante duracion_s segundos, por_minuto peticiones por minuto.
    pct_consultas: porcentaje de CONSULTA (0 a 100); el resto son escrituras.
    pct_modificaciones y pct_cancelaciones: de las escrituras, porcentaje que modifica o
    cancela una reserva propia ya hecha (el resto son RESERVA).
    Devuelve cuantas peticiones envio.
    """
    azar = random.Random(semilla)
    catalogo = obtener_catalogo(cliente, mes)
    intervalo = 60.0 / por_minuto                 # segundos entre una peticion y la siguiente
    mis_reservas = []                             # numeros de las reservas confirmadas de este cliente
    canceladas = 0

    ruta = Path(ruta_csv)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    enviadas = 0
    with open(ruta, "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(COLUMNAS)

        inicio = time.time()
        siguiente = inicio
        while time.time() - inicio < duracion_s:
            hora_envio = time.time()
            if azar.uniform(0, 100) < pct_consultas:
                tipo = m.CONSULTA
                respuesta, ms = cliente.consultar(mes)
            elif mis_reservas and (suerte := azar.uniform(0, 100)) < pct_modificaciones + pct_cancelaciones:
                if suerte < pct_modificaciones:
                    tipo = m.MODIFICACION
                    respuesta, ms = cliente.modificar(azar.choice(mis_reservas), azar.randint(1, max_asientos))
                else:
                    tipo = m.CANCELACION
                    respuesta, ms = cliente.cancelar(mis_reservas.pop(azar.randrange(len(mis_reservas))))
                    canceladas += 1
            else:
                tipo = m.RESERVA
                evento, fecha = azar.choice(catalogo)
                respuesta, ms = cliente.reservar(evento, fecha, azar.randint(1, max_asientos))
                if respuesta["estado"] == m.EXITO:
                    mis_reservas.append(respuesta["datos"]["id_reserva"])
            escritor.writerow([f"{hora_envio:.3f}", cliente.id_cliente, tipo, respuesta["estado"],
                               respuesta["motivo"] or "", f"{ms:.3f}", respuesta["uuid"]])
            enviadas += 1

            # Ritmo fijo: la siguiente peticion sale 'intervalo' segundos despues de la
            # anterior, no despues de que llego la respuesta. Asi el ritmo no se atrasa.
            siguiente += intervalo
            espera = siguiente - time.time()
            if espera > 0:
                time.sleep(espera)
            else:
                siguiente = time.time()           # el sistema va lento: no acumular atraso
    cliente.esperar_notificaciones(canceladas)    # que alcancen a llegar las ultimas notificaciones
    return enviadas
