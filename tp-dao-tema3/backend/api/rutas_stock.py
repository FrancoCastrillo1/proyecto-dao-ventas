from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from backend.servicios.stock_service import StockService
from backend.dominio.stock import TipoMovimiento

router = APIRouter(prefix="/stock", tags=["Stock"])
service = StockService()

class StockIngresoDTO(BaseModel):
    ubicacion_id: int
    producto_id: int
    cantidad: int
    referencia: str

@router.get("/{ubicacion_id}/{producto_id}")
def obtener_stock(ubicacion_id: int, producto_id: int):
    resultado = service.obtener_stock_ubicacion(ubicacion_id, producto_id)
    if not resultado:
        raise HTTPException(status_code=404, detail="No se encontró registro de stock para esta ubicación y producto.")
    return resultado

@router.post("/ingresar", status_code=status.HTTP_201_CREATED)
def ingresar_stock_endpoint(datos: StockIngresoDTO):
    try:
        service.ingresar_stock(
            ubicacion_id=datos.ubicacion_id,
            producto_id=datos.producto_id,
            cantidad=datos.cantidad,
            tipo=TipoMovimiento.COMPRA,
            referencia=datos.referencia
        )
        return {"mensaje": "Stock ingresado exitosamente"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))