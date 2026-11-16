"""
Logica del RMC (Reservas, Modificaciones y Consultas): recibe una peticion del
GT (dict) y devuelve una respuesta (dict). Para resolverla le pregunta a la
persistencia. Sigue los pasos de la tabla del enunciado.

Una peticion marcada como reintento (el GT o el cliente la reenviaron porque no hubo
respuesta) va directo a la escritura: si ya se habia hecho, la persistencia devuelve
el mismo resultado. Consultar el cupo otra vez podria rechazarla por los asientos que
ella misma ocupo.
"""
from config import E_mensaje as m
from capa_negocios.cliente_persistencia import PersistenciaNoDisponible


def asientos_invalidos(peticion, n_asientos):
    """Respuesta de error si n_asientos no es un entero mayor que 0; None si esta bien."""
    if isinstance(n_asientos, int) and not isinstance(n_asientos, bool) and n_asientos > 0:
        return None
    return m.crear_respuesta(peticion, m.ERROR, m.DATO_INVALIDO,
                             {"razon": f"n_asientos debe ser un entero mayor que 0: {n_asientos}"})


class ServicioRMC:
    def __init__(self, persistencia):
        self.persistencia = persistencia
        # tipo de peticion -> metodo que la atiende
        self.operaciones = {
            m.CONSULTA: self.consultar_eventos,
            m.RESERVA: self.reservar,
            m.MODIFICACION: self.modificar,
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

    def pedir(self, tipo, peticion, datos):
        """Le pide algo a la persistencia con el mismo uuid del cliente, para seguirlo en los logs."""
        return self.persistencia.enviar(m.crear_peticion(tipo, peticion["id_cliente"], datos, peticion["uuid"]))

    # CONSULTA: {"mes": "noviembre"}
    def consultar_eventos(self, peticion):
        # 1. recibir  2. enviar a la persistencia  3. devolver el resultado
        return self.persistencia.enviar(peticion)

    # RESERVA: {"id_evento": "E1", "fecha": "2026/11/01", "n_asientos": 2}
    def reservar(self, peticion):
        datos = peticion.get("datos", {})
        n_asientos = datos.get("n_asientos")
        error = asientos_invalidos(peticion, n_asientos)
        if error:
            return error

        if not peticion.get("reintento"):
            # 2. consultar la disponibilidad en tiempo real
            disponibilidad = self.pedir(m.CONSULTA_DISPONIBILIDAD, peticion,
                                        {"id_evento": datos.get("id_evento"), "fecha": datos.get("fecha")})
            if disponibilidad["estado"] != m.EXITO:
                return disponibilidad          # NO_EXISTE o DATO_INVALIDO: ya trae el uuid correcto
            libres = disponibilidad["datos"]["libres"]
            if libres < n_asientos:
                return m.crear_respuesta(peticion, m.FALLO, m.SIN_CUPO,
                                         {"razon": f"hay {libres} puestos libres, se pidieron {n_asientos}"})

        # 3. confirmar. La persistencia vuelve a verificar el cupo en una sola
        #    instruccion: otro cliente pudo reservar entre el paso 2 y este.
        # 4. responder lo que diga la persistencia (EXITO o FALLO SIN_CUPO)
        return self.pedir(m.AGREGAR_RESERVA, peticion, datos)

    # MODIFICACION: {"id_reserva": 3, "n_asientos": 5}  o  {"id_reserva": 3, "fecha": "2026/11/15"}
    def modificar(self, peticion):
        datos = peticion.get("datos", {})
        cambia_fecha = "fecha" in datos
        if not cambia_fecha:
            n_asientos = datos.get("n_asientos")
            error = asientos_invalidos(peticion, n_asientos)
            if error:
                return error

        if not peticion.get("reintento"):
            # 1. buscar la reserva
            reserva = self.pedir(m.CONSULTAR_RESERVA, peticion, {"id_reserva": datos.get("id_reserva")})
            if reserva["estado"] != m.EXITO:
                return reserva                 # NO_EXISTE o DATO_INVALIDO
            actual = reserva["datos"]

            # 2. consultar la disponibilidad: en la nueva fecha, o de mas asientos en la misma
            fecha = datos["fecha"] if cambia_fecha else actual["fecha"]
            faltan = actual["n_asientos"] if cambia_fecha else n_asientos - actual["n_asientos"]
            if faltan > 0:
                disponibilidad = self.pedir(m.CONSULTA_DISPONIBILIDAD, peticion,
                                            {"id_evento": actual["id_evento"], "fecha": fecha})
                if disponibilidad["estado"] != m.EXITO:
                    return disponibilidad      # la nueva fecha no existe (evento de una sola ocurrencia)
                libres = disponibilidad["datos"]["libres"]
                if libres < faltan:
                    return m.crear_respuesta(peticion, m.FALLO, m.SIN_CUPO,
                                             {"razon": f"hay {libres} puestos libres, se necesitan {faltan}"})

        # 3. aplicar el cambio. La persistencia vuelve a verificar el cupo en la misma transaccion;
        #    si no se puede, no cambia nada y el cliente queda como estaba.
        # 4. responder lo que diga la persistencia (EXITO o FALLO)
        return self.pedir(m.MODIFICAR_RESERVA, peticion, datos)
