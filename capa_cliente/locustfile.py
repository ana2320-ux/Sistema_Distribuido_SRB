"""
Carga de un cliente con Locust. Cada proceso de Locust tiene UN usuario virtual, que es un
cliente: envia una peticion por ZeroMQ, espera la respuesta, la registra y espera hasta
completar el ritmo pedido. Para varios clientes se lanzan varios procesos
(capa_cliente.escenarios lo hace). Un cliente solo:

    python -m locust -f capa_cliente/locustfile.py --headless -u 1 -r 1 -t 150s \
        --id-cliente 1 --por-minuto 20 --consultas 70 --modificaciones 30 --cancelaciones 10 \
        --semilla 101 --salida resultados/cliente_1.csv
"""
import sys
import time

from locust import User, constant_pacing, events, task

# Locust parchea los hilos con gevent: el cliente tiene que usar los sockets de zmq.green,
# o un poll bloqueante dejaria colgado al hilo de las notificaciones y a la tarea.
import zmq.green
sys.modules["zmq"] = zmq.green

from config import E_mensaje as m
from config import configuracion as config
from capa_cliente.carga import Carga
from capa_cliente.cliente import Cliente


@events.init_command_line_parser.add_listener
def opciones(parser):
    parser.add_argument("--id-cliente", type=int, default=1, help="identificador del cliente (mayor que 0)")
    parser.add_argument("--por-minuto", type=float, default=20, help="peticiones por minuto")
    parser.add_argument("--consultas", type=float, default=70, help="porcentaje de consultas; el resto son escrituras")
    parser.add_argument("--modificaciones", type=float, default=0,
                        help="de las escrituras, porcentaje que modifica una reserva propia")
    parser.add_argument("--cancelaciones", type=float, default=0,
                        help="de las escrituras, porcentaje que cancela una reserva propia")
    parser.add_argument("--semilla", type=int, help="semilla del azar, para repetir una corrida")
    parser.add_argument("--salida", help="CSV de resultados; por defecto resultados/cliente_<id>.csv")


@events.test_start.add_listener
def validar(environment, **kwargs):
    o = environment.parsed_options
    if o.id_cliente <= 0 or o.por_minuto <= 0 or not (0 <= o.consultas <= 100 and o.modificaciones >= 0
                                                       and o.cancelaciones >= 0 and o.modificaciones + o.cancelaciones <= 100):
        sys.exit("--id-cliente y --por-minuto deben ser mayores que 0, --consultas va de 0 a 100 "
                 "y --modificaciones mas --cancelaciones no pasan de 100")


class ClienteSRB(User):
    def on_start(self):
        o = self.environment.parsed_options
        self._ritmo = constant_pacing(60 / o.por_minuto)        # segundos entre el inicio de una peticion y la siguiente
        self.cliente = Cliente(o.id_cliente)
        salida = o.salida or config.RAIZ / "resultados" / f"cliente_{o.id_cliente}.csv"
        try:
            self.carga = Carga(self.cliente, salida, o.consultas, o.modificaciones, o.cancelaciones, semilla=o.semilla)
        except RuntimeError:
            self.cliente.cerrar()
            raise

    def on_stop(self):
        self.carga.cerrar()
        print(f"[C{self.cliente.id_cliente}] terminado: {len(self.cliente.notificaciones)} notificaciones recibidas",
              flush=True)
        self.cliente.cerrar()

    def wait_time(self):
        return self._ritmo(self)

    @task
    def peticion(self):
        hora = time.time()
        tipo, respuesta, ms = self.carga.enviar_una(hora)
        error = Exception(respuesta["motivo"]) if respuesta["estado"] == m.ERROR else None
        self.environment.events.request.fire(request_type="ZMQ", name=tipo, response_time=ms, response_length=0,
                                             response=None, context={}, exception=error)
