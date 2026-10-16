# Casos de uso de los maestros: dar de alta/modificar/listar productos, categorías,
# proveedores, ubicaciones, sucursales y el CD.
# Acá NO va SQL (usa dao_maestros) ni nada de endpoints (eso está en api).
from backend.dominio.excepciones import DatoInvalido, EntidadDuplicada, NoEncontrado
from backend.dominio.maestros import Categoria, Producto
from backend.persistencia.dao_maestros import CategoriaDAO, ProductoDAO

class CategoriaService:
    def __init__(self, dao=None):
        self.dao = dao or CategoriaDAO()

    def crear(self, nombre):
        categoria = Categoria(nombre)
        if self.dao.obtener_por_nombre(categoria.nombre):
            raise EntidadDuplicada(f"Ya existe la categoría '{categoria.nombre}'")
        return self.dao.crear(categoria)

    def obtener(self, id):
        categoria = self.dao.obtener_por_id(id)
        if categoria is None:
            raise NoEncontrado(f"No se encontro la categoria {id}")
        return categoria

    def listar(self):
        return self.dao.listar()

    def modificar(self, id, nombre):
        categoria = self.obtener(id)
        categoria.nombre = nombre
        otra = self.dao.obtener_por_nombre(nombre)

        if otra and otra.id != id:
            raise EntidadDuplicada(f"Ya existe la categoría '{categoria.nombre}'")
        return self.dao.actualizar(categoria)

    def dar_de_baja(self, id):
        categoria = self.obtener(id)
        categoria.dar_de_baja()
        self.dao.actualizar(categoria)


class ProductoService:
    def __init__(self, dao=None, categoria_dao=None):
        self.dao = dao or ProductoDAO()
        self.categoria_dao = categoria_dao or CategoriaDAO()

    def validar_categoria(self, categoria_id):
        categoria = self.categoria_dao.obtener_por_id(categoria_id)
        if categoria is None:
            raise NoEncontrado(f"No se encontro la categoria {categoria_id}")
        if not categoria.activo:
            raise DatoInvalido(f"La categoría '{categoria.nombre}' está dada de baja")

    def crear(self, codigo, nombre, categoria_id, precio_venta, costo, stock_minimo=0):
        # Primero el dominio valida el formato, después lo que necesita la base
        producto = Producto(codigo, nombre, categoria_id, precio_venta, costo, stock_minimo)
        if self.dao.obtener_por_codigo(producto.codigo):
            raise EntidadDuplicada(f"Ya existe un producto con el código '{producto.codigo}'")
        self.validar_categoria(producto.categoria_id)
        return self.dao.crear(producto)

    def obtener(self, id):
        producto = self.dao.obtener_por_id(id)
        if producto is None:
            raise NoEncontrado(f"No se encontro el producto {id}")
        return producto

    def listar(self, categoria_id=None):
        return self.dao.listar(categoria_id=categoria_id)

    # El código no se recibe: es la identidad del producto y no se modifica
    def modificar(self, id, nombre, categoria_id, precio_venta, costo, stock_minimo):
        producto = self.obtener(id)
        producto.nombre = nombre
        producto.categoria_id = categoria_id
        producto.precio_venta = precio_venta
        producto.costo = costo
        producto.stock_minimo = stock_minimo
        self.validar_categoria(producto.categoria_id)
        return self.dao.actualizar(producto)

    def dar_de_baja(self, id):
        producto = self.obtener(id)
        producto.dar_de_baja()
        self.dao.actualizar(producto)
