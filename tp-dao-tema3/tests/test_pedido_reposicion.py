# Tests del pedido de reposición: lo que pide un local al Centro de Distribución.
import pytest

from backend.dominio.excepciones import DatoInvalido, TransicionDeEstadoInvalida
from backend.dominio.logistica import PedidoReposicion, DetallePedido

LOCAL = "local-1"


def pedido_con_items():
    pedido = PedidoReposicion(1, LOCAL)
    pedido.agregar_item("prod-1", 10)
    return pedido


def test_pedido_nuevo_nace_pendiente_y_vacio():
    pedido = PedidoReposicion(1, LOCAL)
    assert pedido.estado == "PENDIENTE"
    assert pedido.local == LOCAL
    assert pedido.items == []


def test_pedido_sin_local_es_dato_invalido():
    with pytest.raises(DatoInvalido):
        PedidoReposicion(1, None)


def test_se_pueden_agregar_items():
    pedido = PedidoReposicion(1, LOCAL)
    pedido.agregar_item("prod-1", 10)
    pedido.agregar_item("prod-2", 4)
    assert pedido.items == [DetallePedido("prod-1", 10), DetallePedido("prod-2", 4)]


def test_agregar_el_mismo_producto_suma_la_cantidad():
    pedido = pedido_con_items()
    pedido.agregar_item("prod-1", 5)
    assert pedido.items == [DetallePedido("prod-1", 15)]


@pytest.mark.parametrize("cantidad_invalida", [0, -3, 1.5, None])
def test_agregar_con_cantidad_invalida_es_dato_invalido(cantidad_invalida):
    pedido = pedido_con_items()
    with pytest.raises(DatoInvalido):
        pedido.agregar_item("prod-2", cantidad_invalida)
    assert pedido.items == [DetallePedido("prod-1", 10)]


def test_se_puede_quitar_un_item():
    pedido = pedido_con_items()
    pedido.quitar_item("prod-1")
    assert pedido.items == []


def test_quitar_un_item_que_no_esta_es_dato_invalido():
    pedido = pedido_con_items()
    with pytest.raises(DatoInvalido):
        pedido.quitar_item("prod-que-no-esta")


def test_consolidar_un_pedido_vacio_es_dato_invalido():
    pedido = PedidoReposicion(1, LOCAL)
    with pytest.raises(DatoInvalido):
        pedido.consolidar()
    assert pedido.estado == "PENDIENTE"


def test_consolidar_pasa_a_consolidado():
    pedido = pedido_con_items()
    pedido.consolidar()
    assert pedido.estado == "CONSOLIDADO"


@pytest.mark.parametrize("accion", [
    lambda p: p.agregar_item("prod-2", 1),
    lambda p: p.quitar_item("prod-1"),
    lambda p: p.consolidar(),
])
def test_un_pedido_consolidado_no_se_puede_modificar(accion):
    pedido = pedido_con_items()
    pedido.consolidar()
    with pytest.raises(TransicionDeEstadoInvalida):
        accion(pedido)
    assert pedido.estado == "CONSOLIDADO"
    assert pedido.items == [DetallePedido("prod-1", 10)]
    