# Sistema Distribuido de Reserva de Boletos (SRB)

Proyecto de Introducción a Sistemas Distribuidos, Pontificia Universidad Javeriana, 2026-30.

Sistema de tres capas para consultar los eventos de un mes, reservar asientos y modificar
reservas. Cada capa corre en una máquina distinta y se comunican con ZeroMQ (`pyzmq`), con
mensajes JSON. Los datos quedan en SQLite.

## Estado actual

| Operación | Estado |
|---|---|
| Consulta de eventos de un mes | Hecha |
| Reserva de asientos | Hecha |
| Modificación de una reserva (asientos o fecha) | Hecha |
| Cancelación asíncrona con notificación al cliente | En construcción |
| Tolerancia a fallas del GT y del RMC | En construcción |

Las escrituras son idempotentes: cada petición lleva un `uuid` y la persistencia guarda las que
ya aplicó, así una petición repetida (por un reintento) devuelve el mismo resultado sin repetir la
operación.

## Las tres máquinas

```
clientes (REQ) --> [ROUTER :5555]  Gestor de Transacciones  [DEALER :5556] <-- RMC (REP)
                                                                                  |
                                                                          REQ --> Persistencia (REP :5558) --> SQLite
```

| Máquina | IP | Capa | Qué corre | Puertos abiertos |
|---|---|---|---|---|
| 1 | 10.43.99.236 | Consumidores | Clientes, casos de prueba y generador de carga | ninguno |
| 2 | 10.43.100.36 | Negocio | Gestor de Transacciones (GT) y Servicio RMC | 5555 hacia la máquina 1, 5556 (RMC, local) |
| 3 | 10.43.99.246 | Almacenamiento | Servicio de Persistencia y base de datos SQLite | 5558 hacia la máquina 2 |

El GT hace `bind` en sus dos puertos; los clientes y los RMC se conectan a él. Para agregar una
réplica del RMC basta con arrancar otra: el GT reparte el trabajo entre todas. Solo el Servicio
de Persistencia toca la base de datos (`datos/srb.db`).

## Requisitos

- Python 3.12 o superior en las tres máquinas.
- Dependencias: `pyzmq` y `python-dotenv` (SQLite viene con Python).

Con [uv](https://docs.astral.sh/uv/), desde la raíz del proyecto:

```bash
uv sync
```

O con pip:

```bash
python -m venv .venv && source .venv/bin/activate && pip install -r dependencias.txt
```

## Configuración

El archivo `.env` de la raíz ya trae las tres IP y los puertos; es el mismo en las tres máquinas.
`.env.example` es una copia de respaldo.

```env
HOST_CAPA_CONSUMIDORES=10.43.99.236
HOST_CAPA_SERVICIOS=10.43.100.36
HOST_CAPA_PERSISTENCIA=10.43.99.246
```

Para ver la configuración que se está leyendo: `python -m config.configuracion`

## Ejecución

Todos los comandos se ejecutan desde la raíz del proyecto, en este orden: máquina 3, 2 y 1.
Con `uv`, cada comando lleva `uv run` adelante.

### Máquina 3 (10.43.99.246): persistencia

```bash
python -m capa_persistencia.cargar_datos      # crea la BD con el caso del enunciado
python -m capa_persistencia.main              # queda escuchando en el puerto 5558
```

`cargar_datos` borra y recrea la base: 50 eventos de noviembre de 2026, los primeros 20 con dos
ocurrencias y el resto con una (70 ocurrencias), 100 asientos cada una. También acepta otro
catálogo en JSON:

```bash
python -m capa_persistencia.cargar_datos pruebas/ejemplo.json
```

Al iniciar y al detenerse (Ctrl+C), el servicio imprime el estado de la base de datos.

### Máquina 2 (10.43.100.36): Gestor de Transacciones y RMC

En dos terminales:

```bash
python -m capa_negocios.main gt
python -m capa_negocios.main rmc
```

Se pueden arrancar varios `rmc` (uno por terminal) para repartir la carga.

### Máquina 1 (10.43.99.236): clientes

**Caso de prueba desde un archivo de operaciones:**

```bash
python -m capa_cliente.main --id 1 --script pruebas/caso_basico.txt --detalle
```

Formato del archivo (una operación por línea):

```
# comentario
CONSULTA      noviembre
RESERVA       E1 2026/11/01 2     # evento, fecha (AAAA/MM/DD), número de asientos
MODIFICACION  3 5                 # número de reserva, nuevo número de asientos
MODIFICACION  3 2026/11/15        # número de reserva, nueva fecha (otra ocurrencia del mismo evento)
ESPERAR       1.5                 # pausa en segundos
```

`pruebas/caso_basico.txt` trae en sus comentarios el estado final esperado de la base de datos.

**Carga continua de un cliente:**

```bash
python -m capa_cliente.main --id 1 --carga --duracion 150 --por-minuto 20 --consultas 70 --modificaciones 30 --semilla 42
```

| Parámetro | Significado | Por defecto |
|---|---|---|
| `--id` | Identificador del cliente (entero mayor que 0) | obligatorio |
| `--duracion` | Segundos de carga | 150 |
| `--por-minuto` | Peticiones por minuto | 20 |
| `--consultas` | Porcentaje de consultas; el resto son escrituras | 70 |
| `--modificaciones` | De las escrituras, porcentaje que modifica una reserva propia; el resto son reservas | 0 |
| `--semilla` | Semilla del azar, para repetir una corrida | aleatoria |
| `--salida` | CSV de resultados | `resultados/cliente_<id>.csv` |

## Escenarios de la Tabla 1

Cada cliente se lanza como un proceso aparte:

```bash
python -m capa_cliente.escenarios --escenario 1 --etiqueta base
python -m capa_cliente.escenarios --escenario 2 --etiqueta base
python -m capa_cliente.escenarios --escenario 3 --etiqueta base --duracion 150 --por-minuto 20
```

| Escenario | Clientes | Perfil |
|---|---|---|
| 1 | 3 | 2 solo consultan, 1 consulta y reserva |
| 2 | 5 | 3 solo consultan, 2 reservan y modifican |
| 3 | 8 | 4 solo consultan, 4 reservan y modifican |

`--etiqueta` (`base`, `escalable`) separa las corridas de cada arquitectura.

## Resultados y métricas

| Archivo | Lo escribe | Contenido |
|---|---|---|
| `resultados/<etiqueta>_<N>clientes/cliente_<id>.csv` | Cada cliente | hora de envío, tipo, estado, motivo, tiempo de respuesta (ms), uuid |
| `resultados/gt_metricas.csv` | Gestor de Transacciones | hora de fin, tipo, estado, motivo, tiempo (ms), cliente, uuid |

Con los CSV de los clientes se calculan el tiempo promedio de respuesta y la desviación
estándar; con el CSV del GT, las transacciones por minuto (TPM). Antes de cada corrida se
reinicia la base de datos con `cargar_datos` y se borra `resultados/gt_metricas.csv`, para no
mezclar corridas.

## Estado de la base de datos

En la máquina 3, que es donde está el archivo de la base de datos:

```bash
python -m herramientas.ver_bd                # solo las fechas con reservas
python -m herramientas.ver_bd --todas        # las 70 ocurrencias
python -m herramientas.ver_bd --cada 2       # se refresca cada 2 segundos
python -m herramientas.ver_bd --verificar    # los ocupados coinciden con las reservas
```

## Pruebas

Scripts que se ejecutan con la base de datos recién cargada y los servicios en marcha:

```bash
python -m capa_persistencia.prueba                  # capa de datos, sin red (máquina 3)
python -m capa_persistencia.prueba_presistencia     # servicio de persistencia por la red
python -m capa_negocios.prueba                      # RMC (requiere persistencia y RMC)
python -m capa_negocios.prueba_gt                   # sistema completo (persistencia, RMC y GT)
```

## Respuestas del sistema

| Estado | Significado |
|---|---|
| `EXITO` | Se hizo lo pedido |
| `FALLO` | Regla de negocio: `SIN_CUPO` o `NO_EXISTE` |
| `ERROR` | Petición mal formada (`PETICION_INVALIDA`, `DATO_INVALIDO`), `NO_IMPLEMENTADO` o servicio sin respuesta (`NO_DISPONIBLE`) |
| `ACK` | Recibida; se procesará después (cancelación) |

Una modificación rechazada no cambia nada: la reserva queda como estaba. Si un servicio no
responde en `TIMEOUT_MS`, el cliente recibe `ERROR NO_DISPONIBLE` y no se queda esperando.

## Estructura del proyecto

```
capa_cliente/        Cliente, casos de prueba, generador de carga y escenarios
capa_negocios/       Gestor de Transacciones, RMC y métricas del GT
capa_persistencia/   Servicio de Persistencia, acceso a SQLite y carga de datos
config/              Lectura del .env y definición de los mensajes (protocolo)
herramientas/        ver_bd: estado de la base de datos
pruebas/             Casos de prueba (caso_basico.txt, ejemplo.json)
datos/               Base de datos SQLite (srb.db), se crea al cargar los datos
resultados/          CSV de métricas, se crea al correr
```
