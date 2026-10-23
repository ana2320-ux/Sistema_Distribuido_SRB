"""
Registro de metricas del Gestor de Transacciones.

Cada transaccion que el GT despacha al RMC y recibe de vuelta queda como una fila
en un CSV. Con ese archivo se calculan las transacciones por minuto (TPM) medidas
en el GT, que es lo que pide la Tabla 1 del enunciado.
"""
import csv
import time
from pathlib import Path

COLUMNAS = ["hora_fin", "tipo", "estado", "motivo", "ms", "id_cliente", "uuid"]


class RegistroMetricas:
    def __init__(self, ruta):
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        archivo_nuevo = not self.ruta.exists()
        self.archivo = open(self.ruta, "a", newline="", encoding="utf-8")
        self.escritor = csv.writer(self.archivo)
        if archivo_nuevo:
            self.escritor.writerow(COLUMNAS)

    def registrar(self, tipo, estado, motivo, ms, id_cliente, uuid):
        self.escritor.writerow([f"{time.time():.3f}", tipo, estado, motivo or "",
                                f"{ms:.3f}", id_cliente, uuid])
        self.archivo.flush()          # que quede en disco aunque el GT se detenga de golpe

    def cerrar(self):
        self.archivo.close()
