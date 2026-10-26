# Endpoints de ventas: registrar ventas, cobros, comprobantes y devoluciones.
# Llaman a ventas_service.
# Permisos: vende, cotiza y devuelve un local, siempre en SU local (sale del
# usuario, nunca del formulario). Las ventas, la caja y los comprobantes los ve
# quien tiene ve_ventas (el local, solo los suyos; el administrador, todos).
# El CD no: solo abastece.
# Acá NO va lógica de negocio ni acceso a la base.
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel

from backend.api.dependencias import LOGUEADO, exigir_que_sea_suyo, requiere, ubicacion_para_filtrar
from backend.servicios.comprobantes_service import ComprobantesService
from backend.servicios.ventas_service import VentasService

router = APIRouter(prefix="/ventas", tags=["Ventas"])
service = VentasService()

VE_VENTAS = Depends(requiere("ve_ventas"))


# Forma del JSON que llega (POST)
class ItemEntrada(BaseModel):
    producto_id: int
    cantidad: int


class VentaEntrada(BaseModel):
    items: list[ItemEntrada]                 # el local es el del usuario que vende
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
    nota_credito: str | None   # número de la nota de crédito (ej: 0002-00000001)
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
        nota_credito=devolucion.nota_credito.codigo if devolucion.nota_credito else None,
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
@router.get("/medios-pago", response_model=list[MedioPagoSalida], dependencies=[LOGUEADO])
def listar_medios_pago():
    return [MedioPagoSalida(nombre=m.nombre, porcentaje_ajuste=m.porcentaje_ajuste) for m in service.medios_pago()]


@router.get("", response_model=list[VentaSalida])
def listar_ventas(sucursal_id: int | None = None, desde: date | None = None, hasta: date | None = None,
                  usuario=VE_VENTAS):
    sucursal_id = ubicacion_para_filtrar(usuario, sucursal_id)
    return [venta_a_salida(v) for v in service.listar(sucursal_id, desde, hasta)]


@router.get("/{id}", response_model=VentaSalida)
def obtener_venta(id: int, usuario=VE_VENTAS):
    venta = service.obtener(id)
    exigir_que_sea_suyo(usuario, venta.sucursal_id, "Esa venta")
    return venta_a_salida(venta)


class LineaCotizacionSalida(BaseModel):
    producto_id: int
    cantidad: int
    precio_unitario: float
    subtotal: float
    disponible: int     # cuánto hay en el local
    alcanza: bool       # si el stock alcanza para esta línea


class CotizacionSalida(BaseModel):
    subtotal: float          # precio de lista
    medio_pago: str
    porcentaje_ajuste: float
    total: float             # lo que se cobraría, con el descuento o recargo
    vuelto: float
    alcanza_pago: bool       # en efectivo: si el monto entregado cubre el total
    hay_stock: bool          # si alcanzan todas las líneas
    lineas: list[LineaCotizacionSalida]


# Lo que costaría la venta, para mostrarlo antes de confirmar. No guarda nada.
@router.post("/cotizar", response_model=CotizacionSalida)
def cotizar_venta(datos: VentaEntrada, usuario=Depends(requiere("puede_vender"))):
    venta, disponible, alcanza_pago = service.cotizar(
        usuario.ubicacion_id, a_pares(datos.items), datos.medio_pago, datos.monto_entregado,
    )
    lineas = [
        LineaCotizacionSalida(producto_id=d.producto_id, cantidad=d.cantidad, precio_unitario=d.precio_unitario,
                              subtotal=d.subtotal, disponible=disponible[d.producto_id],
                              alcanza=d.cantidad <= disponible[d.producto_id])
        for d in venta.detalles
    ]
    return CotizacionSalida(
        subtotal=venta.subtotal, medio_pago=venta.pago.medio.nombre, porcentaje_ajuste=venta.pago.porcentaje_ajuste,
        total=venta.total, vuelto=venta.pago.vuelto, alcanza_pago=alcanza_pago,
        hay_stock=all(linea.alcanza for linea in lineas), lineas=lineas,
    )


@router.post("", response_model=VentaSalida, status_code=201)
def registrar_venta(datos: VentaEntrada, usuario=Depends(requiere("puede_vender"))):
    venta = service.vender(usuario.ubicacion_id, a_pares(datos.items), datos.medio_pago, datos.monto_entregado,
                           usuario.id)
    return venta_a_salida(venta)


@router.post("/{id}/devoluciones", response_model=DevolucionSalida, status_code=201)
def registrar_devolucion(id: int, datos: DevolucionEntrada, usuario=Depends(requiere("puede_vender"))):
    exigir_que_sea_suyo(usuario, service.obtener(id).sucursal_id, "Esa venta")
    return devolucion_a_salida(service.devolver(id, a_pares(datos.items), datos.motivo, usuario.id))


# ------------------------------------------------- Documentos en PDF
# Los descarga quien puede ver la venta: el local que la hizo, o quien ve toda
# la red. Qué dice cada documento lo arma el dominio (Template Method).
comprobantes = ComprobantesService()


def pdf(nombre_archivo, contenido):
    return Response(content=contenido, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'})


@router.get("/{id}/comprobante.pdf", response_class=Response)
def descargar_comprobante(id: int, usuario=VE_VENTAS):
    venta = comprobantes.obtener_venta(id)
    exigir_que_sea_suyo(usuario, venta.sucursal_id, "Esa venta")
    return pdf(*comprobantes.comprobante_de_venta(venta))


@router.get("/{id}/devoluciones/{devolucion_id}/nota-credito.pdf", response_class=Response)
def descargar_nota_de_credito(id: int, devolucion_id: int, usuario=VE_VENTAS):
    venta = comprobantes.obtener_venta(id)
    exigir_que_sea_suyo(usuario, venta.sucursal_id, "Esa venta")
    return pdf(*comprobantes.nota_de_credito(venta, devolucion_id))


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
def ver_caja(sucursal_id: int, desde: date | None = None, hasta: date | None = None, usuario=VE_VENTAS):
    exigir_que_sea_suyo(usuario, sucursal_id, "Esa caja")
    movimientos, por_medio = service.caja(sucursal_id, desde, hasta)
    return CajaSalida(
        sucursal_id=sucursal_id,
        movimientos=[MovimientoCajaSalida(fecha=m.fecha, tipo=m.tipo, medio_pago=m.medio_pago,
                                          importe=m.importe, referencia=m.referencia) for m in movimientos],
        por_medio=por_medio,
        saldo=sum(por_medio.values()),
    )
