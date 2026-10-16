# Casos de uso de los maestros: dar de alta/modificar/listar productos, categorías,
# proveedores, ubicaciones, sucursales y el CD.
# Acá NO va SQL (usa dao_maestros) ni nada de endpoints (eso está en api).
from backend.dominio.excepciones import DatoInvalido, EntidadDuplicada, NoEncontrado
from backend.dominio.maestros import Categoria, Producto, Proveedor
from backend.persistencia.dao_maestros import CategoriaDAO, ProductoDAO, ProveedorDAO

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


class ProveedorService:
    def __init__(self, dao=None, producto_dao=None):
        self.dao = dao or ProveedorDAO()
        self.producto_dao = producto_dao or ProductoDAO()

    def crear(self, cuit, razon_social, telefono=None, email=None):
        proveedor = Proveedor(cuit, razon_social, telefono, email)
        if self.dao.obtener_por_cuit(proveedor.cuit):
            raise EntidadDuplicada(f"Ya existe un proveedor con el CUIT {proveedor.cuit_formateado}")
        return self.dao.crear(proveedor)

    def obtener(self, id):
        proveedor = self.dao.obtener_por_id(id)
        if proveedor is None:
            raise NoEncontrado(f"No se encontro el proveedor {id}")
        return proveedor

    def listar(self):
        return self.dao.listar()

    # El CUIT no se recibe: es la identidad del proveedor y no se modifica
    def modificar(self, id, razon_social, telefono=None, email=None):
        proveedor = self.obtener(id)
        proveedor.razon_social = razon_social
        proveedor.telefono = telefono
        proveedor.email = email
        return self.dao.actualizar(proveedor)

    def dar_de_baja(self, id):
        proveedor = self.obtener(id)
        proveedor.dar_de_baja()
        self.dao.actualizar(proveedor)

    # ---- Relación con productos

    def obtener_activo(self, id):
        proveedor = self.obtener(id)
        if not proveedor.activo:
            raise DatoInvalido(f"El proveedor '{proveedor.razon_social}' está dado de baja")
        return proveedor

    def obtener_producto_activo(self, producto_id):
        producto = self.producto_dao.obtener_por_id(producto_id)
        if producto is None:
            raise NoEncontrado(f"No se encontro el producto {producto_id}")
        if not producto.activo:
            raise DatoInvalido(f"El producto '{producto.nombre}' está dado de baja")
        return producto

    def asignar_producto(self, proveedor_id, producto_id):
        proveedor = self.obtener_activo(proveedor_id)
        producto = self.obtener_producto_activo(producto_id)
        if self.dao.existe_asignacion(proveedor_id, producto_id):
            raise EntidadDuplicada(f"'{proveedor.razon_social}' ya provee el producto '{producto.nombre}'")
        self.dao.asignar_producto(proveedor_id, producto_id)

    def quitar_producto(self, proveedor_id, producto_id):
        if not self.dao.existe_asignacion(proveedor_id, producto_id):
            raise NoEncontrado(f"El proveedor {proveedor_id} no provee el producto {producto_id}")
        self.dao.quitar_producto(proveedor_id, producto_id)

    def listar_productos(self, proveedor_id):
        self.obtener(proveedor_id)
        return self.producto_dao.listar_por_proveedor(proveedor_id)

    def listar_proveedores_de_producto(self, producto_id):
        if self.producto_dao.obtener_por_id(producto_id) is None:
            raise NoEncontrado(f"No se encontro el producto {producto_id}")
        return self.dao.listar_por_producto(producto_id)
