"""
Logica del Servicio de Persistencia: recibe una peticion (dict) y devuelve una
respuesta (dict). Aqui no hay sockets; eso lo maneja main.py.

Peticiones que atiende:
  CONSULTA                 {"mes": "noviembre"}
  CONSULTA_DISPONIBILIDAD  {"id_evento": "E1", "fecha": "2026/11/01"}
  AGREGAR_RESERVA          {"id_evento": "E1", "fecha": "2026/11/01", "n_asientos": 2}
  CONSULTAR_RESERVA        {"id_reserva": 3}
  MODIFICAR_RESERVA        {"id_reserva": 3, "n_asientos": 5}  o  {"id_reserva": 3, "fecha": "2026/11/15"}
  LIBERAR_RESERVA          {"id_reserva": 3}

Las escrituras (AGREGAR_RESERVA, MODIFICAR_RESERVA, LIBERAR_RESERVA) son idempotentes por el uuid de la
peticion: si ya se aplicaron, se devuelve el resultado guardado sin repetirlas.
"""
import sqlite3
from datetime import datetime

from config import E_mensaje as mensaje
from capa_persistencia.db import NoExiste, SinCupo


class DatoInvalido(Exception):
    """Un dato de la peticion falta o no tiene el formato esperado."""


class ServicioPersistencia:
    def __init__(self, db, solo_lectura=False):
        """solo_lectura=True: la replica de lectura, que no atiende escrituras."""
        self.db = db
        # tipo de peticion -> metodo que la atiende
        self.operaciones = {
            mensaje.CONSULTA: self.consultar_eventos,
            mensaje.CONSULTA_DISPONIBILIDAD: self.consultar_disponibilidad,
            mensaje.AGREGAR_RESERVA: self.agregar_reserva,
            mensaje.CONSULTAR_RESERVA: self.consultar_reserva,
            mensaje.MODIFICAR_RESERVA: self.modificar_reserva,
            mensaje.LIBERAR_RESERVA: self.liberar_reserva,
        }
        self.escrituras = {mensaje.AGREGAR_RESERVA, mensaje.MODIFICAR_RESERVA, mensaje.LIBERAR_RESERVA}
        if solo_lectura:
            for tipo in self.escrituras:
                del self.operaciones[tipo]

    def atender(self, peticion):
        """Recibe una peticion y SIEMPRE devuelve una respuesta."""
        tipo = peticion.get("tipo")
        operacion = self.operaciones.get(tipo)
        if operacion is None:
            return mensaje.crear_respuesta(peticion, mensaje.ERROR, mensaje.PETICION_INVALIDA,
                                           {"razon": f"tipo no atendido: {tipo}"})
        try:
            if tipo in self.escrituras:
                hecha = self.db.operacion_hecha(peticion.get("uuid"))
                if hecha is not None:        # peticion repetida: mismo resultado, sin repetir la escritura
                    return mensaje.crear_respuesta(peticion, mensaje.EXITO, datos=hecha)
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
        reserva = self.db.agregar_reserva(peticion["id_cliente"], id_evento, fecha, n_asientos,
                                          peticion.get("uuid"))
        return mensaje.crear_respuesta(peticion, mensaje.EXITO, datos=reserva)

    def consultar_reserva(self, peticion):
        reserva = self.db.consultar_reserva(leer_id_reserva(peticion))
        del reserva["ocurrencia_id"]
        return mensaje.crear_respuesta(peticion, mensaje.EXITO, datos=reserva)

    def modificar_reserva(self, peticion):
        id_reserva = leer_id_reserva(peticion)
        if "fecha" in peticion["datos"]:
            fecha = leer_fecha(peticion["datos"].get("fecha"))
            reserva = self.db.modificar_reserva(id_reserva, fecha=fecha, uuid=peticion.get("uuid"))
        else:
            n_asientos = leer_asientos(peticion)
            reserva = self.db.modificar_reserva(id_reserva, n_asientos=n_asientos, uuid=peticion.get("uuid"))
        return mensaje.crear_respuesta(peticion, mensaje.EXITO, datos=reserva)

    def liberar_reserva(self, peticion):
        reserva = self.db.liberar_reserva(leer_id_reserva(peticion), peticion.get("uuid"))
        return mensaje.crear_respuesta(peticion, mensaje.EXITO, datos=reserva)



def leer_mes(peticion):
    """'noviembre' -> 11"""
    nombre = peticion["datos"].get("mes")
    if not isinstance(nombre, str) or nombre.strip().lower() not in mensaje.MESES:
        raise DatoInvalido(f"mes invalido: {nombre}")
    return mensaje.MESES.index(nombre.strip().lower()) + 1


def leer_fecha(texto):
    """'2026/11/1' -> '2026/11/01'. Lanza DatoInvalido si no tiene el formato AAAA/MM/DD."""
    try:
        return datetime.strptime(str(texto), mensaje.FORMATO_FECHA).strftime(mensaje.FORMATO_FECHA)
    except ValueError:
        raise DatoInvalido(f"fecha invalida: {texto} (formato AAAA/MM/DD)")


def leer_evento_y_fecha(peticion):
    datos = peticion["datos"]
    id_evento = datos.get("id_evento")
    if not isinstance(id_evento, str) or not id_evento:
        raise DatoInvalido(f"id_evento invalido: {id_evento}")
    return id_evento, leer_fecha(datos.get("fecha"))


def leer_asientos(peticion):
    n = peticion["datos"].get("n_asientos")
    if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
        raise DatoInvalido(f"n_asientos debe ser un entero mayor que 0: {n}")
    return n


def leer_id_reserva(peticion):
    n = peticion["datos"].get("id_reserva")
    if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
        raise DatoInvalido(f"id_reserva debe ser un entero mayor que 0: {n}")
    return n