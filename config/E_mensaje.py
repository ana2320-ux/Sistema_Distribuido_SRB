"""

Peticion:  {"uuid": str, "tipo": str, "id_cliente": int, "datos": dict}
Respuesta: {"uuid": str, "estado": str, "motivo": str | None, "datos": dict}

una respuesta lleva el mismo uuid de la peticion que responde.
"""
import json
import uuid

import json
import uuid
from typing import Any, Mapping, Optional, TypedDict

class Peticion(TypedDict):
    uuid: str
    tipo: str
    id_cliente: int
    datos: dict


class Respuesta(TypedDict):
    uuid: Optional[str]
    estado: str
    motivo: Optional[str]
    datos: dict

# datos: {"mes": "noviembre"}
CONSULTA = "CONSULTA"
# datos: {"id_evento": "E1", "fecha": "2026/11/01", "n_asientos": 2}
RESERVA = "RESERVA"
# segunda entrega
MODIFICACION = "MODIFICACION"
# segunda entrega
CANCELACION = "CANCELACION"


### Los que usa el RMC para hablar con la persistencia ###

# datos: {"id_evento": "E1", "fecha": "2026/11/01"}
CONSULTA_DISPONIBILIDAD = "CONSULTA_DISPONIBILIDAD"
# datos: igual que RESERVA
AGREGAR_RESERVA = "AGREGAR_RESERVA"


# Del servicio de cancelaciones al cliente
NOTIFICACION = "NOTIFICACION"                  # segunda entrega

TIPOS = {CONSULTA, RESERVA, MODIFICACION, CANCELACION,CONSULTA_DISPONIBILIDAD, AGREGAR_RESERVA, NOTIFICACION}

EXITO = "EXITO" # se hizo lo pedido
FALLO = "FALLO" # no se pudo por una regla de negocio (sin cupo, no existe...)
ERROR = "ERROR" # la peticion estaba mal formada o un servicio no respondio
ACK = "ACK" # recibido, se procesara despues (cancelacion, 2.a entrega)

ESTADOS = {EXITO, FALLO, ERROR, ACK}

SIN_CUPO = "SIN_CUPO"
NO_EXISTE = "NO_EXISTE"
DATO_INVALIDO = "DATO_INVALIDO"
PETICION_INVALIDA = "PETICION_INVALIDA"
NO_IMPLEMENTADO = "NO_IMPLEMENTADO"
NO_DISPONIBLE = "NO_DISPONIBLE" # no se responde en el tiempo ttl

MOTIVOS = {SIN_CUPO, NO_EXISTE, DATO_INVALIDO, PETICION_INVALIDA, NO_IMPLEMENTADO, NO_DISPONIBLE}

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

FORMATO_FECHA = "%Y/%m/%d" # "2026/11/01"

def crear_peticion(tipo: str, id_cliente: int, datos: Optional[dict] = None, uuid_peticion: Optional[str] = None) -> Peticion:
    # verifica que el tipo de peticion sea valido
    if tipo not in TIPOS:
        raise ValueError(f"Tipo de peticion no valido: {tipo}")
    # Verifica qe el id del cliente no sea texto y que el id del cliente sea positivo
    if not isinstance(id_cliente, int) or id_cliente <= 0:
        raise ValueError(f"ID de cliente no valido: {id_cliente}")
    return {
        "uuid": uuid_peticion or str(uuid.uuid4()),
        "tipo": tipo,
        "id_cliente": id_cliente,
        "datos": datos or {}
    }

def crear_respuesta(peticion: Mapping[str, Any], estado: str, motivo: Optional[str] = None, datos: Optional[dict] = None) -> Respuesta:
    # verifica que el estado sea valido
    if estado not in ESTADOS:
        raise ValueError(f"Estado no valido: {estado}")
    # verifica que el estado que se esta enviando tenga un motivo valido
    if estado in (FALLO, ERROR) and motivo not in MOTIVOS:
        raise ValueError(f"Estado: {estado}, necesita un motivo valido, no: {motivo}")
    # si el estado es EXITO o ACK
    if estado in (EXITO, ACK):
        motivo = None
    uuid_peticion = peticion.get("uuid") if isinstance(peticion, dict) else None
    return {
        "uuid": uuid_peticion,
        "estado": estado,
        "motivo": motivo,
        "datos": datos or {}
    }

# cualquier tipo de dato, respuesta o peticon
def codificar(mensaje: Mapping[str, Any]) -> bytes:
    """pone la informacion en texto plano para poderlo enviar a otra capa"""
    # pone todo en texto, ensure_ascii = mantiene las tildes/cosas
    return json.dumps(mensaje, ensure_ascii=False).encode("utf-8")

def decodificar(datos: bytes) -> dict:
    """recoje la info y la vuelve a estructurar"""
    mensaje = json.loads(datos)
    # verifica si es un json valido
    if not isinstance(mensaje, dict):
        raise ValueError("El mensaje debe ser un objeto JSON")
    return mensaje

if __name__ == "__main__":
    # python -m comun.mensajes  -> demostracion
    p = crear_peticion(RESERVA, 7, {"id_evento": "E1", "fecha": "2026/11/01", "n_asientos": 2})
    print("Peticion       :", p)
    print("Codificada     :", codificar(p))
    r = crear_respuesta(p, FALLO, SIN_CUPO, {"libres": 1})
    print("Respuesta      :", r)
    print("Mismo uuid     :", r["uuid"] == p["uuid"])
    print("Ida y vuelta   :", decodificar(codificar(p)) == p)


