# DAO de usuarios: alta, consulta y actualización de usuarios contra la base.
# La columna "perfil" decide qué clase se arma al leer (UsuarioCD o
# UsuarioSucursal), con la fábrica crear_usuario del dominio.
# Acá NO se valida el negocio (eso lo hacen el dominio y el service) ni se
# maneja el login: solo se lee y escribe en SQLite.
from backend.config import DB_PATH
from backend.dominio.usuarios import crear_usuario
from backend.persistencia.conexion import get_conexion


class UsuarioDAO:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    def _conn(self):
        return get_conexion(self.db_path)

    def _a_objeto(self, fila):
        return crear_usuario(
            fila["perfil"], fila["nombre_usuario"], fila["nombre_completo"], fila["ubicacion_id"],
            id=fila["id"], activo=bool(fila["activo"]),
        )

    def crear(self, usuario):
        with self._conn() as cx:
            cur = cx.execute(
                "INSERT INTO usuarios (perfil, nombre_usuario, nombre_completo, ubicacion_id, activo) "
                "VALUES (?, ?, ?, ?, ?)",
                (usuario.perfil, usuario.nombre_usuario, usuario.nombre_completo, usuario.ubicacion_id,
                 int(usuario.activo)),
            )
            usuario.id = cur.lastrowid
        return usuario

    def obtener_por_id(self, id):
        with self._conn() as cx:
            fila = cx.execute("SELECT * FROM usuarios WHERE id = ?", (id,)).fetchone()
        return self._a_objeto(fila) if fila else None

    def obtener_por_nombre_usuario(self, nombre_usuario):
        with self._conn() as cx:
            fila = cx.execute(
                "SELECT * FROM usuarios WHERE nombre_usuario = ?", ((nombre_usuario or "").strip(),)
            ).fetchone()
        return self._a_objeto(fila) if fila else None

    def listar(self, solo_activos=True, ubicacion_id=None):
        sql = "SELECT * FROM usuarios WHERE 1 = 1"
        parametros = []
        if solo_activos:
            sql += " AND activo = 1"
        if ubicacion_id is not None:
            sql += " AND ubicacion_id = ?"
            parametros.append(ubicacion_id)
        sql += " ORDER BY perfil, nombre_usuario"
        with self._conn() as cx:
            filas = cx.execute(sql, parametros).fetchall()
        return [self._a_objeto(f) for f in filas]

    # El perfil y la ubicación no se actualizan: un usuario no cambia de perfil
    # ni de lugar de trabajo (igual que el tipo de una ubicación)
    def actualizar(self, usuario):
        with self._conn() as cx:
            cx.execute(
                "UPDATE usuarios SET nombre_completo = ?, activo = ? WHERE id = ?",
                (usuario.nombre_completo, int(usuario.activo), usuario.id),
            )
        return usuario
