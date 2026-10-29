# Tests del patrón Singleton de la conexión (persistencia/conexion.py): que
# haya una sola BaseDeDatos, que entregue conexiones configuradas siempre igual
# y que cada operación tenga su propia conexión.
import sqlite3
import threading

import pytest

from backend.config import DB_PATH
from backend.persistencia.conexion import BaseDeDatos, crear_tablas, get_conexion
from backend.persistencia.dao_maestros import CategoriaDAO
from backend.persistencia.dao_ventas import VentaDAO


def test_siempre_es_la_misma_instancia():
    assert BaseDeDatos() is BaseDeDatos()
    assert BaseDeDatos.instancia() is BaseDeDatos()


def test_tampoco_se_duplica_si_la_piden_varios_hilos_a_la_vez():
    vistas = []
    hilos = [threading.Thread(target=lambda: vistas.append(BaseDeDatos.instancia())) for _ in range(20)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    assert len({id(instancia) for instancia in vistas}) == 1


def test_sabe_donde_esta_la_base_de_la_app():
    assert BaseDeDatos.instancia().ruta == DB_PATH


def test_cada_conexion_sale_configurada_igual(tmp_path):
    with BaseDeDatos.instancia().conexion(tmp_path / "x.db") as cx:
        assert cx.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        fila = cx.execute("SELECT 1 AS uno").fetchone()
        assert fila["uno"] == 1          # las filas se leen por nombre de columna


def test_cada_operacion_tiene_su_propia_conexion(tmp_path):
    # Lo que hay una sola vez es la BaseDeDatos, no la conexión: si fuera una
    # sola, las transacciones de dos pedidos simultáneos se mezclarían
    base = BaseDeDatos.instancia()
    assert base.conexion(tmp_path / "x.db") is not base.conexion(tmp_path / "x.db")


def test_la_transaccion_deshace_todo_si_algo_falla(tmp_path):
    ruta = tmp_path / "t.db"
    base = BaseDeDatos.instancia()
    base.crear_tablas(ruta)
    with pytest.raises(sqlite3.IntegrityError):
        with base.transaccion(ruta) as cx:
            cx.execute("INSERT INTO categorias (nombre, nombre_normalizado) VALUES ('Bebidas', 'bebidas')")
            cx.execute("INSERT INTO categorias (nombre, nombre_normalizado) VALUES ('Bebidas', 'bebidas')")  # repetida
    assert CategoriaDAO(ruta).listar() == []


def test_los_daos_usan_la_base_de_la_app_si_no_se_les_dice_otra():
    assert VentaDAO().db_path is None     # la ruta la pone la BaseDeDatos al conectar


def test_los_atajos_pasan_por_la_misma_instancia(tmp_path):
    ruta = tmp_path / "a.db"
    crear_tablas(ruta)
    with get_conexion(ruta) as cx:
        tablas = {fila["name"] for fila in cx.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"productos", "ventas", "remitos"} <= tablas
