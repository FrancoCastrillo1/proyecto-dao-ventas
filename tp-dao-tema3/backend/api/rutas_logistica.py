# Endpoints de logística: pedidos de reposición, órdenes, bultos, despacho y recepción.
# Llaman a reposicion_service y recepcion_service.
# Permisos: el local pide y recibe lo suyo; el CD consolida, arma, precinta y
# despacha. El local del pedido sale del usuario, nunca del formulario.
# Quién hizo cada operación se le pasa al service (queda en la base).
# Acá NO va lógica de negocio ni acceso a la base.
#
# Recorrido completo desde /docs (con el token de POST /auth/login):
#   POST /pedidos → POST /ordenes → POST /remitos → POST /remitos/{id}/bultos
#   → POST /bultos/{id}/precintar → POST /remitos/{id}/despachar
#   → POST /bultos/{id}/recibir → POST /bultos/{id}/verificar
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.api.dependencias import exigir_que_sea_suyo, requiere, ubicacion_para_filtrar, usuario_actual
from backend.servicios.recepcion_service import RecepcionService
from backend.servicios.reposicion_service import ReposicionService

reposicion = ReposicionService()
recepcion = RecepcionService()


# ------------------------------------------------------------ Modelos comunes

class ItemEntrada(BaseModel):
    producto_id: int
    cantidad: int


class ItemSalida(BaseModel):
    producto_id: int
    cantidad: int


def a_items(detalles):
    return [ItemSalida(producto_id=d.producto, cantidad=d.cantidad) for d in detalles]


def totales_a_items(totales):
    return [ItemSalida(producto_id=p, cantidad=c) for p, c in sorted(totales.items())]


def a_pares(items):
    return [(item.producto_id, item.cantidad) for item in items]


# -------------------------------------------------------------------- Pedidos
router_pedidos = APIRouter(prefix="/pedidos", tags=["Logística: pedidos"])


class PedidoEntrada(BaseModel):
    items: list[ItemEntrada]   # el local es el del usuario que pide


class PedidoSalida(BaseModel):
    id: int
    sucursal_id: int
    fecha: datetime
    estado: str
    orden_id: int | None
    items: list[ItemSalida]


def pedido_a_salida(pedido):
    return PedidoSalida(id=pedido.id_pedido, sucursal_id=pedido.local, fecha=pedido.fecha, estado=pedido.estado,
                        orden_id=pedido.orden_id, items=a_items(pedido.items))


@router_pedidos.get("", response_model=list[PedidoSalida])
def listar_pedidos(sucursal_id: int | None = None, estado: str | None = None, usuario=Depends(usuario_actual)):
    sucursal_id = ubicacion_para_filtrar(usuario, sucursal_id)
    return [pedido_a_salida(p) for p in reposicion.listar_pedidos(sucursal_id, estado)]


@router_pedidos.get("/{id}", response_model=PedidoSalida)
def obtener_pedido(id: int, usuario=Depends(usuario_actual)):
    pedido = reposicion.obtener_pedido(id)
    exigir_que_sea_suyo(usuario, pedido.local, "Ese pedido")
    return pedido_a_salida(pedido)


@router_pedidos.post("", response_model=PedidoSalida, status_code=201)
def crear_pedido(datos: PedidoEntrada, usuario=Depends(requiere("puede_pedir_reposicion"))):
    return pedido_a_salida(reposicion.crear_pedido(usuario.ubicacion_id, a_pares(datos.items), usuario.id))


# -------------------------------------------------------------------- Órdenes
router_ordenes = APIRouter(prefix="/ordenes", tags=["Logística: órdenes"])


class OrdenEntrada(BaseModel):
    pedido_ids: list[int]


class OrdenSalida(BaseModel):
    id: int
    origen_id: int
    fecha: datetime
    estado: str
    pedidos: list[PedidoSalida]
    total_por_producto: list[ItemSalida]  # lo que el CD tiene que juntar


def orden_a_salida(orden):
    return OrdenSalida(id=orden.id_orden, origen_id=orden.origen, fecha=orden.fecha, estado=orden.estado,
                       pedidos=[pedido_a_salida(p) for p in orden.pedidos],
                       total_por_producto=totales_a_items(orden.total_por_producto()))


@router_ordenes.get("", response_model=list[OrdenSalida], dependencies=[Depends(requiere("puede_preparar_envios"))])
def listar_ordenes():
    return [orden_a_salida(o) for o in reposicion.listar_ordenes()]


@router_ordenes.get("/{id}", response_model=OrdenSalida, dependencies=[Depends(requiere("puede_preparar_envios"))])
def obtener_orden(id: int):
    return orden_a_salida(reposicion.obtener_orden(id))


@router_ordenes.post("", response_model=OrdenSalida, status_code=201)
def crear_orden(datos: OrdenEntrada, usuario=Depends(requiere("puede_preparar_envios"))):
    return orden_a_salida(reposicion.crear_orden(datos.pedido_ids, usuario.id))


# --------------------------------------------------------------------- Bultos
router_bultos = APIRouter(prefix="/bultos", tags=["Logística: bultos"])


class CambioEstadoSalida(BaseModel):
    fecha_hora: datetime
    estado_anterior: str
    estado_nuevo: str
    observacion: str


class BultoSalida(BaseModel):
    id: int
    remito_id: int | None
    estado: str
    nro_precinto: str | None
    habilita_venta: bool
    items: list[ItemSalida]
    historial: list[CambioEstadoSalida]


def bulto_a_salida(bulto):
    return BultoSalida(
        id=bulto.id_bulto, remito_id=bulto.remito_id, estado=bulto.estado, nro_precinto=bulto.nro_precinto,
        habilita_venta=bulto.habilita_venta(), items=a_items(bulto.items),
        historial=[CambioEstadoSalida(fecha_hora=r.fecha_hora, estado_anterior=r.estado_anterior,
                                      estado_nuevo=r.estado_nuevo, observacion=r.observacion)
                   for r in bulto.historial],
    )


class PrecintoEntrada(BaseModel):
    nro_precinto: str


class VerificacionEntrada(BaseModel):
    nro_leido: str      # el número que se lee en el precinto al recibir
    intacto: bool       # si el precinto llegó sano (lo informa quien recibe)


class VerificacionSalida(BaseModel):
    bulto: BultoSalida
    remito_estado: str
    stock_ingresado: bool  # True si con este bulto se completó el remito y se sumó el stock


@router_bultos.get("/{id}", response_model=BultoSalida)
def obtener_bulto(id: int, usuario=Depends(usuario_actual)):
    bulto = reposicion.obtener_bulto(id)
    exigir_que_sea_suyo(usuario, destino_del_bulto(bulto), "Ese bulto")
    return bulto_a_salida(bulto)


def destino_del_bulto(bulto):
    return reposicion.obtener_remito(bulto.remito_id).destino


@router_bultos.post("/{id}/precintar", response_model=BultoSalida)
def precintar_bulto(id: int, datos: PrecintoEntrada, usuario=Depends(requiere("puede_preparar_envios"))):
    return bulto_a_salida(reposicion.precintar(id, datos.nro_precinto, usuario.id))


@router_bultos.post("/{id}/recibir", response_model=BultoSalida)
def recibir_bulto(id: int, usuario=Depends(requiere("puede_recibir"))):
    exigir_que_sea_suyo(usuario, destino_del_bulto(reposicion.obtener_bulto(id)), "Ese bulto")
    return bulto_a_salida(recepcion.recibir(id, usuario.id))


@router_bultos.post("/{id}/verificar", response_model=VerificacionSalida)
def verificar_bulto(id: int, datos: VerificacionEntrada, usuario=Depends(requiere("puede_recibir"))):
    exigir_que_sea_suyo(usuario, destino_del_bulto(reposicion.obtener_bulto(id)), "Ese bulto")
    bulto, remito, ingreso = recepcion.verificar(id, datos.nro_leido, datos.intacto, usuario.id)
    return VerificacionSalida(bulto=bulto_a_salida(bulto), remito_estado=remito.estado, stock_ingresado=ingreso)


# -------------------------------------------------------------------- Remitos
router_remitos = APIRouter(prefix="/remitos", tags=["Logística: remitos"])


class RemitoEntrada(BaseModel):
    orden_id: int
    destino_id: int


class BultoEntrada(BaseModel):
    items: list[ItemEntrada]


class RemitoSalida(BaseModel):
    id: int
    orden_id: int
    origen_id: int
    destino_id: int
    fecha: datetime
    estado: str
    bultos: list[BultoSalida]
    total_por_producto: list[ItemSalida]


def remito_a_salida(remito):
    return RemitoSalida(id=remito.id_remito, orden_id=remito.orden_id, origen_id=remito.origen,
                        destino_id=remito.destino, fecha=remito.fecha, estado=remito.estado,
                        bultos=[bulto_a_salida(b) for b in remito.bultos],
                        total_por_producto=totales_a_items(remito.total_por_producto()))


@router_remitos.get("", response_model=list[RemitoSalida])
def listar_remitos(destino_id: int | None = None, estado: str | None = None, usuario=Depends(usuario_actual)):
    destino_id = ubicacion_para_filtrar(usuario, destino_id)
    return [remito_a_salida(r) for r in reposicion.listar_remitos(destino_id, estado)]


@router_remitos.get("/{id}", response_model=RemitoSalida)
def obtener_remito(id: int, usuario=Depends(usuario_actual)):
    remito = reposicion.obtener_remito(id)
    exigir_que_sea_suyo(usuario, remito.destino, "Ese remito")
    return remito_a_salida(remito)


@router_remitos.post("", response_model=RemitoSalida, status_code=201)
def crear_remito(datos: RemitoEntrada, usuario=Depends(requiere("puede_preparar_envios"))):
    return remito_a_salida(reposicion.crear_remito(datos.orden_id, datos.destino_id, usuario.id))


@router_remitos.post("/{id}/bultos", response_model=BultoSalida, status_code=201)
def agregar_bulto(id: int, datos: BultoEntrada, usuario=Depends(requiere("puede_preparar_envios"))):
    return bulto_a_salida(reposicion.agregar_bulto(id, a_pares(datos.items), usuario.id))


@router_remitos.post("/{id}/despachar", response_model=RemitoSalida)
def despachar_remito(id: int, usuario=Depends(requiere("puede_preparar_envios"))):
    return remito_a_salida(reposicion.despachar(id, usuario.id))
