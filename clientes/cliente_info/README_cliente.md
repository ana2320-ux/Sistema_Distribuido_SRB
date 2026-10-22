# Capa de clientes (consumidores) – SRB

Simula los consumidores de la Figura 1 y genera la carga del sistema a partir de un
**archivo de entrada** (escenario JSON), como permite el enunciado
("scripts/archivos de entrada o generadores de carga continua").

## Estructura

```
clientes/
├── cliente.py               Un cliente: REQ al GT, socket PULL para notificaciones, CSV de tiempos
├── config_cliente.json      IP:puerto del GT, IP de notificaciones, mes/año, timeout
├── generador_carga.py       Lee un escenario y lanza N clientes en paralelo (un proceso por cliente)
├── metricas_clientes.py     Promedio, desviación estándar y TPM por operación; escribe resumen.csv
├── escenarios/              Escenarios de la Tabla 1 (3, 5 y 8 clientes) + demo con todas las operaciones
├── cliente_profesor/
│   ├── cliente_profesor.py  Ejecuta un caso de prueba con operaciones EXACTAS y muestra la BD antes/después
│   └── casos/               Archivos de casos de prueba (caso_ejemplo.txt)
├── cliente_info/
│   ├── README_cliente.md    Este archivo
│   └── requirements.txt     Dependencias (pyzmq)
├── pruebas/                 Solo para pruebas locales (no son parte del sistema)
│   ├── probar_cliente.py    GT falso en memoria
│   └── cliente_prueba.py    Cliente de demostración: una operación de cada tipo y termina
└── resultados/              Se crea al ejecutar: CSV por cliente y resumen.csv (no se sube al repo)
```

**Todos los comandos se ejecutan desde la carpeta `clientes/`.**

## Instalación

Windows (PowerShell):
```
cd clientes
python -m venv .venv
.venv\Scripts\activate
pip install -r cliente_info\requirements.txt
```

Linux / Mac:
```
cd clientes
python3 -m venv .venv
source .venv/bin/activate
pip install -r cliente_info/requirements.txt
```

En Linux/Mac use `python3` en lugar de `python` en los comandos siguientes, y `/` en lugar de `\` en las rutas.

## Configuración

En `config_cliente.json`:

| Campo | Valor |
|---|---|
| `gt_endpoints` | Dirección del Gestor de Transacciones, p. ej. `["tcp://10.43.100.36:5557"]` |
| `host_notificaciones` | IP **de la máquina donde corren los clientes** (p. ej. `10.43.99.237`). El servicio de cancelación se conecta a esta IP para enviar la notificación; con `127.0.0.1` no llegaría desde otra máquina |
| `mes`, `anio` | Mes y año de los eventos a consultar |
| `timeout_ms` | Tiempo máximo de espera de una respuesta (por defecto 5000) |
| `asientos_min`, `asientos_max` | Rango de asientos por reserva |

## Ejecución

1. Levantar el sistema (persistencia, RMC, cancelación y GT) o, solo para probar el cliente,
   el GT falso en otra terminal:
   ```
   python pruebas\probar_cliente.py
   ```
   (escucha en `tcp://*:5550`, que es el valor por defecto de `config_cliente.json`)

2. Lanzar un escenario:
   ```
   python generador_carga.py escenarios\escenario_3_clientes.json
   python generador_carga.py escenarios\escenario_5_clientes.json
   python generador_carga.py escenarios\escenario_8_clientes.json
   python generador_carga.py escenarios\escenario_completo_demo.json
   ```
   El último incluye cancelaciones con notificación asíncrona.

   Opciones:

   | Opción | Efecto |
   |---|---|
   | `--gt tcp://IP:PUERTO` | Dirección del GT; reemplaza la de `config_cliente.json` |
   | `--duracion SEG` | Duración de la corrida; reemplaza la del escenario (120 s) |
   | `--rpm N` | Solicitudes por minuto de todos los clientes |
   | `--salida CARPETA` | Carpeta de resultados |
   | `--semilla N` | Semilla aleatoria, para repetir exactamente la misma corrida |

   Ejemplo contra el sistema desplegado en las VM:
   ```
   python generador_carga.py escenarios\escenario_3_clientes.json --gt tcp://10.43.100.36:5557
   ```

3. Los resultados quedan en `resultados\<escenario>\cliente_<id>.csv` y `resumen.csv`.
   Para recalcular las métricas sin volver a correr:
   ```
   python metricas_clientes.py resultados\8_clientes
   ```

Un solo cliente suelto:
```
python cliente.py --id C1 --rpm 60 --duracion 120 --pct-consulta 100
```

## Caso de prueba del profesor (`cliente_profesor/`)

`generador_carga.py` sortea las operaciones (sirve para medir rendimiento). Para el caso de
prueba de la sustentación, donde el profesor indica **cuáles** operaciones hacer sobre **cuáles**
eventos y la BD final debe coincidir, se usa `cliente_profesor.py`: ejecuta una lista exacta de
operaciones, en orden, y muestra el estado de los eventos involucrados antes y después.

1. Escribir el caso en un archivo de texto dentro de `cliente_profesor/casos/` (una operación por línea):
   ```
   # cliente  OPERACION  datos                 => resultado esperado (opcional)
   C1  CONSULTAR
   C1  RESERVAR  E5   1  4                     => OK
   C2  RESERVAR  E5   1  96                    => OK
   C3  RESERVAR  E5   1  1                     => RECHAZADO
   ```

   | Operación | Datos |
   |---|---|
   | `CONSULTAR` | – |
   | `RESERVAR` | `evento ocurrencia asientos` |
   | `MODIFICAR` | `evento ocurrencia_actual ocurrencia_nueva asientos` (cambio de fecha: nueva distinta; cambio de asientos: nueva = actual) |
   | `CANCELAR` | `evento ocurrencia asientos` |

   - El evento se escribe `E5` (o `5`) y la ocurrencia `1` o `2`: la 1.a o 2.a fecha del evento
     en el mes. El script la traduce al `id_ocurrencia` de la BD con una consulta inicial.
   - `=> OK`, `=> RECHAZADO`, `=> ERROR` o `=> ACEPTADO` al final es opcional: si está, el
     script indica si el resultado real coincide con el esperado.
   - Lo que va después de `#` es comentario.

2. Reiniciar la BD para que el caso parta del estado inicial: en la máquina de persistencia,
   desde `persistencia/`, ejecutar `init_bd.py` (y volver a levantar el servicio de persistencia).

3. Ejecutar desde `clientes/` (con el sistema levantado):
   ```
   python cliente_profesor\cliente_profesor.py caso_ejemplo.txt --gt tcp://10.43.100.36:5557
   ```
   Basta el nombre del archivo: si no se da una ruta, se busca en `cliente_profesor/casos/`.

   `cliente_profesor.py` usa `cliente.py` y `config_cliente.json` de la carpeta `clientes/`
   (agrega esa carpeta a la ruta de búsqueda de Python al iniciar), así que esos archivos deben
   seguir en `clientes/`.

Salida: tabla con el estado inicial de los eventos del caso, cada operación con el cliente, su
resultado y si coincide con el esperado, las notificaciones de cancelación (si hay), y la tabla
del estado final con el cambio en asientos ocupados. El detalle queda en
`clientes/resultados/caso_profesor/cliente_PROFESOR.csv`, desde donde sea que se ejecute.

El archivo completo se valida antes de enviar nada (operaciones desconocidas, datos faltantes,
eventos u ocurrencias que no existen); si hay un error se indica la línea y no se ejecuta nada.
Las operaciones se envían una tras otra, aunque sean de clientes distintos, para que el
resultado sea predecible.

Opciones: `--gt`, `--pausa SEG` (espera entre operaciones, útil para mostrar paso a paso),
`--espera-notif SEG` (máximo de espera por notificaciones, por defecto 5), `--salida CARPETA`.

## Salida del generador

Por cada cliente muestra cuántas operaciones hizo de cada tipo y dos contadores de control:

- `cambiadas`: modificaciones o cancelaciones que salieron sorteadas cuando el cliente no tenía
  reservas, y se reemplazaron por una reserva. Si es mayor que 0 se muestra un AVISO. Valores
  bajos (1 o 2) son normales; un valor alto con `modificacion: 0` indica un problema.
- `notif_sin_recibir`: cancelaciones cuya notificación no llegó.

Después imprime la tabla de métricas (ver *Medición*).

## Formato del escenario

```json
{
  "nombre": "8_clientes",
  "duracion_seg": 120,
  "grupos": [
    {"prefijo": "CQ", "cantidad": 4, "rpm": 60, "mezcla": {"consulta": 100}},
    {"prefijo": "CR", "cantidad": 4, "rpm": 60, "mezcla": {"consulta": 20, "reserva": 60, "modificacion": 20}}
  ]
}
```

Las solicitudes por minuto (`rpm`, mínimo 20 según el enunciado) y los porcentajes de la
mezcla son parametrizables por grupo. Los porcentajes se normalizan para sumar 100.

| Escenario (Tabla 1) | Solo consultas | Resto |
|---|---|---|
| 3 clientes | 2 | 1 con consultas y reservas |
| 5 clientes | 3 | 2 con reservas y modificaciones |
| 8 clientes | 4 | 4 con reservas y modificaciones |

## Contrato de mensajes con el GT (el mismo de `modelo_negocio/` y `persistencia/`)

Petición: `{"operacion": "...", "payload": {...}}`. Respuesta: `{"status": "OK|RECHAZADO|ERROR", "mensaje": "..."}`.

| operacion | payload | respuesta (además de status) |
|---|---|---|
| `CONSULTAR` | `id_cliente, mes, anio` | `data`: lista de `{id_evento, nombre, id_ocurrencia, fecha, capacidad, ocupados, libres}` |
| `RESERVAR` | `id_cliente, id_ocurrencia, asientos` | `id_reserva` si el servidor lo devuelve (opcional) |
| `MODIFICAR` | `id_cliente, id_ocurrencia_actual, id_ocurrencia_nueva, asientos` | – |
| `CANCELAR` | `id_cliente, id_reserva, id_ocurrencia, asientos, endpoint_notificacion` | ACK inmediato con `status: "ACEPTADO"` |

En MODIFICAR: cambio de fecha → `id_ocurrencia_nueva` distinta y `asientos` = los de la reserva;
cambio de asientos → `id_ocurrencia_nueva` igual a la actual y `asientos` = el nuevo número.

**Notificación** (el servicio de cancelación la envía por PUSH a `endpoint_notificacion`):
`{"status": "OK|ERROR", "mensaje": "Cancelación de reserva #N ..."}`. El cliente la empareja
con su cancelación pendiente por `id_reserva` (si viene), por el `#N` del mensaje o, si no, por orden.

Pendiente en otros servicios (no es del cliente): RESERVAR no devuelve `id_reserva`; el cambio de
número de asientos en MODIFICAR (actual == nueva) responde OK sin cambiar la BD; y la cancelación
responde OK sin liberar los asientos.

## Medición

Cada cliente mide el tiempo de respuesta de cada solicitud con `time.perf_counter` (desde que
envía la petición hasta que recibe la respuesta) y lo guarda en su CSV
(`ts, tipo, ok, latencia_ms, detalle`).

`metricas_clientes.py` calcula por operación:

| Columna | Significado |
|---|---|
| `n` | Solicitudes enviadas |
| `ok` | Solicitudes exitosas |
| `media ms`, `desv ms` | Tiempo promedio de respuesta y desviación estándar, **solo de las exitosas** |
| `TPM`, `TPM ok` | Transacciones por minuto (enviadas / exitosas) |

Las fallidas (rechazos, errores, timeouts) se ven en la diferencia entre `n` y `ok`, y no entran
en el promedio: un timeout registra ~`timeout_ms` sin respuesta y lo inflaría. Si el GT no responde
en `timeout_ms`, la solicitud se registra como `TIMEOUT` y el socket REQ se reconstruye.

El TPM calculado aquí es del lado del cliente; el enunciado pide medirlo en el GT o en la BD, así
que conviene contrastarlo con un contador en el GT.

Las métricas de la Tabla 1 deben tomarse contra el sistema real desplegado en las máquinas,
no contra `pruebas/probar_cliente.py`.