# Sistema Distribuido de Reserva de Boletos (SRB)

Proyecto de Introducción a Sistemas Distribuidos, Pontificia Universidad Javeriana, 2026-30.

Sistema de tres capas para consultar los eventos de un mes, reservar asientos, modificar
reservas y cancelarlas. Cada capa corre en una máquina distinta y se comunican con ZeroMQ
(`pyzmq`), con mensajes JSON. Los datos quedan en SQLite. La arquitectura final es escalable
y tolera la caída del Gestor de Transacciones y del Servicio de Procesamiento de Reservas,
Modificaciones y Consultas (RMC).

El informe de pruebas y rendimiento está en `docs/informe/`.

## 1. Operaciones

| Operación | Tipo | Camino |
|---|---|---|
| Consulta de los eventos de un mes | Síncrona | Cliente → Gestor de Transacciones → RMC → Persistencia |
| Reserva de asientos | Síncrona | Igual; el RMC consulta la disponibilidad y luego confirma |
| Modificación de una reserva (asientos o fecha) | Síncrona | Igual; si no hay cupo, la reserva queda como estaba |
| Cancelación de una reserva | Asíncrona | El Gestor de Transacciones responde `ACK` de inmediato y pasa la cancelación al Servicio de Cancelaciones, que libera los asientos y notifica al cliente |

## 2. Arquitectura y máquinas

```
Máquina 1 (10.43.99.236)        Máquina 2 (10.43.100.36)                        Máquina 3 (10.43.99.246)

clientes (REQ) ───────────────► [ROUTER :5555] Gestor de Transacciones
                                [DEALER :5556] ◄── RMC 1..N (REP) ── REQ ─────► Persistencia (REP :5558) ─► SQLite
                                      │                └──── consultas (REQ) ─► Réplica de lectura (REP :5559) ─┘
                                 PUSH ▼
clientes (PULL :6000+id) ◄─ PUSH ─ Cancelaciones (PULL :5557) ── REQ ─────────► Persistencia (REP :5558)
```

| Máquina | IP | Capa | Procesos | Puertos |
|---|---|---|---|---|
| 1 | 10.43.99.236 | Consumidores | Clientes, casos de prueba y generador de carga | 6000 + id del cliente (notificaciones) |
| 2 | 10.43.100.36 | Negocio | Gestor de Transacciones (activo y de respaldo), RMC (una o varias réplicas) y Servicio de Cancelaciones | 5555 (clientes), 5556 (RMC), 5557 (cancelaciones) |
| 3 | 10.43.99.246 | Almacenamiento | Servicio de Persistencia, réplica de lectura y base de datos SQLite | 5558 (principal), 5559 (réplica de lectura) |

Componentes de la arquitectura final:

| Componente | Atributo | Qué hace |
|---|---|---|
| Réplicas del RMC | Escalabilidad | El Gestor de Transacciones reparte las peticiones entre todos los RMC conectados (ROUTER/DEALER). Agregar una réplica es arrancar otro proceso |
| Réplica de lectura | Escalabilidad | Segundo proceso de persistencia sobre la misma base de datos (SQLite en modo WAL) que atiende solo consultas, mientras el principal escribe |
| Gestor de Transacciones de respaldo | Tolerancia a fallas | Queda en espera en la máquina 2 y toma los puertos cuando el activo se cae |
| Reenvío a otro RMC | Tolerancia a fallas | Si un RMC no responde, el Gestor de Transacciones reenvía la petición a otro |
| Reintento del cliente | Tolerancia a fallas | Si no hay respuesta, el cliente reenvía la petición una vez, con el mismo `uuid` |
| Escrituras idempotentes | Tolerancia a fallas | La persistencia guarda cada escritura por el `uuid` de la petición: una petición repetida devuelve el mismo resultado y no se aplica dos veces |
| Cola de cancelaciones | Tolerancia a fallas | Si el Servicio de Cancelaciones está caído, las cancelaciones aceptadas esperan y se procesan cuando vuelve |

## 3. Requisitos

- Ubuntu 22.04 y Python 3.12 o superior en las tres máquinas.
- Dependencias: `pyzmq` y `python-dotenv`. Para las pruebas y el análisis de métricas, además
  `pytest` y `matplotlib`. SQLite viene con Python.

Con [uv](https://docs.astral.sh/uv/), desde la raíz del proyecto:

```bash
uv sync
```

O con pip:

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r dependencias.txt
```

Todos los comandos de este documento se ejecutan desde la raíz del proyecto. Con `uv`, cada
`python` se reemplaza por `uv run python`.

## 4. Configuración

El archivo `.env` de la raíz trae las tres IP y los puertos; es el mismo en las tres máquinas.
`.env.example` es una copia de respaldo.

```env
HOST_CAPA_CONSUMIDORES=10.43.99.236
HOST_CAPA_SERVICIOS=10.43.100.36
HOST_CAPA_PERSISTENCIA=10.43.99.246
```

La configuración leída se comprueba con `python -m config.configuracion`.

Reglas del firewall (`ufw`) para que cada puerto solo acepte conexiones de la máquina que lo usa:

```bash
# Máquina 2: los clientes entran al Gestor de Transacciones
sudo ufw allow from 10.43.99.236 to any port 5555 proto tcp
# Máquina 3: solo la capa de negocio habla con la persistencia
sudo ufw allow from 10.43.100.36 to any port 5558:5559 proto tcp
# Máquina 1: el Servicio de Cancelaciones notifica a los clientes
sudo ufw allow from 10.43.100.36 to any port 6001:6099 proto tcp
```

Los puertos 5556 y 5557 solo se usan dentro de la máquina 2 y no se abren hacia afuera.

## 5. Ejecución

El orden es máquina 3, máquina 2 y máquina 1. Cada proceso va en su propia terminal y se
detiene con `Ctrl+C`.

### 5.1 Arquitectura base

```bash
# Máquina 3 (10.43.99.246)
python -m capa_persistencia.cargar_datos        # crea la base de datos con el caso del enunciado
python -m capa_persistencia.main                # Servicio de Persistencia, puerto 5558

# Máquina 2 (10.43.100.36)
python -m capa_negocios.main gt                 # Gestor de Transacciones
python -m capa_negocios.main rmc                # un RMC
python -m capa_negocios.main cancelaciones      # Servicio de Cancelaciones
```

### 5.2 Arquitectura escalable y tolerante a fallas

```bash
# Máquina 3 (10.43.99.246)
python -m capa_persistencia.cargar_datos
python -m capa_persistencia.main                # servicio principal
python -m capa_persistencia.main lectura        # réplica de lectura, puerto 5559

# Máquina 2 (10.43.100.36)
python -m capa_negocios.main gt                 # Gestor de Transacciones activo
python -m capa_negocios.main gt                 # de respaldo: queda en espera
python -m capa_negocios.main rmc --con-replica  # RMC 1
python -m capa_negocios.main rmc --con-replica  # RMC 2
python -m capa_negocios.main rmc --con-replica  # RMC 3
python -m capa_negocios.main cancelaciones
```

`cargar_datos` borra y recrea la base: 50 eventos de noviembre de 2026, los primeros 20 con dos
ocurrencias y el resto con una (70 ocurrencias), 100 asientos cada una. También acepta otro
catálogo en JSON (`python -m capa_persistencia.cargar_datos pruebas/ejemplo.json`) y se puede
ejecutar con los servicios en marcha.

### 5.3 Clientes (máquina 1, 10.43.99.236)

**Caso de prueba desde un archivo de operaciones:**

```bash
python -m capa_cliente.main --id 1 --script pruebas/caso_basico.txt --detalle
```

Formato del archivo, una operación por línea:

```
# comentario
CONSULTA      noviembre
RESERVA       E1 2026/11/01 2     # evento, fecha (AAAA/MM/DD), número de asientos
MODIFICACION  3 5                 # número de reserva, nuevo número de asientos
MODIFICACION  3 2026/11/15        # número de reserva, nueva fecha (otra ocurrencia del mismo evento)
CANCELACION   3                   # número de reserva; el resultado llega como notificación
ESPERAR       1.5                 # pausa en segundos
```

Las reservas se numeran en el orden en que se aceptan (1, 2, 3...). `pruebas/caso_basico.txt`
trae en sus comentarios el resultado de cada operación y el estado final de la base de datos.

**Carga continua de un cliente:**

```bash
python -m capa_cliente.main --id 1 --carga --duracion 150 --por-minuto 20 --consultas 70 --modificaciones 30 --cancelaciones 10 --semilla 42
```

| Parámetro | Significado | Por defecto |
|---|---|---|
| `--id` | Identificador del cliente (entero mayor que 0); cada cliente en marcha usa uno distinto | obligatorio |
| `--duracion` | Segundos de carga | 150 |
| `--por-minuto` | Peticiones por minuto | 20 |
| `--consultas` | Porcentaje de consultas; el resto son escrituras | 70 |
| `--modificaciones` | De las escrituras, porcentaje que modifica una reserva propia | 0 |
| `--cancelaciones` | De las escrituras, porcentaje que cancela una reserva propia; las demás son reservas | 0 |
| `--semilla` | Semilla del azar, para repetir una corrida | aleatoria |
| `--salida` | CSV de resultados | `resultados/cliente_<id>.csv` |

## 6. Estado de la base de datos y bitácoras

En la máquina 3, que es donde está el archivo de la base de datos:

```bash
python -m herramientas.ver_bd                # solo las fechas con reservas
python -m herramientas.ver_bd --todas        # las 70 ocurrencias
python -m herramientas.ver_bd --cada 2       # se refresca cada 2 segundos
python -m herramientas.ver_bd --verificar    # los ocupados coinciden con las reservas activas
```

El Servicio de Persistencia imprime el estado de la base al iniciar y al detenerse. Cada
proceso escribe en su terminal lo que recibe y lo que responde; el `uuid` de la petición es
el mismo en todas las capas.

## 7. Tolerancia a fallas

Con la arquitectura de la sección 5.2 en marcha y una carga corriendo (sección 5.3):

| Falla | Cómo se provoca | Qué pasa |
|---|---|---|
| Cae el Gestor de Transacciones activo | `Ctrl+C` o `kill` en su terminal | El de respaldo imprime «toma el control» en menos de 2 segundos. Las peticiones que iban en camino las reenvía el cliente con el mismo `uuid`; ninguna se pierde ni se repite |
| Cae un RMC | `Ctrl+C` o `kill` en una de sus terminales | El Gestor de Transacciones imprime «se reenvía a otro RMC» y otro RMC termina la operación |
| Cae el Servicio de Cancelaciones | `Ctrl+C` o `kill` | Las cancelaciones se siguen aceptando (`ACK`); al arrancarlo de nuevo se procesan y llegan las notificaciones |
| Cae la réplica de lectura | `Ctrl+C` o `kill` | Los RMC pasan sus consultas al servicio principal |

Un proceso caído se reemplaza arrancándolo de nuevo con el mismo comando; un RMC que perdió la
réplica vuelve a usarla al reiniciarse. Al final, `python -m herramientas.ver_bd --verificar`
confirma que los asientos ocupados coinciden con las reservas.

Tiempos de espera (`TIMEOUT_MS=5000` en el `.env`): el cliente espera 5 s y reintenta una vez;
el Gestor de Transacciones reenvía a otro RMC a los 2 s; el RMC espera a la persistencia 1,6 s.

## 8. Pruebas automáticas

```bash
bash scripts/protocolo-pruebas.sh                              # con python3
PYTHON="uv run python" bash scripts/protocolo-pruebas.sh       # con uv
```

Ejecuta las pruebas de `pytest` de la carpeta `pruebas/` y muestra un resumen PASA / FALLA por
tipo. Las pruebas arrancan sus propios procesos en el mismo computador (`127.0.0.1`), en otros
puertos (15555 a 15559) y con una base de datos aparte (`datos/pruebas.db`): no interfieren con
un sistema en marcha. Tarda cerca de un minuto.

| Tipo | Archivo | Qué comprueba |
|---|---|---|
| Unitarias | `test_mensajes.py`, `test_bd.py`, `test_servicios.py` | Validación de mensajes, reglas de la base de datos (cupo, modificación, liberación, idempotencia) y lógica del RMC y de la persistencia, sin red |
| Integración y funcionales | `test_sistema.py` | El caso `caso_basico.txt` completo con el estado final de la base, consulta, reserva, modificación y cancelación con notificación |
| Concurrencia y consistencia | `test_sistema.py` | 8 clientes compiten por los últimos asientos: entran exactamente 100 de 150 |
| Seguridad básica | `test_sistema.py` | Mensajes mal formados, tipos internos, cantidades excesivas e inyección SQL se rechazan sin cambiar la base |
| Tolerancia a fallas | `test_fallas.py` | Caída del Gestor de Transacciones, de un RMC (antes y después de guardar), del Servicio de Cancelaciones y de la réplica |

Una sola prueba se ejecuta con `python -m pytest pruebas/test_fallas.py -k respaldo -v`.

## 9. Medición del rendimiento (Tabla 1)

Cada escenario se corre tres veces, 150 segundos, con 20 peticiones por minuto por cliente:

| Escenario | Clientes | Perfil |
|---|---|---|
| 1 | 3 | 2 solo consultan, 1 consulta y reserva |
| 2 | 5 | 3 solo consultan, 2 reservan y modifican |
| 3 | 8 | 4 solo consultan, 4 reservan y modifican |

1. Máquinas 3 y 2: arquitectura base en marcha (sección 5.1).
2. Máquina 1: `bash scripts/medir.sh base`. El script corre los tres escenarios, tres corridas
   de cada uno, y se detiene antes de cada escenario para reiniciar la base de datos en la
   máquina 3 (`python -m capa_persistencia.cargar_datos`).
3. Máquinas 3 y 2: se detiene todo y se levanta la arquitectura escalable (sección 5.2).
4. Máquina 1: `bash scripts/medir.sh escalable`.
5. El CSV del Gestor de Transacciones (`resultados/gt_metricas.csv`, en la máquina 2) se copia
   a la máquina 1:
   `scp 10.43.100.36:<carpeta del proyecto>/resultados/gt_metricas.csv resultados/`
6. Máquina 1: `python -m herramientas.analizar_metricas`

Un escenario suelto se lanza con
`python -m capa_cliente.escenarios --escenario 3 --etiqueta base --corrida 1`.

El análisis imprime la tabla, la guarda en `resultados/resumen.csv` y deja los gráficos en
`resultados/graficos/`. Para cada arquitectura, número de clientes y operación calcula:

| Métrica | Cómo se obtiene |
|---|---|
| Tiempo de respuesta: promedio, desviación estándar y percentil 95 (ms) | En el cliente, con `time.perf_counter()`: desde que envía la petición hasta que recibe la respuesta |
| Transacciones por minuto (TPM) | Contadas en el Gestor de Transacciones: filas de su CSV que corresponden a la corrida (por `uuid`), divididas por su duración |
| Tasa de error (%) | Peticiones que terminaron en `ERROR` sobre el total |

| Archivo | Lo escribe | Contenido |
|---|---|---|
| `resultados/<etiqueta>_<N>clientes/corrida_<n>/cliente_<id>.csv` | Cada cliente | hora de envío, tipo, estado, motivo, tiempo de respuesta (ms), uuid |
| `resultados/gt_metricas.csv` | Gestor de Transacciones | hora de fin, tipo, estado, motivo, tiempo (ms), cliente, uuid |

## 10. Mensajes y respuestas

Todos los mensajes son JSON (`config/E_mensaje.py`):

```
Petición:  {"uuid": "...", "tipo": "RESERVA", "id_cliente": 7, "datos": {...}}
Respuesta: {"uuid": "...", "estado": "EXITO", "motivo": null, "datos": {...}}
```

| Tipo | Datos | Respuesta |
|---|---|---|
| `CONSULTA` | `{"mes": "noviembre"}` | Lista de ocurrencias del mes con asientos libres y ocupados |
| `RESERVA` | `{"id_evento": "E1", "fecha": "2026/11/01", "n_asientos": 2}` | La reserva con su número (`id_reserva`) |
| `MODIFICACION` | `{"id_reserva": 3, "n_asientos": 5}` o `{"id_reserva": 3, "fecha": "2026/11/15"}` | La reserva como quedó |
| `CANCELACION` | `{"id_reserva": 3, "notificar_a": "tcp://10.43.99.236:6001"}` | `ACK`; después llega la notificación |
| `NOTIFICACION` | (la envía el Servicio de Cancelaciones) | Respuesta con el `uuid` de la cancelación y la reserva liberada |

| Estado | Significado |
|---|---|
| `EXITO` | Se hizo lo pedido |
| `FALLO` | Regla de negocio: `SIN_CUPO` o `NO_EXISTE` |
| `ERROR` | Petición mal formada (`PETICION_INVALIDA`, `DATO_INVALIDO`) o servicio sin respuesta (`NO_DISPONIBLE`) |
| `ACK` | Cancelación aceptada; se procesa después |

## 11. Problemas frecuentes

| Síntoma | Causa probable | Corrección |
|---|---|---|
| `No se puede obtener el valor ...` al arrancar | Falta una variable en el `.env` | Se copia `.env.example` sobre `.env` |
| El cliente recibe `ERROR NO_DISPONIBLE: el GT no respondio` | El Gestor de Transacciones no está en marcha, la IP de `HOST_CAPA_SERVICIOS` no es la de la máquina 2 o el puerto 5555 está cerrado | Se revisan la máquina 2, el `.env` y la regla de `ufw` |
| `ERROR NO_DISPONIBLE: no hay ningun RMC conectado` | No hay ningún RMC en marcha | Se arranca un RMC en la máquina 2 |
| `ERROR NO_DISPONIBLE: la persistencia no respondio` | El Servicio de Persistencia no está en marcha o el puerto 5558 está cerrado | Se revisan la máquina 3 y la regla de `ufw` |
| La cancelación responde `ACK` pero no llega la notificación | El Servicio de Cancelaciones no está en marcha, o los puertos 6001 en adelante de la máquina 1 están cerrados | Se arranca el servicio y se revisa la regla de `ufw` de la máquina 1 |
| `el puerto 6001 esta ocupado` | Ya hay un cliente con ese `--id` | Se usa otro `--id` |
| `database is locked` o errores de SQLite | La carpeta del proyecto está en un disco de red (NFS), que no admite el modo WAL | `BD_RUTA` se cambia por una ruta absoluta en el disco local de la máquina 3, por ejemplo `/var/tmp/srb/srb.db` |

## 12. Estructura del proyecto

```
capa_cliente/        Cliente, casos de prueba, generador de carga y escenarios de la Tabla 1
capa_negocios/       Gestor de Transacciones, RMC, Servicio de Cancelaciones y métricas
capa_persistencia/   Servicio de Persistencia (principal y réplica de lectura), SQLite y carga de datos
config/              Lectura del .env y definición de los mensajes (protocolo)
herramientas/        ver_bd (estado de la base de datos) y analizar_metricas
pruebas/             Pruebas de pytest y casos de prueba (caso_basico.txt, ejemplo.json)
scripts/             protocolo-pruebas.sh y medir.sh
docs/                Informe y diagramas de la arquitectura final
datos/               Base de datos SQLite (se crea al cargar los datos)
resultados/          CSV de métricas y gráficos (se crea al correr)
```
