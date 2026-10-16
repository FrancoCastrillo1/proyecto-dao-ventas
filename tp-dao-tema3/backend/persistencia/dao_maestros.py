# DAO de los maestros: alta, baja, modificación y consultas de Producto, Categoria,
# Proveedor, Ubicacion, Sucursal y CentroDistribucion contra la base.
# Acá NO se valida el negocio, solo se lee y escribe en SQLite.
from backend.config import DB_PATH
from backend.dominio.maestros import Categoria, Producto
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
            cur = cx.execute("INSERT INTO categorias (nombre,activo) VALUES (?, ?)", (categoria.nombre, int(categoria.activo)),)
            categoria.id = cur.lastrowid
        return categoria

    def obtener_por_id(self, id):
        with self._conn() as cx:
            fila = cx.execute("SELECT * FROM categorias WHERE id = ?", (id,)).fetchone()
        return self._a_objeto(fila) if fila else None

    def obtener_por_nombre(self, nombre):
        with self._conn() as cx:
            fila = cx.execute("SELECT * FROM categorias WHERE nombre = ?", (nombre,)).fetchone()
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
                "UPDATE categorias SET nombre = ?, activo = ? WHERE id = ?",
                (categoria.nombre, int(categoria.activo), categoria.id),
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