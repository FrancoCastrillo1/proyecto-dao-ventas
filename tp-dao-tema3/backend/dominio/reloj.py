# La hora "de ahora" para el dominio: cuándo se hace un pedido, cuándo cambia
# de estado un bulto, cuándo se mueve el stock. Todo el dominio la pide acá en
# vez de llamar a datetime.now(), así hay un solo lugar que dice qué hora es.
#
# Normalmente es la hora real. Solo el seed la fija en el pasado mientras carga
# el historial de prueba (con a_las), para que los pedidos, los envíos y las
# ventas de prueba queden con su fecha y pasen igual por todas las reglas. La
# api nunca la toca: una operación real lleva la hora en que se hace.
# Acá NO va nada de base de datos ni de cómo se muestran las fechas.
from contextlib import contextmanager
from datetime import datetime


class Reloj:
    fijo = None          # un datetime mientras está detenido (solo en el seed); si no, None

    @classmethod
    def ahora(cls):
        return cls.fijo if cls.fijo is not None else datetime.now()


def ahora():
    return Reloj.ahora()


@contextmanager
def a_las(momento):
    """Mientras dure el with, "ahora" es momento. Al salir vuelve a lo que era
    (la hora real, salvo que hubiera otro a_las afuera)."""
    anterior = Reloj.fijo
    Reloj.fijo = momento
    try:
        yield
    finally:
        Reloj.fijo = anterior
