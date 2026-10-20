# El stock de cada producto en cada ubicación (CD o local) y los MovimientoStock
# que registran cada entrada/salida. Acá van reglas tipo "no puede quedar negativo".
# Acá NO se guarda nada en la base: eso lo hace dao_stock.py.
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from backend.dominio.excepciones import DatoInvalido, StockInsuficiente


class TipoMovimiento(Enum):
    # Los valores son el texto que se guarda en la base
    COMPRA = "COMPRA"            # ingresa al CD lo comprado al proveedor
    DESPACHO = "DESPACHO"        # egresa del CD cuando sale el bulto
    RECEPCION = "RECEPCION"      # ingresa al local cuando el bulto se verifica
    VENTA = "VENTA"              # egresa del local al vender
    DEVOLUCION = "DEVOLUCION"    # ingresa al local cuando el cliente devuelve
    AJUSTE = "AJUSTE"            # corrección manual, puede sumar o restar


# Qué tipos de movimiento tienen sentido en cada sentido
TIPOS_DE_INGRESO = {TipoMovimiento.COMPRA, TipoMovimiento.RECEPCION,
                    TipoMovimiento.DEVOLUCION, TipoMovimiento.AJUSTE}
TIPOS_DE_EGRESO = {TipoMovimiento.DESPACHO, TipoMovimiento.VENTA,
                   TipoMovimiento.AJUSTE}


def validar_ubicacion_para(tipo, ubicacion):
    """Cada tipo de movimiento ocurre en un solo tipo de ubicación. Esta regla
    es la que garantiza que a una sucursal solo entre stock vendible por
    RECEPCION de un bulto verificado (o por DEVOLUCION de algo vendido ahí):
    una COMPRA directa a un local saltearía todo el circuito del bulto.
    El AJUSTE (corrección manual) vale en cualquier ubicación."""
    if not ubicacion.activo:
        raise DatoInvalido(f"La ubicación '{ubicacion.nombre}' está dada de baja")
    if tipo in (TipoMovimiento.COMPRA, TipoMovimiento.DESPACHO) and not ubicacion.puede_despachar():
        raise DatoInvalido(f"El movimiento {tipo.value} solo puede hacerse en el Centro de Distribución")
    if tipo == TipoMovimiento.RECEPCION and not ubicacion.puede_recibir():
        raise DatoInvalido("Solo una sucursal puede recibir bultos")
    if tipo in (TipoMovimiento.VENTA, TipoMovimiento.DEVOLUCION) and not ubicacion.puede_vender():
        raise DatoInvalido(f"El movimiento {tipo.value} solo puede hacerse en una sucursal")


@dataclass(frozen=True)
class MovimientoStock:
    """Un registro del libro de movimientos. Es inmutable (frozen): una vez
    creado no se modifica. La cantidad lleva signo: positiva si entra
    mercadería, negativa si sale."""
    fecha: datetime
    cantidad: int
    tipo: TipoMovimiento
    referencia: str = ""


def _validar_entero(valor, nombre, minimo):
    # bool es subclase de int en Python, por eso se lo excluye aparte
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise DatoInvalido(f"{nombre} tiene que ser un número entero")
    if valor < minimo:
        raise DatoInvalido(f"{nombre} no puede ser menor a {minimo}")
    return valor


class Stock:
    """Cantidad de un producto en una ubicación. La cantidad nunca se pisa a
    mano: solo cambia con ingresar() y egresar(), y cada cambio deja un
    MovimientoStock."""

    def __init__(self, producto, ubicacion, stock_minimo=0, cantidad=0, id=None):
        self.id = id
        self.producto = producto
        self.ubicacion = ubicacion
        self.stock_minimo = stock_minimo
        # Un stock nuevo arranca en 0. El parámetro cantidad existe para que el
        # DAO pueda reconstruir un stock que ya estaba guardado en la base.
        self._cantidad = _validar_entero(cantidad, "La cantidad inicial", 0)
        self._movimientos = []

    @property
    def cantidad(self):
        return self._cantidad

    @property
    def stock_minimo(self):
        return self._stock_minimo

    @stock_minimo.setter
    def stock_minimo(self, valor):
        self._stock_minimo = _validar_entero(valor, "El stock mínimo", 0)

    @property
    def movimientos(self):
        # Tupla: desde afuera no se puede agregar, quitar ni reemplazar nada
        return tuple(self._movimientos)

    def esta_bajo_minimo(self):
        return self._cantidad < self._stock_minimo

    def ingresar(self, cantidad, tipo, referencia=""):
        self._validar_movimiento(cantidad, tipo, TIPOS_DE_INGRESO, "ingreso")
        self._registrar(cantidad, tipo, referencia)

    def egresar(self, cantidad, tipo, referencia=""):
        self._validar_movimiento(cantidad, tipo, TIPOS_DE_EGRESO, "egreso")
        if cantidad > self._cantidad:
            raise StockInsuficiente(
                f"Stock insuficiente: hay {self._cantidad} y se piden {cantidad}"
            )
        self._registrar(-cantidad, tipo, referencia)

    def _validar_movimiento(self, cantidad, tipo, tipos_validos, sentido):
        # Primero se valida todo, después se modifica el stock
        _validar_entero(cantidad, "La cantidad", 1)
        if not isinstance(tipo, TipoMovimiento):
            raise DatoInvalido("El tipo de movimiento no es válido")
        if tipo not in tipos_validos:
            raise DatoInvalido(f"El tipo {tipo.value} no corresponde a un {sentido}")

    def _registrar(self, cantidad_con_signo, tipo, referencia):
        self._movimientos.append(MovimientoStock(
            datetime.now(), cantidad_con_signo, tipo, (referencia or "").strip()
        ))
        self._cantidad += cantidad_con_signo

    def __str__(self):
        return f"Stock: producto {self.producto}, ubicación {self.ubicacion}, cantidad {self._cantidad}"