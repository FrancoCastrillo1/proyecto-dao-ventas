# Lo de ventas en el local: Venta, DetalleVenta, Pago, Comprobante y Devolucion,
# con reglas como calcular totales o validar que lo devuelto se haya vendido.
# Los medios de pago concretos NO van acá, van en medios_pago.py (patrón Strategy).
from dataclasses import dataclass
from datetime import datetime, timedelta

from backend.dominio.dinero import CERO, a_dinero, aplicar_porcentaje
from backend.dominio.excepciones import DatoInvalido, TransicionDeEstadoInvalida

# Regla del negocio definida por el grupo: pasado este plazo no se aceptan devoluciones
PLAZO_DEVOLUCION_DIAS = 30


def ahora():
    # Sin microsegundos: es la precisión con la que se guarda en la base, así
    # una venta leída de la base es igual a la que se guardó
    return datetime.now().replace(microsecond=0)


def _validar_cantidad(cantidad):
    # bool es subclase de int en Python, por eso se lo excluye aparte
    if isinstance(cantidad, bool) or not isinstance(cantidad, int):
        raise DatoInvalido("La cantidad tiene que ser un número entero")
    if cantidad < 1:
        raise DatoInvalido("La cantidad tiene que ser al menos 1")


@dataclass(frozen=True)
class DetalleVenta:
    """Una línea de la venta. Guarda el precio y el costo DEL MOMENTO de la
    venta: si mañana cambia el precio del producto, esta venta no cambia (y
    el margen y las devoluciones se calculan con lo que realmente se cobró)."""
    producto_id: int
    cantidad: int
    precio_unitario: object
    costo_unitario: object

    def __post_init__(self):
        _validar_cantidad(self.cantidad)
        precio = a_dinero(self.precio_unitario, "precio unitario")
        costo = a_dinero(self.costo_unitario, "costo unitario")
        if precio <= 0:
            raise DatoInvalido("El precio unitario tiene que ser mayor a 0")
        if costo < 0:
            raise DatoInvalido("El costo unitario no puede ser negativo")
        # frozen no deja asignar con "=": así se guarda el valor ya convertido
        object.__setattr__(self, "precio_unitario", precio)
        object.__setattr__(self, "costo_unitario", costo)

    @property
    def subtotal(self):
        return self.precio_unitario * self.cantidad

    @property
    def costo_total(self):
        return self.costo_unitario * self.cantidad


@dataclass(frozen=True)
class Pago:
    """El cobro de la venta. Guarda el porcentaje que se aplicó en ese momento:
    si después cambia el descuento del efectivo, esta venta no cambia."""
    medio: object               # una estrategia de medios_pago.py
    porcentaje_ajuste: object   # Decimal
    monto: object               # Decimal: lo que se cobró, ya con el ajuste
    vuelto: object = CERO


@dataclass(frozen=True)
class Comprobante:
    """Ticket de la venta. Se numera correlativo por sucursal (punto de venta),
    como un comprobante real: 0002-00000015."""
    punto_venta: int
    numero: int
    fecha: datetime

    @property
    def codigo(self):
        return f"{self.punto_venta:04d}-{self.numero:08d}"


@dataclass(frozen=True)
class MovimientoCaja:
    """Entrada (venta) o salida (devolución) de dinero de la caja de un local.
    Como el libro de stock: solo se agregan registros, el importe lleva signo."""
    fecha: datetime
    sucursal_id: int
    tipo: str        # "VENTA" o "DEVOLUCION"
    medio_pago: str
    importe: object  # Decimal, positivo entra y negativo sale
    referencia: str = ""


class Venta:
    """Una venta en un local. Se arma en tres pasos, en este orden:
    agregar_item() → cobrar() → emitir_comprobante(). Una vez cobrada ya no
    se puede modificar."""

    # Los parámetros detalles, pago, comprobante y devoluciones existen para que
    # el DAO pueda reconstruir una venta guardada; una venta nueva arranca vacía.
    def __init__(self, sucursal_id, fecha=None, id=None, detalles=(), pago=None, comprobante=None, devoluciones=()):
        self.id = id
        self.sucursal_id = sucursal_id
        self.fecha = fecha or ahora()
        self._detalles = list(detalles)
        self._pago = pago
        self._comprobante = comprobante
        self._devoluciones = list(devoluciones)

    # Solo lectura desde afuera: se cambian con los métodos de abajo
    @property
    def detalles(self):
        return tuple(self._detalles)

    @property
    def pago(self):
        return self._pago

    @property
    def comprobante(self):
        return self._comprobante

    @property
    def devoluciones(self):
        return tuple(self._devoluciones)

    def esta_cobrada(self):
        return self._pago is not None

    def _validar_sin_cobrar(self, accion):
        if self.esta_cobrada():
            raise TransicionDeEstadoInvalida(f"No se puede {accion} una venta ya cobrada")

    def agregar_item(self, producto, cantidad):
        """Recibe el Producto (no el id) para copiar su precio y su costo."""
        self._validar_sin_cobrar("modificar")
        if not producto.activo:
            raise DatoInvalido(f"El producto '{producto.nombre}' está dado de baja: no se puede vender")
        _validar_cantidad(cantidad)
        for i, detalle in enumerate(self._detalles):
            # El mismo producto dos veces suma a la misma línea
            if detalle.producto_id == producto.id:
                self._detalles[i] = DetalleVenta(producto.id, detalle.cantidad + cantidad,
                                                 detalle.precio_unitario, detalle.costo_unitario)
                return
        self._detalles.append(DetalleVenta(producto.id, cantidad, producto.precio_venta, producto.costo))

    @property
    def subtotal(self):
        # Precio de lista, antes del descuento o recargo del medio de pago
        return sum((d.subtotal for d in self._detalles), CERO)

    @property
    def costo_total(self):
        return sum((d.costo_total for d in self._detalles), CERO)

    @property
    def total(self):
        # Lo que se cobró: solo existe una vez cobrada
        return self._pago.monto if self._pago else None

    @property
    def ganancia(self):
        # Puede ser negativa: con el descuento del efectivo se puede vender bajo costo
        return self.total - self.costo_total if self._pago else None

    def cobrar(self, medio, monto_entregado=None):
        """Patrón Strategy: la venta no sabe qué medio es, le delega el cálculo
        del total y del vuelto."""
        self._validar_sin_cobrar("cobrar")
        if not self._detalles:
            raise DatoInvalido("No se puede cobrar una venta sin productos")
        total = medio.calcular_total(self.subtotal)
        vuelto = medio.calcular_vuelto(total, monto_entregado)
        self._pago = Pago(medio, medio.porcentaje_ajuste, total, vuelto)

    def emitir_comprobante(self, numero):
        if not self.esta_cobrada():
            raise TransicionDeEstadoInvalida("No se puede emitir el comprobante de una venta sin cobrar")
        if self._comprobante is not None:
            raise TransicionDeEstadoInvalida("La venta ya tiene comprobante")
        _validar_cantidad(numero)
        # El ticket lleva la fecha de la venta
        self._comprobante = Comprobante(self.sucursal_id, numero, self.fecha)

    def referencia(self):
        # Cómo se nombra la venta en los movimientos de stock y caja
        return f"Venta {self._comprobante.codigo}" if self._comprobante else f"Venta {self.id}"

    def movimiento_caja(self):
        if not self.esta_cobrada():
            raise TransicionDeEstadoInvalida("Una venta sin cobrar no mueve la caja")
        return MovimientoCaja(self.fecha, self.sucursal_id, "VENTA", self._pago.medio.nombre,
                              self._pago.monto, self.referencia())

    # ------------------------------------------------------------ Devoluciones

    def cantidad_vendida(self, producto_id):
        return sum(d.cantidad for d in self._detalles if d.producto_id == producto_id)

    def cantidad_devuelta(self, producto_id):
        return sum(d.cantidad for dev in self._devoluciones for d in dev.detalles if d.producto_id == producto_id)

    def cantidad_devolvible(self, producto_id):
        return self.cantidad_vendida(producto_id) - self.cantidad_devuelta(producto_id)

    @property
    def total_reintegrado(self):
        return sum((dev.importe for dev in self._devoluciones), CERO)

    def devolver(self, items, motivo, fecha=None):
        """items: pares (producto_id, cantidad). Valida todo antes de crear la
        devolución: si un ítem no cumple, no se devuelve nada.
        Se reintegra lo que realmente se cobró: si se pagó en efectivo con 15%
        de descuento, devolver un producto de $1000 reintegra $850."""
        fecha = fecha or ahora()
        motivo = (motivo or "").strip()
        if not self.esta_cobrada():
            raise TransicionDeEstadoInvalida("No se puede devolver una venta que no se cobró")
        if not motivo:
            raise DatoInvalido("La devolución tiene que indicar el motivo")
        if len(motivo) > 200:
            raise DatoInvalido("El motivo no puede tener más de 200 caracteres")
        if fecha - self.fecha > timedelta(days=PLAZO_DEVOLUCION_DIAS):
            raise DatoInvalido(f"Venció el plazo de {PLAZO_DEVOLUCION_DIAS} días para devolver esta venta")

        # El mismo producto dos veces en el pedido de devolución suma
        pedidas = {}
        for producto_id, cantidad in items:
            _validar_cantidad(cantidad)
            pedidas[producto_id] = pedidas.get(producto_id, 0) + cantidad
        if not pedidas:
            raise DatoInvalido("La devolución tiene que tener al menos un producto")

        detalles = []
        for producto_id, cantidad in pedidas.items():
            if self.cantidad_vendida(producto_id) == 0:
                raise DatoInvalido(f"El producto {producto_id} no está en esta venta")
            devolvible = self.cantidad_devolvible(producto_id)
            if cantidad > devolvible:
                raise DatoInvalido(
                    f"Del producto {producto_id} se pueden devolver {devolvible} unidades y se piden {cantidad}"
                )
            precio = next(d.precio_unitario for d in self._detalles if d.producto_id == producto_id)
            importe = aplicar_porcentaje(precio * cantidad, self._pago.porcentaje_ajuste)
            detalles.append(DetalleDevolucion(producto_id, cantidad, importe))

        # Por el redondeo de cada línea, la suma de varias devoluciones puede
        # pasarse por un centavo de lo cobrado (ej. 3 x $0.10 en efectivo se
        # cobra $0.26, pero cada unidad reintegra $0.09). Nunca se reintegra
        # más de lo que entró a la caja.
        exceso = self.total_reintegrado + sum(d.importe for d in detalles) - self._pago.monto
        if exceso > 0:
            ultimo = detalles[-1]
            detalles[-1] = DetalleDevolucion(ultimo.producto_id, ultimo.cantidad, ultimo.importe - exceso)

        devolucion = Devolucion(self.id, self.sucursal_id, self._pago.medio.nombre, motivo, detalles, fecha)
        self._devoluciones.append(devolucion)
        return devolucion

    def __str__(self):
        return f"Venta {self.id}: sucursal {self.sucursal_id}, {len(self._detalles)} productos, total {self.total}"


@dataclass(frozen=True)
class DetalleDevolucion:
    producto_id: int
    cantidad: int
    importe: object  # Decimal: lo que se reintegra por esta línea


class Devolucion:
    """Lo que el cliente devuelve de UNA venta registrada. No se crea suelta:
    la arma Venta.devolver(), que valida contra lo vendido."""

    def __init__(self, venta_id, sucursal_id, medio_pago, motivo, detalles, fecha=None, id=None):
        self.id = id
        self.venta_id = venta_id
        self.sucursal_id = sucursal_id
        self.medio_pago = medio_pago  # se reintegra por el mismo medio con que se cobró
        self.motivo = motivo
        self.detalles = tuple(detalles)
        self.fecha = fecha or ahora()

    @property
    def importe(self):
        return sum((d.importe for d in self.detalles), CERO)

    def movimiento_caja(self):
        # Salida de dinero: el importe va en negativo
        return MovimientoCaja(self.fecha, self.sucursal_id, "DEVOLUCION", self.medio_pago, -self.importe,
                              f"Devolución {self.id} de la venta {self.venta_id}")
