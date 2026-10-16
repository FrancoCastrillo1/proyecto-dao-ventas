# DAO de los maestros: alta, baja, modificación y consultas de Producto, Categoria,
# Proveedor, Ubicacion, Sucursal y CentroDistribucion contra la base.
# Acá NO se valida el negocio, solo se lee y escribe en SQLite.
from backend.config import DB_PATH
from backend.dominio.maestros import Categoria, Producto, Proveedor, crear_ubicacion, normalizar_texto
from backend.persistencia.conexion import get_conexion

class CategoriaDAO:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    def _conn(self):
        return get_conexion(self.db_path)

    def _a_objeto(self, fila): #funcion para transformar de una fila de la db a un objeto (el famoso materializar y desmaterializar)
        return Categoria(nombre=fila["nombre"], id=fila["id"], activo=bool(fila["activo"]))

    def crear(self, categoria):
        with self._conn() as cx:
            cur = cx.execute(
                "INSERT INTO categorias (nombre, nombre_normalizado, activo) VALUES (?, ?, ?)",
                (categoria.nombre, categoria.nombre_normalizado, int(categoria.activo)),
            )
            categoria.id = cur.lastrowid
        return categoria

    def obtener_por_id(self, id):
        with self._conn() as cx:
            fila = cx.execute("SELECT * FROM categorias WHERE id = ?", (id,)).fetchone()
        return self._a_objeto(fila) if fila else None

    # Busca sin importar mayúsculas, tildes ni espacios de más
    def obtener_por_nombre(self, nombre):
        with self._conn() as cx:
            fila = cx.execute(
                "SELECT * FROM categorias WHERE nombre_normalizado = ?", (normalizar_texto(nombre),)
            ).fetchone()
        return self._a_objeto(fila) if fila else None

    def listar(self, solo_activas=True):
        sql = "SELECT * FROM categorias"
        if solo_activas:
            sql += " WHERE activo = 1"
        sql += " ORDER BY nombre"
        with self._conn() as cx:
            filas = cx.execute(sql).fetchall()
        return [self._a_objeto(f) for f in filas]

    def actualizar(self, categoria):
        with self._conn() as cx:
            cx.execute(
                "UPDATE categorias SET nombre = ?, nombre_normalizado = ?, activo = ? WHERE id = ?",
                (categoria.nombre, categoria.nombre_normalizado, int(categoria.activo), categoria.id),
            )
        return categoria


class ProductoDAO:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    def _conn(self):
        return get_conexion(self.db_path)

    def _a_objeto(self, fila):
        return Producto(
            codigo=fila["codigo"],
            nombre=fila["nombre"],
            categoria_id=fila["categoria_id"],
            precio_venta=fila["precio_venta"],
            costo=fila["costo"],
            stock_minimo=fila["stock_minimo"],
            id=fila["id"],
            activo=bool(fila["activo"]),
        )

    def crear(self, producto):
        with self._conn() as cx:
            cur = cx.execute(
                "INSERT INTO productos (codigo, nombre, categoria_id, precio_venta, costo, stock_minimo, activo) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (producto.codigo, producto.nombre, producto.categoria_id, producto.precio_venta,
                 producto.costo, producto.stock_minimo, int(producto.activo)),
            )
            producto.id = cur.lastrowid
        return producto

    def obtener_por_id(self, id):
        with self._conn() as cx:
            fila = cx.execute("SELECT * FROM productos WHERE id = ?", (id,)).fetchone()
        return self._a_objeto(fila) if fila else None

    def obtener_por_codigo(self, codigo):
        with self._conn() as cx:
            fila = cx.execute("SELECT * FROM productos WHERE codigo = ?", (codigo,)).fetchone()
        return self._a_objeto(fila) if fila else None

    def listar(self, solo_activos=True, categoria_id=None):
        sql = "SELECT * FROM productos WHERE 1 = 1"
        parametros = []
        if solo_activos:
            sql += " AND activo = 1"
        if categoria_id is not None:
            sql += " AND categoria_id = ?"
            parametros.append(categoria_id)
        sql += " ORDER BY nombre"
        with self._conn() as cx:
            filas = cx.execute(sql, parametros).fetchall()
        return [self._a_objeto(f) for f in filas]

    # El código no se actualiza: es la identidad del producto
    def actualizar(self, producto):
        with self._conn() as cx:
            cx.execute(
                "UPDATE productos SET nombre = ?, categoria_id = ?, precio_venta = ?, costo = ?, "
                "stock_minimo = ?, activo = ? WHERE id = ?",
                (producto.nombre, producto.categoria_id, producto.precio_venta, producto.costo,
                 producto.stock_minimo, int(producto.activo), producto.id),
            )
        return producto

    # Productos activos que vende un proveedor (relación producto_proveedor)
    def listar_por_proveedor(self, proveedor_id):
        with self._conn() as cx:
            filas = cx.execute(
                "SELECT p.* FROM productos p "
                "JOIN producto_proveedor pp ON pp.producto_id = p.id "
                "WHERE pp.proveedor_id = ? AND p.activo = 1 ORDER BY p.nombre",
                (proveedor_id,),
            ).fetchall()
        return [self._a_objeto(f) for f in filas]


class ProveedorDAO:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    def _conn(self):
        return get_conexion(self.db_path)

    def _a_objeto(self, fila):
        return Proveedor(
            cuit=fila["cuit"],
            razon_social=fila["razon_social"],
            telefono=fila["telefono"],
            email=fila["email"],
            id=fila["id"],
            activo=bool(fila["activo"]),
        )

    def crear(self, proveedor):
        with self._conn() as cx:
            cur = cx.execute(
                "INSERT INTO proveedores (cuit, razon_social, telefono, email, activo) VALUES (?, ?, ?, ?, ?)",
                (proveedor.cuit, proveedor.razon_social, proveedor.telefono, proveedor.email, int(proveedor.activo)),
            )
            proveedor.id = cur.lastrowid
        return proveedor

    def obtener_por_id(self, id):
        with self._conn() as cx:
            fila = cx.execute("SELECT * FROM proveedores WHERE id = ?", (id,)).fetchone()
        return self._a_objeto(fila) if fila else None

    def obtener_por_cuit(self, cuit):
        with self._conn() as cx:
            fila = cx.execute("SELECT * FROM proveedores WHERE cuit = ?", (cuit,)).fetchone()
        return self._a_objeto(fila) if fila else None

    def listar(self, solo_activos=True):
        sql = "SELECT * FROM proveedores"
        if solo_activos:
            sql += " WHERE activo = 1"
        sql += " ORDER BY razon_social"
        with self._conn() as cx:
            filas = cx.execute(sql).fetchall()
        return [self._a_objeto(f) for f in filas]

    # El CUIT no se actualiza: es la identidad del proveedor
    def actualizar(self, proveedor):
        with self._conn() as cx:
            cx.execute(
                "UPDATE proveedores SET razon_social = ?, telefono = ?, email = ?, activo = ? WHERE id = ?",
                (proveedor.razon_social, proveedor.telefono, proveedor.email, int(proveedor.activo), proveedor.id),
            )
        return proveedor

    # Proveedores activos que venden un producto (relación producto_proveedor)
    def listar_por_producto(self, producto_id):
        with self._conn() as cx:
            filas = cx.execute(
                "SELECT pr.* FROM proveedores pr "
                "JOIN producto_proveedor pp ON pp.proveedor_id = pr.id "
                "WHERE pp.producto_id = ? AND pr.activo = 1 ORDER BY pr.razon_social",
                (producto_id,),
            ).fetchall()
        return [self._a_objeto(f) for f in filas]

    def existe_asignacion(self, proveedor_id, producto_id):
        with self._conn() as cx:
            fila = cx.execute(
                "SELECT 1 FROM producto_proveedor WHERE proveedor_id = ? AND producto_id = ?",
                (proveedor_id, producto_id),
            ).fetchone()
        return fila is not None

    def asignar_producto(self, proveedor_id, producto_id):
        with self._conn() as cx:
            cx.execute(
                "INSERT INTO producto_proveedor (proveedor_id, producto_id) VALUES (?, ?)",
                (proveedor_id, producto_id),
            )

    def quitar_producto(self, proveedor_id, producto_id):
        with self._conn() as cx:
            cx.execute(
                "DELETE FROM producto_proveedor WHERE proveedor_id = ? AND producto_id = ?",
                (proveedor_id, producto_id),
            )


class UbicacionDAO:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    def _conn(self):
        return get_conexion(self.db_path)

    # La columna "tipo" decide la clase (Sucursal o CentroDistribucion)
    def _a_objeto(self, fila):
        return crear_ubicacion(
            fila["tipo"], fila["nombre"], fila["direccion"], id=fila["id"], activo=bool(fila["activo"]),
        )

    def crear(self, ubicacion):
        with self._conn() as cx:
            cur = cx.execute(
                "INSERT INTO ubicaciones (tipo, nombre, nombre_normalizado, direccion, activo) VALUES (?, ?, ?, ?, ?)",
                (ubicacion.tipo, ubicacion.nombre, ubicacion.nombre_normalizado, ubicacion.direccion, int(ubicacion.activo)),
            )
            ubicacion.id = cur.lastrowid
        return ubicacion

    def obtener_por_id(self, id):
        with self._conn() as cx:
            fila = cx.execute("SELECT * FROM ubicaciones WHERE id = ?", (id,)).fetchone()
        return self._a_objeto(fila) if fila else None

    # Busca sin importar mayúsculas, tildes ni espacios de más
    def obtener_por_nombre(self, nombre):
        with self._conn() as cx:
            fila = cx.execute(
                "SELECT * FROM ubicaciones WHERE nombre_normalizado = ?", (normalizar_texto(nombre),)
            ).fetchone()
        return self._a_objeto(fila) if fila else None

    def obtener_cd_activo(self):
        with self._conn() as cx:
            fila = cx.execute("SELECT * FROM ubicaciones WHERE tipo = 'CD' AND activo = 1").fetchone()
        return self._a_objeto(fila) if fila else None

    def listar(self, solo_activas=True, tipo=None):
        sql = "SELECT * FROM ubicaciones WHERE 1 = 1"
        parametros = []
        if solo_activas:
            sql += " AND activo = 1"
        if tipo is not None:
            sql += " AND tipo = ?"
            parametros.append(tipo)
        sql += " ORDER BY tipo, nombre"
        with self._conn() as cx:
            filas = cx.execute(sql, parametros).fetchall()
        return [self._a_objeto(f) for f in filas]

    # El tipo no se actualiza: una ubicación no cambia de clase
    def actualizar(self, ubicacion):
        with self._conn() as cx:
            cx.execute(
                "UPDATE ubicaciones SET nombre = ?, nombre_normalizado = ?, direccion = ?, activo = ? WHERE id = ?",
                (ubicacion.nombre, ubicacion.nombre_normalizado, ubicacion.direccion, int(ubicacion.activo), ubicacion.id),
            )
        return ubicacion