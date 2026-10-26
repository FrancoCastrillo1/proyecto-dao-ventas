# Endpoints de stock: consultar existencias por ubicación y cargar compras al CD.
# Los egresos no tienen endpoint propio: los hacen el despacho y la venta.
# Permisos: el stock de una ubicación lo ve quien ve toda la red o ese mismo
# local; las compras las registra el CD, y entran a SU ubicación.
# Llaman a stock_service y nada más; los errores del negocio los traduce main.py.
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.api.dependencias import exigir_que_sea_suyo, requiere, usuario_actual
from backend.dominio.stock import TipoMovimiento
from backend.servicios.stock_service import StockService

router = APIRouter(prefix="/stock", tags=["Stock"])
service = StockService()


class CompraEntrada(BaseModel):
    producto_id: int   # entra al CD del usuario que compra
    cantidad: int
    referencia: str = ""


class StockSalida(BaseModel):
    producto_id: int
    ubicacion_id: int
    cantidad: int
    stock_minimo: int
    bajo_minimo: bool


class ExistenciaSalida(StockSalida):
    codigo: str
    nombre: str


class MovimientoSalida(BaseModel):
    fecha: datetime
    cantidad: int
    tipo: str
    referencia: str


def a_salida(stock):
    return StockSalida(producto_id=stock.producto, ubicacion_id=stock.ubicacion, cantidad=stock.cantidad,
                       stock_minimo=stock.stock_minimo, bajo_minimo=stock.esta_bajo_minimo())


@router.get("/{ubicacion_id}", response_model=list[ExistenciaSalida])
def listar_existencias(ubicacion_id: int, usuario=Depends(usuario_actual)):
    exigir_que_sea_suyo(usuario, ubicacion_id, "Ese stock")
    return [
        ExistenciaSalida(**a_salida(stock).model_dump(), codigo=producto.codigo, nombre=producto.nombre)
        for producto, stock in service.listar_por_ubicacion(ubicacion_id)
    ]


@router.get("/{ubicacion_id}/{producto_id}", response_model=StockSalida)
def obtener_stock(ubicacion_id: int, producto_id: int, usuario=Depends(usuario_actual)):
    exigir_que_sea_suyo(usuario, ubicacion_id, "Ese stock")
    return a_salida(service.obtener(ubicacion_id, producto_id))


@router.get("/{ubicacion_id}/{producto_id}/movimientos", response_model=list[MovimientoSalida])
def listar_movimientos(ubicacion_id: int, producto_id: int, usuario=Depends(usuario_actual)):
    exigir_que_sea_suyo(usuario, ubicacion_id, "Ese stock")
    return [
        MovimientoSalida(fecha=m.fecha, cantidad=m.cantidad, tipo=m.tipo.value, referencia=m.referencia)
        for m in service.listar_movimientos(ubicacion_id, producto_id)
    ]


# Compra al proveedor: la mercadería entra al Centro de Distribución.
# A una sucursal solo le entra stock por recepción de un bulto verificado.
@router.post("/ingresar", response_model=StockSalida, status_code=201)
def registrar_compra(datos: CompraEntrada, usuario=Depends(requiere("puede_comprar"))):
    stock = service.ingresar(usuario.ubicacion_id, datos.producto_id, datos.cantidad,
                             TipoMovimiento.COMPRA, datos.referencia, usuario_id=usuario.id)
    return a_salida(stock)
