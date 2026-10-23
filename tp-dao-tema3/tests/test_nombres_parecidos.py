# Tests de la comparación de nombres de los maestros:
# 1) Regla: en Categorías y Ubicaciones, nombres que solo difieren en
#    mayúsculas, tildes o espacios son duplicados (409), también en la base.
# 2) Ayuda: buscar nombres parecidos para que el front pregunte "¿crear igual?".
# 3) La migración que agrega nombre_normalizado a bases creadas antes del cambio.
# Acá NO se prueba la api.
import sqlite3

import pytest

from backend.dominio.excepciones import EntidadDuplicada
from backend.dominio.maestros import Categoria, normalizar_texto, son_parecidos
from backend.persistencia.conexion import crear_tablas
from backend.persistencia.dao_maestros import CategoriaDAO, ProductoDAO, ProveedorDAO, UbicacionDAO
from backend.servicios.maestros_service import (
    CategoriaService, ProductoService, ProveedorService, UbicacionService,
)


# ------------------------------------------------------------ Normalización

@pytest.mark.parametrize("texto, esperado", [
    ("Lácteos", "lacteos"),
    ("  Lácteos   FRESCOS ", "lacteos frescos"),
    ("Pingüino", "pinguino"),
    ("PEÑA", "peña"),  # la ñ se conserva
    ("", ""),
    (None, ""),
])
def test_normalizar_texto(texto, esperado):
    assert normalizar_texto(texto) == esperado


def test_la_enie_no_se_confunde_con_la_ene():
    assert normalizar_texto("Peña") != normalizar_texto("Pena")


@pytest.mark.parametrize("a, b, parecidos", [
    ("Bebida", "Bebidas", True),
    ("Coca 500ml", "Coca 500 ml", True),
    ("Distribuidora Sur SA", "Distribuidora Sur S.A.", True),
    ("Lácteos", "lacteos", True),
    ("Coca 500ml", "Coca 1L", False),
    ("Local Centro", "Local Norte", False),
    ("Limpieza", "Bebidas", False),
])
def test_son_parecidos(a, b, parecidos):
    assert son_parecidos(a, b) is parecidos


# ------------------------------------------------- Regla: duplicados (409)

@pytest.fixture
def db(tmp_path):
    ruta = tmp_path / "test.db"
    crear_tablas(ruta)
    return ruta


@pytest.mark.parametrize("repetido", ["lacteos", "LÁCTEOS", "  Lácteos ", "Lacteos"])
def test_categoria_duplicada_ignorando_tildes_y_espacios(db, repetido):
    service = CategoriaService(CategoriaDAO(db))
    service.crear("Lácteos")
    with pytest.raises(EntidadDuplicada):
        service.crear(repetido)


def test_categorias_con_enie_y_sin_enie_son_distintas(db):
    service = CategoriaService(CategoriaDAO(db))
    service.crear("Peña")
    service.crear("Pena")
    assert len(service.listar()) == 2


def test_modificar_categoria_a_un_nombre_igual_sin_tildes_es_duplicado(db):
    service = CategoriaService(CategoriaDAO(db))
    service.crear("Lácteos")
    otra = service.crear("Bebidas")
    with pytest.raises(EntidadDuplicada):
        service.modificar(otra.id, "lacteos")


def test_ubicacion_duplicada_ignorando_tildes(db):
    service = UbicacionService(UbicacionDAO(db))
    service.crear("SUCURSAL", "Local Constitución", "Calle 1")
    with pytest.raises(EntidadDuplicada):
        service.crear("SUCURSAL", "local constitucion", "Calle 2")


def test_la_base_tambien_rechaza_duplicados_sin_tildes(db):
    CategoriaDAO(db).crear(Categoria("Lácteos"))
    with pytest.raises(sqlite3.IntegrityError):
        CategoriaDAO(db).crear(Categoria("Lacteos"))  # salteando el service


# ------------------------------------------------------- Ayuda: parecidos

def test_categorias_parecidas_sin_incluir_las_identicas(db):
    service = CategoriaService(CategoriaDAO(db))
    service.crear("Bebidas")
    service.crear("Limpieza")
    assert [c.nombre for c in service.parecidos("Bebida")] == ["Bebidas"]
    assert service.parecidos("bebidas") == []  # idéntica: eso lo frena el 409


def test_parecidos_excluye_al_que_se_esta_editando(db):
    service = CategoriaService(CategoriaDAO(db))
    bebidas = service.crear("Bebidas")
    assert service.parecidos("Bebida", excluir_id=bebidas.id) == []


def test_parecidos_no_incluye_dados_de_baja(db):
    service = CategoriaService(CategoriaDAO(db))
    bebidas = service.crear("Bebidas")
    service.dar_de_baja(bebidas.id)
    assert service.parecidos("Bebida") == []


def test_productos_parecidos_avisa_los_parecidos_pero_no_los_identicos(db):
    categoria = CategoriaService(CategoriaDAO(db)).crear("Bebidas")
    service = ProductoService(ProductoDAO(db), CategoriaDAO(db))
    service.crear("BEB-001", "Coca 500ml", categoria.id, 1500, 900)
    # El idéntico no se avisa: el alta lo rechaza (dos activos no se llaman igual)
    assert service.parecidos("COCA 500ml") == []
    assert [p.codigo for p in service.parecidos("coca 500 ml")] == ["BEB-001"]
    assert service.parecidos("Agua 1L") == []


def test_proveedores_parecidos(db):
    service = ProveedorService(ProveedorDAO(db), ProductoDAO(db))
    service.crear("20-12345678-6", "Distribuidora Sur SA")
    assert len(service.parecidos("Distribuidora Sur S.A.")) == 1
    assert service.parecidos("Mayorista Norte") == []


def test_ubicaciones_parecidas(db):
    service = UbicacionService(UbicacionDAO(db))
    service.crear("SUCURSAL", "Local Centro", "Calle 1")
    assert [u.nombre for u in service.parecidos("Local Centr")] == ["Local Centro"]
    assert service.parecidos("Local Norte") == []


# -------------------------------------------------------------- Migración

def test_migra_una_base_creada_antes_del_cambio(tmp_path):
    ruta = tmp_path / "vieja.db"
    # Tabla como estaba antes: sin nombre_normalizado, con datos cargados
    with sqlite3.connect(ruta) as cx:
        cx.execute("""CREATE TABLE categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE COLLATE NOCASE,
            activo INTEGER NOT NULL DEFAULT 1)""")
        cx.execute("INSERT INTO categorias (nombre) VALUES ('Lácteos'), ('Bebidas')")

    crear_tablas(ruta)  # lo que hace la app al arrancar

    dao = CategoriaDAO(ruta)
    assert [c.nombre for c in dao.listar()] == ["Bebidas", "Lácteos"]  # no se perdió nada
    assert dao.obtener_por_nombre("lacteos").nombre == "Lácteos"       # se completó la columna
    with pytest.raises(EntidadDuplicada):
        CategoriaService(dao).crear("LACTEOS")                         # y la regla ya funciona


def test_arrancar_dos_veces_no_rompe_nada(db):
    CategoriaService(CategoriaDAO(db)).crear("Lácteos")
    crear_tablas(db)
    assert CategoriaDAO(db).obtener_por_nombre("lacteos") is not None
