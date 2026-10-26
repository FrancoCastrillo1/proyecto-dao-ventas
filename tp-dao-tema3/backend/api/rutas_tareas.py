# Endpoint de la bandeja de tareas de Inicio: GET /tareas devuelve lo que
# tiene pendiente el usuario que entró. Qué le toca a cada uno lo decide el
# service según las capacidades del usuario.
# Acá NO va lógica de negocio ni acceso a la base.
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.api.dependencias import usuario_actual
from backend.servicios.tareas_service import TareasService

router = APIRouter(prefix="/tareas", tags=["Tareas"])
service = TareasService()


class ItemSugerido(BaseModel):
    producto_id: int
    cantidad: int


class TareaSalida(BaseModel):
    tipo: str
    titulo: str
    detalle: str
    pantalla: str
    accion: str
    urgente: bool
    items: list[ItemSugerido]   # para precargar un pedido (solo en "reponer")


@router.get("", response_model=list[TareaSalida])
def mis_tareas(usuario=Depends(usuario_actual)):
    return [
        TareaSalida(tipo=t.tipo, titulo=t.titulo, detalle=t.detalle, pantalla=t.pantalla, accion=t.accion,
                    urgente=t.urgente, items=[ItemSugerido(producto_id=p, cantidad=c) for p, c in t.items])
        for t in service.para(usuario)
    ]
