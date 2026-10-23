"""
Ejecuta un caso de prueba escrito en un archivo de texto, una operacion por linea:

    # comentario
    CONSULTA  noviembre
    RESERVA   E1 2026/11/01 2        (evento, fecha, numero de asientos)
    ESPERAR   1.5                    (pausa en segundos)
"""
import time

from config import E_mensaje as m


def interpretar_linea(linea):
    """
    Convierte una linea del archivo en una operacion.
    Devuelve una tupla: ("CONSULTA", mes) | ("RESERVA", evento, fecha, n) | ("ESPERAR", segundos)
    Lanza ValueError si la linea no tiene el formato esperado.
    """
    partes = linea.split()
    orden = partes[0].upper()
    if orden == "CONSULTA" and len(partes) == 2:
        return ("CONSULTA", partes[1])
    if orden == "RESERVA" and len(partes) == 4:
        return ("RESERVA", partes[1], partes[2], int(partes[3]))
    if orden == "ESPERAR" and len(partes) == 2:
        return ("ESPERAR", float(partes[1]))
    raise ValueError(f"no se entiende '{linea}'")

def mostrar(cliente, descripcion, respuesta, ms, detalle=False):
    """Imprime una linea con el resultado de una operacion."""
    texto = f"{descripcion} => {respuesta['estado']}"
    datos = respuesta.get("datos", {})
    if respuesta["estado"] != m.EXITO:
        texto += f" {respuesta['motivo']}: {datos.get('razon', '')}"
    elif "id_reserva" in datos:
        texto += f" (reserva {datos['id_reserva']})"
    elif "eventos" in datos:
        con_reservas = sum(1 for e in datos["eventos"] if e["puestos_ocupados"] > 0)
        texto += f" ({len(datos['eventos'])} ocurrencias, {con_reservas} con reservas)"
    print(f"[{time.strftime('%H:%M:%S')}] [C{cliente.id_cliente}] {texto} ({ms:.1f} ms)", flush=True)

    if detalle and "eventos" in datos:
        for e in datos["eventos"]:
            if e["puestos_ocupados"] > 0:
                print(f"      {e['id_evento']:<6}{e['fecha']}  ocupados {e['puestos_ocupados']:>3}"
                      f"  libres {e['libres']:>3}")

def ejecutar_script(cliente, ruta, detalle=False):
    """Ejecuta el archivo linea por linea y devuelve un resumen {estado: cantidad}."""
    resumen: dict[str, int] = {}
    with open(ruta, encoding="utf-8") as archivo:
        for numero, linea in enumerate(archivo, start=1):
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            try:
                operacion = interpretar_linea(linea)
            except (ValueError, IndexError) as e:
                print(f"  linea {numero} ignorada: {e}")
                continue

            if operacion[0] == "ESPERAR":
                time.sleep(operacion[1])
                continue
            if operacion[0] == "CONSULTA":
                respuesta, ms = cliente.consultar(operacion[1])
                descripcion = f"CONSULTA {operacion[1]}"
            else:
                _, evento, fecha, n = operacion
                respuesta, ms = cliente.reservar(evento, fecha, n)
                descripcion = f"RESERVA {evento} {fecha} x{n}"

            mostrar(cliente, descripcion, respuesta, ms, detalle)
            resumen[respuesta["estado"]] = resumen.get(respuesta["estado"], 0) + 1
    return resumen