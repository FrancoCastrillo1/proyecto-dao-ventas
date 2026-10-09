# Endpoints de los maestros (productos, categorías, proveedores, ubicaciones,
# sucursales, CD). Llaman a maestros_service y nada más.
# Acá NO va lógica de negocio ni acceso a la base.
from fastapi import APIRouter
from pydantic import BaseModel

from backend.servicios.maestros_service import CategoriaService

router = APIRouter(prefix="/categorias", tags=["Categorías"])
service = CategoriaService()


# Forma del JSON que llega (POST / PUT)
class CategoriaEntrada(BaseModel):
    nombre: str


# Forma del JSON que sale
class CategoriaSalida(BaseModel):
    id: int
    nombre: str
    activo: bool


def a_salida(categoria):
    return CategoriaSalida(id=categoria.id, nombre=categoria.nombre, activo=categoria.activo)


@router.get("", response_model=list[CategoriaSalida])
def listar_categorias():
    return [a_salida(c) for c in service.listar()]


@router.get("/{id}", response_model=CategoriaSalida)
def obtener_categoria(id: int):
    return a_salida(service.obtener(id))


@router.post("", response_model=CategoriaSalida, status_code=201)
def crear_categoria(datos: CategoriaEntrada):
    return a_salida(service.crear(datos.nombre))


@router.put("/{id}", response_model=CategoriaSalida)
def modificar_categoria(id: int, datos: CategoriaEntrada):
    return a_salida(service.modificar(id, datos.nombre))


@router.delete("/{id}", status_code=204)
def dar_de_baja_categoria(id: int):
    service.dar_de_baja(id)