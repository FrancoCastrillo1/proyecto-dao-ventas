# Endpoints de los maestros (productos, categorías, proveedores, ubicaciones,
# sucursales, CD). Llaman a maestros_service y nada más.
# Acá NO va lógica de negocio ni acceso a la base.
from fastapi import APIRouter
from pydantic import BaseModel

from backend.servicios.maestros_service import CategoriaService, ProductoService, ProveedorService

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


# -------------------------------------------------------------- Proveedores
router_proveedores = APIRouter(prefix="/proveedores", tags=["Proveedores"])
proveedor_service = ProveedorService()


class ProveedorModificacion(BaseModel):
    razon_social: str
    telefono: str | None = None
    email: str | None = None


# Al crear se agrega el CUIT, que después no se puede modificar
class ProveedorEntrada(ProveedorModificacion):
    cuit: str


class ProveedorSalida(BaseModel):
    id: int
    cuit: str
    razon_social: str
    telefono: str | None
    email: str | None
    activo: bool


def proveedor_a_salida(proveedor):
    return ProveedorSalida(
        id=proveedor.id,
        cuit=proveedor.cuit_formateado,
        razon_social=proveedor.razon_social,
        telefono=proveedor.telefono,
        email=proveedor.email,
        activo=proveedor.activo,
    )


@router_proveedores.get("", response_model=list[ProveedorSalida])
def listar_proveedores():
    return [proveedor_a_salida(p) for p in proveedor_service.listar()]


@router_proveedores.get("/{id}", response_model=ProveedorSalida)
def obtener_proveedor(id: int):
    return proveedor_a_salida(proveedor_service.obtener(id))


@router_proveedores.post("", response_model=ProveedorSalida, status_code=201)
def crear_proveedor(datos: ProveedorEntrada):
    return proveedor_a_salida(proveedor_service.crear(datos.cuit, datos.razon_social, datos.telefono, datos.email))


@router_proveedores.put("/{id}", response_model=ProveedorSalida)
def modificar_proveedor(id: int, datos: ProveedorModificacion):
    return proveedor_a_salida(proveedor_service.modificar(id, datos.razon_social, datos.telefono, datos.email))


@router_proveedores.delete("/{id}", status_code=204)
def dar_de_baja_proveedor(id: int):
    proveedor_service.dar_de_baja(id)


# Relación con productos: rutas anidadas, cada operación toca un solo vínculo
@router_proveedores.get("/{id}/productos", response_model=list[ProductoSalida])
def listar_productos_del_proveedor(id: int):
    return [producto_a_salida(p) for p in proveedor_service.listar_productos(id)]


@router_proveedores.post("/{id}/productos/{producto_id}", status_code=204)
def asignar_producto_al_proveedor(id: int, producto_id: int):
    proveedor_service.asignar_producto(id, producto_id)


@router_proveedores.delete("/{id}/productos/{producto_id}", status_code=204)
def quitar_producto_del_proveedor(id: int, producto_id: int):
    proveedor_service.quitar_producto(id, producto_id)


@router_productos.get("/{id}/proveedores", response_model=list[ProveedorSalida])
def listar_proveedores_del_producto(id: int):
    return [proveedor_a_salida(p) for p in proveedor_service.listar_proveedores_de_producto(id)]