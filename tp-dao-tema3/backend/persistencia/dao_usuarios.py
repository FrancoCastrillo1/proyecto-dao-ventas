# DAO de usuarios y de sus sesiones: alta, consulta y actualización contra la
# base. La columna "perfil" decide qué clase se arma al leer (UsuarioAdministrador,
# UsuarioCD o UsuarioSucursal), con la fábrica crear_usuario del dominio.
# El hash de la contraseña y su sal se guardan y se leen acá, pero NO viajan
# dentro del objeto Usuario: solo los pide el login.
# Acá NO se valida el negocio (eso lo hacen el dominio y el service) ni se
# calcula ningún hash: solo se lee y escribe en SQLite.
from backend.dominio.usuarios import crear_usuario
from backend.persistencia.conexion import BaseDeDatos


class UsuarioDAO:
    def __init__(self, db_path=None):
        self.db_path = db_path

    def _conn(self):
        return BaseDeDatos.instancia().conexion(self.db_path)

    def _a_objeto(self, fila):
        return crear_usuario(
            fila["perfil"], fila["nombre_usuario"], fila["nombre_completo"], fila["ubicacion_id"],
            id=fila["id"], activo=bool(fila["activo"]),
        )

    def crear(self, usuario, hash_contrasena=None, sal=None):
        with self._conn() as cx:
            cur = cx.execute(
                "INSERT INTO usuarios (perfil, nombre_usuario, nombre_completo, ubicacion_id, hash_contrasena, sal, activo) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (usuario.perfil, usuario.nombre_usuario, usuario.nombre_completo, usuario.ubicacion_id,
                 hash_contrasena, sal, int(usuario.activo)),
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

    def obtener_credenciales(self, nombre_usuario):
        """(usuario, hash, sal) para el login, o None si no existe. El hash y la
        sal son None si al usuario todavía no se le puso contraseña."""
        with self._conn() as cx:
            fila = cx.execute(
                "SELECT * FROM usuarios WHERE nombre_usuario = ?", ((nombre_usuario or "").strip(),)
            ).fetchone()
        if fila is None:
            return None
        return self._a_objeto(fila), fila["hash_contrasena"], fila["sal"]

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

    def cambiar_contrasena(self, usuario_id, hash_contrasena, sal):
        with self._conn() as cx:
            cx.execute(
                "UPDATE usuarios SET hash_contrasena = ?, sal = ? WHERE id = ?",
                (hash_contrasena, sal, usuario_id),
            )


class SesionDAO:
    # Las fechas se guardan como texto ISO: así se comparan bien en SQL
    def __init__(self, db_path=None):
        self.db_path = db_path

    def crear(self, token_hash, usuario_id, vence):
        with BaseDeDatos.instancia().conexion(self.db_path) as cx:
            cx.execute(
                "INSERT INTO sesiones (token_hash, usuario_id, vence) VALUES (?, ?, ?)",
                (token_hash, usuario_id, vence.isoformat()),
            )

    def usuario_de(self, token_hash, ahora):
        """Id del usuario de una sesión que no venció, o None."""
        with BaseDeDatos.instancia().conexion(self.db_path) as cx:
            fila = cx.execute(
                "SELECT usuario_id FROM sesiones WHERE token_hash = ? AND vence > ?",
                (token_hash, ahora.isoformat()),
            ).fetchone()
        return fila["usuario_id"] if fila else None

    def borrar(self, token_hash):
        with BaseDeDatos.instancia().conexion(self.db_path) as cx:
            cx.execute("DELETE FROM sesiones WHERE token_hash = ?", (token_hash,))

    def borrar_de_usuario(self, usuario_id):
        # Al dar de baja a alguien o cambiarle la contraseña, se cierran sus sesiones
        with BaseDeDatos.instancia().conexion(self.db_path) as cx:
            cx.execute("DELETE FROM sesiones WHERE usuario_id = ?", (usuario_id,))

    def borrar_vencidas(self, ahora):
        with BaseDeDatos.instancia().conexion(self.db_path) as cx:
            cx.execute("DELETE FROM sesiones WHERE vence <= ?", (ahora.isoformat(),))
