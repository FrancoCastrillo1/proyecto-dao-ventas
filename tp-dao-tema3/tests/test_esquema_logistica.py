# Tests del esquema de logística: que las tablas se creen y que la base misma
# haga cumplir las reglas (estados válidos, historial inmutable, un pedido en
# una sola orden). Acá NO se prueban DAO ni servicios.
import sqlite3
from pathlib import Path

import pytest

ESQUEMA = Path(__file__).resolve().parent.parent / "backend" / "persistencia" / "esquema.sql"

CD, LOCAL_1, LOCAL_2 = 1, 2, 3
PRODUCTO = 1


@pytest.fixture
def con():
    conexion = sqlite3.connect(":memory:")
    conexion.execute("PRAGMA foreign_keys = ON")
    conexion.executescript(ESQUEMA.read_text(encoding="utf-8"))
    conexion.execute("INSERT INTO categorias (nombre) VALUES ('Almacen')")
    conexion.execute(
        "INSERT INTO productos (codigo, nombre, categoria_id, precio_venta, costo) "
        "VALUES ('P1', 'Yerba', 1, 100, 60)"
    )
    conexion.executemany(
        "INSERT INTO ubicaciones (tipo, nombre, direccion) VALUES (?, ?, ?)",
        [("CD", "CD Central", "Calle 1"), ("SUCURSAL", "Local 1", "Calle 2"), ("SUCURSAL", "Local 2", "Calle 3")],
    )
    yield conexion
    conexion.close()


def crear_bulto(con, estado="PREPARADO", precinto=None):
    return con.execute(
        "INSERT INTO bultos (estado, nro_precinto) VALUES (?, ?)", (estado, precinto)
    ).lastrowid


def crear_pedido(con, local=LOCAL_1):
    return con.execute("INSERT INTO pedidos_reposicion (ubicacion_id) VALUES (?)", (local,)).lastrowid


def crear_orden(con):
    return con.execute("INSERT INTO ordenes_reposicion (origen_id) VALUES (?)", (CD,)).lastrowid


def registrar_cambio(con, bulto_id):
    return con.execute(
        "INSERT INTO historial_bulto (bulto_id, fecha_hora, estado_anterior, estado_nuevo) "
        "VALUES (?, '2026-10-20 10:00:00', 'PREPARADO', 'PRECINTADO')",
        (bulto_id,),
    ).lastrowid


# ---------- las tablas existen ----------

TABLAS = [
    "pedidos_reposicion", "detalles_pedido", "ordenes_reposicion", "orden_pedido",
    "remitos", "bultos", "detalles_bulto", "historial_bulto",
]


@pytest.mark.parametrize("tabla", TABLAS)
def test_la_tabla_existe(con, tabla):
    fila = con.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (tabla,)).fetchone()
    assert fila is not None


# ---------- bultos ----------

def test_un_bulto_nuevo_nace_preparado_sin_precinto(con):
    bulto_id = crear_bulto(con)
    estado, precinto = con.execute("SELECT estado, nro_precinto FROM bultos WHERE id = ?", (bulto_id,)).fetchone()
    assert (estado, precinto) == ("PREPARADO", None)


def test_la_base_rechaza_un_estado_de_bulto_inventado(con):
    with pytest.raises(sqlite3.IntegrityError):
        crear_bulto(con, estado="INVENTADO")


def test_la_base_rechaza_un_bulto_precintado_sin_numero_de_precinto(con):
    with pytest.raises(sqlite3.IntegrityError):
        crear_bulto(con, estado="PRECINTADO", precinto=None)


def test_la_base_acepta_un_bulto_precintado_con_numero(con):
    assert crear_bulto(con, estado="PRECINTADO", precinto="PRE-001") > 0


def test_un_producto_no_se_repite_en_el_mismo_bulto(con):
    bulto_id = crear_bulto(con)
    con.execute("INSERT INTO detalles_bulto (bulto_id, producto_id, cantidad) VALUES (?, ?, 5)", (bulto_id, PRODUCTO))
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO detalles_bulto (bulto_id, producto_id, cantidad) VALUES (?, ?, 3)", (bulto_id, PRODUCTO))


def test_la_base_rechaza_cantidad_cero_en_una_linea_del_bulto(con):
    bulto_id = crear_bulto(con)
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO detalles_bulto (bulto_id, producto_id, cantidad) VALUES (?, ?, 0)", (bulto_id, PRODUCTO))


# ---------- historial inmutable ----------

def test_el_historial_acepta_nuevos_registros(con):
    assert registrar_cambio(con, crear_bulto(con)) > 0


def test_el_historial_no_se_puede_modificar(con):
    registro_id = registrar_cambio(con, crear_bulto(con))
    with pytest.raises(sqlite3.DatabaseError, match="inmutable"):
        con.execute("UPDATE historial_bulto SET estado_nuevo = 'VERIFICADO' WHERE id = ?", (registro_id,))


def test_el_historial_no_se_puede_borrar(con):
    registro_id = registrar_cambio(con, crear_bulto(con))
    with pytest.raises(sqlite3.DatabaseError, match="inmutable"):
        con.execute("DELETE FROM historial_bulto WHERE id = ?", (registro_id,))


# ---------- pedidos, órdenes y remitos ----------

def test_un_pedido_solo_puede_estar_en_una_orden(con):
    pedido_id = crear_pedido(con)
    orden_1, orden_2 = crear_orden(con), crear_orden(con)
    con.execute("INSERT INTO orden_pedido (orden_id, pedido_id) VALUES (?, ?)", (orden_1, pedido_id))
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO orden_pedido (orden_id, pedido_id) VALUES (?, ?)", (orden_2, pedido_id))


def test_un_remito_no_puede_tener_el_mismo_origen_y_destino(con):
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO remitos (origen_id, destino_id) VALUES (?, ?)", (CD, CD))


def test_un_remito_entre_el_cd_y_un_local_es_valido(con):
    assert con.execute("INSERT INTO remitos (origen_id, destino_id) VALUES (?, ?)", (CD, LOCAL_1)).lastrowid > 0