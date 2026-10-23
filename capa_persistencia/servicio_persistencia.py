"""
Logica del Servicio de Persistencia: recibe una peticion (dict) y devuelve una
respuesta (dict). Aqui no hay sockets; eso lo maneja main.py.

Peticiones que atiende:
  CONSULTA                 {"mes": "noviembre"}
  CONSULTA_DISPONIBILIDAD  {"id_evento": "E1", "fecha": "2026/11/01"}
  AGREGAR_RESERVA          {"id_evento": "E1", "fecha": "2026/11/01", "n_asientos": 2}
"""
import sqlite3
from datetime import datetime

from config import E_mensaje as mensaje
from capa_persistencia.db import NoExiste, SinCupo


class DatoInvalido(Exception):
    """Un dato de la peticion falta o no tiene el formato esperado."""


class ServicioPersistencia:
    def __init__(self, db):
        self.db = db
        # tipo de peticion -> metodo que la atiende
        self.operaciones = {
            mensaje.CONSULTA: self.consultar_eventos,
            mensaje.CONSULTA_DISPONIBILIDAD: self.consultar_disponibilidad,
            mensaje.AGREGAR_RESERVA: self.agregar_reserva,
        }

    def atender(self, peticion):
        """Recibe una peticion y SIEMPRE devuelve una respuesta."""
        operacion = self.operaciones.get(peticion.get("tipo"))
        if operacion is None:
            return mensaje.crear_respuesta(peticion, mensaje.ERROR, mensaje.PETICION_INVALIDA,
                                           {"razon": f"tipo no atendido: {peticion.get('tipo')}"})
        try:
            return operacion(peticion)
        except DatoInvalido as e:
            return mensaje.crear_respuesta(peticion, mensaje.ERROR, mensaje.DATO_INVALIDO,
                                           {"razon": str(e)})
        except NoExiste as e:
            return mensaje.crear_respuesta(peticion, mensaje.FALLO, mensaje.NO_EXISTE,
                                           {"razon": str(e)})
        except SinCupo as e:
            return mensaje.crear_respuesta(peticion, mensaje.FALLO, mensaje.SIN_CUPO,
                                           {"razon": str(e)})
        except sqlite3.Error as e:
            return mensaje.crear_respuesta(peticion, mensaje.ERROR, mensaje.NO_DISPONIBLE,
                                           {"razon": f"error de base de datos: {e}"})

    def consultar_eventos(self, peticion):
        numero_mes = leer_mes(peticion)
        eventos = self.db.consultar_mes(numero_mes)
        return mensaje.crear_respuesta(peticion, mensaje.EXITO, datos={"mes": mensaje.MESES[numero_mes - 1], "eventos": eventos})

    def consultar_disponibilidad(self, peticion):
        id_evento, fecha = leer_evento_y_fecha(peticion)
        return mensaje.crear_respuesta(peticion, mensaje.EXITO, datos=self.db.disponibilidad(id_evento, fecha))

    def agregar_reserva(self, peticion):
        id_evento, fecha = leer_evento_y_fecha(peticion)
        n_asientos = leer_asientos(peticion)
        reserva = self.db.agregar_reserva(peticion["id_cliente"], id_evento, fecha, n_asientos)
        return mensaje.crear_respuesta(peticion, mensaje.EXITO, datos=reserva)



def leer_mes(peticion):
    """'noviembre' -> 11"""
    nombre = peticion["datos"].get("mes")
    if not isinstance(nombre, str) or nombre.strip().lower() not in mensaje.MESES:
        raise DatoInvalido(f"mes invalido: {nombre}")
    return mensaje.MESES.index(nombre.strip().lower()) + 1


def leer_evento_y_fecha(peticion):
    datos = peticion["datos"]
    id_evento = datos.get("id_evento")
    if not isinstance(id_evento, str) or not id_evento:
        raise DatoInvalido(f"id_evento invalido: {id_evento}")
    texto = datos.get("fecha")
    try:
        fecha = datetime.strptime(str(texto), mensaje.FORMATO_FECHA)
    except ValueError:
        raise DatoInvalido(f"fecha invalida: {texto} (formato AAAA/MM/DD)")
    return id_evento, fecha.strftime(mensaje.FORMATO_FECHA)     # '2026/11/1' -> '2026/11/01'


def leer_asientos(peticion):
    n = peticion["datos"].get("n_asientos")
    if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
        raise DatoInvalido(f"n_asientos debe ser un entero mayor que 0: {n}")
    return n