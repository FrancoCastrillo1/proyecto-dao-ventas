# Patrón Strategy para los medios de pago: efectivo, débito, crédito, etc.
# Cada uno con su forma de calcular recargos/descuentos o validar el cobro.
# Acá NO va la Venta ni el Pago en sí (eso está en ventas.py), solo las estrategias.
#
# La Venta no sabe con qué se le paga: le pide el total y el vuelto a la
# estrategia que recibe. Agregar un medio nuevo (ej. MercadoPago) es escribir
# una clase más y sumarla a MEDIOS_PAGO, sin tocar la Venta ni ningún if.
from abc import ABC, abstractmethod
from decimal import Decimal

from backend.dominio.dinero import CERO, a_dinero, aplicar_porcentaje
from backend.dominio.excepciones import DatoInvalido, PagoInsuficiente


class MedioPago(ABC):
    # Lo obligatorio para cada estrategia: cómo se llama (el texto que se
    # guarda en la base) y cuánto ajusta el precio
    @property
    @abstractmethod
    def nombre(self):
        pass

    @property
    @abstractmethod
    def porcentaje_ajuste(self):
        """Decimal: negativo es descuento, positivo es recargo, 0 es precio de lista."""
        pass

    def calcular_total(self, subtotal):
        return aplicar_porcentaje(subtotal, self.porcentaje_ajuste)

    # Por defecto (tarjetas, transferencia) se cobra justo el total: no hay
    # vuelto y lo entregado no se usa
    def calcular_vuelto(self, total, monto_entregado=None):
        return CERO

    def __str__(self):
        return self.nombre


class Efectivo(MedioPago):
    @property
    def nombre(self):
        return "EFECTIVO"

    @property
    def porcentaje_ajuste(self):
        return Decimal("-15")

    # El único medio que valida lo entregado: tiene que alcanzar y se da vuelto.
    # Si no se informa cuánto entregó, se asume que pagó justo.
    def calcular_vuelto(self, total, monto_entregado=None):
        if monto_entregado is None:
            return CERO
        entregado = a_dinero(monto_entregado, "monto entregado")
        if entregado < total:
            raise PagoInsuficiente(f"El monto entregado (${entregado}) no alcanza para pagar ${total}")
        return entregado - total


class Debito(MedioPago):
    @property
    def nombre(self):
        return "DEBITO"

    @property
    def porcentaje_ajuste(self):
        return Decimal("0")


class Transferencia(MedioPago):
    @property
    def nombre(self):
        return "TRANSFERENCIA"

    @property
    def porcentaje_ajuste(self):
        return Decimal("0")


class Credito(MedioPago):
    @property
    def nombre(self):
        return "CREDITO"

    @property
    def porcentaje_ajuste(self):
        return Decimal("10")


# Fábrica simple, igual que TIPOS_UBICACION: el único lugar que sabe qué
# clase corresponde a cada nombre. La usan el service (al vender) y el DAO
# (al leer una venta guardada).
MEDIOS_PAGO = {clase().nombre: clase for clase in (Efectivo, Debito, Transferencia, Credito)}


def crear_medio_pago(nombre):
    clase = MEDIOS_PAGO.get((nombre or "").strip().upper())
    if clase is None:
        raise DatoInvalido(f"Medio de pago '{nombre}' inválido. Opciones: {', '.join(MEDIOS_PAGO)}")
    return clase()
