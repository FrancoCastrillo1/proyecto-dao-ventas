# Tests del reloj del dominio (dominio/reloj.py): normalmente es la hora real;
# con a_las se fija una hora (lo usa el seed para el historial) y al salir
# vuelve a la real. Se prueba que el dominio la use: el pedido, el historial
# del bulto y los movimientos de stock quedan con la hora fijada.
from datetime import datetime, timedelta

from backend.dominio.estados_bulto import Precintado
from backend.dominio.logistica import Bulto, PedidoReposicion
from backend.dominio.reloj import Reloj, a_las, ahora
from backend.dominio.stock import Stock, TipoMovimiento
from backend.dominio.ventas import Venta

UN_MARTES = datetime(2026, 9, 15, 10, 30)


def test_sin_fijar_es_la_hora_real():
    assert Reloj.fijo is None
    assert abs(ahora() - datetime.now()) < timedelta(seconds=5)


def test_a_las_fija_la_hora_y_al_salir_vuelve_a_la_real():
    with a_las(UN_MARTES):
        assert ahora() == UN_MARTES
        with a_las(UN_MARTES + timedelta(hours=2)):            # uno adentro de otro
            assert ahora() == UN_MARTES + timedelta(hours=2)
        assert ahora() == UN_MARTES
    assert Reloj.fijo is None


def test_vuelve_a_la_hora_real_aunque_haya_un_error():
    try:
        with a_las(UN_MARTES):
            raise ValueError("algo salió mal")
    except ValueError:
        pass
    assert Reloj.fijo is None


def test_el_dominio_usa_la_hora_del_reloj():
    with a_las(UN_MARTES):
        pedido = PedidoReposicion(None, 1)
        bulto = Bulto(None)
        bulto.agregar_item(1, 2)
        bulto.precintar("P-1")
        stock = Stock(1, 1)
        stock.ingresar(5, TipoMovimiento.COMPRA)
        venta = Venta(1)
    assert pedido.fecha == UN_MARTES
    assert bulto.historial[0].fecha_hora == UN_MARTES and isinstance(bulto.estado_actual, Precintado)
    assert stock.movimientos[0].fecha == UN_MARTES
    assert venta.fecha == UN_MARTES


def test_un_despacho_en_el_pasado_valida_la_llegada_contra_esa_hora():
    from backend.dominio.logistica import Remito
    with a_las(UN_MARTES):
        remito = Remito(None, 1, 2)
        bulto = Bulto(None)
        bulto.agregar_item(1, 2)
        bulto.precintar("P-1")
        remito.agregar_bulto(bulto)
        remito.despachar(UN_MARTES + timedelta(days=1))           # posterior al despacho de ese martes: vale
    assert remito.estado == Remito.EN_TRANSITO and remito.fecha == UN_MARTES
