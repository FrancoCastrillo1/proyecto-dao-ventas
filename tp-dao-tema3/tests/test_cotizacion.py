# Tests de la cotización de una venta: el total que se muestra antes de
# confirmar sale del mismo cálculo que la venta real (Strategy del medio de
# pago) y no guarda nada ni mueve stock ni caja. Acá NO se prueba la api.
from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.dominio.excepciones import DatoInvalido, NoEncontrado
from backend.dominio.stock import TipoMovimiento
from backend.persistencia.conexion import crear_tablas
from backend.persistencia.dao_maestros import CategoriaDAO, ProductoDAO, UbicacionDAO
from backend.persistencia.dao_stock import StockDAO
from backend.persistencia.dao_ventas import VentaDAO
from backend.servicios.maestros_service import CategoriaService, ProductoService, UbicacionService
from backend.servicios.stock_service import StockService
from backend.servicios.ventas_service import VentasService


@pytest.fixture
def v(tmp_path):
    db = tmp_path / "test.db"
    crear_tablas(db)
    categoria = CategoriaService(CategoriaDAO(db)).crear("Bebidas")
    productos = ProductoService(ProductoDAO(db), CategoriaDAO(db))
    agua = productos.crear("BEB-1", "Agua", categoria.id, 1200, 650)
    coca = productos.crear("BEB-2", "Coca", categoria.id, 2500, 1600)
    ubicaciones = UbicacionService(UbicacionDAO(db))
    cd = ubicaciones.crear("CD", "CD Central", "Ruta 9")
    local = ubicaciones.crear("SUCURSAL", "Local Centro", "Calle 1")
    stock = StockService(StockDAO(db), ProductoDAO(db), UbicacionDAO(db))
    stock.ingresar(local.id, agua.id, 10, TipoMovimiento.RECEPCION, "Bulto 1")
    ventas = VentasService(VentaDAO(db), stock, ProductoDAO(db), UbicacionDAO(db))
    return SimpleNamespace(agua=agua, coca=coca, cd=cd, local=local, stock=stock, ventas=ventas)


@pytest.mark.parametrize("medio, total", [
    ("EFECTIVO", Decimal("2040.00")),       # 2400 con -15%
    ("DEBITO", Decimal("2400.00")),
    ("CREDITO", Decimal("2640.00")),        # 2400 con +10%
])
def test_la_cotizacion_aplica_el_medio_de_pago(v, medio, total):
    venta, _, _ = v.ventas.cotizar(v.local.id, [(v.agua.id, 2)], medio)
    assert venta.subtotal == Decimal("2400.00")
    assert venta.total == total


def test_cotizar_da_lo_mismo_que_vender(v):
    cotizada, _, _ = v.ventas.cotizar(v.local.id, [(v.agua.id, 3)], "EFECTIVO", 5000)
    vendida = v.ventas.vender(v.local.id, [(v.agua.id, 3)], "EFECTIVO", 5000)
    assert (cotizada.total, cotizada.pago.vuelto) == (vendida.total, vendida.pago.vuelto)


def test_cotizar_no_guarda_nada_ni_mueve_stock(v):
    v.ventas.cotizar(v.local.id, [(v.agua.id, 2)], "DEBITO")
    assert v.ventas.listar() == []
    assert v.stock.obtener(v.local.id, v.agua.id).cantidad == 10


def test_informa_cuanto_hay_de_cada_producto(v):
    _, disponible, _ = v.ventas.cotizar(v.local.id, [(v.agua.id, 2), (v.coca.id, 1)], "DEBITO")
    assert disponible == {v.agua.id: 10, v.coca.id: 0}


def test_cotizar_mas_de_lo_que_hay_no_falla(v):
    # La cotización solo informa: el que rechaza es vender()
    venta, disponible, _ = v.ventas.cotizar(v.local.id, [(v.agua.id, 50)], "DEBITO")
    assert venta.total == Decimal("60000.00")
    assert disponible[v.agua.id] == 10


def test_vuelto_en_efectivo(v):
    venta, _, alcanza = v.ventas.cotizar(v.local.id, [(v.agua.id, 2)], "EFECTIVO", 3000)
    assert (alcanza, venta.pago.vuelto) == (True, Decimal("960.00"))  # 3000 - 2040


def test_si_el_monto_no_alcanza_la_cotizacion_igual_da_el_total(v):
    venta, _, alcanza = v.ventas.cotizar(v.local.id, [(v.agua.id, 2)], "EFECTIVO", 1000)
    assert alcanza is False
    assert venta.total == Decimal("2040.00")


@pytest.mark.parametrize("sucursal, items, medio, error", [
    ("cd", [("agua", 1)], "DEBITO", DatoInvalido),        # en el CD no se vende
    ("local", [("agua", 0)], "DEBITO", DatoInvalido),     # cantidad inválida
    ("local", [("agua", 1)], "BITCOIN", DatoInvalido),    # medio de pago inexistente
    ("local", [(999, 1)], "DEBITO", NoEncontrado),        # producto inexistente
])
def test_cotizar_aplica_las_mismas_validaciones_que_vender(v, sucursal, items, medio, error):
    ids = {"agua": v.agua.id}
    items = [(ids.get(p, p), c) for p, c in items]
    with pytest.raises(error):
        v.ventas.cotizar(getattr(v, sucursal).id, items, medio)
