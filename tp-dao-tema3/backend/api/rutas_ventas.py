# Endpoints de ventas: registrar ventas, cobros, comprobantes y devoluciones.
# Llaman a ventas_service.
# Acá NO va lógica de negocio ni acceso a la base.
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel

from backend.servicios.ventas_service import VentasService

router = APIRouter(prefix="/ventas", tags=["Ventas"])
service = VentasService()


# Forma del JSON que llega (POST)
class ItemEntrada(BaseModel):
    producto_id: int
    cantidad: int


class VentaEntrada(BaseModel):
    sucursal_id: int
    items: list[ItemEntrada]
    medio_pago: str                          # EFECTIVO, DEBITO, TRANSFERENCIA o CREDITO
    monto_entregado: Decimal | None = None   # solo para efectivo: calcula el vuelto


class DevolucionEntrada(BaseModel):
    items: list[ItemEntrada]
    motivo: str


# Forma del JSON que sale. Los montos salen como número (igual que los
# precios de productos); adentro del sistema siempre son Decimal.
class MedioPagoSalida(BaseModel):
    nombre: str
    porcentaje_ajuste: float


class DetalleVentaSalida(BaseModel):
    producto_id: int
    cantidad: int
    precio_unitario: float
    subtotal: float


class DetalleDevolucionSalida(BaseModel):
    producto_id: int
    cantidad: int
    importe: float


class DevolucionSalida(BaseModel):
    id: int
    venta_id: int
    fecha: datetime
    motivo: str
    medio_pago: str
    importe: float
    detalles: list[DetalleDevolucionSalida]


class VentaSalida(BaseModel):
    id: int
    sucursal_id: int
    fecha: datetime
    comprobante: str
    medio_pago: str
    porcentaje_ajuste: float
    subtotal: float          # precio de lista
    total: float             # lo cobrado, con el descuento o recargo
    vuelto: float
    detalles: list[DetalleVentaSalida]
    devoluciones: list[DevolucionSalida]
    total_reintegrado: float


def devolucion_a_salida(devolucion):
    return DevolucionSalida(
        id=devolucion.id, venta_id=devolucion.venta_id, fecha=devolucion.fecha, motivo=devolucion.motivo,
        medio_pago=devolucion.medio_pago, importe=devolucion.importe,
        detalles=[DetalleDevolucionSalida(producto_id=d.producto_id, cantidad=d.cantidad, importe=d.importe)
                  for d in devolucion.detalles],
    )


def venta_a_salida(venta):
    return VentaSalida(
        id=venta.id, sucursal_id=venta.sucursal_id, fecha=venta.fecha, comprobante=venta.comprobante.codigo,
        medio_pago=venta.pago.medio.nombre, porcentaje_ajuste=venta.pago.porcentaje_ajuste,
        subtotal=venta.subtotal, total=venta.total, vuelto=venta.pago.vuelto,
        detalles=[DetalleVentaSalida(producto_id=d.producto_id, cantidad=d.cantidad,
                                     precio_unitario=d.precio_unitario, subtotal=d.subtotal)
                  for d in venta.detalles],
        devoluciones=[devolucion_a_salida(d) for d in venta.devoluciones],
        total_reintegrado=venta.total_reintegrado,
    )


def a_pares(items):
    return [(item.producto_id, item.cantidad) for item in items]


# Tiene que ir antes que "/{id}": si no, FastAPI intenta leer "medios-pago" como un id
@router.get("/medios-pago", response_model=list[MedioPagoSalida])
def listar_medios_pago():
    return [MedioPagoSalida(nombre=m.nombre, porcentaje_ajuste=m.porcentaje_ajuste) for m in service.medios_pago()]


@router.get("", response_model=list[VentaSalida])
def listar_ventas(sucursal_id: int | None = None, desde: date | None = None, hasta: date | None = None):
    return [venta_a_salida(v) for v in service.listar(sucursal_id, desde, hasta)]


@router.get("/{id}", response_model=VentaSalida)
def obtener_venta(id: int):
    return venta_a_salida(service.obtener(id))


@router.post("", response_model=VentaSalida, status_code=201)
def registrar_venta(datos: VentaEntrada):
    venta = service.vender(datos.sucursal_id, a_pares(datos.items), datos.medio_pago, datos.monto_entregado)
    return venta_a_salida(venta)


@router.post("/{id}/devoluciones", response_model=DevolucionSalida, status_code=201)
def registrar_devolucion(id: int, datos: DevolucionEntrada):
    return devolucion_a_salida(service.devolver(id, a_pares(datos.items), datos.motivo))


# -------------------------------------------------------------------- Caja
router_caja = APIRouter(prefix="/caja", tags=["Caja"])


class MovimientoCajaSalida(BaseModel):
    fecha: datetime
    tipo: str
    medio_pago: str
    importe: float
    referencia: str


class CajaSalida(BaseModel):
    sucursal_id: int
    movimientos: list[MovimientoCajaSalida]
    por_medio: dict[str, float]
    saldo: float


@router_caja.get("/{sucursal_id}", response_model=CajaSalida)
def ver_caja(sucursal_id: int, desde: date | None = None, hasta: date | None = None):
    movimientos, por_medio = service.caja(sucursal_id, desde, hasta)
    return CajaSalida(
        sucursal_id=sucursal_id,
        movimientos=[MovimientoCajaSalida(fecha=m.fecha, tipo=m.tipo, medio_pago=m.medio_pago,
                                          importe=m.importe, referencia=m.referencia) for m in movimientos],
        por_medio=por_medio,
        saldo=sum(por_medio.values()),
    )
