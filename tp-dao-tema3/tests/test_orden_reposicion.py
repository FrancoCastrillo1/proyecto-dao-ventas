# Tests de la orden de reposición: lo que arma el CD juntando pedidos de varios locales.
import pytest

from backend.dominio.excepciones import DatoInvalido, TransicionDeEstadoInvalida
from backend.dominio.logistica import OrdenReposicion, PedidoReposicion

CD = "cd-1"


def pedido_consolidado(id_pedido, local, items):
    pedido = PedidoReposicion(id_pedido, local)
    for producto, cantidad in items:
        pedido.agregar_item(producto, cantidad)
    pedido.consolidar()
    return pedido


def orden_con_pedidos():
    orden = OrdenReposicion(1, CD)
    orden.agregar_pedido(pedido_consolidado(1, "local-1", [("prod-1", 10)]))
    return orden


def test_orden_nueva_nace_abierta_y_sin_pedidos():
    orden = OrdenReposicion(1, CD)
    assert orden.estado == "ABIERTA"
    assert orden.origen == CD
    assert orden.pedidos == []


@pytest.mark.parametrize("origen_invalido", [None, "", "   "])
def test_orden_sin_origen_es_dato_invalido(origen_invalido):
    with pytest.raises(DatoInvalido):
        OrdenReposicion(1, origen_invalido)


def test_se_pueden_agregar_pedidos_consolidados():
    orden = OrdenReposicion(1, CD)
    p1 = pedido_consolidado(1, "local-1", [("prod-1", 10)])
    p2 = pedido_consolidado(2, "local-2", [("prod-1", 5)])
    orden.agregar_pedido(p1)
    orden.agregar_pedido(p2)
    assert orden.pedidos == [p1, p2]


def test_no_se_puede_agregar_un_pedido_pendiente():
    orden = OrdenReposicion(1, CD)
    pendiente = PedidoReposicion(1, "local-1")
    pendiente.agregar_item("prod-1", 10)
    with pytest.raises(DatoInvalido):
        orden.agregar_pedido(pendiente)
    assert orden.pedidos == []


def test_no_se_puede_agregar_el_mismo_pedido_dos_veces():
    orden = OrdenReposicion(1, CD)
    pedido = pedido_consolidado(1, "local-1", [("prod-1", 10)])
    orden.agregar_pedido(pedido)
    with pytest.raises(DatoInvalido):
        orden.agregar_pedido(pedido)
    assert orden.pedidos == [pedido]


def test_cerrar_una_orden_sin_pedidos_es_dato_invalido():
    orden = OrdenReposicion(1, CD)
    with pytest.raises(DatoInvalido):
        orden.cerrar()
    assert orden.estado == "ABIERTA"


def test_cerrar_pasa_a_cerrada():
    orden = orden_con_pedidos()
    orden.cerrar()
    assert orden.estado == "CERRADA"


@pytest.mark.parametrize("accion", [
    lambda o: o.agregar_pedido(pedido_consolidado(9, "local-9", [("prod-9", 1)])),
    lambda o: o.cerrar(),
])
def test_una_orden_cerrada_no_se_puede_modificar(accion):
    orden = orden_con_pedidos()
    orden.cerrar()
    with pytest.raises(TransicionDeEstadoInvalida):
        accion(orden)
    assert orden.estado == "CERRADA"
    assert len(orden.pedidos) == 1


def test_total_por_producto_suma_las_cantidades_de_todos_los_pedidos():
    orden = OrdenReposicion(1, CD)
    orden.agregar_pedido(pedido_consolidado(1, "local-1", [("prod-1", 10), ("prod-2", 4)]))
    orden.agregar_pedido(pedido_consolidado(2, "local-2", [("prod-1", 5)]))
    assert orden.total_por_producto() == {"prod-1": 15, "prod-2": 4}


def test_total_por_producto_de_una_orden_vacia_es_vacio():
    assert OrdenReposicion(1, CD).total_por_producto() == {}