"""Textos del informe. Los parrafos de analisis corresponden a los datos de docs/informe/datos/."""

TEXTOS = {'introduccion': ['En este informe se presentan las pruebas hechas al Sistema Distribuido de Reserva de Boletos '
                  '(SRB) y las métricas de desempeño obtenidas en la segunda entrega. En la primera entrega se '
                  'construyó la arquitectura base con la consulta y la reserva. Para esta entrega se han '
                  'implementado la modificación de reservas y la cancelación asíncrona con notificación al cliente, '
                  'y se han agregado los componentes que hacen el sistema escalable y tolerante a fallas del Gestor '
                  'de Transacciones y del Servicio de Procesamiento de Reservas, Modificaciones y Consultas (en '
                  'adelante, RMC).',
                  'El informe describe el entorno de medición, la arquitectura final con sus diagramas, el protocolo '
                  'de pruebas ejecutado con el resultado de cada caso y las métricas principales: tiempo de '
                  'respuesta, transacciones por minuto y tasa de error, en la arquitectura base y en la escalable, '
                  'para los tres escenarios del enunciado. El código fuente está en el repositorio '
                  'https://github.com/ana2320-ux/Sistema_Distribuido_SRB.'],
 'hardware': 'El sistema se despliega en tres máquinas con Ubuntu, una por capa (Tabla 1). Las tres tienen el mismo '
             'procesador (4 núcleos asignados a cada máquina) y la misma memoria. La carpeta del proyecto está '
             'compartida por NFS entre las tres; la base de datos queda en el disco local de la máquina 3.',
 'equipo_medicion': 'Las mediciones de este informe se han tomado en un solo computador: procesador Intel Core '
                    'i7-13700HX (16 núcleos, 24 hilos), 31,8 GB de RAM y Windows 11 Home. Las tres capas corren en '
                    'él como procesos separados que se comunican por TCP con ZeroMQ, igual que en el despliegue, '
                    'pero sin la latencia de la red entre máquinas. Por eso los tiempos absolutos son menores que '
                    'los que se obtendrán en las tres máquinas; la comparación entre la arquitectura base y la '
                    'escalable sí es válida, porque ambas se midieron en el mismo equipo y con la misma carga. La '
                    'sección 8 indica cómo se repiten las mediciones en las tres máquinas.',
 'herramientas': ['El tiempo de respuesta se mide en el cliente con `time.perf_counter()` de Python: desde que envía '
                  'la petición hasta que recibe la respuesta. Cada cliente guarda una fila por petición en un '
                  'archivo CSV (hora de envío, tipo, estado, motivo, milisegundos y `uuid`).',
                  'La carga la genera Locust 2.47: cada cliente es un proceso de Locust con un usuario virtual que '
                  'usa el cliente ZeroMQ del proyecto, envía las peticiones a ritmo fijo y le reporta a Locust el '
                  'tiempo de cada una. El mismo usuario escribe el CSV del cliente, que es el que se analiza.',
                  'Las transacciones por minuto se miden en el Gestor de Transacciones, como pide el enunciado: el '
                  'gestor escribe en `resultados/gt_metricas.csv` una fila por cada transacción que despacha y '
                  'recibe de vuelta. El programa `herramientas/analizar_metricas.py` asocia esas filas a cada '
                  'corrida por el `uuid` de la petición y calcula, por arquitectura, número de clientes y operación, '
                  'el promedio, la desviación estándar y el percentil 95 del tiempo de respuesta, las transacciones '
                  'por minuto y la tasa de error; también dibuja los gráficos con `matplotlib`. Las pruebas '
                  'automáticas se ejecutan con `pytest`.'],
 'arquitectura': 'La arquitectura final conserva las tres capas de la Figura 1 del enunciado y agrega réplicas y '
                 'mecanismos de recuperación. Todos los procesos están escritos en Python y se comunican solo con '
                 'ZeroMQ, con mensajes JSON.',
 'despliegue': 'Cada capa corre en una máquina (Figura 1). En la máquina 2 corren el Gestor de Transacciones activo, '
               'uno de respaldo, las réplicas del RMC y el Servicio de Cancelaciones. En la máquina 3 corren el '
               'Servicio de Persistencia principal y su réplica de lectura sobre la misma base de datos SQLite. Con '
               'Kubernetes (k3s) las tres máquinas son los nodos del clúster, cada una etiquetada con su capa, y '
               'esos mismos procesos son contenedores: los manifiestos están en la carpeta `k8s/` del repositorio.',
 'componentes': 'El Gestor de Transacciones es la única entrada. Envía las consultas, reservas y modificaciones a '
                'los RMC por el canal síncrono (ROUTER/DEALER) y las cancelaciones al Servicio de Cancelaciones por '
                'el canal asíncrono (PUSH/PULL). Solo los servicios de persistencia tocan la base de datos (Figura '
                '2). La Tabla 3 resume los componentes agregados y su justificación.',
 'tabla_componentes': [['Kubernetes (k3s)',
                        'Escalabilidad y tolerancia a fallas',
                        'Cada servicio es un contenedor desplegado como Deployment. Un `nodeSelector` fija cada capa '
                        'en su nodo, los servicios se localizan por el nombre DNS de su Service y las pruebas de '
                        'vida y de disponibilidad (liveness y readiness) detectan un contenedor que dejó de atender. '
                        'Si un pod o un contenedor cae, Kubernetes crea otro.'],
                       ['Réplicas del RMC',
                        'Escalabilidad',
                        'El Gestor de Transacciones hace de intermediario ROUTER/DEALER y reparte las peticiones '
                        'entre todos los RMC conectados. En Kubernetes el RMC es un Deployment de 3 réplicas que se '
                        'amplía con `kubectl scale`; el gestor no cambia. El RMC es el servicio que más trabaja por '
                        'petición, porque espera a la persistencia.'],
                       ['Réplica de lectura de la persistencia',
                        'Escalabilidad',
                        'Un segundo proceso de persistencia abre la misma base SQLite en modo WAL (SQLite, s. f.) y '
                        'atiende solo consultas, mientras el principal escribe. Así las consultas, que son la '
                        'mayoría de la carga, no hacen fila detrás de las escrituras.'],
                       ['Gestor de Transacciones de respaldo',
                        'Tolerancia a fallas',
                        'Un segundo gestor queda en espera en la máquina 2 e intenta tomar los puertos cada segundo. '
                        'Cuando el activo se cae, los toma y sigue atendiendo; los clientes y los RMC se reconectan '
                        'solos. En Kubernetes son dos contenedores del mismo pod, que comparten la red, y el '
                        'contenedor caído se reinicia como respaldo.'],
                       ['Reenvío a otro RMC',
                        'Tolerancia a fallas',
                        'Si un RMC no responde en 2 segundos, el gestor reenvía la petición, marcada como reintento '
                        'y con el mismo `uuid`, y el DEALER la entrega a otro RMC.'],
                       ['Reintento del cliente',
                        'Tolerancia a fallas',
                        'Si el cliente no recibe respuesta en 5 segundos, reenvía la petición una vez con el mismo '
                        '`uuid`. Cubre las peticiones que iban en camino cuando cayó el gestor.'],
                       ['Escrituras idempotentes',
                        'Tolerancia a fallas',
                        'La persistencia guarda en la tabla `operacion` el resultado de cada escritura por el `uuid` '
                        'de la petición. Una petición repetida devuelve el mismo resultado y no se aplica dos veces: '
                        'la operación continúa donde iba, sin duplicarse.'],
                       ['Cola de cancelaciones',
                        'Tolerancia a fallas',
                        'El gestor se conecta al Servicio de Cancelaciones con un socket PUSH; si ese servicio está '
                        'caído, ZeroMQ guarda las cancelaciones aceptadas y las entrega cuando vuelve.']],
 'kubernetes': ['La escalabilidad y la tolerancia a fallas se obtienen como se planteó en la primera entrega, con '
                'Kubernetes: cada servicio se empaqueta en una imagen de contenedor y se despliega como Deployment; '
                'las tres máquinas son nodos de un clúster k3s y un `nodeSelector` asigna una capa a cada nodo; las '
                'réplicas del RMC reciben el trabajo por el intermediario ROUTER/DEALER del gestor; los servicios se '
                'encuentran por el nombre DNS de su Service; y el cliente reintenta con un identificador único, de '
                'modo que una operación interrumpida continúa sin duplicarse. La persistencia lleva una sola réplica '
                'con almacenamiento en el disco del nodo, porque SQLite admite un solo escritor; su réplica de '
                'lectura es un segundo contenedor del mismo pod, sobre el mismo volumen.',
                'El código de la aplicación es el mismo con Kubernetes y sin él: los manifiestos solo cambian las '
                'variables de entorno de cada contenedor. Por eso el despliegue con procesos (un comando por '
                'servicio) se conserva: es la arquitectura base de las mediciones y una alternativa cuando no hay '
                'clúster. Los manifiestos se han validado en su sintaxis y la aplicación se ha probado con procesos; '
                'el despliegue en el clúster de las tres máquinas queda por ejecutar (sección 8).'],
 'clases': 'El código está organizado en un paquete por capa (Figura 3). La lógica de cada servicio está separada de '
           'los sockets: `ServicioRMC` y `ServicioPersistencia` reciben una petición y devuelven una respuesta, y '
           'los módulos `main` manejan la comunicación. `BaseDatos` concentra todo el SQL. La base de datos tiene '
           'cuatro tablas (Figura 4); la tabla `operacion` es la que hace idempotentes las escrituras.',
 'secuencia': 'En una reserva (Figura 5) el RMC consulta la disponibilidad y, si alcanza, pide confirmar; la '
              'persistencia vuelve a verificar el cupo dentro de la misma transacción, así dos clientes que reservan '
              'a la vez nunca superan la capacidad. La modificación sigue los mismos pasos y, si no hay cupo, deja '
              'la reserva como estaba. En la cancelación (Figura 6) el gestor responde `ACK` de inmediato y el '
              'resultado llega después como notificación, directamente del Servicio de Cancelaciones al cliente. La '
              'Figura 7 muestra la recuperación cuando cae un RMC o el gestor activo.',
 'mensajes': 'Toda petición lleva un `uuid`, el tipo, el identificador del cliente y los datos; la respuesta lleva '
             'el mismo `uuid`, un estado (`EXITO`, `FALLO`, `ERROR` o `ACK`) y, si aplica, un motivo. La Tabla 4 '
             'completa la lista de mensajes de la primera entrega con la modificación, la cancelación y la '
             'notificación.',
 'tabla_mensajes': [['`CONSULTA`',
                     'Cliente',
                     '`{"mes": "noviembre"}`',
                     'Ocurrencias del mes con capacidad, ocupados y libres'],
                    ['`RESERVA`',
                     'Cliente',
                     '`{"id_evento": "E1", "fecha": "2026/11/01", "n_asientos": 2}`',
                     '`EXITO` con el número de reserva, o `FALLO` (`SIN_CUPO`, `NO_EXISTE`)'],
                    ['`MODIFICACION`',
                     'Cliente',
                     '`{"id_reserva": 3, "n_asientos": 5}` o `{"id_reserva": 3, "fecha": "2026/11/15"}`',
                     '`EXITO` con la reserva como quedó, o `FALLO` sin cambios'],
                    ['`CANCELACION`',
                     'Cliente',
                     '`{"id_reserva": 3, "notificar_a": "tcp://10.43.99.236:6001"}`',
                     '`ACK` inmediato'],
                    ['`NOTIFICACION`',
                     'Servicio de Cancelaciones, al cliente',
                     '`uuid` de la cancelación, estado y reserva liberada',
                     'No se responde'],
                    ['`CONSULTA_DISPONIBILIDAD`',
                     'RMC',
                     '`{"id_evento": "E1", "fecha": "2026/11/01"}`',
                     'Capacidad, ocupados y libres de la ocurrencia'],
                    ['`AGREGAR_RESERVA`', 'RMC', 'Los de `RESERVA`', '`EXITO` con el número de reserva, o `FALLO`'],
                    ['`CONSULTAR_RESERVA`',
                     'RMC',
                     '`{"id_reserva": 3}`',
                     'Cliente, evento, fecha y asientos de la reserva'],
                    ['`MODIFICAR_RESERVA`',
                     'RMC',
                     'Los de `MODIFICACION`',
                     '`EXITO` con la reserva, o `FALLO` sin cambios'],
                    ['`LIBERAR_RESERVA`',
                     'Servicio de Cancelaciones',
                     '`{"id_reserva": 3}`',
                     '`EXITO` con la reserva liberada, o `FALLO NO_EXISTE`']],
 'fallos_seguridad': ['El modelo de fallos es de parada: un proceso que falla deja de responder y no envía '
                      'respuestas incorrectas (Coulouris et al., 2012). La falla se detecta por tiempo de espera en '
                      'cada salto, más corto cuanto más adentro: 5 segundos en el cliente, 2 segundos del gestor al '
                      'RMC y 1,6 segundos del RMC a la persistencia. Las verificaciones periódicas previstas se '
                      'concretan en el gestor de respaldo, que cada segundo comprueba si el activo sigue ocupando '
                      'los puertos. Los mensajes perdidos se recuperan con el reenvío, siguiendo los patrones de '
                      'petición y respuesta confiable de la guía de ZeroMQ (Hintjens, 2013).',
                      'En seguridad se asume una red interna. El Gestor de Transacciones revisa cada mensaje (que '
                      'sea JSON, que tenga `uuid`, cliente y datos con el tipo correcto) y solo acepta los cuatro '
                      'tipos del cliente; el RMC valida las cantidades; la persistencia valida fechas, eventos y '
                      'cupo, usa consultas SQL con parámetros y tiene restricciones `CHECK` para que los ocupados '
                      'nunca superen la capacidad. Solo los servicios de persistencia abren la base de datos. La '
                      'restricción por dirección IP prevista se hace con reglas de `ufw`, documentadas en el README: '
                      'el puerto 5555 solo acepta a la máquina 1, los puertos 5558 y 5559 solo a la máquina 2 y los '
                      'puertos de notificación solo a la máquina 2.'],
 'protocolo': ['El protocolo es el definido en la primera entrega, con todos los tipos de prueba. Las pruebas '
               'unitarias, de integración, funcionales, de concurrencia, de seguridad y de tolerancia a fallas se '
               'han automatizado con `pytest`: 75 pruebas en la carpeta `pruebas/` (20 de mensajes, 11 de la base de '
               'datos, 32 de la lógica de los servicios, 6 del sistema completo, 5 de tolerancia a fallas y 1 de la '
               'carga con Locust). El script `scripts/protocolo-pruebas.sh` las ejecuta en orden y muestra un '
               'resumen por tipo. Las pruebas del sistema completo arrancan los procesos reales, que se comunican '
               'por TCP, y en las de tolerancia a fallas se mata un proceso mientras el sistema trabaja.',
               'La carga se genera con Locust, como se había previsto (Locust, s. f.). Locust está hecho para HTTP, '
               'así que se ha escrito un usuario propio (`capa_cliente/locustfile.py`) que se comunica con el Gestor '
               'de Transacciones por ZeroMQ y le informa a Locust el resultado y la duración de cada petición. Cada '
               'usuario virtual es un proceso cliente: mantiene un ritmo fijo de al menos 20 peticiones por minuto, '
               'elige la operación, el evento y los asientos al azar con semilla fija, y recibe por parámetros el '
               'número de peticiones por minuto, el porcentaje de cada operación, la duración y la semilla.',
               'La Tabla 5 muestra el resultado de cada caso. Las 75 pruebas automáticas pasan.'],
 'tabla_protocolo': [['Unitaria',
                      'Validar mensajes JSON (campos obligatorios, tipos, cantidad mayor que 0)',
                      'Los inválidos se rechazan con error y los válidos pasan',
                      'Peticiones sin `uuid`, con cliente o datos de otro tipo y con asientos 0, negativos o no '
                      'enteros se rechazan con `PETICION_INVALIDA` o `DATO_INVALIDO`',
                      'Pasa'],
                     ['Unitaria',
                      'Asientos libres y ocupados tras una reserva',
                      'libres + ocupados = capacidad y libres ≥ 0',
                      'Tras reservar 10 quedan 90 libres y 10 ocupados; una reserva de 91 se rechaza sin cambios',
                      'Pasa'],
                     ['Unitaria',
                      'Un evento de una sola ocurrencia solo admite cambio de asientos',
                      'Cambio de fecha rechazado',
                      'El cambio de fecha de E30 devuelve `NO_EXISTE` y la reserva queda igual; el cambio de '
                      'asientos se aplica',
                      'Pasa'],
                     ['Integración',
                      'Cliente → Gestor de Transacciones → RMC → Persistencia → respuesta',
                      'La respuesta llega al cliente con el resultado correcto',
                      'El caso `caso_basico.txt` da 8 éxitos, 6 rechazos, 2 errores y 3 cancelaciones aceptadas, y '
                      'la base queda con 109 asientos ocupados y 3 reservas, como se esperaba',
                      'Pasa (1)'],
                     ['Integración',
                      'Cancelación: Gestor → Cancelaciones → Persistencia → notificación al cliente',
                      'El gestor responde `ACK` de inmediato y luego llega la notificación',
                      '`ACK` recibido; la notificación llega con el mismo `uuid` y los asientos quedan liberados',
                      'Pasa (1)'],
                     ['Funcional',
                      'Consultar los eventos del mes',
                      'Lista de 50 eventos con fechas y asientos libres',
                      '70 ocurrencias de 50 eventos, todas con 100 asientos libres',
                      'Pasa'],
                     ['Funcional',
                      'Reservar con disponibilidad',
                      '`EXITO`, libres −n, ocupados +n y reserva registrada',
                      'Reserva de 4 asientos: `EXITO` y 4 ocupados',
                      'Pasa'],
                     ['Funcional',
                      'Reservar más asientos de los libres',
                      '`FALLO`; la base no cambia',
                      '97 asientos con 96 libres: `FALLO SIN_CUPO`; siguen 4 ocupados',
                      'Pasa'],
                     ['Funcional',
                      'Modificar el número de asientos',
                      'Éxito o rechazo según disponibilidad',
                      'De 4 a 10 asientos: `EXITO`; a 101: `FALLO SIN_CUPO`',
                      'Pasa'],
                     ['Funcional',
                      'Cambiar la fecha en un evento de dos ocurrencias',
                      'Asientos devueltos en la fecha origen y descontados en la destino',
                      'E5 del día 05 al 19: 0 ocupados en el origen y 10 en el destino',
                      'Pasa'],
                     ['Funcional',
                      'Cambiar la fecha en un evento de una sola ocurrencia',
                      'Rechazo',
                      'E30: `FALLO NO_EXISTE`',
                      'Pasa'],
                     ['Funcional',
                      'Modificación rechazada',
                      'El cliente queda como estaba',
                      'Tras cada rechazo la reserva conserva su fecha y sus asientos',
                      'Pasa'],
                     ['Funcional',
                      'Cancelar una reserva existente',
                      '`ACK` inmediato, liberación en la base y notificación',
                      '`ACK`, notificación `EXITO` y 0 asientos ocupados',
                      'Pasa'],
                     ['Funcional',
                      'Cancelar una reserva inexistente',
                      'Notificación de error',
                      '`ACK` y notificación `FALLO NO_EXISTE`',
                      'Pasa'],
                     ['Concurrencia y consistencia',
                      'Varios clientes reservan a la vez los últimos asientos',
                      'Los libres nunca bajan de 0; las excedentes se rechazan',
                      '8 clientes, 150 intentos sobre 100 asientos: 100 `EXITO`, 50 `FALLO SIN_CUPO` y ninguna '
                      'reserva repetida',
                      'Pasa'],
                     ['Tolerancia a fallas',
                      'Matar el Gestor de Transacciones durante una carga',
                      'El sustituto toma el control; el cliente no ve error ni se pierden operaciones',
                      '90 reservas con el gestor muerto a mitad: 90 `EXITO` y 90 asientos ocupados',
                      'Pasa'],
                     ['Tolerancia a fallas',
                      'Matar un RMC a mitad de una reserva',
                      'Otro RMC retoma la reserva, sin duplicados',
                      'Caída antes de atender y caída después de guardar: el cliente recibe `EXITO` y la reserva '
                      'queda una sola vez',
                      'Pasa'],
                     ['Tolerancia a fallas',
                      'Matar el Servicio de Cancelaciones antes de procesar',
                      'La cancelación pendiente se procesa al recuperarse',
                      '`ACK` con el servicio caído; al arrancarlo llega la notificación y se liberan los asientos',
                      'Pasa'],
                     ['Tolerancia a fallas',
                      'Caída de una réplica de la base de datos',
                      'El sistema sigue operando y no se pierden datos',
                      'Con la réplica de lectura caída, las consultas pasan al servicio principal',
                      'Pasa'],
                     ['Rendimiento',
                      'Escenario 1: 3 clientes (2 solo consultan, 1 consulta y reserva)',
                      'Promedio, desviación estándar y TPM; meta de 60 TPM con 0 % de error',
                      '61,2 TPM en total y 0 % de error (Tablas 7 y 8)',
                      'Medido (1)'],
                     ['Rendimiento',
                      'Escenario 2: 5 clientes (3 solo consultan, 2 reservan y modifican)',
                      'Identificar cuellos de botella',
                      '102 TPM, 0 % de error; sin cuello de botella a esta carga',
                      'Medido (1)'],
                     ['Rendimiento',
                      'Escenario 3: 8 clientes (4 solo consultan, 4 reservan y modifican)',
                      'Identificar el punto de saturación',
                      '163 TPM, 0 % de error; la saturación se midió aparte (Tabla 9)',
                      'Medido (1)'],
                     ['Escalabilidad',
                      'Repetir los tres escenarios en la arquitectura base y en la escalable',
                      'Comparación de las métricas con porcentaje de mejora',
                      'Tablas 7, 8 y 9',
                      'Medido (1)'],
                     ['Despliegue',
                      'Arrancar el sistema con las IP reales, una capa por máquina',
                      'Funciona en las tres máquinas siguiendo el README',
                      'La configuración, el README y los manifiestos de Kubernetes (`k8s/`) están preparados para '
                      'las tres máquinas; falta ejecutarlos en ellas',
                      'Pendiente'],
                     ['Seguridad básica',
                      'Mensajes mal formados, identificadores inexistentes y cantidades excesivas',
                      'Rechazo controlado: el sistema no se cae ni cambia la base',
                      '13 mensajes (texto que no es JSON, tipos internos, 1 000 000 000 de asientos, inyección SQL, '
                      'cancelación sin dirección) rechazados; la base no cambia y el sistema sigue atendiendo',
                      'Pasa']],
 'nota_protocolo': '(1) Ejecutado con todos los procesos en un solo computador, comunicados por TCP. Falta repetirlo '
                   'entre las tres máquinas (sección 8).',
 'fallas': ['Además de las pruebas automáticas, se ha medido la recuperación con los tiempos de espera reales. Con '
            'la arquitectura escalable en marcha, tres clientes envían 120 peticiones por minuto cada uno durante 40 '
            'segundos (40 % consultas; el resto reservas, modificaciones y cancelaciones) y a los 15 segundos se '
            'mata un proceso. La Tabla 6 muestra el resultado.',
            'En los cuatro casos ningún cliente recibió un error, todas las cancelaciones aceptadas se notificaron y '
            'la base de datos quedó consistente: los asientos ocupados coinciden con las reservas activas. Al caer '
            'el Gestor de Transacciones, la petición más lenta tardó cerca de 1 segundo, que es lo que demora el '
            'gestor de respaldo en tomar los puertos. Al caer la réplica de lectura, la petición más lenta tardó 1,7 '
            'segundos: es el tiempo que el RMC espera a la réplica antes de pasar la consulta al servicio principal; '
            'las siguientes consultas van directo al principal. La caída de un RMC y la del Servicio de '
            'Cancelaciones no se notaron en los tiempos.'],
 'nota_fallas': 'La arquitectura tenía tres RMC. El Servicio de Cancelaciones se arrancó de nuevo 10 segundos '
                'después de matarlo; las cancelaciones aceptadas en ese intervalo se procesaron al volver.',
 'experimentos': ['Se han medido los tres escenarios de la Tabla 1 del enunciado: 3 clientes (2 solo consultan y 1 '
                  'consulta y reserva), 5 clientes (3 solo consultan y 2 reservan y modifican) y 8 clientes (4 solo '
                  'consultan y 4 reservan y modifican). Cada cliente es un proceso de Locust que envía 20 peticiones '
                  'por minuto a ritmo fijo durante 150 segundos. Cada escenario se ha corrido tres veces en cada '
                  'arquitectura, con la base de datos recién cargada antes de cada escenario; los valores de las '
                  'tablas reúnen las tres corridas. La semilla del azar de cada cliente depende de la corrida y de '
                  'su número, de modo que la arquitectura base y la escalable reciben exactamente las mismas '
                  'operaciones.',
                  'La arquitectura base tiene un Gestor de Transacciones, un RMC, el Servicio de Cancelaciones y un '
                  'Servicio de Persistencia. La escalable tiene además un gestor de respaldo, tres RMC y la réplica '
                  'de lectura.'],
 'nota_tiempos': 'El cambio del promedio es positivo cuando la arquitectura escalable responde más rápido que la '
                 'base. Mediciones en un solo computador.',
 'nota_tpm': 'TPM contadas en el Gestor de Transacciones. Cada cliente envía 20 peticiones por minuto, así que las '
             'TPM esperadas son 60, 100 y 160 en total.',
 'saturacion': ['Con 20 peticiones por minuto por cliente el sistema trabaja muy por debajo de su capacidad, así que '
                'los tres escenarios no muestran dónde se satura. Para encontrarlo se ha hecho una prueba adicional: '
                'los 8 clientes del escenario 3 envían una petición apenas reciben la respuesta de la anterior, sin '
                'pausa, durante 60 segundos. Para que las reservas no se rechazaran por falta de cupo, en esta '
                'prueba cada ocurrencia se cargó con 10 000 000 de asientos (Tabla 9).'],
 'nota_saturacion': 'Una corrida por arquitectura. En esta prueba las TPM son la capacidad máxima del sistema con 8 '
                    'clientes.',
 'analisis': ['Con la carga del enunciado las dos arquitecturas atienden todo lo que reciben. Las transacciones por '
              'minuto son las que envían los clientes (61, 102 y 163 en total, frente a 60, 100 y 160 esperadas) y '
              'son iguales en la arquitectura base y en la escalable; la tasa de error es 0 % en todos los casos. A '
              'esta carga las TPM dependen de los clientes y no de la arquitectura: 160 peticiones por minuto son '
              'menos de 3 por segundo y cada una se atiende en menos de 7 milisegundos.',
              'El tiempo de respuesta de la consulta es prácticamente el mismo en las dos arquitecturas (entre 2,6 y '
              '3,1 ms) y no crece con el número de clientes; la escalable es entre 3 % y 5 % más rápida. En la '
              'reserva y la modificación la arquitectura escalable es más lenta, entre 1 y 2 ms: una reserva tarda '
              'de 3,6 a 4,7 ms en la base y de 4,9 a 6,7 ms en la escalable. La causa es que en la escalable cada '
              'escritura usa dos servicios de persistencia: la disponibilidad se consulta en la réplica de lectura y '
              'la confirmación va al principal, que además comparte la base de datos con la réplica. Es el costo de '
              'la escalabilidad cuando la carga es baja: más procesos y más saltos, sin filas que acortar.',
              'La desviación estándar es pequeña frente al promedio en casi todos los casos. La más alta es la de la '
              'reserva con 3 clientes (2,2 ms en la base y 5,4 ms en la escalable): en ese escenario hay solo 78 '
              'reservas en total y las primeras de cada corrida, que abren las conexiones, pesan más en el cálculo. '
              'El percentil 95 queda por debajo de 9 ms en todos los escenarios.',
              'La diferencia aparece en la prueba de saturación. Con los 8 clientes enviando sin pausa, la '
              'arquitectura base procesa unas 34 600 transacciones por minuto y cada petición tarda 13,8 ms, porque '
              'todas hacen fila en el único RMC, que atiende una a la vez. La arquitectura escalable procesa unas 90 '
              '800 transacciones por minuto, 2,6 veces más: las consultas pasan de 17 294 a 52 207 por minuto (+202 '
              '%) y las reservas de 8 664 a 19 383 (+124 %), y el tiempo promedio baja a 4,6 ms en la consulta y a '
              '6,2 ms en la reserva. Las consultas mejoran más que las escrituras porque se reparten entre los tres '
              'RMC y la réplica de lectura, mientras que todas las escrituras terminan en el único proceso de '
              'persistencia principal, que pasa a ser el cuello de botella.',
              'En cuanto a los patrones de comunicación, el ROUTER/DEALER del Gestor de Transacciones permitió '
              'escalar sin cambiar el gestor ni los clientes, y el PUSH/PULL de la cancelación mantuvo su respuesta '
              'inmediata aun con el Servicio de Cancelaciones caído. La tolerancia a fallas no costó rendimiento '
              'medible con la carga del enunciado, y en las pruebas de la sección 4.1 ninguna falla produjo errores '
              'ni operaciones duplicadas.'],
 'conclusiones': ['El sistema final implementa las cuatro operaciones, está preparado para correr con una capa por '
                  'máquina y tolera la caída del Gestor de Transacciones, de un RMC, del Servicio de Cancelaciones y '
                  'de la réplica de lectura sin que el cliente reciba errores y sin perder ni repetir operaciones. '
                  'La pieza que lo hace posible es la idempotencia de las escrituras por `uuid`: gracias a ella '
                  'cualquier capa puede reenviar una petición sin riesgo.',
                  'Con la carga del enunciado (hasta 8 clientes y 20 peticiones por minuto cada uno) la arquitectura '
                  'escalable no mejora las métricas: las TPM son iguales, la consulta mejora menos de 5 % y la '
                  'reserva empeora entre 1 y 2 ms. La arquitectura base es suficiente para esa carga. La mejora real '
                  'se ve cuando el sistema se satura: la arquitectura escalable procesa 2,6 veces más transacciones '
                  'por minuto y responde entre 2 y 3 veces más rápido.',
                  'La recomendación es desplegar la arquitectura escalable. Para una universidad con más de 10 000 '
                  'estudiantes la carga real tendrá picos muy superiores a los del enunciado, el costo a baja carga '
                  'es de 1 a 2 ms en las escrituras, y es la única de las dos que tolera fallas. Si la carga de '
                  'escritura creciera más, el siguiente paso sería cambiar SQLite por un motor con varios '
                  'escritores, porque el Servicio de Persistencia principal es el límite de la arquitectura actual.'],
 'tres_maquinas': ['Las cifras de este informe corresponden a un solo computador. Para obtenerlas en las tres '
                   'máquinas del despliegue se siguen estos pasos, detallados en la sección 9 del README; el informe '
                   'se regenera con `python docs/informe/generar_informe.py` después de copiar los resultados a '
                   '`docs/informe/datos/`.'],
 'pasos_tres_maquinas': ['Clúster: se instala k3s, se etiquetan los nodos, se importa la imagen y se aplica `kubectl '
                         'apply -f k8s/` (sección 5.4 del README); el caso `pruebas/caso_basico.txt` desde el pod de '
                         'clientes comprueba el despliegue.',
                         'Máquinas 3 y 2: se levanta la arquitectura base. Máquina 1: `bash scripts/medir.sh base`.',
                         'Máquinas 3 y 2: se levanta la arquitectura escalable. Máquina 1: `bash scripts/medir.sh '
                         'escalable`.',
                         'Se copia `resultados/gt_metricas.csv` de la máquina 2 a la máquina 1 y se ejecuta `python '
                         '-m herramientas.analizar_metricas`.'],
 'referencias': ['Coulouris, G., Dollimore, J., Kindberg, T., & Blair, G. (2012). *Distributed systems: Concepts and '
                 'design* (5.ª ed.). Addison-Wesley.',
                 "Hintjens, P. (2013). *ZeroMQ: Messaging for many applications*. O'Reilly Media. "
                 'https://zguide.zeromq.org/docs/chapter4/',
                 'Locust. (s. f.). *Testing other systems/protocols*. '
                 'https://docs.locust.io/en/stable/testing-other-systems.html',
                 'SQLite. (s. f.). *Write-ahead logging*. https://www.sqlite.org/wal.html']}
