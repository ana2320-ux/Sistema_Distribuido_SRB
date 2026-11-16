"""
Configuracion de las pruebas automaticas (pytest).

Todas corren en un solo computador: las tres capas en 127.0.0.1, en puertos distintos
a los reales y con una base de datos aparte (datos/pruebas.db), para no tocar un
sistema que este en marcha. Las variables se fijan antes de importar la configuracion.

Uso (desde la raiz del proyecto):   python -m pytest
"""
import os
import subprocess
import sys
import time

os.environ.update(
    HOST_CAPA_CONSUMIDORES="127.0.0.1", HOST_CAPA_SERVICIOS="127.0.0.1", HOST_CAPA_PERSISTENCIA="127.0.0.1",
    GT_PUERTO_CLIENTES="15555", GT_PUERTO_RMC="15556", GT_PUERTO_CANCELACION="15557",
    SP_PUERTO="15558", SP_PUERTO_LECTURA="15559", PUERTO_BASE_NOTIFICACIONES="16000",
    BD_RUTA="datos/pruebas.db", TIMEOUT_MS="2000", PYTHONUNBUFFERED="1",
)

import pytest

from config import configuracion as config
from config import E_mensaje as m
from capa_cliente.cliente import Cliente
from capa_persistencia.cargar_datos import generar_eventos
from capa_persistencia.db import BaseDatos


@pytest.fixture
def bd(tmp_path):
    """Base de datos nueva con el caso del enunciado: 50 eventos, 70 ocurrencias de 100 asientos."""
    base = BaseDatos(tmp_path / "srb.db")
    base.cargar_eventos(generar_eventos())
    yield base
    base.cerrar()


class Sistema:
    """Los procesos del sistema, para arrancarlos y matarlos desde las pruebas."""

    def __init__(self, carpeta_logs):
        self.carpeta_logs = carpeta_logs
        self.procesos = {}

    def arrancar(self, nombre, *modulo_y_argumentos):
        salida = open(self.carpeta_logs / f"{nombre}.log", "a", encoding="utf-8")
        self.procesos[nombre] = subprocess.Popen([sys.executable, "-m", *modulo_y_argumentos],
                                                 cwd=config.RAIZ, stdout=salida, stderr=subprocess.STDOUT)

    def matar(self, nombre):
        """Mata el proceso de golpe, como una caida."""
        proceso = self.procesos.pop(nombre)
        proceso.kill()
        proceso.wait()

    def log(self, nombre):
        return (self.carpeta_logs / f"{nombre}.log").read_text(encoding="utf-8")

    def bd(self):
        """Conexion a la base de datos de prueba, para comprobar como quedo."""
        return BaseDatos()

    def esperar_listo(self, id_cliente=99):
        """Espera a que una consulta atraviese todas las capas."""
        cliente = Cliente(id_cliente, timeout_ms=500)
        try:
            limite = time.time() + 20
            while time.time() < limite:
                respuesta, _ = cliente.consultar("noviembre")
                if respuesta["estado"] == m.EXITO:
                    return
            raise RuntimeError("el sistema no arranco; ver los logs en " + str(self.carpeta_logs))
        finally:
            cliente.cerrar()


@pytest.fixture
def sistema(tmp_path):
    """
    Arquitectura escalable completa: persistencia y su replica de lectura, GT, dos RMC
    y el Servicio de Cancelaciones, con la base de datos recien cargada.
    """
    s = Sistema(tmp_path)
    subprocess.run([sys.executable, "-m", "capa_persistencia.cargar_datos"], cwd=config.RAIZ,
                   check=True, capture_output=True)
    s.arrancar("persistencia", "capa_persistencia.main")
    s.arrancar("lectura", "capa_persistencia.main", "lectura")
    s.arrancar("gt", "capa_negocios.main", "gt")
    s.arrancar("rmc1", "capa_negocios.main", "rmc", "--con-replica")
    s.arrancar("rmc2", "capa_negocios.main", "rmc", "--con-replica")
    s.arrancar("cancelaciones", "capa_negocios.main", "cancelaciones")
    try:
        s.esperar_listo()
        yield s
    finally:
        for nombre in list(s.procesos):
            s.matar(nombre)
