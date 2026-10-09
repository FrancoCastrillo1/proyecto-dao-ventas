# DAO de los maestros: alta, baja, modificación y consultas de Producto, Categoria,
# Proveedor, Ubicacion, Sucursal y CentroDistribucion contra la base.
# Acá NO se valida el negocio, solo se lee y escribe en SQLite.
from backend.config import DB_PATH
from backend.dominio.maestros import Categoria
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