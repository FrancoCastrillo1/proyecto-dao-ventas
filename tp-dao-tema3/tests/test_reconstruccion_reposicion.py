# Tests de los métodos reconstruir de Pedido, Orden y Remito: el DAO los usa para
# armar el objeto ya en su estado, sin pasar por las reglas de cada acción.
import pytest

from backend.dominio.excepciones import DatoInvalido, TransicionDeEstadoInvalida
from backend.dominio.logistica import Bulto, DetallePedido, OrdenReposicion, PedidoReposicion, Remito


def bulto_en_transito(id_bulto):
    bulto = Bulto(id_bulto)
    bulto.agregar_item(1, 5)
    bulto.precintar("PRE-001")
    bulto.despachar()
    return bulto


# ---------- pedido ----------

def test_pedido_reconstruido_conserva_todo_y_no_se_edita_si_esta_consolidado():
    pedido = PedidoReposicion.reconstruir(3, 2, "CONSOLIDADO", [DetallePedido(1, 10)])
    assert (pedido.id_pedido, pedido.local, pedido.estado) == (3, 2, "CONSOLIDADO")
    assert pedido.items == [DetallePedido(1, 10)]
    with pytest.raises(TransicionDeEstadoInvalida):
        pedido.agregar_item(2, 1)


def test_pedido_reconstruido_pendiente_sigue_editable():
    pedido = PedidoReposicion.reconstruir(3, 2, "PENDIENTE", [DetallePedido(1, 10)])
    pedido.agregar_item(1, 5)
    assert pedido.items == [DetallePedido(1, 15)]


def test_pedido_reconstruir_con_estado_invalido_es_dato_invalido():
    with pytest.raises(DatoInvalido):
        PedidoReposicion.reconstruir(3, 2, "INVENTADO", [])


def test_pedido_reconstruir_no_comparte_la_lista_de_items():
    items = [DetallePedido(1, 10)]
    pedido = PedidoReposicion.reconstruir(3, 2, "PENDIENTE", items)
    items.append(DetallePedido(2, 1))
    assert pedido.items == [DetallePedido(1, 10)]


# ---------- orden ----------

def test_orden_reconstruida_cerrada_conserva_todo_y_no_admite_pedidos():
    pedido = PedidoReposicion.reconstruir(1, 2, "CONSOLIDADO", [DetallePedido(1, 10)])
    orden = OrdenReposicion.reconstruir(5, 1, "CERRADA", [pedido])
    assert (orden.id_orden, orden.origen, orden.estado) == (5, 1, "CERRADA")
    assert orden.pedidos == [pedido]
    assert orden.total_por_producto() == {1: 10}
    otro = PedidoReposicion.reconstruir(2, 3, "CONSOLIDADO", [DetallePedido(1, 1)])
    with pytest.raises(TransicionDeEstadoInvalida):
        orden.agregar_pedido(otro)


def test_orden_reconstruir_con_estado_invalido_es_dato_invalido():
    with pytest.raises(DatoInvalido):
        OrdenReposicion.reconstruir(5, 1, "INVENTADA", [])


# ---------- remito ----------

def test_remito_reconstruido_admite_bultos_que_ya_salieron_del_cd():
    # agregar_bulto() los rechazaría; reconstruir no pasa por esa regla
    bulto = bulto_en_transito(1)
    remito = Remito.reconstruir(9, 1, 2, "CERRADO", [bulto])
    assert (remito.id_remito, remito.origen, remito.destino, remito.estado) == (9, 1, 2, "CERRADO")
    assert remito.bultos == [bulto]
    assert remito.total_por_producto() == {1: 5}


def test_remito_reconstruido_cerrado_no_se_modifica():
    remito = Remito.reconstruir(9, 1, 2, "CERRADO", [bulto_en_transito(1)])
    with pytest.raises(TransicionDeEstadoInvalida):
        remito.cerrar()


def test_remito_reconstruir_con_estado_invalido_es_dato_invalido():
    with pytest.raises(DatoInvalido):
        Remito.reconstruir(9, 1, 2, "INVENTADO", [])