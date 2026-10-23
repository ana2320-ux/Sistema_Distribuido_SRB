"""
Logica del RMC (Reservas, Modificaciones y Consultas): recibe una peticion del
GT (dict) y devuelve una respuesta (dict). Para resolverla le pregunta a la
persistencia. Sigue los pasos de la tabla del enunciado.
"""
from config import E_mensaje as m
from capa_negocios.cliente_persistencia import PersistenciaNoDisponible


class ServicioRMC:
    def __init__(self, persistencia):
        self.persistencia = persistencia
        # tipo de peticion -> metodo que la atiende
        self.operaciones = {
            m.CONSULTA: self.consultar_eventos,
            m.RESERVA: self.reservar,
        }

    def atender(self, peticion):
        """Recibe una peticion y SIEMPRE devuelve una respuesta."""
        operacion = self.operaciones.get(peticion.get("tipo"))
        if operacion is None:
            return m.crear_respuesta(peticion, m.ERROR, m.PETICION_INVALIDA,
                                     {"razon": f"tipo no atendido: {peticion.get('tipo')}"})
        try:
            return operacion(peticion)
        except PersistenciaNoDisponible as e:
            return m.crear_respuesta(peticion, m.ERROR, m.NO_DISPONIBLE, {"razon": str(e)})

    # CONSULTA: {"mes": "noviembre"}
    def consultar_eventos(self, peticion):
        # 1. recibir  2. enviar a la persistencia  3. devolver el resultado
        return self.persistencia.enviar(peticion)

    # RESERVA: {"id_evento": "E1", "fecha": "2026/11/01", "n_asientos": 2}
    def reservar(self, peticion):
        datos = peticion.get("datos", {})
        n_asientos = datos.get("n_asientos")
        if not isinstance(n_asientos, int) or isinstance(n_asientos, bool) or n_asientos <= 0:
            return m.crear_respuesta(peticion, m.ERROR, m.DATO_INVALIDO,
                                     {"razon": f"n_asientos debe ser un entero mayor que 0: {n_asientos}"})

        # 2. consultar la disponibilidad en tiempo real (mismo uuid, para seguirla en los logs)
        consulta = m.crear_peticion(m.CONSULTA_DISPONIBILIDAD, peticion["id_cliente"],
                                    {"id_evento": datos.get("id_evento"), "fecha": datos.get("fecha")},
                                    peticion["uuid"])
        disponibilidad = self.persistencia.enviar(consulta)
        if disponibilidad["estado"] != m.EXITO:
            return disponibilidad          # NO_EXISTE o DATO_INVALIDO: ya trae el uuid correcto

        libres = disponibilidad["datos"]["libres"]
        if libres < n_asientos:
            return m.crear_respuesta(peticion, m.FALLO, m.SIN_CUPO,
                                     {"razon": f"hay {libres} puestos libres, se pidieron {n_asientos}"})

        # 3. confirmar. La persistencia vuelve a verificar el cupo en una sola
        #    instruccion: otro cliente pudo reservar entre el paso 2 y este.
        agregar = m.crear_peticion(m.AGREGAR_RESERVA, peticion["id_cliente"], datos, peticion["uuid"])
        # 4. responder lo que diga la persistencia (EXITO o FALLO SIN_CUPO)
        return self.persistencia.enviar(agregar, reintentar=False)