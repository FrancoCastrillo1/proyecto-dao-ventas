# Endpoints de los maestros (productos, categorías, proveedores, ubicaciones,
# sucursales, CD). Llaman a maestros_service y nada más.
# Permisos: consultar productos, categorías y ubicaciones puede cualquiera
# que haya entrado; los proveedores, quien los administra o les compra;
# crear, modificar, dar de baja o reactivar, solo el administrador.
# Acá NO va lógica de negocio ni acceso a la base.
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.api.dependencias import ADMINISTRADOR, LOGUEADO, requiere
from backend.servicios.maestros_service import CategoriaService, ProductoService, ProveedorService, UbicacionService

PROVEEDORES = Depends(requiere("puede_consultar_proveedores"))

router = APIRouter(prefix="/categorias", tags=["Categorías"])
service = CategoriaService()


# Respuesta común de los endpoints /parecidos de todos los maestros: el front
# muestra el mismo aviso "¿crear igual?" para cualquiera de ellos
class Parecido(BaseModel):
    id: int
    nombre: str


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


@router.get("", response_model=list[CategoriaSalida], dependencies=[LOGUEADO])
def listar_categorias(incluir_bajas: bool = False):
    return [a_salida(c) for c in service.listar(incluir_bajas)]


# Las rutas /parecidos van antes que "/{id}": si no, FastAPI intenta leer "parecidos" como un id
@router.get("/parecidos", response_model=list[Parecido], dependencies=[ADMINISTRADOR])
def categorias_parecidas(nombre: str, excluir_id: int | None = None):
    return [Parecido(id=c.id, nombre=c.nombre) for c in service.parecidos(nombre, excluir_id)]


@router.get("/{id}", response_model=CategoriaSalida, dependencies=[LOGUEADO])
def obtener_categoria(id: int):
    return a_salida(service.obtener(id))


@router.post("", response_model=CategoriaSalida, status_code=201, dependencies=[ADMINISTRADOR])
def crear_categoria(datos: CategoriaEntrada):
    return a_salida(service.crear(datos.nombre))


@router.put("/{id}", response_model=CategoriaSalida, dependencies=[ADMINISTRADOR])
def modificar_categoria(id: int, datos: CategoriaEntrada):
    return a_salida(service.modificar(id, datos.nombre))


@router.delete("/{id}", status_code=204, dependencies=[ADMINISTRADOR])
def dar_de_baja_categoria(id: int):
    service.dar_de_baja(id)


@router.post("/{id}/reactivar", response_model=CategoriaSalida, dependencies=[ADMINISTRADOR])
def reactivar_categoria(id: int):
    return a_salida(service.reactivar(id))


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


@router_productos.get("", response_model=list[ProductoSalida], dependencies=[LOGUEADO])
def listar_productos(categoria_id: int | None = None, incluir_bajas: bool = False):
    return [producto_a_salida(p) for p in producto_service.listar(categoria_id, incluir_bajas)]


@router_productos.get("/parecidos", response_model=list[Parecido], dependencies=[ADMINISTRADOR])
def productos_parecidos(nombre: str, excluir_id: int | None = None):
    return [Parecido(id=p.id, nombre=f"{p.codigo} · {p.nombre}") for p in producto_service.parecidos(nombre, excluir_id)]


@router_productos.get("/{id}", response_model=ProductoSalida, dependencies=[LOGUEADO])
def obtener_producto(id: int):
    return producto_a_salida(producto_service.obtener(id))


@router_productos.post("", response_model=ProductoSalida, status_code=201, dependencies=[ADMINISTRADOR])
def crear_producto(datos: ProductoEntrada):
    return producto_a_salida(producto_service.crear(
        datos.codigo, datos.nombre, datos.categoria_id, datos.precio_venta, datos.costo, datos.stock_minimo,
    ))


@router_productos.put("/{id}", response_model=ProductoSalida, dependencies=[ADMINISTRADOR])
def modificar_producto(id: int, datos: ProductoModificacion):
    return producto_a_salida(producto_service.modificar(
        id, datos.nombre, datos.categoria_id, datos.precio_venta, datos.costo, datos.stock_minimo,
    ))


@router_productos.delete("/{id}", status_code=204, dependencies=[ADMINISTRADOR])
def dar_de_baja_producto(id: int):
    producto_service.dar_de_baja(id)


@router_productos.post("/{id}/reactivar", response_model=ProductoSalida, dependencies=[ADMINISTRADOR])
def reactivar_producto(id: int):
    return producto_a_salida(producto_service.reactivar(id))


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


@router_proveedores.get("", response_model=list[ProveedorSalida], dependencies=[PROVEEDORES])
def listar_proveedores(incluir_bajas: bool = False):
    return [proveedor_a_salida(p) for p in proveedor_service.listar(incluir_bajas)]


@router_proveedores.get("/parecidos", response_model=list[Parecido], dependencies=[ADMINISTRADOR])
def proveedores_parecidos(razon_social: str, excluir_id: int | None = None):
    return [
        Parecido(id=p.id, nombre=f"{p.razon_social} ({p.cuit_formateado})")
        for p in proveedor_service.parecidos(razon_social, excluir_id)
    ]


@router_proveedores.get("/{id}", response_model=ProveedorSalida, dependencies=[PROVEEDORES])
def obtener_proveedor(id: int):
    return proveedor_a_salida(proveedor_service.obtener(id))


@router_proveedores.post("", response_model=ProveedorSalida, status_code=201, dependencies=[ADMINISTRADOR])
def crear_proveedor(datos: ProveedorEntrada):
    return proveedor_a_salida(proveedor_service.crear(datos.cuit, datos.razon_social, datos.telefono, datos.email))


@router_proveedores.put("/{id}", response_model=ProveedorSalida, dependencies=[ADMINISTRADOR])
def modificar_proveedor(id: int, datos: ProveedorModificacion):
    return proveedor_a_salida(proveedor_service.modificar(id, datos.razon_social, datos.telefono, datos.email))


@router_proveedores.delete("/{id}", status_code=204, dependencies=[ADMINISTRADOR])
def dar_de_baja_proveedor(id: int):
    proveedor_service.dar_de_baja(id)


@router_proveedores.post("/{id}/reactivar", response_model=ProveedorSalida, dependencies=[ADMINISTRADOR])
def reactivar_proveedor(id: int):
    return proveedor_a_salida(proveedor_service.reactivar(id))


# Relación con productos: rutas anidadas, cada operación toca un solo vínculo
@router_proveedores.get("/{id}/productos", response_model=list[ProductoSalida], dependencies=[PROVEEDORES])
def listar_productos_del_proveedor(id: int):
    return [producto_a_salida(p) for p in proveedor_service.listar_productos(id)]


@router_proveedores.post("/{id}/productos/{producto_id}", status_code=204, dependencies=[ADMINISTRADOR])
def asignar_producto_al_proveedor(id: int, producto_id: int):
    proveedor_service.asignar_producto(id, producto_id)


@router_proveedores.delete("/{id}/productos/{producto_id}", status_code=204, dependencies=[ADMINISTRADOR])
def quitar_producto_del_proveedor(id: int, producto_id: int):
    proveedor_service.quitar_producto(id, producto_id)


@router_productos.get("/{id}/proveedores", response_model=list[ProveedorSalida], dependencies=[PROVEEDORES])
def listar_proveedores_del_producto(id: int):
    return [proveedor_a_salida(p) for p in proveedor_service.listar_proveedores_de_producto(id)]


# ------------------------------------------------- Ubicaciones (Sucursal y CD)
router_ubicaciones = APIRouter(prefix="/ubicaciones", tags=["Ubicaciones"])
ubicacion_service = UbicacionService()


class UbicacionModificacion(BaseModel):
    nombre: str
    direccion: str


# Al crear se agrega el tipo ("SUCURSAL" o "CD"), que después no se puede modificar
class UbicacionEntrada(UbicacionModificacion):
    tipo: str


class UbicacionSalida(BaseModel):
    id: int
    tipo: str
    nombre: str
    direccion: str
    activo: bool
    # Para que el frontend sepa qué acciones mostrar sin conocer las reglas
    puede_vender: bool
    puede_despachar: bool
    puede_recibir: bool


def ubicacion_a_salida(ubicacion):
    return UbicacionSalida(
        id=ubicacion.id,
        tipo=ubicacion.tipo,
        nombre=ubicacion.nombre,
        direccion=ubicacion.direccion,
        activo=ubicacion.activo,
        puede_vender=ubicacion.puede_vender(),
        puede_despachar=ubicacion.puede_despachar(),
        puede_recibir=ubicacion.puede_recibir(),
    )


@router_ubicaciones.get("", response_model=list[UbicacionSalida], dependencies=[LOGUEADO])
def listar_ubicaciones(tipo: str | None = None, incluir_bajas: bool = False):
    return [ubicacion_a_salida(u) for u in ubicacion_service.listar(tipo, incluir_bajas)]


# Tiene que ir antes que "/{id}": si no, FastAPI intenta leer "cd" como un id
@router_ubicaciones.get("/cd", response_model=UbicacionSalida, dependencies=[LOGUEADO])
def obtener_centro_distribucion():
    return ubicacion_a_salida(ubicacion_service.obtener_cd())


@router_ubicaciones.get("/parecidos", response_model=list[Parecido], dependencies=[ADMINISTRADOR])
def ubicaciones_parecidas(nombre: str, excluir_id: int | None = None):
    return [Parecido(id=u.id, nombre=u.nombre) for u in ubicacion_service.parecidos(nombre, excluir_id)]


@router_ubicaciones.get("/{id}", response_model=UbicacionSalida, dependencies=[LOGUEADO])
def obtener_ubicacion(id: int):
    return ubicacion_a_salida(ubicacion_service.obtener(id))


@router_ubicaciones.post("", response_model=UbicacionSalida, status_code=201, dependencies=[ADMINISTRADOR])
def crear_ubicacion(datos: UbicacionEntrada):
    return ubicacion_a_salida(ubicacion_service.crear(datos.tipo, datos.nombre, datos.direccion))


@router_ubicaciones.put("/{id}", response_model=UbicacionSalida, dependencies=[ADMINISTRADOR])
def modificar_ubicacion(id: int, datos: UbicacionModificacion):
    return ubicacion_a_salida(ubicacion_service.modificar(id, datos.nombre, datos.direccion))


@router_ubicaciones.delete("/{id}", status_code=204, dependencies=[ADMINISTRADOR])
def dar_de_baja_ubicacion(id: int):
    ubicacion_service.dar_de_baja(id)


@router_ubicaciones.post("/{id}/reactivar", response_model=UbicacionSalida, dependencies=[ADMINISTRADOR])
def reactivar_ubicacion(id: int):
    return ubicacion_a_salida(ubicacion_service.reactivar(id))