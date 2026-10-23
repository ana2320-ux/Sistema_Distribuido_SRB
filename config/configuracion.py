from pathlib import Path
from dotenv import load_dotenv
import os

CARPETA_CONFIG = Path(__file__).resolve().parent # .../config
RAIZ = CARPETA_CONFIG.parent # .../limpio

load_dotenv(RAIZ / ".env")


def texto(nombre):
    """Lee una variable obligatoria del .env."""
    v = os.getenv(nombre)
    if not v:
        raise RuntimeError(f"No se puede obtener el valor {nombre}, no esta presente en el .env")
    return v


def valor(nombre):
    """Lee una variable obligatoria que debe ser un numero entero."""
    v = texto(nombre)
    try:
        return int(v)
    except ValueError:
        raise RuntimeError(f"La variable {nombre} debe ser un numero entero, pero vale '{v}'")


def direccion(host, puerto):
    """Direccion para connect(): tcp://host:puerto"""
    return f"tcp://{host}:{puerto}"


def direccion_bind(puerto):
    """Direccion para bind(), en todas las interfaces de la maquina: tcp://*:puerto"""
    return f"tcp://*:{puerto}"


# --- Maquinas
HOST_CAPA_CONSUMIDORES = texto("HOST_CAPA_CONSUMIDORES")
HOST_CAPA_SERVICIOS = texto("HOST_CAPA_SERVICIOS")
HOST_CAPA_PERSISTENCIA = texto("HOST_CAPA_PERSISTENCIA")

# --- Gestor de Transacciones
GT_PUERTO_CLIENTES = valor("GT_PUERTO_CLIENTES")
GT_PUERTO_RMC = valor("GT_PUERTO_RMC")
GT_PUERTO_CANCELACION = valor("GT_PUERTO_CANCELACION")

# --- Persistencia
SP_PUERTO = valor("SP_PUERTO")
BD_RUTA = RAIZ / texto("BD_RUTA")

# --- Tiempos
TIMEOUT_MS = valor("TIMEOUT_MS")


if __name__ == "__main__":
    # uv run python -m config.configuracion  -> muestra la configuracion leida
    print("Configuracion leida de", RAIZ / ".env")
    print("  Consumidores :", HOST_CAPA_CONSUMIDORES)
    print("  Servicios    :", HOST_CAPA_SERVICIOS)
    print("  Persistencia :", HOST_CAPA_PERSISTENCIA)
    print("  GT clientes  :", direccion(HOST_CAPA_SERVICIOS, GT_PUERTO_CLIENTES))
    print("  GT para RMC  :", direccion(HOST_CAPA_SERVICIOS, GT_PUERTO_RMC))
    print("  Persistencia :", direccion(HOST_CAPA_PERSISTENCIA, SP_PUERTO))
    print("  Bind persist.:", direccion_bind(SP_PUERTO))
    print("  Base de datos:", BD_RUTA)
    print("  Timeout      :", TIMEOUT_MS, "ms")