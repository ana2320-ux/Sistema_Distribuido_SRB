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
 'equipo_medicion': 'Las mediciones de este informe se han tomado en las tres máquinas del despliegue, con los '
                    'servicios como procesos: los clientes de Locust en la máquina 1, la capa de negocio en la '
                    'máquina 2 y la persistencia en la máquina 3, comunicados por la red de la sala. Las máquinas y '
                    'la red son compartidas, así que otros usuarios pueden estar trabajando en ellas durante una '
                    'medición. Antes se habían hecho las mismas pruebas en un portátil, con las tres capas en un '
                    'solo equipo; en las máquinas los tiempos son entre 2 y 3,5 veces mayores, porque cada petición '
                    'cruza la red de la máquina 1 a la 2 y de la 2 a la 3, y de vuelta, y cada máquina tiene 4 '
                    'núcleos. El despliegue en Kubernetes se ha comprobado en las mismas máquinas (sección 8).',
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
                '3). La Tabla 3 resume los componentes agregados y su justificación.',
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
                'Kubernetes: cada servicio corre en un contenedor desplegado como Deployment; las tres máquinas son '
                'nodos de un clúster k3s y un `nodeSelector` asigna una capa a cada nodo; las réplicas del RMC '
                'reciben el trabajo por el intermediario ROUTER/DEALER del gestor; los servicios se encuentran por '
                'el nombre DNS de su Service; las pruebas de vida y de disponibilidad detectan un contenedor que '
                'dejó de atender; y el cliente reintenta con un identificador único, de modo que una operación '
                'interrumpida continúa sin duplicarse. La persistencia lleva una sola réplica con almacenamiento en '
                'el disco del nodo, porque SQLite admite un solo escritor; su réplica de lectura es un segundo '
                'contenedor del mismo pod, sobre el mismo volumen.',
                'Los contenedores usan la imagen oficial `python:3.12-slim` con la carpeta del proyecto, compartida '
                'por NFS, montada en `/app`; así no hace falta construir ni distribuir una imagen propia, y el '
                'despliegue completo son tres comandos de `scripts/k8s.sh` (instalar el servidor, unir los agentes y '
                'desplegar). El código es el mismo con Kubernetes y sin él: los manifiestos solo cambian las '
                'variables de entorno de cada contenedor, y el despliegue con procesos se conserva como arquitectura '
                'base de las mediciones.',
                'El despliegue se ha probado en las tres máquinas: `scripts/k8s.sh` ha instalado k3s con el servidor '
                'en la máquina 2 y los agentes en las máquinas 1 y 3, y el paso `desplegar` ha dejado los siete pods '
                'cada uno en el nodo de su capa en unos 30 segundos. El caso `pruebas/caso_basico.txt`, lanzado desde '
                'el pod de clientes, ha dado el resultado esperado, y las pruebas de fallas dentro del clúster están '
                'en la sección 8.',
                'En las máquinas han aparecido dos problemas que no se veían en un solo computador. El primero es '
                'que k3s usa por defecto la red 10.43.0.0/16 para los Services, y esa red contiene la de la sala '
                '(10.43.96.0/20): un Service podía recibir la dirección de una máquina y quitarle su tráfico. El '
                'script fija rangos propios, 172.30.0.0/16 para los pods y 172.31.0.0/16 para los Services. El '
                'segundo es que un pod que se conecta a un Service antes de que k3s termine de crear sus reglas de '
                'red deja ese intento de conexión colgado, y Linux lo repite durante unos dos minutos; por eso los '
                'RMC tardaban en conectarse al gestor recién desplegado. Los procesos que se conectan a otro '
                'servicio fijan ahora un tiempo máximo de conexión de 1 segundo (la opción `CONNECT_TIMEOUT` de '
                'ZeroMQ), de modo que el intento se abandona y se repite enseguida.'],
 'clases': 'El código está organizado en un paquete por capa (Figura 4). La lógica de cada servicio está separada de '
           'los sockets: `ServicioRMC` y `ServicioPersistencia` reciben una petición y devuelven una respuesta, y '
           'los módulos `main` manejan la comunicación. `BaseDatos` concentra todo el SQL. La base de datos tiene '
           'cuatro tablas (Figura 5); la tabla `operacion` es la que hace idempotentes las escrituras.',
 'secuencia': 'En una reserva (Figura 6) el RMC consulta la disponibilidad y, si alcanza, pide confirmar; la '
              'persistencia vuelve a verificar el cupo dentro de la misma transacción, así dos clientes que reservan '
              'a la vez nunca superan la capacidad. La modificación sigue los mismos pasos y, si no hay cupo, deja '
              'la reserva como estaba. En la cancelación (Figura 7) el gestor responde `ACK` de inmediato y el '
              'resultado llega después como notificación, directamente del Servicio de Cancelaciones al cliente. La '
              'Figura 8 muestra la recuperación cuando cae un RMC o el gestor activo.',
 'mensajes': 'Toda petición lleva un `uuid`, el tipo, el identificador del cliente y los datos; la respuesta lleva '
             'el mismo `uuid`, un estado (`EXITO`, `FALLO`, `ERROR` o `ACK`) y, si aplica, un motivo. La Tabla 5 '
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
               'La Tabla 6 muestra el resultado de cada caso. Las 75 pruebas automáticas pasan.'],
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
                      '61,2 TPM en total y 0 % de error (Tablas 8 y 9)',
                      'Medido (1)'],
                     ['Rendimiento',
                      'Escenario 2: 5 clientes (3 solo consultan, 2 reservan y modifican)',
                      'Identificar cuellos de botella',
                      '102 TPM, 0 % de error; sin cuello de botella a esta carga',
                      'Medido (1)'],
                     ['Rendimiento',
                      'Escenario 3: 8 clientes (4 solo consultan, 4 reservan y modifican)',
                      'Identificar el punto de saturación',
                      '163 TPM, 0 % de error; la saturación se midió aparte (Tabla 10)',
                      'Medido (1)'],
                     ['Escalabilidad',
                      'Repetir los tres escenarios en la arquitectura base y en la escalable',
                      'Comparación de las métricas con porcentaje de mejora',
                      'Tablas 8, 9 y 10',
                      'Medido (1)'],
                     ['Despliegue',
                      'Arrancar el sistema con las IP reales, una capa por máquina',
                      'Funciona en las tres máquinas siguiendo el README',
                      'Con procesos y con Kubernetes (k3s, los siete pods en el nodo de su capa): el caso básico da '
                      'el resultado esperado y la base queda consistente',
                      'Pasa (1)'],
                     ['Seguridad básica',
                      'Mensajes mal formados, identificadores inexistentes y cantidades excesivas',
                      'Rechazo controlado: el sistema no se cae ni cambia la base',
                      '13 mensajes (texto que no es JSON, tipos internos, 1 000 000 000 de asientos, inyección SQL, '
                      'cancelación sin dirección) rechazados; la base no cambia y el sistema sigue atendiendo',
                      'Pasa']],
 'nota_protocolo': '(1) Ejecutado en las tres máquinas del despliegue. Las pruebas automáticas de `pytest` corren en '
                   'un solo computador, con los procesos comunicados por TCP.',
 'fallas': ['Además de las pruebas automáticas, se ha medido la recuperación en las tres máquinas, con los tiempos '
            'de espera reales. Con la arquitectura escalable en marcha, tres clientes de Locust envían 120 '
            'peticiones por minuto cada uno durante 40 segundos (40 % consultas; el resto reservas, modificaciones '
            'y cancelaciones) y a los 15 segundos se mata un proceso con `kill -9`. La Tabla 7 muestra el '
            'resultado.',
            'En los cuatro casos ningún cliente recibió un error, todas las cancelaciones aceptadas se notificaron y '
            'la base de datos quedó consistente: los asientos ocupados coinciden con las reservas activas. Al caer '
            'el Gestor de Transacciones, las dos peticiones que iban en camino tardaron 0,72 segundos, lo que '
            'demoró el gestor de respaldo en tomar los puertos (lo intenta cada segundo). Al caer la réplica de '
            'lectura, la petición más lenta tardó 1,7 segundos: es el tiempo que el RMC espera a la réplica antes '
            'de pasar la consulta al servicio principal; las siguientes consultas van directo al principal. La '
            'caída de un RMC y la del Servicio de Cancelaciones no se notaron en los tiempos.'],
 'nota_fallas': 'La arquitectura tenía tres RMC. El Servicio de Cancelaciones se arrancó de nuevo 10 segundos '
                'después de matarlo; las cancelaciones aceptadas en ese intervalo se procesaron al volver. La prueba '
                'del gestor se ha repetido: en la primera ejecución ninguna petición coincidió con el cambio de '
                'gestor y el mayor tiempo fue de 51 ms.',
 'experimentos': ['Se han medido los tres escenarios de la Tabla 1 del enunciado: 3 clientes (2 solo consultan y 1 '
                  'consulta y reserva), 5 clientes (3 solo consultan y 2 reservan y modifican) y 8 clientes (4 solo '
                  'consultan y 4 reservan y modifican). Cada cliente es un proceso de Locust en la máquina 1 que '
                  'envía 20 peticiones por minuto a ritmo fijo durante 150 segundos. Cada escenario se ha corrido tres veces en cada '
                  'arquitectura, con la base de datos recién cargada antes de cada escenario; los valores de las '
                  'tablas reúnen las tres corridas. La semilla del azar de cada cliente depende de la corrida y de '
                  'su número, de modo que la arquitectura base y la escalable reciben exactamente las mismas '
                  'operaciones.',
                  'La arquitectura base tiene un Gestor de Transacciones, un RMC, el Servicio de Cancelaciones y un '
                  'Servicio de Persistencia. La escalable tiene además un gestor de respaldo, tres RMC y la réplica '
                  'de lectura.'],
 'nota_tiempos': 'El cambio del promedio es positivo cuando la arquitectura escalable responde más rápido que la '
                 'base. Mediciones en las tres máquinas.',
 'nota_tpm': 'TPM contadas en el Gestor de Transacciones. Cada cliente envía 20 peticiones por minuto, así que las '
             'TPM esperadas son 60, 100 y 160 en total.',
 'saturacion': ['Con 20 peticiones por minuto por cliente el sistema trabaja muy por debajo de su capacidad, así que '
                'los tres escenarios no muestran dónde se satura. Para encontrarlo se ha hecho una prueba adicional: '
                'los 8 clientes del escenario 3 envían una petición apenas reciben la respuesta de la anterior, sin '
                'pausa, durante 60 segundos. Para que las reservas no se rechazaran por falta de cupo, en esta '
                'prueba cada ocurrencia se cargó con 10 000 000 de asientos. Se han hecho dos corridas con la '
                'arquitectura base y tres con la escalable; la Tabla 10 reúne todas.'],
 'nota_saturacion': 'Promedio de las corridas: dos en la base y tres en la escalable. La primera corrida escalable '
                    'se degradó a partir del segundo 40 (sección 6) y baja el promedio de sus TPM. En esta prueba las '
                    'TPM son la capacidad del sistema con 8 clientes.',
 'analisis': ['Con la carga del enunciado las dos arquitecturas atienden todo lo que reciben. Las transacciones por '
              'minuto son las que envían los clientes (61, 102 y 163 en total, frente a 60, 100 y 160 esperadas) y '
              'son iguales en la arquitectura base y en la escalable; ninguna de las 4 800 peticiones terminó en '
              'error. A esta carga las TPM dependen de los clientes y no de la arquitectura: 160 peticiones por '
              'minuto son menos de 3 por segundo y cada una se atiende en unos 10 milisegundos.',
              'En la consulta la arquitectura base se va haciendo más lenta a medida que crecen los clientes (de '
              '7,9 ms con 3 clientes a 9,6 ms con 8), porque todas las peticiones pasan por su único RMC y empiezan '
              'a coincidir. En la escalable la consulta se mantiene entre 7,4 y 8,0 ms; con 8 clientes es 22 % más '
              'rápida que en la base y su percentil 95 baja de 16,4 a 9,9 ms, porque las consultas se reparten '
              'entre los tres RMC y la réplica de lectura. En la reserva y la modificación las dos arquitecturas '
              'quedan casi iguales, cerca de 11 ms: la escalable es hasta 6 % más lenta con 3 y 5 clientes y entre '
              '4 % y 6 % más rápida con 8. En las máquinas la escalable no hace más viajes por la red que la base: '
              'la disponibilidad se consulta en la réplica en lugar del principal, y los dos están en la máquina 3. '
              'El costo de 1 a 2 ms en las escrituras que se había visto en un solo computador, donde todos los '
              'procesos compartían los mismos núcleos, aquí queda dentro de la variación normal.',
              'La desviación estándar es pequeña frente al promedio en todos los casos (4,7 ms como máximo) y el '
              'percentil 95 queda por debajo de 20 ms en todos los escenarios. Los tiempos son entre 2 y 3,5 veces '
              'los del portátil: la mayor parte de cada petición es el tiempo de la red entre las máquinas.',
              'La diferencia grande aparece en la prueba de saturación. Con los 8 clientes enviando sin pausa, la '
              'arquitectura base procesa unas 14 300 transacciones por minuto y cada petición tarda unos 33 ms, '
              'porque todas hacen fila en el único RMC, que atiende una a la vez. La arquitectura escalable procesa '
              'en promedio unas 28 900 transacciones por minuto, el doble: las consultas pasan de 7 129 a 16 073 '
              'por minuto (+125 %) y las reservas de 3 545 a 6 404 (+81 %), y el tiempo promedio baja a 14,8 ms en '
              'la consulta y a 19,2 ms en la reserva. Las consultas mejoran más que las escrituras porque se '
              'reparten entre los tres RMC y la réplica de lectura, mientras que todas las escrituras terminan en el '
              'único proceso de persistencia principal, que pasa a ser el cuello de botella.',
              'El promedio de la escalable incluye una corrida que se degradó. Dos de las tres corridas procesaron '
              '36 629 y 33 997 peticiones por minuto, entre 2,4 y 2,6 veces la base, con una mediana de 11 a 12 ms, '
              'lo mismo que se había medido en el portátil. La primera corrida mantuvo ese ritmo, unas 550 '
              'peticiones por segundo, durante 40 segundos; desde ahí bajó a unas 20 por segundo, con medianas de '
              '300 a 400 ms, hasta el final, y Locust detuvo a los clientes a los 96 segundos en lugar de a los 60. '
              'La prueba se ha repetido dos veces vigilando cada 5 segundos la CPU de cada proceso y el archivo WAL '
              'de SQLite: ningún proceso llegó al 100 % de un núcleo, el WAL se mantuvo en su tamaño normal (4 MB) '
              'y la degradación no volvió a aparecer. Su causa no se ha podido determinar; como las máquinas y la '
              'red son compartidas, no se descarta que haya sido una interferencia externa.',
              'En cuanto a los patrones de comunicación, el ROUTER/DEALER del Gestor de Transacciones permitió '
              'escalar sin cambiar el gestor ni los clientes, y el PUSH/PULL de la cancelación mantuvo su respuesta '
              'inmediata aun con el Servicio de Cancelaciones caído. La tolerancia a fallas no costó rendimiento '
              'medible con la carga del enunciado, y en las pruebas de las secciones 4.1 y 8 ninguna falla produjo '
              'errores ni operaciones duplicadas.'],
 'conclusiones': ['El sistema final implementa las cuatro operaciones, corre en las tres máquinas con una capa por '
                  'máquina, como procesos o en un clúster de Kubernetes, y tolera la caída del Gestor de '
                  'Transacciones, de un RMC, del Servicio de Cancelaciones y de la réplica de lectura sin que el '
                  'cliente reciba errores y sin perder ni repetir operaciones. La pieza que lo hace posible es la '
                  'idempotencia de las escrituras por `uuid`: gracias a ella cualquier capa puede reenviar una '
                  'petición sin riesgo.',
                  'Con la carga del enunciado (hasta 8 clientes y 20 peticiones por minuto cada uno) las TPM son las '
                  'mismas en las dos arquitecturas, porque las fija la carga. La escalable mejora la consulta a '
                  'medida que crecen los clientes (22 % más rápida con 8) y deja las escrituras prácticamente '
                  'iguales. La mejora grande se ve cuando el sistema se satura: la arquitectura escalable procesa '
                  'el doble de transacciones por minuto en promedio, entre 2,4 y 2,6 veces en las corridas sin '
                  'degradación, y responde entre 2 y 3 veces más rápido.',
                  'La recomendación es desplegar la arquitectura escalable en Kubernetes. Para una universidad con '
                  'más de 10 000 estudiantes la carga real tendrá picos muy superiores a los del enunciado, en las '
                  'máquinas no cuesta rendimiento a baja carga, y es la única de las dos que tolera fallas; '
                  'Kubernetes agrega la recreación automática de los procesos caídos. Si la carga de escritura '
                  'creciera más, el siguiente paso sería cambiar SQLite por un motor con varios escritores, porque el '
                  'Servicio de Persistencia principal es el límite de la arquitectura actual.'],
 'kubernetes_maquinas': ['En el clúster k3s de las tres máquinas se han repetido las pruebas de fallas de la sección '
                         '4.1, adaptadas a Kubernetes: tres clientes de Locust corren en el pod de clientes, cada uno '
                         'con 120 peticiones por minuto durante 40 segundos, y a los 15 segundos se provoca la falla. '
                         'La Tabla 11 muestra el resultado.',
                         'En los tres casos ningún cliente recibió un error y la base de datos quedó consistente. Al '
                         'caer el proceso del gestor activo, el respaldo del mismo pod tomó los puertos en cerca de 1 '
                         'segundo y Kubernetes reinició el contenedor caído, que quedó como nuevo respaldo. Al borrar '
                         'un pod del RMC, los otros dos siguieron atendiendo y Kubernetes creó uno nuevo. Al caer los '
                         'dos procesos del gestor a la vez no quedó ningún gestor: Kubernetes reinició los dos '
                         'contenedores, los RMC se reconectaron solos y las peticiones que iban en camino llegaron al '
                         'gestor nuevo en 1,5 segundos como máximo.',
                         'Las mediciones de rendimiento de la sección 5 se han tomado con los servicios como procesos, '
                         'que permite cambiar entre la arquitectura base y la escalable sin reinstalar nada. En el '
                         'clúster se repiten con un solo comando, `bash scripts/k8s-medir.sh` (sección 9 del README).'],
 'nota_fallas_k8s': 'Borrar el pod del gestor con `kubectl delete pod` no sirve como prueba de caída: Python, como '
                    'primer proceso del contenedor, ignora la señal de terminación y el pod sigue atendiendo durante '
                    'los 30 segundos de gracia. Por eso se mataron sus dos procesos con `kill -9`.',
 'referencias': ['Coulouris, G., Dollimore, J., Kindberg, T., & Blair, G. (2012). *Distributed systems: Concepts and '
                 'design* (5.ª ed.). Addison-Wesley.',
                 "Hintjens, P. (2013). *ZeroMQ: Messaging for many applications*. O'Reilly Media. "
                 'https://zguide.zeromq.org/docs/chapter4/',
                 'Locust. (s. f.). *Testing other systems/protocols*. '
                 'https://docs.locust.io/en/stable/testing-other-systems.html',
                 'SQLite. (s. f.). *Write-ahead logging*. https://www.sqlite.org/wal.html'],
 'patrones': ['La Tabla 4 resume los patrones de sistemas distribuidos resilientes que se han usado en el SRB y cómo se aplica cada uno. Varias de las técnicas con que se aplican son los patrones de petición y respuesta confiable de la guía de ZeroMQ (Hintjens, 2013).'],
 'tabla_patrones': [['Replicación (Replication)',
                     'Hay copias de cada servicio de la capa de negocio: un Gestor de Transacciones de respaldo en espera '
                     '(activo-pasivo), tres RMC que atienden a la vez detrás del intermediario ROUTER/DEALER, que reenvía a '
                     'otro RMC la petición que no tuvo respuesta en 2 s, y un segundo proceso de persistencia que atiende las '
                     'consultas. Los datos no se replican: la base SQLite es una sola y la réplica de lectura la abre en modo '
                     'WAL.'],
                    ['Compartimentos (Bulkhead)',
                     'Cada capa corre en su máquina y cada servicio en su propio proceso o contenedor. Las cancelaciones van '
                     'por un canal propio (PUSH/PULL) a un servicio aparte: si ese servicio cae, ZeroMQ guarda las '
                     'cancelaciones en una cola acotada y las reservas y consultas siguen; si la cola se llena, solo se '
                     'rechazan cancelaciones. Lecturas y escrituras van a procesos distintos.'],
                    ['Dejar que falle (Let It Crash)',
                     'En Kubernetes, un proceso que se cae no se repara: Kubernetes vuelve a crear el contenedor o el pod, y '
                     'mientras tanto el gestor de respaldo o los otros RMC atienden. El cliente reintenta una vez con el mismo '
                     '`uuid` (Lazy Pirate) y la persistencia reconoce la petición repetida (receptor idempotente), así que '
                     'repetir es seguro.'],
                    ['Degradación controlada (Graceful Degradation)',
                     'Si la réplica de lectura no responde, las consultas pasan al servicio principal. Si no hay ningún RMC, el '
                     'gestor espera 0,5 s y responde NO_DISPONIBLE en vez de dejar esperando al cliente. Si cae el Servicio de '
                     'Cancelaciones, el gestor sigue aceptando cancelaciones.'],
                    ['Señales de falla proactivas (Proactive Failure Signals)',
                     'Los tiempos de espera son más cortos cuanto más adentro (5 s el cliente, 2 s el gestor, 1,6 s el RMC): el '
                     'RMC alcanza a responder ERROR con el motivo NO_DISPONIBLE antes de que venza la espera del cliente. Los '
                     'mensajes mal formados se rechazan de inmediato (PETICION_INVALIDA) y la base tiene restricciones `CHECK`. '
                     'En Kubernetes, la prueba de disponibilidad (readiness) saca de servicio el contenedor que dejó de '
                     'atender.']],
 'nota_patrones': 'Además de estos patrones, la transacción atómica (verificar el cupo y ocupar los asientos en una sola '
                  'instrucción) y las escrituras idempotentes garantizan que no haya sobreventa ni reservas '
                  'duplicadas cuando una petición se repite.'}
