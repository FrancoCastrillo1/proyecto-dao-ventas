# Tests de las reglas del producto del paso 4 y de la búsqueda con filtros:
# - Dos productos ACTIVOS no se llaman igual (dominio normaliza, service
#   consulta, índice único en la base); uno dado de baja libera el nombre.
# - Un producto con stock no se da de baja (dominio con el dato, service que
#   lo cuenta, trigger en la base).
# - FiltroProductos valida los valores y el DAO filtra en SQL.
# Acá NO se prueba la api (está en test_api_productos.py).
import sqlite3

import pytest

from backend.dominio.excepciones import DatoInvalido, EntidadDuplicada, NoEncontrado
from backend.dominio.maestros import FiltroProductos, Producto
from backend.dominio.stock import TipoMovimiento
from backend.persistencia.conexion import columnas_de, crear_tablas, get_conexion
from backend.persistencia.dao_maestros import CategoriaDAO, ProductoDAO, ProveedorDAO, UbicacionDAO
from backend.persistencia.dao_stock import StockDAO
from backend.servicios.maestros_service import CategoriaService, ProductoService, ProveedorService, UbicacionService
from backend.servicios.stock_service import StockService


@pytest.fixture
def db(tmp_path):
    ruta = tmp_path / "test.db"
    crear_tablas(ruta)
    return ruta


@pytest.fixture
def red(db):
    """Dos categorías, un CD, cuatro productos y un proveedor que vende dos."""
    categorias = CategoriaService(CategoriaDAO(db))
    bebidas = categorias.crear("Bebidas")
    lacteos = categorias.crear("Lácteos")
    productos = ProductoService(ProductoDAO(db))
    coca = productos.crear("BEB-001", "Coca-Cola 500ml", bebidas.id, 1500, 900)
    agua = productos.crear("BEB-002", "Agua Mineral 1.5L", bebidas.id, 1200, 650)
    leche = productos.crear("LAC-001", "Leche Entera 1L", lacteos.id, 1400, 950)
    yogur = productos.crear("LAC-002", "Yogur Bebible", lacteos.id, 2000, 1500)
    proveedores = ProveedorService(ProveedorDAO(db), ProductoDAO(db))
    sur = proveedores.crear("20-12345678-6", "Distribuidora Sur SA")
    proveedores.asignar_producto(sur.id, coca.id)
    proveedores.asignar_producto(sur.id, agua.id)
    cd = UbicacionService(UbicacionDAO(db)).crear("CD", "CD Central", "Ruta 9")
    stock = StockService(StockDAO(db), ProductoDAO(db), UbicacionDAO(db))
    return dict(db=db, productos=productos, stock=stock, bebidas=bebidas, lacteos=lacteos, cd=cd, sur=sur,
                coca=coca, agua=agua, leche=leche, yogur=yogur)


def codigos(productos):
    return [p.codigo for p in productos]


# ===================================================== Nombre sin repetir

def test_el_nombre_normalizado_ignora_mayusculas_tildes_y_espacios():
    producto = Producto("LAC-001", "  Leche   ENTERA Lácteo ", 1, 100, 50)
    assert producto.nombre_normalizado == "leche entera lacteo"


def test_no_se_crea_un_producto_con_el_nombre_de_otro_activo(red):
    with pytest.raises(EntidadDuplicada, match=r"Ya existe el producto 'Leche Entera 1L' \(código LAC-001\)"):
        red["productos"].crear("LAC-009", "leche entera 1l", red["lacteos"].id, 1400, 950)


def test_no_se_renombra_un_producto_con_el_nombre_de_otro(red):
    with pytest.raises(EntidadDuplicada):
        red["productos"].modificar(red["agua"].id, "COCA-COLA 500ML", red["bebidas"].id, 1200, 650, 0)


def test_modificar_sin_cambiar_el_nombre_no_choca_consigo_mismo(red):
    assert red["productos"].modificar(red["agua"].id, "Agua Mineral 1.5L", red["bebidas"].id, 1300, 650, 5).precio_venta == 1300


def test_uno_dado_de_baja_libera_el_nombre_y_no_se_reactiva_si_lo_ocupan(red):
    productos = red["productos"]
    productos.dar_de_baja(red["yogur"].id)                                   # sin stock: se puede
    nuevo = productos.crear("LAC-003", "Yogur Bebible", red["lacteos"].id, 2100, 1500)
    assert nuevo.nombre == "Yogur Bebible"
    with pytest.raises(EntidadDuplicada):
        productos.reactivar(red["yogur"].id)


def test_la_base_rechaza_dos_activos_con_el_mismo_nombre_y_acepta_si_uno_esta_de_baja(red):
    with get_conexion(red["db"]) as cx:
        fila = ("BEB-099", "Agua", "agua mineral 1.5l", red["bebidas"].id, 1, 1)
        with pytest.raises(sqlite3.IntegrityError):
            cx.execute("INSERT INTO productos (codigo, nombre, nombre_normalizado, categoria_id, precio_venta, costo, activo) "
                       "VALUES (?, ?, ?, ?, ?, ?, 1)", fila)
        cx.execute("INSERT INTO productos (codigo, nombre, nombre_normalizado, categoria_id, precio_venta, costo, activo) "
                   "VALUES (?, ?, ?, ?, ?, ?, 0)", fila)                     # de baja: no cuenta


def test_migra_productos_con_nombres_repetidos_sin_romper(tmp_path):
    ruta = tmp_path / "vieja.db"
    with sqlite3.connect(ruta) as cx:   # la tabla como era antes, con dos activos que se llaman igual
        cx.execute("CREATE TABLE categorias (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL, activo INTEGER NOT NULL DEFAULT 1)")
        cx.execute("""CREATE TABLE productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT NOT NULL UNIQUE COLLATE NOCASE, nombre TEXT NOT NULL,
            categoria_id INTEGER NOT NULL, precio_venta REAL NOT NULL, costo REAL NOT NULL,
            stock_minimo INTEGER NOT NULL DEFAULT 0, activo INTEGER NOT NULL DEFAULT 1)""")
        cx.execute("INSERT INTO categorias (nombre) VALUES ('Bebidas')")
        for codigo in ("BEB-001", "BEB-002"):
            cx.execute("INSERT INTO productos (codigo, nombre, categoria_id, precio_venta, costo) VALUES (?, 'Agua', 1, 100, 50)",
                       (codigo,))

    crear_tablas(ruta)   # lo que hace la app al arrancar

    nombres = {p.codigo: p.nombre for p in ProductoDAO(ruta).listar()}
    assert nombres == {"BEB-001": "Agua", "BEB-002": "Agua (BEB-002)"}
    with get_conexion(ruta) as cx:
        assert "nombre_normalizado" in columnas_de(cx, "productos")
        assert cx.execute("SELECT 1 FROM sqlite_master WHERE name = 'productos_nombre_activo'").fetchone()


# ================================================= No dar de baja con stock

def test_el_dominio_no_da_de_baja_si_quedan_unidades():
    producto = Producto("BEB-001", "Coca", 1, 100, 50)
    with pytest.raises(DatoInvalido, match="todavía quedan 5 unidades"):
        producto.dar_de_baja(unidades_en_stock=5)
    assert producto.activo
    producto.dar_de_baja(unidades_en_stock=0)
    assert not producto.activo


def test_no_se_da_de_baja_un_producto_con_stock_en_alguna_ubicacion(red):
    red["stock"].ingresar(red["cd"].id, red["coca"].id, 30, TipoMovimiento.COMPRA, "Factura 1")
    with pytest.raises(DatoInvalido, match="todavía quedan 30 unidades"):
        red["productos"].dar_de_baja(red["coca"].id)
    assert red["productos"].obtener(red["coca"].id).activo


def test_cuando_se_vacia_el_stock_se_puede_dar_de_baja(red):
    red["stock"].ingresar(red["cd"].id, red["coca"].id, 30, TipoMovimiento.COMPRA, "Factura 1")
    red["stock"].egresar(red["cd"].id, red["coca"].id, 30, TipoMovimiento.AJUSTE, "Vencidos")
    red["productos"].dar_de_baja(red["coca"].id)
    assert not red["productos"].obtener(red["coca"].id).activo


def test_la_base_no_deja_dar_de_baja_con_stock(red):
    red["stock"].ingresar(red["cd"].id, red["coca"].id, 30, TipoMovimiento.COMPRA, "Factura 1")
    with get_conexion(red["db"]) as cx, pytest.raises(sqlite3.IntegrityError, match="todavía tiene stock"):
        cx.execute("UPDATE productos SET activo = 0 WHERE id = ?", (red["coca"].id,))   # salteando el service


# ========================================================= FiltroProductos

def test_un_filtro_vacio_no_restringe_nada():
    filtro = FiltroProductos("", "", None, "", None)
    assert (filtro.texto, filtro.categoria_id, filtro.proveedor_id, filtro.precio_desde, filtro.precio_hasta) == \
        (None, None, None, None, None)
    assert not filtro.incluir_bajas


def test_el_filtro_normaliza_el_texto_y_convierte_los_valores():
    filtro = FiltroProductos("  LÁCTEO ", "3", 2, "100", "250.5")
    assert (filtro.texto, filtro.texto_en_codigo()) == ("lacteo", "LACTEO")
    assert (filtro.categoria_id, filtro.proveedor_id, filtro.precio_desde, filtro.precio_hasta) == (3, 2, 100, 250.5)


@pytest.mark.parametrize("datos, mensaje", [
    (dict(precio_desde=500, precio_hasta=100), "«desde» no puede ser mayor"),
    (dict(precio_desde=-1), "no puede ser negativo"),
    (dict(precio_hasta="mucho"), "debe ser un número"),
    (dict(categoria_id=0), "mayor a cero"),
    (dict(proveedor_id="x"), "número entero"),
])
def test_filtros_invalidos(datos, mensaje):
    with pytest.raises(DatoInvalido, match=mensaje):
        FiltroProductos(**datos)


# ================================================================ Búsqueda

def buscar(red, **criterios):
    return codigos(red["productos"].buscar(FiltroProductos(**criterios)))


def test_buscar_sin_filtros_trae_los_activos_ordenados_por_nombre(red):
    assert buscar(red) == ["BEB-002", "BEB-001", "LAC-001", "LAC-002"]


@pytest.mark.parametrize("texto, esperados", [
    ("coca", ["BEB-001"]),            # parte del nombre
    ("LECHE entera", ["LAC-001"]),    # sin importar mayúsculas
    ("bebíble", ["LAC-002"]),         # ni tildes
    ("lac-", ["LAC-001", "LAC-002"]), # parte del código
    ("pan", []),
])
def test_buscar_por_texto_en_nombre_o_codigo(red, texto, esperados):
    assert buscar(red, texto=texto) == esperados


def test_buscar_por_categoria_y_por_proveedor(red):
    assert buscar(red, categoria_id=red["lacteos"].id) == ["LAC-001", "LAC-002"]
    assert buscar(red, proveedor_id=red["sur"].id) == ["BEB-002", "BEB-001"]


def test_buscar_por_rango_de_precio_incluye_los_extremos(red):
    assert buscar(red, precio_desde=1400) == ["BEB-001", "LAC-001", "LAC-002"]
    assert buscar(red, precio_hasta=1400) == ["BEB-002", "LAC-001"]
    assert buscar(red, precio_desde=1300, precio_hasta=1600) == ["BEB-001", "LAC-001"]


def test_los_filtros_se_combinan(red):
    assert buscar(red, texto="a", categoria_id=red["bebidas"].id, precio_hasta=1300) == ["BEB-002"]


def test_buscar_incluyendo_los_dados_de_baja(red):
    red["productos"].dar_de_baja(red["yogur"].id)
    assert "LAC-002" not in buscar(red)
    assert "LAC-002" in buscar(red, incluir_bajas=True)


@pytest.mark.parametrize("criterio", ["categoria_id", "proveedor_id"])
def test_buscar_con_una_categoria_o_proveedor_que_no_existe(red, criterio):
    with pytest.raises(NoEncontrado):
        buscar(red, **{criterio: 999})


# ================================================ Proveedores al crear el producto

def proveedores_de(red, producto_id):
    return [p.razon_social for p in ProveedorService(ProveedorDAO(red["db"]), ProductoDAO(red["db"]))
            .listar_proveedores_de_producto(producto_id)]


def test_se_crea_el_producto_con_sus_proveedores(red):
    otro = ProveedorService(ProveedorDAO(red["db"]), ProductoDAO(red["db"])).crear("30-71234567-1", "Mayorista Norte SA")
    nuevo = red["productos"].crear("BEB-010", "Soda 2L", red["bebidas"].id, 900, 500,
                                   proveedor_ids=[red["sur"].id, otro.id, red["sur"].id])   # repetido: se ignora
    assert sorted(proveedores_de(red, nuevo.id)) == ["Distribuidora Sur SA", "Mayorista Norte SA"]


def test_sin_proveedores_tambien_se_puede(red):
    nuevo = red["productos"].crear("BEB-011", "Tónica 1L", red["bebidas"].id, 900, 500)
    assert proveedores_de(red, nuevo.id) == []


def test_con_un_proveedor_que_no_existe_no_se_crea_nada(red):
    with pytest.raises(NoEncontrado, match="proveedor 999"):
        red["productos"].crear("BEB-012", "Agua con gas", red["bebidas"].id, 900, 500, proveedor_ids=[red["sur"].id, 999])
    assert ProductoDAO(red["db"]).obtener_por_codigo("BEB-012") is None


def test_con_un_proveedor_dado_de_baja_no_se_crea(red):
    ProveedorService(ProveedorDAO(red["db"]), ProductoDAO(red["db"])).dar_de_baja(red["sur"].id)
    with pytest.raises(DatoInvalido, match="está dado de baja"):
        red["productos"].crear("BEB-013", "Pomelo 1L", red["bebidas"].id, 900, 500, proveedor_ids=[red["sur"].id])
    assert ProductoDAO(red["db"]).obtener_por_codigo("BEB-013") is None
