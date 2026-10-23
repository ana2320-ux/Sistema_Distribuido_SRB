# Sistema de Reserva de Boletos (SRB)

Sistema distribuido basado en servicios para reservar puestos en eventos universitarios.
Proyecto de Introducción a Sistemas Distribuidos, Pontificia Universidad Javeriana, 2026-30.

Autores: Ana Murcia Gómez, Martín Sanmiguel Delgado

## Alcance de la primera entrega

- Arquitectura base de tres capas (Figura 1 del enunciado), una por máquina.
- Operaciones síncronas: **consulta de eventos de un mes** y **reserva de asientos**.
- Comunicación con ZeroMQ (pyzmq); mensajes en JSON.
- Sin tolerancia a fallas, modificación ni cancelación (segunda entrega). El GT responde
  `NO_IMPLEMENTADO` a esas peticiones.

## Arquitectura

```
clientes (REQ) --> [ROUTER :5555]  Gestor de Transacciones  [DEALER :5556] <-- RMC (REP)
                                                                                  |
                                                                          REQ --> Persistencia (REP :5558) --> SQLite
```

| Capa | Componente | Módulo | Puerto |
|---|---|---|---|
| Consumidores | Clientes y generador de carga | `capa_cliente` | – |
| Negocio | Gestor de Transacciones (GT) | `capa_negocios` (`gt`) | 5555 (clientes), 5556 (RMC) |
| Negocio | Servicio RMC (réplicas posibles) | `capa_negocios` (`rmc`) | se conecta al GT |
| Almacenamiento | Servicio de Persistencia + SQLite | `capa_persistencia` | 5558 |

- El GT hace `bind` en sus dos puertos; los clientes y los RMC se conectan a él. Para agregar
  una réplica del RMC basta con arrancarla otra vez; el GT reparte el trabajo.
- Solo el Servicio de Persistencia accede a la base de datos (`datos/srb.db`).
- El puerto 5557 (`GT_PUERTO_CANCELACION`) está reservado para la cancelación asíncrona
  de la segunda entrega.

### Despliegue en tres máquinas

| Máquina | Nombre | IP | Rol |
|---|---|---|---|
| VM1 | NBIG296 | 10.43.99.237 | Clientes |
| VM2 | NBIG333 | 10.43.100.36 | Gestor de Transacciones y RMC |
| VM3 | NBIG305 | 10.43.99.246 | Persistencia y base de datos |

## Requisitos

- Python 3.12 o superior
- Dependencias: `pyzmq` y `python-dotenv` (SQLite viene con Python)
- Conectividad entre las máquinas por los puertos 5555, 5556 y 5558

Con [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

O con pip:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r dependencias.txt
```

## Configuración

Cada máquina tiene su propio archivo `.env` en la raíz del proyecto. Se crea a partir del ejemplo:

```bash
cp .env.example .env
```

Para correr todo en un solo computador, deja las tres IP en `127.0.0.1` (valor por defecto).
Para las tres máquinas, usa las IP reales en **las tres** copias del `.env`:

```env
HOST_CAPA_CONSUMIDORES=10.43.99.237
HOST_CAPA_SERVICIOS=10.43.100.36
HOST_CAPA_PERSISTENCIA=10.43.99.246

GT_PUERTO_CLIENTES=5555
GT_PUERTO_RMC=5556
GT_PUERTO_CANCELACION=5557

SP_PUERTO=5558
BD_RUTA=datos/srb.db

TIMEOUT_MS=5000
```

Para comprobar la configuración leída: `python -m config.configuracion`

## Ejecución

Todos los comandos se ejecutan **desde la raíz del proyecto**. Arranca en este orden
(con `uv`, antepón `uv run` a cada comando).

### 1. VM3: Persistencia

```bash
python -m capa_persistencia.cargar_datos      # crea la BD con el caso del enunciado
python -m capa_persistencia.main              # queda escuchando en el puerto 5558
```

`cargar_datos` borra y recrea la base: 50 eventos de noviembre de 2026, los primeros 20 con
dos ocurrencias y el resto con una (70 ocurrencias), 100 asientos cada una. También acepta el
caso del profesor en un archivo JSON:

```bash
python -m capa_persistencia.cargar_datos pruebas/ejemplo.json
```

Al iniciar y al detenerse (Ctrl+C), el servicio imprime el estado de la BD.

### 2. VM2: Gestor de Transacciones y RMC

En dos terminales:

```bash
python -m capa_negocios.main gt
python -m capa_negocios.main rmc
```

Pueden arrancarse varios `rmc` (uno por terminal) para repartir la carga.

### 3. VM1: Clientes

**Caso de prueba desde un archivo de operaciones:**

```bash
python -m capa_cliente.main --id 1 --script pruebas/caso_basico.txt --detalle
```

Formato del archivo (una operación por línea):

```
# comentario
CONSULTA  noviembre
RESERVA   E1 2026/11/01 2       # evento, fecha (AAAA/MM/DD), número de asientos
ESPERAR   1.5                   # pausa en segundos
```

**Carga continua de un cliente:**

```bash
python -m capa_cliente.main --id 1 --carga --duracion 150 --por-minuto 20 --consultas 70 --semilla 42
```

| Parámetro | Significado | Por defecto |
|---|---|---|
| `--id` | Identificador del cliente (entero > 0) | obligatorio |
| `--duracion` | Segundos de carga | 150 |
| `--por-minuto` | Peticiones por minuto | 20 |
| `--consultas` | % de consultas; el resto son reservas | 70 |
| `--semilla` | Semilla del azar, para repetir una corrida | aleatoria |
| `--salida` | CSV de resultados | `resultados/cliente_<id>.csv` |

## Escenarios de la Tabla 1

Lanzan cada cliente como un proceso aparte:

```bash
python -m capa_cliente.escenarios --escenario 1 --etiqueta base
python -m capa_cliente.escenarios --escenario 2 --etiqueta base
python -m capa_cliente.escenarios --escenario 3 --etiqueta base --duracion 150 --por-minuto 20
```

| Escenario | Clientes | Perfil |
|---|---|---|
| 1 | 3 | 2 solo consultan, 1 consulta y reserva |
| 2 | 5 | 3 solo consultan, 2 reservan |
| 3 | 8 | 4 solo consultan, 4 reservan |

En la arquitectura base los clientes "de reserva y modificación" solo reservan, porque la
modificación se implementa en la segunda entrega. Usa `--etiqueta` (`base`, `escalable`) para
separar las corridas.

## Resultados y métricas

| Archivo | Lo escribe | Contenido |
|---|---|---|
| `resultados/<etiqueta>_<N>clientes/cliente_<id>.csv` | Cada cliente | hora de envío, tipo, estado, motivo, latencia (ms), uuid |
| `resultados/gt_metricas.csv` | Gestor de Transacciones | hora de fin, tipo, estado, motivo, tiempo (ms), cliente, uuid |

Con los CSV de los clientes se calculan el tiempo promedio de respuesta y la desviación estándar;
con el CSV del GT, las transacciones por minuto (TPM). Antes de cada corrida conviene
reiniciar la BD con `cargar_datos` y borrar `resultados/gt_metricas.csv` para no mezclar corridas.

## Estado de la base de datos

Se ejecuta en la máquina de persistencia (VM3):

```bash
python -m herramientas.ver_bd                # solo las fechas con reservas
python -m herramientas.ver_bd --todas        # las 70 ocurrencias
python -m herramientas.ver_bd --cada 2       # se refresca cada 2 segundos
python -m herramientas.ver_bd --verificar    # ¿los ocupados coinciden con las reservas?
```

## Pruebas

Scripts que se ejecutan contra los servicios en marcha, con la BD recién cargada:

```bash
python -m capa_persistencia.prueba                  # capa de datos, sin red
python -m capa_persistencia.prueba_presistencia     # servicio de persistencia por la red
python -m capa_negocios.prueba                      # RMC (requiere persistencia y RMC)
python -m capa_negocios.prueba_gt                   # sistema completo (persistencia, RMC y GT)
```

`pruebas/caso_basico.txt` incluye el estado final esperado de la BD en sus comentarios.

## Respuestas del sistema

| Estado | Significado |
|---|---|
| `EXITO` | Se hizo lo pedido |
| `FALLO` | Regla de negocio: `SIN_CUPO` o `NO_EXISTE` |
| `ERROR` | Petición mal formada (`PETICION_INVALIDA`, `DATO_INVALIDO`), `NO_IMPLEMENTADO` o servicio sin respuesta (`NO_DISPONIBLE`) |
| `ACK` | Recibido, se procesará después (cancelación, segunda entrega) |

Si un servicio no responde en `TIMEOUT_MS`, el cliente recibe un `ERROR NO_DISPONIBLE` y no se
queda esperando.

## Estructura del proyecto

```
capa_cliente/        Cliente, generador de carga y escenarios
capa_negocios/       Gestor de Transacciones, RMC y métricas del GT
capa_persistencia/   Servicio de Persistencia, acceso a SQLite y carga de datos
config/              Lectura del .env y definición de mensajes (protocolo)
herramientas/        ver_bd: estado de la base de datos
pruebas/             Casos de prueba (caso_basico.txt, ejemplo.json)
datos/               Base de datos SQLite (srb.db)
resultados/          CSV de métricas (se crea al correr)
```
