# Tests del service de stock contra un SQLite temporal por test (tmp_path):
# que ingresar y egresar se guarden en la base con su movimiento, que cada
# movimiento vaya a la ubicación que corresponde y que una operación con varios
# movimientos se guarde toda junta o nada. Acá NO se prueba la api.
from datetime import datetime, timedelta

import pytest

from backend.dominio.excepciones import DatoInvalido, NoEncontrado, StockInsuficiente
from backend.dominio.maestros import Categoria, CentroDistribucion, Producto, Sucursal
from backend.dominio.stock import TipoMovimiento
from backend.persistencia.conexion import crear_tablas
from backend.persistencia.dao_maestros import CategoriaDAO, ProductoDAO, UbicacionDAO
from backend.persistencia.dao_stock import StockDAO
from backend.servicios.stock_service import StockService

COMPRA = TipoMovimiento.COMPRA
DESPACHO = TipoMovimiento.DESPACHO
RECEPCION = TipoMovimiento.RECEPCION
VENTA = TipoMovimiento.VENTA


@pytest.fixture
def db(tmp_path):
    ruta = tmp_path / "test.db"
    crear_tablas(ruta)
    return ruta


@pytest.fixture
def service(db):
    return StockService(StockDAO(db), ProductoDAO(db), UbicacionDAO(db))


@pytest.fixture
def datos(db):
    """Un CD, una sucursal y dos productos (uno con mínimo 10)."""
    categoria = CategoriaDAO(db).crear(Categoria("Bebidas"))
    productos = ProductoDAO(db)
    coca = productos.crear(Producto("BEB-001", "Coca 500ml", categoria.id, 1500, 900, stock_minimo=10))
    agua = productos.crear(Producto("BEB-002", "Agua 1L", categoria.id, 800, 400))
    ubicaciones = UbicacionDAO(db)
    cd = ubicaciones.crear(CentroDistribucion("CD Central", "Ruta 9 km 5"))
    local = ubicaciones.crear(Sucursal("Local Centro", "San Martín 100"))
    return {"coca": coca.id, "agua": agua.id, "cd": cd.id, "local": local.id}


# ------------------------------------------------------- Ingresar y egresar

def test_un_par_sin_movimientos_tiene_cantidad_cero_y_el_minimo_del_producto(service, datos):
    stock = service.obtener(datos["cd"], datos["coca"])
    assert (stock.cantidad, stock.stock_minimo, stock.id) == (0, 10, None)


def test_la_compra_al_cd_queda_guardada_con_su_movimiento(service, datos):
    service.ingresar(datos["cd"], datos["coca"], 50, COMPRA, "  Factura A-0001  ")

    assert service.obtener(datos["cd"], datos["coca"]).cantidad == 50
    [movimiento] = service.listar_movimientos(datos["cd"], datos["coca"])
    assert (movimiento.cantidad, movimiento.tipo, movimiento.referencia) == (50, COMPRA, "Factura A-0001")


def test_la_fecha_del_movimiento_es_la_hora_local(service, datos):
    service.ingresar(datos["cd"], datos["coca"], 5, COMPRA)
    [movimiento] = service.listar_movimientos(datos["cd"], datos["coca"])
    assert abs(datetime.now() - movimiento.fecha) < timedelta(seconds=5)


def test_varios_movimientos_se_acumulan_y_la_cantidad_es_la_suma_del_libro(service, datos):
    service.ingresar(datos["cd"], datos["coca"], 50, COMPRA)
    service.egresar(datos["cd"], datos["coca"], 20, DESPACHO, "Bulto 1")
    service.ingresar(datos["cd"], datos["coca"], 5, COMPRA)

    movimientos = service.listar_movimientos(datos["cd"], datos["coca"])
    assert [m.cantidad for m in movimientos] == [50, -20, 5]
    assert service.obtener(datos["cd"], datos["coca"]).cantidad == sum(m.cantidad for m in movimientos) == 35


def test_egresar_mas_de_lo_que_hay_no_modifica_la_base(service, datos):
    service.ingresar(datos["cd"], datos["coca"], 10, COMPRA)
    with pytest.raises(StockInsuficiente):
        service.egresar(datos["cd"], datos["coca"], 11, DESPACHO)

    assert service.obtener(datos["cd"], datos["coca"]).cantidad == 10
    assert len(service.listar_movimientos(datos["cd"], datos["coca"])) == 1


def test_cada_ubicacion_tiene_su_propio_stock(service, datos):
    service.ingresar(datos["cd"], datos["coca"], 30, COMPRA)
    service.ingresar(datos["local"], datos["coca"], 4, RECEPCION, "Bulto 1")
    assert service.obtener(datos["cd"], datos["coca"]).cantidad == 30
    assert service.obtener(datos["local"], datos["coca"]).cantidad == 4


# -------------------------------------------- Qué movimiento va en cada lugar

def test_no_se_puede_comprar_directo_a_una_sucursal(service, datos):
    # Si se pudiera, entraría stock vendible al local sin pasar por un bulto verificado
    with pytest.raises(DatoInvalido):
        service.ingresar(datos["local"], datos["coca"], 10, COMPRA)
    assert service.obtener(datos["local"], datos["coca"]).cantidad == 0


@pytest.mark.parametrize("ubicacion, tipo, ingreso", [
    ("cd", RECEPCION, True), ("cd", VENTA, False), ("local", DESPACHO, False),
])
def test_movimientos_en_la_ubicacion_equivocada(service, datos, ubicacion, tipo, ingreso):
    mover = service.ingresar if ingreso else service.egresar
    with pytest.raises(DatoInvalido):
        mover(datos[ubicacion], datos["coca"], 1, tipo)


def test_no_se_compra_un_producto_dado_de_baja(db, service, datos):
    productos = ProductoDAO(db)
    coca = productos.obtener_por_id(datos["coca"])
    coca.dar_de_baja()
    productos.actualizar(coca)
    with pytest.raises(DatoInvalido):
        service.ingresar(datos["cd"], datos["coca"], 10, COMPRA)


def test_no_se_mueve_stock_en_una_ubicacion_dada_de_baja(db, service, datos):
    ubicaciones = UbicacionDAO(db)
    cd = ubicaciones.obtener_por_id(datos["cd"])
    cd.dar_de_baja()
    ubicaciones.actualizar(cd)
    with pytest.raises(DatoInvalido):
        service.ingresar(datos["cd"], datos["coca"], 10, COMPRA)


@pytest.mark.parametrize("ubicacion_id, producto_id", [(999, None), (None, 999)])
def test_producto_o_ubicacion_inexistentes(service, datos, ubicacion_id, producto_id):
    ubicacion_id = ubicacion_id or datos["cd"]
    producto_id = producto_id or datos["coca"]
    with pytest.raises(NoEncontrado):
        service.ingresar(ubicacion_id, producto_id, 1, COMPRA)
    with pytest.raises(NoEncontrado):
        service.obtener(ubicacion_id, producto_id)


# -------------------------------------------------------------- Transacción

def test_una_operacion_con_varios_movimientos_se_guarda_toda_o_nada(service, datos):
    # Como hará el despacho de un bulto: si un producto no alcanza, no se
    # descuenta ninguno
    service.ingresar(datos["cd"], datos["coca"], 10, COMPRA)
    with pytest.raises(StockInsuficiente):
        with service.dao.transaccion() as cx:
            service.egresar(datos["cd"], datos["coca"], 5, DESPACHO, "Bulto 1", cx=cx)
            service.egresar(datos["cd"], datos["agua"], 1, DESPACHO, "Bulto 1", cx=cx)  # no hay agua

    assert service.obtener(datos["cd"], datos["coca"]).cantidad == 10
    assert len(service.listar_movimientos(datos["cd"], datos["coca"])) == 1


def test_dentro_de_una_transaccion_se_ve_lo_que_ya_se_movio(service, datos):
    with service.dao.transaccion() as cx:
        service.ingresar(datos["cd"], datos["coca"], 10, COMPRA, cx=cx)
        service.egresar(datos["cd"], datos["coca"], 10, DESPACHO, cx=cx)
    assert service.obtener(datos["cd"], datos["coca"]).cantidad == 0
    assert len(service.listar_movimientos(datos["cd"], datos["coca"])) == 2


# ------------------------------------------------------- Existencias por lugar

def test_las_existencias_incluyen_productos_sin_movimientos_y_marcan_el_minimo(service, datos):
    service.ingresar(datos["cd"], datos["agua"], 3, COMPRA)
    existencias = {producto.codigo: stock for producto, stock in service.listar_por_ubicacion(datos["cd"])}

    assert existencias["BEB-002"].cantidad == 3
    assert existencias["BEB-001"].cantidad == 0
    assert existencias["BEB-001"].esta_bajo_minimo()       # mínimo 10, hay 0
    assert not existencias["BEB-002"].esta_bajo_minimo()   # mínimo 0


def test_las_existencias_de_una_ubicacion_inexistente(service):
    with pytest.raises(NoEncontrado):
        service.listar_por_ubicacion(999)
