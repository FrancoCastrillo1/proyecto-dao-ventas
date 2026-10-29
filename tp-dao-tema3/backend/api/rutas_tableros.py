# Endpoints de los tableros de la pantalla Reportes. Llaman a tableros_service
# y nada más. Cada gráfico de un tablero abre en el front uno de los 7
# reportes de detalle (/reportes/...), con sus propios permisos.
# Quién ve qué, según sus capacidades:
#   - ejecutivo: ve_resultados_empresa (solo el administrador);
#   - ventas del local: ve_ventas (administrador: todos o uno; local: el suyo);
#   - productos e inventario: todos; el ranking y la matriz volumen × margen,
#     solo quien ve ventas (el CD ve el stock, no los márgenes);
#   - abastecimiento: todos (un local ve solo sus pedidos); lo más pedido de
#     la red, solo quien ve toda la red (CD y administrador).
# Un local siempre ve solo lo suyo: lo fija ubicacion_para_filtrar, no el front.
# Cada tablero se pide en JSON (pantalla) o con formato=pdf (todo el tablero,
# con todos sus gráficos), en la misma ruta y con el mismo permiso.
# Acá NO va lógica de negocio ni acceso a la base.
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response

from backend.api.dependencias import requiere, ubicacion_para_filtrar, usuario_actual
from backend.servicios.tableros_service import TablerosService

router = APIRouter(prefix="/tableros", tags=["Tableros"])
service = TablerosService()

DESDE = Query(None, description="Fecha inicial, inclusive (AAAA-MM-DD). Sin fechas: los últimos 30 días")
HASTA = Query(None, description="Fecha final, inclusive (AAAA-MM-DD)")
COMPARAR = Query("anterior", description="anterior: los mismos días justo antes; anio: las mismas fechas un año antes")
FORMATO = Query("json", description="json para la pantalla, pdf para descargar el tablero")
Comparar = Literal["anterior", "anio"]
Formato = Literal["json", "pdf"]


def responder(clave, datos, formato, usuario, ubicacion_id):
    """Los datos tal cual, o el PDF del tablero para descargar."""
    if formato == "json":
        return datos
    nombre, contenido = service.pdf(clave, datos, usuario.nombre_completo, ubicacion_id)
    return Response(content=contenido, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.get("/ejecutivo")
def ejecutivo(desde: date | None = DESDE, hasta: date | None = HASTA, comparar: Comparar = COMPARAR,
              sucursal_id: int | None = None, formato: Formato = FORMATO,
              usuario=Depends(requiere("ve_resultados_empresa"))):
    """Ventas, ganancia, margen y tickets contra el período comparado; evolución
    de las ventas, ranking de locales y ventas por categoría."""
    return responder("ejecutivo", service.ejecutivo(desde, hasta, comparar, sucursal_id), formato, usuario, sucursal_id)


@router.get("/ventas")
def ventas_local(desde: date | None = DESDE, hasta: date | None = HASTA, comparar: Comparar = COMPARAR,
                 sucursal_id: int | None = None, formato: Formato = FORMATO, usuario=Depends(requiere("ve_ventas"))):
    """Tickets, ticket promedio, ventas por día, mapa de calor día × hora, por
    categoría y lo que más se devuelve."""
    sucursal = ubicacion_para_filtrar(usuario, sucursal_id)
    return responder("ventas", service.ventas_local(desde, hasta, comparar, sucursal), formato, usuario, sucursal)


@router.get("/productos")
def productos(desde: date | None = DESDE, hasta: date | None = HASTA, ubicacion_id: int | None = None,
              formato: Formato = FORMATO, usuario=Depends(usuario_actual)):
    """Los más vendidos y la matriz volumen × margen (si el perfil ve ventas);
    qué falta reponer y cuánto stock está parado según su última salida."""
    ubicacion = ubicacion_para_filtrar(usuario, ubicacion_id)
    datos = service.productos(desde, hasta, ubicacion, con_rentabilidad=usuario.ve_ventas())
    return responder("productos", datos, formato, usuario, ubicacion)


@router.get("/abastecimiento")
def abastecimiento(desde: date | None = DESDE, hasta: date | None = HASTA, sucursal_id: int | None = None,
                   formato: Formato = FORMATO, usuario=Depends(usuario_actual)):
    """Pedidos de reposición por estado, tiempo desde que el local pide hasta
    que termina de verificar, mermas y (para la red) lo más pedido."""
    sucursal = ubicacion_para_filtrar(usuario, sucursal_id)
    datos = service.abastecimiento(desde, hasta, sucursal, con_demanda=usuario.ve_toda_la_red())
    return responder("abastecimiento", datos, formato, usuario, sucursal)
