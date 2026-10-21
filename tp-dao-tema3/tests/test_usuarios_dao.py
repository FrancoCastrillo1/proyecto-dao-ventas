# Tests de la persistencia de usuarios: el DAO arma la clase según el perfil,
# la base rechaza nombres de usuario repetidos y perfiles que no coinciden con
# el tipo de la ubicación (trigger), y la migración agrega usuario_id a las
# tablas de operaciones de bases creadas antes. Acá NO se prueba el service.
import sqlite3

import pytest

from backend.dominio.usuarios import UsuarioCD, UsuarioSucursal
from backend.persistencia.conexion import TABLAS_CON_USUARIO, columnas_de, crear_tablas, get_conexion
from backend.persistencia.dao_maestros import UbicacionDAO
from backend.persistencia.dao_usuarios import UsuarioDAO
from backend.servicios.maestros_service import UbicacionService


@pytest.fixture
def db(tmp_path):
    ruta = tmp_path / "test.db"
    crear_tablas(ruta)
    ubicaciones = UbicacionService(UbicacionDAO(ruta))
    ubicaciones.crear("CD", "CD Central", "Ruta 9")          # id 1
    ubicaciones.crear("SUCURSAL", "Local Centro", "Calle 1")  # id 2
    ubicaciones.crear("SUCURSAL", "Local Norte", "Calle 2")   # id 3
    return ruta


@pytest.fixture
def dao(db):
    return UsuarioDAO(db)


# -------------------------------------------------------------------- DAO

def test_crear_y_leer_arma_la_clase_segun_el_perfil(dao):
    cd = dao.crear(UsuarioCD("ana.cd", "Ana López", 1))
    local = dao.crear(UsuarioSucursal("beto.centro", "Beto Gómez", 2))
    assert type(dao.obtener_por_id(cd.id)) is UsuarioCD
    leido = dao.obtener_por_id(local.id)
    assert type(leido) is UsuarioSucursal
    assert (leido.nombre_usuario, leido.nombre_completo, leido.ubicacion_id) == ("beto.centro", "Beto Gómez", 2)


def test_buscar_por_nombre_de_usuario_sin_importar_mayusculas(dao):
    dao.crear(UsuarioSucursal("beto.centro", "Beto Gómez", 2))
    assert dao.obtener_por_nombre_usuario(" Beto.Centro ").nombre_usuario == "beto.centro"
    assert dao.obtener_por_nombre_usuario("nadie") is None


def test_listar_solo_activos_y_por_ubicacion(dao):
    dao.crear(UsuarioCD("ana.cd", "Ana López", 1))
    dao.crear(UsuarioSucursal("beto.centro", "Beto Gómez", 2))
    carla = dao.crear(UsuarioSucursal("carla.norte", "Carla Díaz", 3))
    carla.dar_de_baja()
    dao.actualizar(carla)
    assert [u.nombre_usuario for u in dao.listar()] == ["ana.cd", "beto.centro"]
    assert len(dao.listar(solo_activos=False)) == 3
    assert [u.nombre_usuario for u in dao.listar(solo_activos=False, ubicacion_id=3)] == ["carla.norte"]


def test_actualizar_guarda_nombre_y_baja_pero_no_cambia_perfil_ni_ubicacion(dao):
    beto = dao.crear(UsuarioSucursal("beto.centro", "Beto Gómez", 2))
    beto.nombre_completo = "Roberto Gómez"
    beto.dar_de_baja()
    dao.actualizar(beto)
    leido = dao.obtener_por_id(beto.id)
    assert (leido.nombre_completo, leido.activo, leido.ubicacion_id, leido.perfil) == \
        ("Roberto Gómez", False, 2, "SUCURSAL")


# ------------------------------------------------- Red de seguridad en la base

def test_la_base_rechaza_nombres_de_usuario_repetidos(dao):
    dao.crear(UsuarioSucursal("beto.centro", "Beto Gómez", 2))
    with pytest.raises(sqlite3.IntegrityError):
        dao.crear(UsuarioSucursal("beto.centro", "Otro Beto", 3))


@pytest.mark.parametrize("usuario", [
    UsuarioCD("ana.cd", "Ana López", 2),              # usuario CD en un local
    UsuarioSucursal("beto.centro", "Beto Gómez", 1),  # usuario de sucursal en el CD
])
def test_la_base_rechaza_perfil_que_no_coincide_con_la_ubicacion(dao, usuario):
    with pytest.raises(sqlite3.IntegrityError, match="no corresponde"):
        dao.crear(usuario)  # salteando el service


def test_la_base_rechaza_mover_un_usuario_a_una_ubicacion_incompatible(db, dao):
    beto = dao.crear(UsuarioSucursal("beto.centro", "Beto Gómez", 2))
    with get_conexion(db) as cx:
        cx.execute("UPDATE usuarios SET ubicacion_id = 3 WHERE id = ?", (beto.id,))  # otro local: ok
        with pytest.raises(sqlite3.IntegrityError, match="no corresponde"):
            cx.execute("UPDATE usuarios SET ubicacion_id = 1 WHERE id = ?", (beto.id,))  # al CD: no


def test_la_base_rechaza_una_ubicacion_inexistente(dao):
    with pytest.raises(sqlite3.IntegrityError):
        dao.crear(UsuarioSucursal("beto.centro", "Beto Gómez", 99))


# --------------------------------------------------------------- Migración

def test_una_base_nueva_tiene_usuario_id_en_todas_las_operaciones(db):
    with get_conexion(db) as cx:
        for tabla in TABLAS_CON_USUARIO:
            assert "usuario_id" in columnas_de(cx, tabla), tabla


def test_migra_tablas_creadas_antes_de_que_hubiera_usuarios(tmp_path):
    ruta = tmp_path / "vieja.db"
    # Dos tablas como estaban antes, con un dato cargado
    with sqlite3.connect(ruta) as cx:
        cx.execute("""CREATE TABLE pedidos_reposicion (
            id INTEGER PRIMARY KEY AUTOINCREMENT, sucursal_id INTEGER NOT NULL,
            fecha TEXT NOT NULL, estado TEXT NOT NULL, orden_id INTEGER)""")
        cx.execute("""CREATE TABLE movimientos_stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT, stock_id INTEGER NOT NULL, fecha TEXT NOT NULL,
            cantidad INTEGER NOT NULL, tipo TEXT NOT NULL, referencia TEXT NOT NULL DEFAULT '')""")
        cx.execute("INSERT INTO pedidos_reposicion (sucursal_id, fecha, estado) VALUES (2, '2026-10-01', 'PENDIENTE')")

    crear_tablas(ruta)  # lo que hace la app al arrancar

    with get_conexion(ruta) as cx:
        for tabla in ("pedidos_reposicion", "movimientos_stock"):
            assert "usuario_id" in columnas_de(cx, tabla), tabla
        fila = cx.execute("SELECT estado, usuario_id FROM pedidos_reposicion").fetchone()
    assert (fila["estado"], fila["usuario_id"]) == ("PENDIENTE", None)  # el dato viejo sigue, sin usuario


def test_arrancar_dos_veces_no_rompe_nada(db):
    crear_tablas(db)
    crear_tablas(db)
    assert UsuarioDAO(db).listar() == []
