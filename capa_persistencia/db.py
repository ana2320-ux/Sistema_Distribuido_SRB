"""
Base de datos del SRB (SQLite).

Tablas:
  evento      (id, nombre, tipo_evento)
  ocurrencia  (id, evento_id, fecha, capacidad, puestos_ocupados)
  reserva     (id, id_cliente, ocurrencia_id, numero_puestos, activa)

Las fechas se guardan como texto 'AAAA/MM/DD', el mismo formato del protocolo.
"""
import sqlite3
from config import configuracion

ESQUEMA = """
CREATE TABLE IF NOT EXISTS evento (
    id          TEXT PRIMARY KEY,
    nombre      TEXT NOT NULL,
    tipo_evento TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ocurrencia (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    evento_id        TEXT    NOT NULL REFERENCES evento(id),
    fecha            TEXT    NOT NULL,
    capacidad        INTEGER NOT NULL DEFAULT 100,
    puestos_ocupados INTEGER NOT NULL DEFAULT 0,
    UNIQUE (evento_id, fecha),
    CHECK (puestos_ocupados >= 0 AND puestos_ocupados <= capacidad)
);

CREATE TABLE IF NOT EXISTS reserva (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    id_cliente     INTEGER NOT NULL,
    ocurrencia_id  INTEGER NOT NULL REFERENCES ocurrencia(id),
    numero_puestos INTEGER NOT NULL CHECK (numero_puestos > 0),
    activa         INTEGER NOT NULL DEFAULT 1
);
"""

class BaseDatos:
    def __init__(self, ruta=configuracion.BD_RUTA):
        ruta.parent.mkdir(parents=True, exist_ok=True) #crea la carpeta datos si esta no existe
        self.ruta = ruta
        self.conexion = sqlite3.connect(ruta, timeout=10) #SQLite solo deja que se escriba 1 al mismo tiempo, asi que si alguien esta escribiendo, este espera 10s
        self.conexion.row_factory = sqlite3.Row # filas accesibles por nombre de columna
        self.conexion.execute("PRAGMA foreign_keys = ON") #por defecto ignora las llaves foráneas, asi que se activa
        self.conexion.executescript(ESQUEMA) # crea las tablas si no existen

    def reiniciar(self):
        """Borra todos los datos y deja las tablas vacias."""
        with self.conexion:
            self.conexion.executescript("""
                DROP TABLE IF EXISTS reserva;
                DROP TABLE IF EXISTS ocurrencia;
                DROP TABLE IF EXISTS evento;
            """)
            self.conexion.executescript(ESQUEMA)

    def cargar_eventos(self, eventos):
        """
        eventos: lista de diccionarios
          {"id": "E1", "nombre": "...", "tipo_evento": "...",
           "fechas": ["2026/11/01", "2026/11/15"], "capacidad": 100}
        Todo se inserta en una sola transaccion: o entra todo o no entra nada.
        """
        with self.conexion:
            for ev in eventos:
                self.conexion.execute(
                    "INSERT INTO evento (id, nombre, tipo_evento) VALUES (?, ?, ?)",
                    (ev["id"], ev["nombre"], ev["tipo_evento"]))
                for fecha in ev["fechas"]:
                    self.conexion.execute(
                        "INSERT INTO ocurrencia (evento_id, fecha, capacidad) VALUES (?, ?, ?)",
                        (ev["id"], fecha, ev.get("capacidad", 100)))

    def consultar_mes(self, numero_mes):
        """Todas las ocurrencias de un mes (1 a 12), ordenadas por fecha."""
        filas = self.conexion.execute("""
            SELECT e.id AS id_evento, e.nombre, e.tipo_evento,
                   o.fecha, o.capacidad, o.puestos_ocupados,
                   o.capacidad - o.puestos_ocupados AS libres
            FROM ocurrencia o
            JOIN evento e ON e.id = o.evento_id
            WHERE CAST(SUBSTR(o.fecha, 6, 2) AS INTEGER) = ?
            ORDER BY o.fecha, CAST(SUBSTR(e.id, 2) AS INTEGER)
        """, (numero_mes,)).fetchall()
        return [dict(f) for f in filas]

    def disponibilidad(self, id_evento, fecha):
        """Capacidad y ocupacion de una ocurrencia. Lanza NoExiste si no existe."""
        fila = self.conexion.execute("""
            SELECT capacidad, puestos_ocupados,
                   capacidad - puestos_ocupados AS libres
            FROM ocurrencia
            WHERE evento_id = ? AND fecha = ?
        """, (id_evento, fecha)).fetchone()
        if fila is None:
            raise NoExiste(f"{id_evento} no tiene ocurrencia el {fecha}")
        return dict(fila)

    def agregar_reserva(self, id_cliente, id_evento, fecha, n_asientos):
        """
        Ocupa n_asientos y registra la reserva, todo en una transaccion.
        Lanza NoExiste o SinCupo; en ese caso no cambia nada.
        """
        with self.conexion:
            fila = self.conexion.execute(
                "SELECT id FROM ocurrencia WHERE evento_id = ? AND fecha = ?",
                (id_evento, fecha)).fetchone()
            if fila is None:
                raise NoExiste(f"{id_evento} no tiene ocurrencia el {fecha}")
            ocurrencia_id = fila["id"]

            # Sumar SOLO si caben. Verificar y actualizar es una sola instruccion,
            cursor = self.conexion.execute("""
                UPDATE ocurrencia
                SET puestos_ocupados = puestos_ocupados + ?
                WHERE id = ? AND puestos_ocupados + ? <= capacidad
            """, (n_asientos, ocurrencia_id, n_asientos))
            if cursor.rowcount == 0:
                libres = self.conexion.execute(
                    "SELECT capacidad - puestos_ocupados FROM ocurrencia WHERE id = ?",
                    (ocurrencia_id,)).fetchone()[0]
                raise SinCupo(f"hay {libres} puestos libres en {id_evento} el {fecha}, "
                              f"se pidieron {n_asientos}")

            cursor = self.conexion.execute("""
                INSERT INTO reserva (id_cliente, ocurrencia_id, numero_puestos)
                VALUES (?, ?, ?)
            """, (id_cliente, ocurrencia_id, n_asientos))
            return {"id_reserva": cursor.lastrowid, "id_cliente": id_cliente,
                    "id_evento": id_evento, "fecha": fecha, "n_asientos": n_asientos}


    def verificar(self):
        """True si en cada ocurrencia los ocupados coinciden con la suma de sus reservas activas."""
        malas = self.conexion.execute("""
            SELECT o.evento_id, o.fecha, o.puestos_ocupados,
                   COALESCE(SUM(r.numero_puestos), 0) AS suma_reservas
            FROM ocurrencia o
            LEFT JOIN reserva r ON r.ocurrencia_id = o.id AND r.activa = 1
            GROUP BY o.id
            HAVING o.puestos_ocupados != suma_reservas
        """).fetchall()
        return len(malas) == 0

    def resumen(self):
        fila = self.conexion.execute("""
            SELECT (SELECT COUNT(*) FROM evento)                          AS eventos,
                   (SELECT COUNT(*) FROM ocurrencia)                      AS ocurrencias,
                   (SELECT COALESCE(SUM(capacidad), 0) FROM ocurrencia)   AS capacidad,
                   (SELECT COALESCE(SUM(puestos_ocupados), 0) FROM ocurrencia) AS ocupados,
                   (SELECT COUNT(*) FROM reserva WHERE activa = 1)        AS reservas
        """).fetchone()
        return dict(fila)

    def imprimir_estado(self, solo_ocupadas=False):
        filas = self.conexion.execute("""
            SELECT evento_id, fecha, capacidad, puestos_ocupados
            FROM ocurrencia
            ORDER BY CAST(SUBSTR(evento_id, 2) AS INTEGER), fecha
        """).fetchall()
        print(f"{'evento':<8}{'fecha':<12}{'capacidad':>10}{'ocupados':>10}{'libres':>8}")
        for f in filas:
            if solo_ocupadas and f["puestos_ocupados"] == 0:
                continue
            libres = f["capacidad"] - f["puestos_ocupados"]
            print(f"{f['evento_id']:<8}{f['fecha']:<12}{f['capacidad']:>10}"
                  f"{f['puestos_ocupados']:>10}{libres:>8}")
        r = self.resumen()
        print(f"-- {r['eventos']} eventos, {r['ocurrencias']} ocurrencias, "
              f"{r['capacidad']} asientos, {r['ocupados']} ocupados, {r['reservas']} reservas activas")

    def cerrar(self):
        self.conexion.close()


class NoExiste(Exception):
    """El evento no tiene ocurrencia en esa fecha."""


class SinCupo(Exception):
    """No hay suficientes puestos libres."""