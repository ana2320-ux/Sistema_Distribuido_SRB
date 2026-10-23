# Sistema de Reserva de Boletos (SRB)

Sistema distribuido basado en servicios para reservar puestos en eventos universitarios.
Proyecto de Introducción a Sistemas Distribuidos, Pontificia Universidad Javeriana, 2026-30.

Autores: Ana Murcia Gómez, Martín Sanmiguel Delgado

## Alcance de la primera entrega

- Arquitectura base de tres capas (Figura 1 del enunciado).
- Operaciones síncronas: **consulta de eventos del mes** y **reserva de asientos**.
- Comunicación con ZeroMQ (Request/Reply).
- Sin tolerancia a fallas, modificación ni cancelación (segunda entrega).

## Arquitectura

| Capa | Componente | Máquina | IP | Puerto |
|---|---|---|---|---|
| Consumidores | Clientes (Locust) | VM1 – NBIG296 | 10.43.99.237 | – |
| Negocio | Gestor de Transacciones (GT) | VM2 – NBIG333 | 10.43.100.36 | 5557 |
| Negocio | Servicio RMC | VM2 – NBIG333 | 10.43.100.36 | *(completar)* |
| Almacenamiento | Servicio de Persistencia + SQLite | VM3 – NBIG305 | 10.43.99.246 | 5555 |

Flujo de una reserva: Cliente → GT → RMC → Persistencia → respuesta al cliente.

## Requisitos

- Python 3.10 o superior
- Librerías: `pyzmq`, `pyyaml`, `locust`, `pytest`
- SQLite (incluido con Python)
- Conectividad entre las tres máquinas por los puertos indicados

```bash
pip install pyzmq pyyaml locust pytest
```

## Estructura del proyecto

> Ajusta los nombres a los de tu código.

```
.
├── persistencia/       # Servicio de Persistencia (VM3)
│   ├── servicio.py
│   └── seed.py         # Crea y carga reserva_boletos.db
├── negocio/            # Capa de negocio (VM2)
│   ├── gestor_transacciones.py
│   └── rmc.py
├── clientes/           # Capa de consumidores (VM1)
│   ├── locustfile.py
│   └── config.yaml
├── pruebas/            # Pruebas con pytest
└── README.md
```

## Ejecución

Arranca los servicios **en este orden**, de abajo hacia arriba.

### 1. VM3 – Persistencia (10.43.99.246)

```bash
cd persistencia
python seed.py          # crea reserva_boletos.db con 50 eventos
python servicio.py      # escucha en tcp://*:5555
```

`seed.py` carga 50 eventos en un mismo mes: 20 con dos ocurrencias y 30 con una
(70 ocurrencias en total), cada una con 100 asientos. Ejecútalo antes de cada
prueba para partir siempre del mismo estado.

### 2. VM2 – Negocio (10.43.100.36)

```bash
cd negocio
python rmc.py                    # en una terminal
python gestor_transacciones.py   # en otra; escucha en tcp://*:5557
```

### 3. VM1 – Clientes (10.43.99.237)

Un cliente de prueba o la carga con Locust:

```bash
cd clientes
locust -f locustfile.py --headless -u 3 -r 3 -t 2m
```

Parámetros: `-u` número de clientes, `-r` clientes nuevos por segundo, `-t` duración.

## Configuración de la carga

`clientes/config.yaml` (ejemplo):

```yaml
gestor: tcp://10.43.100.36:5557
clientes: 3
solicitudes_por_minuto: 20
duracion_min: 2
porcentaje_consulta: 70
porcentaje_reserva: 30
semilla: 42
```

## Escenarios de prueba

| Escenario | Clientes | Perfil |
|---|---|---|
| A | 3 | 2 solo consulta, 1 consulta y reserva |
| B | 5 | 3 solo consulta, 2 reserva y modificación |
| C | 8 | 4 solo consulta, 4 reserva y modificación |

En la primera entrega solo se ejecutan consultas y reservas.

## Pruebas funcionales

```bash
pytest pruebas/
```

Cubren consulta de eventos, reserva con cupo, rechazo por falta de cupo y control
de overbooking (los asientos libres nunca bajan de cero).

## Notas

- Si la base de datos queda en un estado raro, vuelve a ejecutar `seed.py`.
- Si un cliente se queda esperando, revisa que GT, RMC y Persistencia estén
  corriendo y que los puertos 5557 y 5555 estén abiertos entre las VMs.
