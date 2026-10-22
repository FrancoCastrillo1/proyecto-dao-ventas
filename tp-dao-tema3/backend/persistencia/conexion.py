# Manejo de la conexión a SQLite: abrirla, cerrarla, y crear las tablas
# a partir de esquema.sql si la base no existe.
# Acá NO van consultas de ninguna entidad, eso lo hace cada DAO.
import sqlite3
from contextlib import contextmanager

from backend.config import DB_PATH, ESQUEMA_PATH
from backend.dominio.maestros import normalizar_texto

def get_conexion(db_path= DB_PATH):
    conexion = sqlite3.connect(db_path)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


# Para operaciones que tocan varias filas y tienen que guardarse todas juntas o
# ninguna (un despacho descuenta varios productos y cambia el estado del bulto).
# Quien la abre le pasa la conexión a cada DAO; si algo falla adentro del with,
# se deshace todo. BEGIN IMMEDIATE toma el permiso de escritura desde el
# principio: así dos pedidos simultáneos no leen la misma cantidad y uno pisa
# lo que guardó el otro.
@contextmanager
def transaccion(db_path=DB_PATH):
    cx = get_conexion(db_path)
    try:
        with cx:  # commit si sale bien, rollback si hubo una excepción
            cx.execute("BEGIN IMMEDIATE")
            yield cx
    finally:
        cx.close()

def crear_tablas(db_path=DB_PATH):
    with get_conexion(db_path) as cx:
        migrar(cx)
        cx.executescript(ESQUEMA_PATH.read_text(encoding="utf-8"))
        completar_migracion(cx)


# Columnas que se agregaron cuando el grupo ya tenía bases creadas. CREATE TABLE
# IF NOT EXISTS no toca tablas existentes, así que si la tabla ya está pero le
# falta la columna, se agrega y se completa con los datos que ya había.
# Corre ANTES del esquema: el esquema crea índices sobre estas columnas.
COLUMNAS_NORMALIZADAS = {"categorias": "nombre", "ubicaciones": "nombre"}

# Tablas de operaciones que registran QUIÉN las hizo. Las filas que ya existían
# quedan con usuario_id vacío: se hicieron antes de que hubiera usuarios.
TABLAS_CON_USUARIO = [
    "pedidos_reposicion", "ordenes_reposicion", "remitos", "historial_bultos",
    "movimientos_stock", "ventas", "devoluciones",
]


def columnas_de(cx, tabla):
    # Vacío si la tabla todavía no existe (base nueva: la crea el esquema)
    return [fila["name"] for fila in cx.execute(f"PRAGMA table_info({tabla})")]


TRIGGERS_DE_USUARIOS = ["usuarios_perfil_segun_ubicacion_alta", "usuarios_perfil_segun_ubicacion_cambio"]


def migrar(cx):
    # La tabla usuarios de antes del login no admitía administradores (sin
    # ubicación) ni guardaba la contraseña. SQLite no deja cambiar un CHECK ni
    # un NOT NULL, así que se aparta la tabla vieja, el esquema crea la nueva y
    # completar_migracion copia los datos. Va primero: los PRAGMA no tienen
    # efecto dentro de una transacción, y lo de abajo abre una.
    columnas = columnas_de(cx, "usuarios")
    if columnas and "hash_contrasena" not in columnas:
        cx.execute("PRAGMA foreign_keys = OFF")     # las operaciones apuntan a usuarios(id)
        cx.execute("PRAGMA legacy_alter_table = ON")  # que esas referencias no se muden a la tabla vieja
        cx.execute("ALTER TABLE usuarios RENAME TO usuarios_anterior")
        for trigger in TRIGGERS_DE_USUARIOS:          # se mudaron con la tabla; el esquema los recrea
            cx.execute(f"DROP TRIGGER IF EXISTS {trigger}")

    for tabla in TABLAS_CON_USUARIO:
        columnas = columnas_de(cx, tabla)
        if columnas and "usuario_id" not in columnas:
            cx.execute(f"ALTER TABLE {tabla} ADD COLUMN usuario_id INTEGER REFERENCES usuarios(id)")

    for tabla, origen in COLUMNAS_NORMALIZADAS.items():
        columnas = columnas_de(cx, tabla)
        if columnas and "nombre_normalizado" not in columnas:
            cx.execute(f"ALTER TABLE {tabla} ADD COLUMN nombre_normalizado TEXT")
            for fila in cx.execute(f"SELECT id, {origen} FROM {tabla}").fetchall():
                cx.execute(
                    f"UPDATE {tabla} SET nombre_normalizado = ? WHERE id = ?",
                    (normalizar_texto(fila[origen]), fila["id"]),
                )


def completar_migracion(cx):
    # Segunda mitad de la reconstrucción de usuarios (ver migrar): los usuarios
    # viejos pasan con su mismo id, así las operaciones siguen apuntando bien.
    # Quedan sin contraseña: no entran hasta que un administrador les ponga una.
    if columnas_de(cx, "usuarios_anterior"):
        cx.execute(
            "INSERT INTO usuarios (id, perfil, nombre_usuario, nombre_completo, ubicacion_id, activo) "
            "SELECT id, perfil, nombre_usuario, nombre_completo, ubicacion_id, activo FROM usuarios_anterior"
        )
        cx.execute("DROP TABLE usuarios_anterior")
        cx.commit()
        cx.execute("PRAGMA foreign_keys = ON")