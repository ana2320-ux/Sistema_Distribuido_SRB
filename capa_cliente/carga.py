"""
Una operacion de la carga de un cliente: elegir cual (consulta, reserva, modificacion o
cancelacion de una reserva propia), enviarla y guardar el resultado en el CSV del cliente.
La usa capa_cliente/locustfile.py, que pone el ritmo y la duracion.
"""
import csv
import random
from pathlib import Path

from config import E_mensaje as m

COLUMNAS = ["hora_envio", "id_cliente", "tipo", "estado", "motivo", "ms", "uuid"]


class Carga:
    """
    pct_consultas: porcentaje de CONSULTA (0 a 100); el resto son escrituras.
    pct_modificaciones y pct_cancelaciones: de las escrituras, porcentaje que modifica o
    cancela una reserva propia ya hecha (el resto son RESERVA).
    """

    def __init__(self, cliente, ruta_csv, pct_consultas, pct_modificaciones=0, pct_cancelaciones=0,
                 mes="noviembre", max_asientos=3, semilla=None):
        self.cliente = cliente
        self.pct_consultas = pct_consultas
        self.pct_modificaciones = pct_modificaciones
        self.pct_cancelaciones = pct_cancelaciones
        self.mes = mes
        self.max_asientos = max_asientos
        self.azar = random.Random(semilla)
        self.mis_reservas = []                   # numeros de las reservas confirmadas de este cliente
        self.canceladas = 0

        # Se consulta el mes una vez para saber que (evento, fecha) existen
        respuesta, _ = cliente.consultar(mes)
        if respuesta["estado"] != m.EXITO:
            raise RuntimeError(f"no se pudo obtener el catalogo: {respuesta['motivo']}")
        self.catalogo = [(e["id_evento"], e["fecha"]) for e in respuesta["datos"]["eventos"]]

        ruta = Path(ruta_csv)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        self._archivo = open(ruta, "w", newline="", encoding="utf-8")
        self._escritor = csv.writer(self._archivo)
        self._escritor.writerow(COLUMNAS)

    def enviar_una(self, hora_envio):
        """Elige y envia una peticion, la anota en el CSV y devuelve (tipo, respuesta, ms)."""
        azar, cliente = self.azar, self.cliente
        if azar.uniform(0, 100) < self.pct_consultas:
            tipo = m.CONSULTA
            respuesta, ms = cliente.consultar(self.mes)
        elif self.mis_reservas and (suerte := azar.uniform(0, 100)) < self.pct_modificaciones + self.pct_cancelaciones:
            if suerte < self.pct_modificaciones:
                tipo = m.MODIFICACION
                respuesta, ms = cliente.modificar(azar.choice(self.mis_reservas), azar.randint(1, self.max_asientos))
            else:
                tipo = m.CANCELACION
                respuesta, ms = cliente.cancelar(self.mis_reservas.pop(azar.randrange(len(self.mis_reservas))))
                self.canceladas += 1
        else:
            tipo = m.RESERVA
            evento, fecha = azar.choice(self.catalogo)
            respuesta, ms = cliente.reservar(evento, fecha, azar.randint(1, self.max_asientos))
            if respuesta["estado"] == m.EXITO:
                self.mis_reservas.append(respuesta["datos"]["id_reserva"])
        self._escritor.writerow([f"{hora_envio:.3f}", cliente.id_cliente, tipo, respuesta["estado"],
                                 respuesta["motivo"] or "", f"{ms:.3f}", respuesta["uuid"]])
        self._archivo.flush()
        return tipo, respuesta, ms

    def cerrar(self):
        """Espera las ultimas notificaciones de cancelacion y cierra el CSV."""
        self.cliente.esperar_notificaciones(self.canceladas)
        self._archivo.close()
