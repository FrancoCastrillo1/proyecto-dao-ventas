# Casos de uso de los maestros: dar de alta/modificar/listar productos, categorías,
# proveedores, ubicaciones, sucursales y el CD.
# Acá NO va SQL (usa dao_maestros) ni nada de endpoints (eso está en api).
from backend.dominio.excepciones import DatoInvalido, EntidadDuplicada, NoEncontrado
from backend.dominio.maestros import (
    TIPOS_UBICACION, Categoria, CentroDistribucion, Producto, Proveedor, buscar_parecidos, crear_ubicacion,
)
from backend.persistencia.dao_maestros import CategoriaDAO, ProductoDAO, ProveedorDAO, UbicacionDAO


# La baja es lógica: el registro sigue existiendo y su nombre/código/CUIT sigue
# ocupado. Si el que choca está dado de baja, se avisa cómo recuperarlo en vez
# de dejar crear un duplicado.
def mensaje_duplicado(texto, existente):
    if existente.activo:
        return texto
    return f"{texto} (se dio de baja): se puede reactivar desde \"Mostrar dados de baja\""


def validar_que_este_de_baja(entidad, descripcion):
    if entidad.activo:
        raise DatoInvalido(f"No hace falta reactivar {descripcion}: no se dio de baja")

class CategoriaService:
    def __init__(self, dao=None):
        self.dao = dao or CategoriaDAO()

    def crear(self, nombre):
        categoria = Categoria(nombre)
        existente = self.dao.obtener_por_nombre(categoria.nombre)
        if existente:
            raise EntidadDuplicada(mensaje_duplicado(f"Ya existe la categoría '{existente.nombre}'", existente))
        return self.dao.crear(categoria)

    def obtener(self, id):
        categoria = self.dao.obtener_por_id(id)
        if categoria is None:
            raise NoEncontrado(f"No se encontro la categoria {id}")
        return categoria

    def listar(self, incluir_bajas=False):
        return self.dao.listar(solo_activas=not incluir_bajas)

    def modificar(self, id, nombre):
        categoria = self.obtener(id)
        categoria.nombre = nombre
        otra = self.dao.obtener_por_nombre(nombre)

        if otra and otra.id != id:
            raise EntidadDuplicada(mensaje_duplicado(f"Ya existe la categoría '{otra.nombre}'", otra))
        return self.dao.actualizar(categoria)

    def dar_de_baja(self, id):
        categoria = self.obtener(id)
        categoria.dar_de_baja()
        self.dao.actualizar(categoria)

    def reactivar(self, id):
        categoria = self.obtener(id)
        validar_que_este_de_baja(categoria, f"la categoría '{categoria.nombre}'")
        categoria.reactivar()
        return self.dao.actualizar(categoria)

    # Ayuda para el front ("¿crear igual?"), no una regla. Los idénticos no se
    # incluyen: el nombre es único y el alta ya los rechaza con un 409.
    def parecidos(self, nombre, excluir_id=None):
        return buscar_parecidos(nombre, self.dao.listar(), lambda c: c.nombre, excluir_id, incluir_iguales=False)


class ProductoService:
    def __init__(self, dao=None, categoria_dao=None, proveedor_dao=None):
        self.dao = dao or ProductoDAO()
        self.categoria_dao = categoria_dao or CategoriaDAO(self.dao.db_path)
        self.proveedor_dao = proveedor_dao or ProveedorDAO(self.dao.db_path)

    def validar_categoria(self, categoria_id):
        categoria = self.categoria_dao.obtener_por_id(categoria_id)
        if categoria is None:
            raise NoEncontrado(f"No se encontro la categoria {categoria_id}")
        if not categoria.activo:
            raise DatoInvalido(f"La categoría '{categoria.nombre}' está dada de baja")

    # Dos productos activos no pueden llamarse igual (el código ya es único)
    def validar_nombre_libre(self, producto):
        otro = self.dao.obtener_activo_por_nombre(producto.nombre_normalizado)
        if otro and otro.id != producto.id:
            raise EntidadDuplicada(f"Ya existe el producto '{otro.nombre}' (código {otro.codigo})")

    def crear(self, codigo, nombre, categoria_id, precio_venta, costo, stock_minimo=0):
        # Primero el dominio valida el formato, después lo que necesita la base
        producto = Producto(codigo, nombre, categoria_id, precio_venta, costo, stock_minimo)
        existente = self.dao.obtener_por_codigo(producto.codigo)
        if existente:
            raise EntidadDuplicada(mensaje_duplicado(f"Ya existe un producto con el código '{producto.codigo}'", existente))
        self.validar_nombre_libre(producto)
        self.validar_categoria(producto.categoria_id)
        return self.dao.crear(producto)

    def obtener(self, id):
        producto = self.dao.obtener_por_id(id)
        if producto is None:
            raise NoEncontrado(f"No se encontro el producto {id}")
        return producto

    def listar(self, categoria_id=None, incluir_bajas=False):
        return self.dao.listar(solo_activos=not incluir_bajas, categoria_id=categoria_id)

    def buscar(self, filtro):
        """filtro: FiltroProductos del dominio (ya validó los valores). Acá se
        controla lo que necesita la base: que la categoría y el proveedor existan."""
        if filtro.categoria_id is not None and self.categoria_dao.obtener_por_id(filtro.categoria_id) is None:
            raise NoEncontrado(f"No se encontro la categoria {filtro.categoria_id}")
        if filtro.proveedor_id is not None and self.proveedor_dao.obtener_por_id(filtro.proveedor_id) is None:
            raise NoEncontrado(f"No se encontro el proveedor {filtro.proveedor_id}")
        return self.dao.buscar(filtro)

    # El código no se recibe: es la identidad del producto y no se modifica
    def modificar(self, id, nombre, categoria_id, precio_venta, costo, stock_minimo):
        producto = self.obtener(id)
        producto.nombre = nombre
        producto.categoria_id = categoria_id
        producto.precio_venta = precio_venta
        producto.costo = costo
        producto.stock_minimo = stock_minimo
        if producto.activo:
            self.validar_nombre_libre(producto)
        self.validar_categoria(producto.categoria_id)
        return self.dao.actualizar(producto)

    # El dominio decide si se puede (sin stock); acá se cuenta cuánto queda
    def dar_de_baja(self, id):
        producto = self.obtener(id)
        producto.dar_de_baja(self.dao.unidades_en_stock(producto.id))
        self.dao.actualizar(producto)

    # No se reactiva un producto cuya categoría sigue dada de baja, ni uno cuyo
    # nombre ya lo usa otro producto activo
    def reactivar(self, id):
        producto = self.obtener(id)
        validar_que_este_de_baja(producto, f"el producto '{producto.nombre}'")
        self.validar_categoria(producto.categoria_id)
        self.validar_nombre_libre(producto)
        producto.reactivar()
        return self.dao.actualizar(producto)

    # Los idénticos no se avisan: el alta ya los rechaza con un 409
    def parecidos(self, nombre, excluir_id=None):
        return buscar_parecidos(nombre, self.dao.listar(), lambda p: p.nombre, excluir_id, incluir_iguales=False)


class ProveedorService:
    def __init__(self, dao=None, producto_dao=None):
        self.dao = dao or ProveedorDAO()
        self.producto_dao = producto_dao or ProductoDAO()

    def crear(self, cuit, razon_social, telefono=None, email=None):
        proveedor = Proveedor(cuit, razon_social, telefono, email)
        existente = self.dao.obtener_por_cuit(proveedor.cuit)
        if existente:
            raise EntidadDuplicada(mensaje_duplicado(
                f"Ya existe el proveedor '{existente.razon_social}' con el CUIT {proveedor.cuit_formateado}", existente,
            ))
        return self.dao.crear(proveedor)

    def obtener(self, id):
        proveedor = self.dao.obtener_por_id(id)
        if proveedor is None:
            raise NoEncontrado(f"No se encontro el proveedor {id}")
        return proveedor

    def listar(self, incluir_bajas=False):
        return self.dao.listar(solo_activos=not incluir_bajas)

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

    def reactivar(self, id):
        proveedor = self.obtener(id)
        validar_que_este_de_baja(proveedor, f"el proveedor '{proveedor.razon_social}'")
        proveedor.reactivar()
        return self.dao.actualizar(proveedor)

    # La razón social puede repetirse (lo identifica el CUIT): los idénticos también se avisan
    def parecidos(self, razon_social, excluir_id=None):
        return buscar_parecidos(razon_social, self.dao.listar(), lambda p: p.razon_social, excluir_id)

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


class UbicacionService:
    def __init__(self, dao=None):
        self.dao = dao or UbicacionDAO()

    def validar_nombre_libre(self, nombre, id_propio=None):
        otra = self.dao.obtener_por_nombre(nombre)
        if otra and otra.id != id_propio:
            raise EntidadDuplicada(mensaje_duplicado(f"Ya existe una ubicación llamada '{otra.nombre}'", otra))

    def crear(self, tipo, nombre, direccion):
        ubicacion = crear_ubicacion(tipo, nombre, direccion)
        self.validar_nombre_libre(ubicacion.nombre)
        # La consigna describe un único CD central. Se valida por lo que la
        # ubicación ES (isinstance), no por lo que puede hacer.
        if isinstance(ubicacion, CentroDistribucion) and self.dao.obtener_cd_activo():
            raise EntidadDuplicada("Ya existe un Centro de Distribución activo")
        return self.dao.crear(ubicacion)

    def obtener(self, id):
        ubicacion = self.dao.obtener_por_id(id)
        if ubicacion is None:
            raise NoEncontrado(f"No se encontro la ubicación {id}")
        return ubicacion

    def listar(self, tipo=None, incluir_bajas=False):
        if tipo is not None:
            tipo = tipo.strip().upper()
            if tipo not in TIPOS_UBICACION:
                raise DatoInvalido(f"Tipo de ubicación '{tipo}' inválido. Opciones: {', '.join(TIPOS_UBICACION)}")
        return self.dao.listar(solo_activas=not incluir_bajas, tipo=tipo)

    def obtener_cd(self):
        cd = self.dao.obtener_cd_activo()
        if cd is None:
            raise NoEncontrado("No hay un Centro de Distribución activo")
        return cd

    # El tipo no se recibe: una ubicación no cambia de clase
    def modificar(self, id, nombre, direccion):
        ubicacion = self.obtener(id)
        ubicacion.nombre = nombre
        ubicacion.direccion = direccion
        self.validar_nombre_libre(ubicacion.nombre, id_propio=id)
        return self.dao.actualizar(ubicacion)

    def dar_de_baja(self, id):
        ubicacion = self.obtener(id)
        ubicacion.dar_de_baja()
        self.dao.actualizar(ubicacion)

    # Reactivar un CD respeta la misma regla que crearlo: un solo CD activo
    def reactivar(self, id):
        ubicacion = self.obtener(id)
        validar_que_este_de_baja(ubicacion, f"la ubicación '{ubicacion.nombre}'")
        if isinstance(ubicacion, CentroDistribucion) and self.dao.obtener_cd_activo():
            raise EntidadDuplicada("Ya existe un Centro de Distribución activo: dalo de baja antes de reactivar este")
        ubicacion.reactivar()
        return self.dao.actualizar(ubicacion)

    # El nombre es único: los idénticos no se incluyen, el alta los rechaza con un 409
    def parecidos(self, nombre, excluir_id=None):
        return buscar_parecidos(nombre, self.dao.listar(), lambda u: u.nombre, excluir_id, incluir_iguales=False)
