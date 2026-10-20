# Endpoints de logística: pedido, orden, remito, despacho, recepción y verificación.
# Es una capa fina: recibe el pedido HTTP, llama al servicio y arma la respuesta.
# Los errores del negocio (DatoInvalido, NoEncontrado, StockInsuficiente, etc.) los
# traduce a códigos HTTP el manejador global de main.py, acá no hay try/except.
# Acá NO van reglas de negocio ni SQL.
from typing import Optional

from fastapi import APIRouter, status
from pydantic import BaseModel

from backend.servicios.recepcion_service import RecepcionService
from backend.servicios.reposicion_service import ReposicionService

router = APIRouter(prefix="/logistica", tags=["Logística"])
reposicion = ReposicionService()
recepcion = RecepcionService()


# ---------- cuerpos de las peticiones ----------

class ItemDTO(BaseModel):
    producto_id: int
    cantidad: int


class PedidoDTO(BaseModel):
    local_id: int
    items: list[ItemDTO]


class OrdenDTO(BaseModel):
    origen_id: int
    pedido_ids: list[int]


class BultoDTO(BaseModel):
    precinto: str
    items: list[ItemDTO]


class RemitoDTO(BaseModel):
    origen_id: int
    destino_id: int
    bultos: list[BultoDTO]


class VerificacionDTO(BaseModel):
    nro_leido: Optional[str] = None
    intacto: bool


# ---------- del objeto del dominio al JSON de la respuesta ----------

def _items(detalles):
    return [{"producto_id": d.producto, "cantidad": d.cantidad} for d in detalles]


def _pedido(p):
    return {"id": p.id_pedido, "local_id": p.local, "estado": p.estado, "items": _items(p.items)}


def _orden(o):
    return {
        "id": o.id_orden,
        "origen_id": o.origen,
        "estado": o.estado,
        "pedido_ids": [p.id_pedido for p in o.pedidos],
        "total_por_producto": {str(k): v for k, v in o.total_por_producto().items()},
    }


def _bulto(b):
    return {
        "id": b.id_bulto,
        "estado": b.estado,
        "nro_precinto": b.nro_precinto,
        "habilita_venta": b.habilita_venta(),
        "items": _items(b.items),
        "historial": [
            {
                "fecha_hora": c.fecha_hora.isoformat(sep=" "),
                "estado_anterior": c.estado_anterior,
                "estado_nuevo": c.estado_nuevo,
                "observacion": c.observacion,
            }
            for c in b.historial
        ],
    }


def _remito(r):
    return {
        "id": r.id_remito,
        "origen_id": r.origen,
        "destino_id": r.destino,
        "estado": r.estado,
        "bultos": [_bulto(b) for b in r.bultos],
        "total_por_producto": {str(k): v for k, v in r.total_por_producto().items()},
    }


# ---------- pedidos ----------

@router.post("/pedidos", status_code=status.HTTP_201_CREATED)
def crear_pedido(datos: PedidoDTO):
    items = [(i.producto_id, i.cantidad) for i in datos.items]
    return {"id": reposicion.crear_pedido(datos.local_id, items)}


@router.get("/pedidos/{pedido_id}")
def obtener_pedido(pedido_id: int):
    return _pedido(reposicion.obtener_pedido(pedido_id))


@router.post("/pedidos/{pedido_id}/consolidar")
def consolidar_pedido(pedido_id: int):
    reposicion.consolidar_pedido(pedido_id)
    return _pedido(reposicion.obtener_pedido(pedido_id))


# ---------- órdenes ----------

@router.post("/ordenes", status_code=status.HTTP_201_CREATED)
def crear_orden(datos: OrdenDTO):
    return {"id": reposicion.crear_orden(datos.origen_id, datos.pedido_ids)}


@router.get("/ordenes/{orden_id}")
def obtener_orden(orden_id: int):
    return _orden(reposicion.obtener_orden(orden_id))


# ---------- remitos y despacho ----------

@router.post("/remitos", status_code=status.HTTP_201_CREATED)
def armar_remito(datos: RemitoDTO):
    bultos = [
        {"precinto": b.precinto, "items": [(i.producto_id, i.cantidad) for i in b.items]}
        for b in datos.bultos
    ]
    return {"id": reposicion.armar_remito(datos.origen_id, datos.destino_id, bultos)}


@router.get("/remitos/{remito_id}")
def obtener_remito(remito_id: int):
    return _remito(reposicion.obtener_remito(remito_id))


@router.post("/remitos/{remito_id}/despachar")
def despachar_remito(remito_id: int):
    reposicion.despachar_remito(remito_id)
    return _remito(reposicion.obtener_remito(remito_id))


# ---------- bultos: recepción y verificación ----------

@router.get("/bultos/{bulto_id}")
def obtener_bulto(bulto_id: int):
    return _bulto(recepcion.obtener_bulto(bulto_id))


@router.post("/bultos/{bulto_id}/recibir")
def recibir_bulto(bulto_id: int):
    recepcion.recibir_bulto(bulto_id)
    return _bulto(recepcion.obtener_bulto(bulto_id))


@router.post("/bultos/{bulto_id}/verificar")
def verificar_bulto(bulto_id: int, datos: VerificacionDTO):
    recepcion.verificar_bulto(bulto_id, datos.nro_leido, datos.intacto)
    return _bulto(recepcion.obtener_bulto(bulto_id))