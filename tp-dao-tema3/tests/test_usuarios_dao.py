# Tests de la persistencia de usuarios: el DAO arma la clase según el perfil,
# la base rechaza nombres de usuario repetidos y perfiles que no coinciden con
# el tipo de la ubicación (trigger), y la migración agrega usuario_id a las
# tablas de operaciones de bases creadas antes. Acá NO se prueba el service.
import sqlite3
from datetime import datetime, timedelta

import pytest

from backend.dominio.usuarios import UsuarioAdministrador, UsuarioCD, UsuarioSucursal
from backend.persistencia.conexion import TABLAS_CON_USUARIO, columnas_de, crear_tablas, get_conexion
from backend.persistencia.dao_maestros import UbicacionDAO
from backend.persistencia.dao_usuarios import SesionDAO, UsuarioDAO
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


def test_el_administrador_se_guarda_sin_ubicacion(dao):
    admin = dao.crear(UsuarioAdministrador("dora", "Dora Admin"))
    leido = dao.obtener_por_id(admin.id)
    assert type(leido) is UsuarioAdministrador
    assert leido.ubicacion_id is None


def test_las_credenciales_se_guardan_aparte_del_objeto(dao):
    beto = dao.crear(UsuarioSucursal("beto.centro", "Beto Gómez", 2), "hash1", "sal1")
    usuario, hash_contrasena, sal = dao.obtener_credenciales("BETO.centro")
    assert (usuario.id, hash_contrasena, sal) == (beto.id, "hash1", "sal1")
    assert not hasattr(usuario, "hash_contrasena")   # el objeto de dominio no lleva el hash
    dao.cambiar_contrasena(beto.id, "hash2", "sal2")
    assert dao.obtener_credenciales("beto.centro")[1:] == ("hash2", "sal2")
    assert dao.obtener_credenciales("nadie") is None


def test_un_usuario_sin_contrasena_tiene_credenciales_vacias(dao):
    dao.crear(UsuarioCD("ana.cd", "Ana López", 1))
    assert dao.obtener_credenciales("ana.cd")[1:] == (None, None)


# ---------------------------------------------------------------- Sesiones

def test_una_sesion_vale_hasta_que_vence(db, dao):
    beto = dao.crear(UsuarioSucursal("beto.centro", "Beto Gómez", 2))
    sesiones = SesionDAO(db)
    ahora = datetime(2026, 10, 23, 12, 0)
    sesiones.crear("token-hash", beto.id, ahora + timedelta(hours=8))
    assert sesiones.usuario_de("token-hash", ahora) == beto.id
    assert sesiones.usuario_de("token-hash", ahora + timedelta(hours=8)) is None   # venció
    assert sesiones.usuario_de("otro", ahora) is None


def test_cerrar_sesiones(db, dao):
    beto = dao.crear(UsuarioSucursal("beto.centro", "Beto Gómez", 2))
    sesiones = SesionDAO(db)
    ahora = datetime(2026, 10, 23, 12, 0)
    sesiones.crear("a", beto.id, ahora + timedelta(hours=1))
    sesiones.crear("b", beto.id, ahora + timedelta(hours=1))
    sesiones.crear("vieja", beto.id, ahora - timedelta(hours=1))
    sesiones.borrar("a")
    assert sesiones.usuario_de("a", ahora) is None
    sesiones.borrar_vencidas(ahora)
    sesiones.borrar_de_usuario(beto.id)
    with get_conexion(db) as cx:
        assert cx.execute("SELECT COUNT(*) FROM sesiones").fetchone()[0] == 0


# ------------------------------------------------- Red de seguridad en la base

@pytest.mark.parametrize("perfil, ubicacion_id", [
    ("ADMIN", 1),        # un administrador con ubicación
    ("CD", None),        # un usuario CD sin ubicación
    ("SUCURSAL", None),  # uno de sucursal sin ubicación
])
def test_la_base_exige_ubicacion_salvo_al_administrador(db, perfil, ubicacion_id):
    with get_conexion(db) as cx, pytest.raises(sqlite3.IntegrityError):
        cx.execute(
            "INSERT INTO usuarios (perfil, nombre_usuario, nombre_completo, ubicacion_id) VALUES (?, 'x.y', 'X', ?)",
            (perfil, ubicacion_id),
        )


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


def test_migra_la_tabla_de_usuarios_de_antes_del_login(tmp_path):
    ruta = tmp_path / "antes_del_login.db"
    crear_tablas(ruta)
    # La tabla usuarios como estaba antes: sin ADMIN, sin contraseña y con
    # ubicación obligatoria; un usuario cargado y una venta hecha por él
    with sqlite3.connect(ruta) as cx:
        cx.execute("PRAGMA foreign_keys = OFF")
        cx.execute("DROP TABLE usuarios")
        cx.execute("""CREATE TABLE usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            perfil TEXT NOT NULL CHECK (perfil IN ('CD', 'SUCURSAL')),
            nombre_usuario TEXT NOT NULL UNIQUE COLLATE NOCASE,
            nombre_completo TEXT NOT NULL,
            ubicacion_id INTEGER NOT NULL REFERENCES ubicaciones(id),
            activo INTEGER NOT NULL DEFAULT 1)""")
        cx.execute("INSERT INTO ubicaciones (tipo, nombre, nombre_normalizado, direccion) VALUES ('SUCURSAL', 'Local', 'local', 'Calle 1')")
        cx.execute("INSERT INTO usuarios (id, perfil, nombre_usuario, nombre_completo, ubicacion_id) VALUES (7, 'SUCURSAL', 'beto', 'Beto', 1)")

    crear_tablas(ruta)  # lo que hace la app al arrancar

    dao = UsuarioDAO(ruta)
    beto = dao.obtener_por_id(7)                                  # mismo id: las operaciones siguen apuntando bien
    assert (beto.nombre_usuario, beto.perfil, beto.ubicacion_id) == ("beto", "SUCURSAL", 1)
    assert dao.obtener_credenciales("beto")[1:] == (None, None)   # sin contraseña hasta que le pongan una
    assert type(dao.crear(UsuarioAdministrador("dora", "Dora"))) is UsuarioAdministrador
    with get_conexion(ruta) as cx:
        assert not columnas_de(cx, "usuarios_anterior")
        # Las tablas de operaciones siguen apuntando a "usuarios", no a la tabla vieja
        sql = cx.execute("SELECT sql FROM sqlite_master WHERE name = 'ventas'").fetchone()["sql"]
        assert "usuarios_anterior" not in sql
        with pytest.raises(sqlite3.IntegrityError, match="no corresponde"):   # los triggers volvieron
            cx.execute("INSERT INTO usuarios (perfil, nombre_usuario, nombre_completo, ubicacion_id) "
                       "VALUES ('CD', 'otro', 'Otro', 1)")


def test_arrancar_dos_veces_no_rompe_nada(db):
    crear_tablas(db)
    crear_tablas(db)
    assert UsuarioDAO(db).listar() == []
