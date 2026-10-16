# Manejo de la conexión a SQLite: abrirla, cerrarla, y crear las tablas
# a partir de esquema.sql si la base no existe.
# Acá NO van consultas de ninguna entidad, eso lo hace cada DAO.
import sqlite3

from backend.config import DB_PATH, ESQUEMA_PATH
from backend.dominio.maestros import normalizar_texto

def get_conexion(db_path= DB_PATH):
    conexion = sqlite3.connect(db_path)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion

def crear_tablas(db_path=DB_PATH):
    with get_conexion(db_path) as cx:
        migrar(cx)
        cx.executescript(ESQUEMA_PATH.read_text(encoding="utf-8"))


# Columnas que se agregaron cuando el grupo ya tenía bases creadas. CREATE TABLE
# IF NOT EXISTS no toca tablas existentes, así que si la tabla ya está pero le
# falta la columna, se agrega y se completa con los datos que ya había.
# Corre ANTES del esquema: el esquema crea índices sobre estas columnas.
COLUMNAS_NORMALIZADAS = {"categorias": "nombre", "ubicaciones": "nombre"}


def migrar(cx):
    for tabla, origen in COLUMNAS_NORMALIZADAS.items():
        columnas = [fila["name"] for fila in cx.execute(f"PRAGMA table_info({tabla})")]
        if columnas and "nombre_normalizado" not in columnas:
            cx.execute(f"ALTER TABLE {tabla} ADD COLUMN nombre_normalizado TEXT")
            for fila in cx.execute(f"SELECT id, {origen} FROM {tabla}").fetchall():
                cx.execute(
                    f"UPDATE {tabla} SET nombre_normalizado = ? WHERE id = ?",
                    (normalizar_texto(fila[origen]), fila["id"]),
                )