# Manejo del dinero en ventas y caja: siempre Decimal con 2 decimales, nunca
# float. Con float, 0.1 + 0.2 da 0.30000000000000004 y los descuentos y
# recargos terminan dejando diferencias de centavos.
# Acá NO va ninguna regla de ventas, solo cómo se representa un monto.
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from backend.dominio.excepciones import DatoInvalido

CENTAVO = Decimal("0.01")
CERO = Decimal("0.00")


def redondear(monto):
    # Redondeo comercial: 0.005 sube a 0.01 (Decimal por defecto redondea "al par")
    return monto.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def a_dinero(valor, campo="monto"):
    """Convierte lo que llega (Decimal, int, float o texto) a un monto con 2
    decimales. El float se pasa por str() para no arrastrar su error:
    Decimal(0.1) es 0.1000000000000000055..., Decimal("0.1") es 0.1."""
    if isinstance(valor, bool) or valor is None:
        raise DatoInvalido(f"El {campo} tiene que ser un número")
    try:
        monto = Decimal(str(valor).strip())
    except InvalidOperation:
        raise DatoInvalido(f"El {campo} tiene que ser un número")
    if not monto.is_finite():
        raise DatoInvalido(f"El {campo} tiene que ser un número")
    return redondear(monto)


def aplicar_porcentaje(monto, porcentaje):
    # porcentaje -15 → descuento del 15%; +10 → recargo del 10%
    return redondear(monto * (100 + porcentaje) / 100)
