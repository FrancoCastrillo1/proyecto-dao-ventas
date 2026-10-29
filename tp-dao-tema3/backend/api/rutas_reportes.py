# Endpoints de reportes (ventas por período, más vendidos, existencias, etc.).
# Llaman a reportes_service y nada más. Quien ve toda la red (administrador y
# CD) puede filtrar por cualquier local; un local ve solo los suyos.
# Cada perfil ve los reportes que le sirven, según sus capacidades:
#   - ventas, más vendidos y devoluciones exigen ve_ventas (el CD no vende);
#   - más pedidos exige ve_toda_la_red (es la demanda de toda la red: CD y admin);
#   - existencias, mermas y tiempos de envío los ve cualquiera (filtrados).
# Acá NO va lógica de negocio ni acceso a la base.
#
# Cada reporte se pide en JSON (para la pantalla) o con formato=pdf (para
# descargarlo): es la misma ruta, con el mismo permiso y los mismos filtros.
# El JSON va directo (sin un modelo Pydantic por fila): son vistas de solo
# lectura con muchas columnas, y FastAPI ya convierte Decimal y fechas.
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response

from backend.api.dependencias import requiere, ubicacion_para_filtrar, usuario_actual
from backend.servicios.reportes_service import ReportesService

router = APIRouter(prefix="/reportes", tags=["Reportes"])
service = ReportesService()

DESDE = Query(None, description="Fecha inicial, inclusive (AAAA-MM-DD)")
HASTA = Query(None, description="Fecha final, inclusive (AAAA-MM-DD)")
FORMATO = Query("json", description="json para la pantalla, pdf para descargarlo")
Formato = Literal["json", "pdf"]


def responder(clave, datos, formato, usuario, filtros, **opciones):
    """Los datos tal cual, o el PDF del reporte para descargar."""
    if formato == "json":
        return datos
    nombre, contenido = service.pdf(clave, datos, filtros, usuario.nombre_completo, **opciones)
    return Response(content=contenido, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.get("/ventas")
def ventas_por_periodo(desde: date | None = DESDE, hasta: date | None = HASTA, sucursal_id: int | None = None,
                       agrupar: str = Query("dia", description="dia, mes o total"), formato: Formato = FORMATO,
                       usuario=Depends(requiere("ve_ventas"))):
    """Ventas, devoluciones e ingreso neto por período, local y medio de pago."""
    sucursal = ubicacion_para_filtrar(usuario, sucursal_id)
    datos = service.ventas(desde, hasta, sucursal, agrupar)
    return responder("ventas", datos, formato, usuario, service.describir_filtros(desde, hasta, sucursal),
                     agrupar=agrupar)


@router.get("/productos-mas-vendidos")
def productos_mas_vendidos(desde: date | None = DESDE, hasta: date | None = HASTA, sucursal_id: int | None = None,
                           limite: int = 10, formato: Formato = FORMATO, usuario=Depends(requiere("ve_ventas"))):
    """Ranking por unidades netas de devoluciones, con ingreso, costo y margen
    (ganancia o pérdida) con los precios del momento de cada venta."""
    sucursal = ubicacion_para_filtrar(usuario, sucursal_id)
    datos = service.productos_mas_vendidos(desde, hasta, sucursal, limite)
    return responder("productos-mas-vendidos", datos, formato, usuario, service.describir_filtros(desde, hasta, sucursal))


@router.get("/existencias")
def existencias(ubicacion_id: int | None = None, solo_bajo_minimo: bool = False, formato: Formato = FORMATO,
                usuario=Depends(usuario_actual)):
    """Stock actual de cada producto en cada ubicación, si está bajo el mínimo
    y su valorización a costo."""
    ubicacion = ubicacion_para_filtrar(usuario, ubicacion_id)
    datos = service.existencias(ubicacion, solo_bajo_minimo)
    return responder("existencias", datos, formato, usuario,
                     service.describir_filtros(ubicacion_id=ubicacion, con_fechas=False))


@router.get("/mermas")
def mermas(desde: date | None = DESDE, hasta: date | None = HASTA, sucursal_id: int | None = None,
           formato: Formato = FORMATO, usuario=Depends(usuario_actual)):
    """Bultos rechazados por precinto (rechazo logístico): qué se perdió, cuánto
    vale a costo y la tasa de rechazo de cada sucursal."""
    sucursal = ubicacion_para_filtrar(usuario, sucursal_id)
    datos = service.mermas(desde, hasta, sucursal)
    return responder("mermas", datos, formato, usuario, service.describir_filtros(desde, hasta, sucursal))


@router.get("/tiempos-transito")
def tiempos_transito(desde: date | None = DESDE, hasta: date | None = HASTA, sucursal_id: int | None = None,
                     formato: Formato = FORMATO, usuario=Depends(usuario_actual)):
    """Horas entre que un bulto sale del CD y llega al local (promedio, mínimo
    y máximo por sucursal), calculadas con el historial de estados."""
    sucursal = ubicacion_para_filtrar(usuario, sucursal_id)
    datos = service.tiempos_transito(desde, hasta, sucursal)
    return responder("tiempos-transito", datos, formato, usuario, service.describir_filtros(desde, hasta, sucursal))


@router.get("/productos-mas-pedidos")
def productos_mas_pedidos(desde: date | None = DESDE, hasta: date | None = HASTA, sucursal_id: int | None = None,
                          limite: int = 10, formato: Formato = FORMATO, usuario=Depends(requiere("ve_toda_la_red"))):
    """Lo que más piden los locales al CD: unidades, pedidos y locales, cuánto
    falta preparar y si alcanza con lo que hay en el CD."""
    datos = service.productos_mas_pedidos(desde, hasta, sucursal_id, limite)
    return responder("productos-mas-pedidos", datos, formato, usuario,
                     service.describir_filtros(desde, hasta, sucursal_id))


@router.get("/devoluciones")
def devoluciones(desde: date | None = DESDE, hasta: date | None = HASTA, sucursal_id: int | None = None,
                 formato: Formato = FORMATO, usuario=Depends(requiere("ve_ventas"))):
    """Qué productos se devuelven, cuánto se reintegró, qué parte de lo vendido
    se devolvió y por qué motivos."""
    sucursal = ubicacion_para_filtrar(usuario, sucursal_id)
    datos = service.devoluciones(desde, hasta, sucursal)
    return responder("devoluciones", datos, formato, usuario, service.describir_filtros(desde, hasta, sucursal))
