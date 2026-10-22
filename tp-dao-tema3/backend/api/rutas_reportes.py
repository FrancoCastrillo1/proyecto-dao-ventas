# Endpoints de reportes (ventas por período, más vendidos, existencias, etc.).
# Llaman a reportes_service y nada más. Quien ve toda la red (administrador y
# CD) puede filtrar por cualquier local; un local ve solo los suyos.
# Acá NO va lógica de negocio ni acceso a la base.
#
# Devuelven JSON directo (sin un modelo Pydantic por fila): son vistas de solo
# lectura con muchas columnas, y FastAPI ya convierte Decimal y fechas.
from datetime import date

from fastapi import APIRouter, Depends, Query

from backend.api.dependencias import ubicacion_para_filtrar, usuario_actual
from backend.servicios.reportes_service import ReportesService

router = APIRouter(prefix="/reportes", tags=["Reportes"])
service = ReportesService()

DESDE = Query(None, description="Fecha inicial, inclusive (AAAA-MM-DD)")
HASTA = Query(None, description="Fecha final, inclusive (AAAA-MM-DD)")


@router.get("/ventas")
def ventas_por_periodo(desde: date | None = DESDE, hasta: date | None = HASTA, sucursal_id: int | None = None,
                       agrupar: str = Query("dia", description="dia, mes o total"), usuario=Depends(usuario_actual)):
    """Ventas, devoluciones e ingreso neto por período, local y medio de pago."""
    return service.ventas(desde, hasta, ubicacion_para_filtrar(usuario, sucursal_id), agrupar)


@router.get("/productos-mas-vendidos")
def productos_mas_vendidos(desde: date | None = DESDE, hasta: date | None = HASTA, sucursal_id: int | None = None,
                           limite: int = 10, usuario=Depends(usuario_actual)):
    """Ranking por unidades netas de devoluciones, con ingreso, costo y margen
    (ganancia o pérdida) con los precios del momento de cada venta."""
    return service.productos_mas_vendidos(desde, hasta, ubicacion_para_filtrar(usuario, sucursal_id), limite)


@router.get("/existencias")
def existencias(ubicacion_id: int | None = None, solo_bajo_minimo: bool = False, usuario=Depends(usuario_actual)):
    """Stock actual de cada producto en cada ubicación, si está bajo el mínimo
    y su valorización a costo."""
    return service.existencias(ubicacion_para_filtrar(usuario, ubicacion_id), solo_bajo_minimo)


@router.get("/mermas")
def mermas(desde: date | None = DESDE, hasta: date | None = HASTA, sucursal_id: int | None = None,
           usuario=Depends(usuario_actual)):
    """Bultos rechazados por precinto (rechazo logístico): qué se perdió, cuánto
    vale a costo y la tasa de rechazo de cada sucursal."""
    return service.mermas(desde, hasta, ubicacion_para_filtrar(usuario, sucursal_id))


@router.get("/tiempos-transito")
def tiempos_transito(desde: date | None = DESDE, hasta: date | None = HASTA, sucursal_id: int | None = None,
                     usuario=Depends(usuario_actual)):
    """Horas entre que un bulto sale del CD y llega al local (promedio, mínimo
    y máximo por sucursal), calculadas con el historial de estados."""
    return service.tiempos_transito(desde, hasta, ubicacion_para_filtrar(usuario, sucursal_id))
