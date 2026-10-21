import sqlite3
import json
import os

# 1. Cargar configuración de fecha
with open('config.json', 'r') as f:
    config = json.load(f)

mes = config.get("mes", 10)
anio = config.get("anio", 2026)

# Eliminar BD previa si existe para reiniciar limpia(por si acaso)
if os.path.exists('reserva_boletos.db'):
    os.remove('reserva_boletos.db')

conn = sqlite3.connect('reserva_boletos.db')
cursor = conn.cursor()

# 2. Crear Tablas
cursor.execute('''
CREATE TABLE IF NOT EXISTS eventos (
    id_evento TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    num_ocurrencias INTEGER NOT NULL
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS ocurrencias (
    id_ocurrencia INTEGER PRIMARY KEY AUTOINCREMENT,
    id_evento TEXT NOT NULL,
    fecha TEXT NOT NULL,
    capacidad INTEGER NOT NULL,
    ocupados INTEGER NOT NULL,
    libres INTEGER NOT NULL,
    FOREIGN KEY (id_evento) REFERENCES eventos (id_evento)
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS reservas (
    id_reserva INTEGER PRIMARY KEY AUTOINCREMENT,
    id_cliente TEXT NOT NULL,
    id_ocurrencia INTEGER NOT NULL,
    asientos_reservados INTEGER NOT NULL,
    fecha_reserva TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_ocurrencia) REFERENCES ocurrencias (id_ocurrencia)
)
''')

# 3. Poblar Eventos y Ocurrencias
# 50 eventos en total: 20 con 2 fechas, 30 con 1 fecha = 70 ocurrencias totales
dia = 1
for i in range(1, 51):
    id_evento = f"E{i}"
    nombre = f"Evento Cultural/Deportivo {i}"
    num_ocurrencias = 2 if i <= 20 else 1
    
    cursor.execute("INSERT INTO eventos VALUES (?, ?, ?)", (id_evento, nombre, num_ocurrencias))
    
    for occ in range(num_ocurrencias):
        fecha_str = f"{anio}-{mes:02d}-{(dia % 28) + 1:02d}"
        cursor.execute('''
            INSERT INTO ocurrencias (id_evento, fecha, capacidad, ocupados, libres)
            VALUES (?, ?, 100, 0, 100)
        ''', (id_evento, fecha_str))
        dia += 1

conn.commit()

# 4. Verificación de Conteos
cursor.execute("SELECT COUNT(*) FROM eventos")
total_eventos = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM ocurrencias")
total_ocurrencias = cursor.fetchone()[0]

cursor.execute("SELECT SUM(libres) FROM ocurrencias")
total_asientos = cursor.fetchone()[0]

print("========================================")
print("      INICIALIZACIÓN DE BASE DE DATOS   ")
print("========================================")
print(f"Total Eventos creados     : {total_eventos}")
print(f"Total Ocurrencias creadas : {total_ocurrencias}")
print(f"Total Asientos disponibles: {total_asientos}")
print("========================================")

conn.close()
