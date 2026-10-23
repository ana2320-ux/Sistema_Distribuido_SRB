"""
Pruebas de la capa de datos, sin red. Reinicia la BD con el caso del enunciado.
Uso:  python -m pruebas.prueba_bd
"""
import threading

from capa_persistencia.db import BaseDatos, NoExiste, SinCupo
from capa_persistencia.cargar_datos import generar_eventos

resultados: list[bool] = []


def revisar(nombre, condicion):
    resultados.append(condicion)
    print(f"[{'PASA' if condicion else 'FALLA'}] {nombre}")


def main():
    bd = BaseDatos()
    bd.reiniciar()
    bd.cargar_eventos(generar_eventos())

    # --- consultas
    noviembre = bd.consultar_mes(11)
    revisar("noviembre tiene 70 ocurrencias", len(noviembre) == 70)
    revisar("octubre no tiene ocurrencias", bd.consultar_mes(10) == [])
    revisar("E1 el 2026/11/01 tiene 100 libres",
            bd.disponibilidad("E1", "2026/11/01")["libres"] == 100)
    try:
        bd.disponibilidad("E99", "2026/11/01")
        revisar("disponibilidad de un evento inexistente lanza NoExiste", False)
    except NoExiste:
        revisar("disponibilidad de un evento inexistente lanza NoExiste", True)

    # --- reservas
    r = bd.agregar_reserva(7, "E1", "2026/11/01", 10)
    revisar("reserva valida devuelve su id", r["id_reserva"] == 1)
    revisar("quedan 90 libres", bd.disponibilidad("E1", "2026/11/01")["libres"] == 90)
    try:
        bd.agregar_reserva(7, "E1", "2026/11/01", 91)
        revisar("91 asientos con 90 libres lanza SinCupo", False)
    except SinCupo:
        revisar("91 asientos con 90 libres lanza SinCupo", True)
    revisar("el rechazo no cambio nada", bd.disponibilidad("E1", "2026/11/01")["libres"] == 90)
    bd.agregar_reserva(8, "E1", "2026/11/01", 90)
    revisar("se pueden reservar exactamente los 90 restantes",
            bd.disponibilidad("E1", "2026/11/01")["libres"] == 0)
    try:
        bd.agregar_reserva(7, "E30", "2026/11/16", 1)
        revisar("fecha en que el evento no ocurre lanza NoExiste", False)
    except NoExiste:
        revisar("fecha en que el evento no ocurre lanza NoExiste", True)

    # --- concurrencia: 8 hilos, cada uno con su conexion, 150 intentos de 1 asiento en E2
    exitos = []

    def comprador(id_cliente, intentos):
        mi_bd = BaseDatos()                      # una conexion por hilo
        ok = 0
        for _ in range(intentos):
            try:
                mi_bd.agregar_reserva(id_cliente, "E2", "2026/11/02", 1)
                ok += 1
            except SinCupo:
                pass
        mi_bd.cerrar()
        exitos.append(ok)

    hilos = [threading.Thread(target=comprador, args=(100 + i, 19 if i < 6 else 18))
             for i in range(8)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    revisar(f"sin sobreventa: {sum(exitos)} reservas aceptadas de 150 intentos", sum(exitos) == 100)
    revisar("E2 quedo lleno", bd.disponibilidad("E2", "2026/11/02")["libres"] == 0)

    revisar("ocupados coinciden con la suma de reservas", bd.verificar())
    print()
    bd.imprimir_estado(solo_ocupadas=True)
    bd.cerrar()
    print(f"\n{sum(resultados)}/{len(resultados)} pruebas pasaron")


if __name__ == "__main__":
    main()