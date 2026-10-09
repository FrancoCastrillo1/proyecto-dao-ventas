# Manejo de la conexión a SQLite: abrirla, cerrarla, y crear las tablas
# a partir de esquema.sql si la base no existe.
# Acá NO van consultas de ninguna entidad, eso lo hace cada DAO.
import sqlite3

from backend.config import DB_PATH, ESQUEMA_PATH

def get_conexion(db_path= DB_PATH):
    conexion = sqlite3.connect(db_path)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion

def crear_tablas(db_path=DB_PATH):
    with get_conexion(db_path) as cx:
        cx.executescript(ESQUEMA_PATH.read_text(encoding="utf-8"))