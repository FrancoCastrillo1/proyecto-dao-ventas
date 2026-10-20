# Tests de ventas contra un SQLite temporal por test (tmp_path): que una venta
# guardada vuelva igual al leerla, y (en el service) que vender y devolver
# muevan el stock y la caja, todo junto o nada. Acá NO se prueba la api.
from datetime import datetime
from decimal import Decimal

import pytest

from backend.dominio.maestros import Categoria, CentroDistribucion, Producto, Sucursal
from backend.dominio.medios_pago import Credito, Efectivo
from backend.dominio.ventas import Venta
from backend.persistencia.conexion import crear_tablas
from backend.persistencia.dao_maestros import CategoriaDAO, ProductoDAO, UbicacionDAO
from backend.persistencia.dao_ventas import VentaDAO, a_centavos, desde_centavos

D = Decimal


@pytest.fixture
def db(tmp_path):
    ruta = tmp_path / "test.db"
    crear_tablas(ruta)
    return ruta


@pytest.fixture
def datos(db):
    """Un CD, dos sucursales y dos productos."""
    categoria = CategoriaDAO(db).crear(Categoria("Bebidas"))
    productos = ProductoDAO(db)
    coca = productos.crear(Producto("BEB-001", "Coca 500ml", categoria.id, 1000, 600, stock_minimo=5))
    agua = productos.crear(Producto("BEB-002", "Agua 1L", categoria.id, 500.5, 200))
    ubicaciones = UbicacionDAO(db)
    cd = ubicaciones.crear(CentroDistribucion("CD Central", "Ruta 9 km 5"))
    centro = ubicaciones.crear(Sucursal("Local Centro", "San Martín 100"))
    norte = ubicaciones.crear(Sucursal("Local Norte", "Belgrano 900"))
    return {"coca": coca, "agua": agua, "cd": cd.id, "centro": centro.id, "norte": norte.id}


# ---------------------------------------------------------------------- DAO

@pytest.mark.parametrize("monto, centavos", [(D("1500.50"), 150050), (D("0.01"), 1), (D("-850.00"), -85000)])
def test_conversion_a_centavos_es_exacta_ida_y_vuelta(monto, centavos):
    assert a_centavos(monto) == centavos
    assert desde_centavos(centavos) == monto


def guardar_venta(db, venta, medio, entregado=None):
    dao = VentaDAO(db)
    venta.cobrar(medio, entregado)
    with dao.transaccion() as cx:
        venta.emitir_comprobante(dao.siguiente_numero_comprobante(cx, venta.sucursal_id))
        dao.crear(cx, venta)
    return venta


def test_una_venta_guardada_vuelve_igual_al_leerla(db, datos):
    venta = Venta(datos["centro"])
    venta.agregar_item(datos["coca"], 2)
    venta.agregar_item(datos["agua"], 3)
    guardar_venta(db, venta, Efectivo(), 5000)

    leida = VentaDAO(db).obtener(venta.id)
    assert (leida.id, leida.sucursal_id, leida.fecha) == (venta.id, venta.sucursal_id, venta.fecha)
    assert leida.detalles == venta.detalles
    assert (leida.subtotal, leida.total, leida.costo_total) == (D("3501.50"), D("2976.28"), D("1800.00"))
    assert type(leida.pago.medio) is Efectivo
    assert (leida.pago.porcentaje_ajuste, leida.pago.vuelto) == (D("-15"), D("2023.72"))
    assert leida.comprobante == venta.comprobante


def test_obtener_una_venta_inexistente_devuelve_none(db):
    assert VentaDAO(db).obtener(999) is None


def test_el_comprobante_es_correlativo_por_sucursal(db, datos):
    numeros = []
    for sucursal in ("centro", "centro", "norte", "centro"):
        venta = Venta(datos[sucursal])
        venta.agregar_item(datos["coca"], 1)
        numeros.append(guardar_venta(db, venta, Credito()).comprobante.codigo)
    assert numeros == [f"{datos['centro']:04d}-00000001", f"{datos['centro']:04d}-00000002",
                       f"{datos['norte']:04d}-00000001", f"{datos['centro']:04d}-00000003"]


def test_una_devolucion_guardada_vuelve_con_la_venta(db, datos):
    venta = Venta(datos["centro"])
    venta.agregar_item(datos["coca"], 3)
    guardar_venta(db, venta, Credito())
    dao = VentaDAO(db)
    devolucion = venta.devolver([(datos["coca"].id, 1)], "Falla")
    with dao.transaccion() as cx:
        dao.crear_devolucion(cx, devolucion)

    [leida] = dao.obtener(venta.id).devoluciones
    assert (leida.id, leida.motivo, leida.importe, leida.medio_pago) == (devolucion.id, "Falla", D("1100.00"), "CREDITO")
    assert leida.detalles == devolucion.detalles
    assert dao.obtener(venta.id).cantidad_devolvible(datos["coca"].id) == 2


def test_listar_filtra_por_sucursal_y_por_fechas(db, datos):
    for sucursal, fecha in (("centro", datetime(2026, 10, 1, 9)), ("centro", datetime(2026, 10, 5, 18)),
                            ("norte", datetime(2026, 10, 5, 12))):
        venta = Venta(datos[sucursal], fecha=fecha)
        venta.agregar_item(datos["coca"], 1)
        guardar_venta(db, venta, Credito())

    dao = VentaDAO(db)
    assert len(dao.listar()) == 3
    assert len(dao.listar(sucursal_id=datos["centro"])) == 2
    assert len(dao.listar(desde=datetime(2026, 10, 5), hasta=datetime(2026, 10, 6))) == 2
    assert len(dao.listar(datos["centro"], datetime(2026, 10, 2), datetime(2026, 10, 6))) == 1
