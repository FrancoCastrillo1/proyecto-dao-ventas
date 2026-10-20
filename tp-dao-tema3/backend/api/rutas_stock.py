# Endpoints de stock: consultar existencias por ubicación y cargar compras al CD.
# Los egresos no tienen endpoint propio: los hacen el despacho y la venta.
# Llaman a stock_service y nada más; los errores del negocio los traduce main.py.
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from backend.dominio.stock import TipoMovimiento
from backend.servicios.stock_service import StockService

router = APIRouter(prefix="/stock", tags=["Stock"])
service = StockService()


class CompraEntrada(BaseModel):
    ubicacion_id: int
    producto_id: int
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
def listar_existencias(ubicacion_id: int):
    return [
        ExistenciaSalida(**a_salida(stock).model_dump(), codigo=producto.codigo, nombre=producto.nombre)
        for producto, stock in service.listar_por_ubicacion(ubicacion_id)
    ]


@router.get("/{ubicacion_id}/{producto_id}", response_model=StockSalida)
def obtener_stock(ubicacion_id: int, producto_id: int):
    return a_salida(service.obtener(ubicacion_id, producto_id))


@router.get("/{ubicacion_id}/{producto_id}/movimientos", response_model=list[MovimientoSalida])
def listar_movimientos(ubicacion_id: int, producto_id: int):
    return [
        MovimientoSalida(fecha=m.fecha, cantidad=m.cantidad, tipo=m.tipo.value, referencia=m.referencia)
        for m in service.listar_movimientos(ubicacion_id, producto_id)
    ]


# Compra al proveedor: la mercadería entra al Centro de Distribución.
# A una sucursal solo le entra stock por recepción de un bulto verificado.
@router.post("/ingresar", response_model=StockSalida, status_code=201)
def registrar_compra(datos: CompraEntrada):
    stock = service.ingresar(datos.ubicacion_id, datos.producto_id, datos.cantidad,
                             TipoMovimiento.COMPRA, datos.referencia)
    return a_salida(stock)
