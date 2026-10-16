# Endpoints de los maestros (productos, categorías, proveedores, ubicaciones,
# sucursales, CD). Llaman a maestros_service y nada más.
# Acá NO va lógica de negocio ni acceso a la base.
from fastapi import APIRouter
from pydantic import BaseModel

from backend.servicios.maestros_service import CategoriaService, ProductoService

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


# ---------------------------------------------------------------- Productos
router_productos = APIRouter(prefix="/productos", tags=["Productos"])
producto_service = ProductoService()


# Pydantic solo controla tipos; las reglas de negocio están en el dominio
class ProductoModificacion(BaseModel):
    nombre: str
    categoria_id: int
    precio_venta: float
    costo: float
    stock_minimo: int = 0


# Al crear se agrega el código, que después no se puede modificar
class ProductoEntrada(ProductoModificacion):
    codigo: str


class ProductoSalida(BaseModel):
    id: int
    codigo: str
    nombre: str
    categoria_id: int
    precio_venta: float
    costo: float
    margen_unitario: float
    stock_minimo: int
    activo: bool


def producto_a_salida(producto):
    return ProductoSalida(
        id=producto.id,
        codigo=producto.codigo,
        nombre=producto.nombre,
        categoria_id=producto.categoria_id,
        precio_venta=producto.precio_venta,
        costo=producto.costo,
        margen_unitario=producto.margen_unitario(),
        stock_minimo=producto.stock_minimo,
        activo=producto.activo,
    )


@router_productos.get("", response_model=list[ProductoSalida])
def listar_productos(categoria_id: int | None = None):
    return [producto_a_salida(p) for p in producto_service.listar(categoria_id)]


@router_productos.get("/{id}", response_model=ProductoSalida)
def obtener_producto(id: int):
    return producto_a_salida(producto_service.obtener(id))


@router_productos.post("", response_model=ProductoSalida, status_code=201)
def crear_producto(datos: ProductoEntrada):
    return producto_a_salida(producto_service.crear(
        datos.codigo, datos.nombre, datos.categoria_id, datos.precio_venta, datos.costo, datos.stock_minimo,
    ))


@router_productos.put("/{id}", response_model=ProductoSalida)
def modificar_producto(id: int, datos: ProductoModificacion):
    return producto_a_salida(producto_service.modificar(
        id, datos.nombre, datos.categoria_id, datos.precio_venta, datos.costo, datos.stock_minimo,
    ))


@router_productos.delete("/{id}", status_code=204)
def dar_de_baja_producto(id: int):
    producto_service.dar_de_baja(id)