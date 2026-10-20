# Tests del DAO de logística para pedidos, órdenes y remitos. Usa una base
# temporal en un archivo, no la base real.
import pytest

from backend.dominio.excepciones import DatoInvalido, NoEncontrado
from backend.dominio.logistica import Bulto, OrdenReposicion, PedidoReposicion, Remito
from backend.persistencia.conexion import crear_tablas, get_conexion
from backend.persistencia.dao_logistica import DaoLogistica

CD, LOCAL_1, LOCAL_2 = 1, 2, 3


@pytest.fixture
def db(tmp_path):
    ruta = tmp_path / "test.db"
    crear_tablas(ruta)
    cx = get_conexion(ruta)
    try:
        cx.execute("INSERT INTO categorias (nombre) VALUES ('Almacen')")
        cx.executemany(
            "INSERT INTO productos (codigo, nombre, categoria_id, precio_venta, costo) "
            "VALUES (?, ?, 1, 100, 60)",
            [("P1", "Yerba"), ("P2", "Azucar")],
        )
        cx.executemany(
            "INSERT INTO ubicaciones (tipo, nombre, direccion) VALUES (?, ?, ?)",
            [("CD", "CD Central", "Calle 1"), ("SUCURSAL", "Local 1", "Calle 2"), ("SUCURSAL", "Local 2", "Calle 3")],
        )
        cx.commit()
    finally:
        cx.close()
    return ruta


def consultar(db, sql, parametros=()):
    cx = get_conexion(db)
    try:
        return [tuple(fila) for fila in cx.execute(sql, parametros).fetchall()]
    finally:
        cx.close()


def pedido_consolidado(local, items):
    pedido = PedidoReposicion(None, local)
    for producto, cantidad in items:
        pedido.agregar_item(producto, cantidad)
    pedido.consolidar()
    return pedido


def bulto_precintado(dao, precinto, items=((1, 5),)):
    bulto = Bulto(None)
    for producto, cantidad in items:
        bulto.agregar_item(producto, cantidad)
    bulto.precintar(precinto)
    dao.guardar_bulto(bulto)
    return bulto


# ---------- pedidos ----------

@pytest.mark.parametrize("consolidar", [False, True])
def test_un_pedido_guardado_vuelve_igual_al_leerlo(db, consolidar):
    dao = DaoLogistica(db)
    pedido = PedidoReposicion(None, LOCAL_1)
    pedido.agregar_item(1, 10)
    pedido.agregar_item(2, 4)
    if consolidar:
        pedido.consolidar()
    pedido_id = dao.guardar_pedido(pedido)
    leido = dao.obtener_pedido(pedido_id)
    assert pedido.id_pedido == pedido_id
    assert leido.local == LOCAL_1
    assert leido.estado == pedido.estado
    assert leido.items == pedido.items


def test_obtener_un_pedido_inexistente_es_no_encontrado(db):
    with pytest.raises(NoEncontrado):
        DaoLogistica(db).obtener_pedido(999)


def test_guardar_dos_veces_el_mismo_pedido_no_duplica_nada(db):
    dao = DaoLogistica(db)
    pedido = PedidoReposicion(None, LOCAL_1)
    pedido.agregar_item(1, 10)
    dao.guardar_pedido(pedido)
    pedido.agregar_item(1, 5)
    dao.guardar_pedido(pedido)
    assert consultar(db, "SELECT COUNT(*) FROM pedidos_reposicion") == [(1,)]
    assert consultar(db, "SELECT producto_id, cantidad FROM detalles_pedido") == [(1, 15)]


# ---------- órdenes ----------

def test_una_orden_guardada_vuelve_igual_al_leerla(db):
    dao = DaoLogistica(db)
    p1 = pedido_consolidado(LOCAL_1, [(1, 10)])
    p2 = pedido_consolidado(LOCAL_2, [(1, 5), (2, 4)])
    dao.guardar_pedido(p1)
    dao.guardar_pedido(p2)
    orden = OrdenReposicion(None, CD)
    orden.agregar_pedido(p1)
    orden.agregar_pedido(p2)
    orden.cerrar()
    orden_id = dao.guardar_orden(orden)
    leida = dao.obtener_orden(orden_id)
    assert (leida.origen, leida.estado) == (CD, "CERRADA")
    assert [p.id_pedido for p in leida.pedidos] == [p1.id_pedido, p2.id_pedido]
    assert leida.total_por_producto() == {1: 15, 2: 4}


def test_obtener_una_orden_inexistente_es_no_encontrado(db):
    with pytest.raises(NoEncontrado):
        DaoLogistica(db).obtener_orden(999)


def test_un_pedido_no_puede_estar_en_dos_ordenes_y_no_queda_una_orden_a_medias(db):
    dao = DaoLogistica(db)
    pedido = pedido_consolidado(LOCAL_1, [(1, 10)])
    dao.guardar_pedido(pedido)
    orden_1 = OrdenReposicion(None, CD)
    orden_1.agregar_pedido(pedido)
    dao.guardar_orden(orden_1)
    orden_2 = OrdenReposicion(None, CD)
    orden_2.agregar_pedido(pedido)
    with pytest.raises(DatoInvalido):
        dao.guardar_orden(orden_2)
    assert consultar(db, "SELECT COUNT(*) FROM ordenes_reposicion") == [(1,)]


def test_una_orden_con_un_pedido_sin_guardar_es_dato_invalido(db):
    orden = OrdenReposicion(None, CD)
    orden.agregar_pedido(pedido_consolidado(LOCAL_1, [(1, 10)]))
    with pytest.raises(DatoInvalido):
        DaoLogistica(db).guardar_orden(orden)


# ---------- remitos ----------

def test_un_remito_guardado_vuelve_igual_al_leerlo(db):
    dao = DaoLogistica(db)
    b1, b2 = bulto_precintado(dao, "PRE-001"), bulto_precintado(dao, "PRE-002", [(2, 3)])
    remito = Remito(None, CD, LOCAL_1)
    remito.agregar_bulto(b1)
    remito.agregar_bulto(b2)
    remito.cerrar()
    remito_id = dao.guardar_remito(remito)
    leido = dao.obtener_remito(remito_id)
    assert (leido.origen, leido.destino, leido.estado) == (CD, LOCAL_1, "CERRADO")
    assert [b.id_bulto for b in leido.bultos] == [b1.id_bulto, b2.id_bulto]
    assert [b.estado for b in leido.bultos] == ["PRECINTADO", "PRECINTADO"]
    assert leido.total_por_producto() == {1: 5, 2: 3}


def test_guardar_un_remito_asigna_su_id_a_los_bultos(db):
    dao = DaoLogistica(db)
    bulto = bulto_precintado(dao, "PRE-001")
    remito = Remito(None, CD, LOCAL_1)
    remito.agregar_bulto(bulto)
    remito_id = dao.guardar_remito(remito)
    assert consultar(db, "SELECT remito_id FROM bultos WHERE id = ?", (bulto.id_bulto,)) == [(remito_id,)]


def test_un_remito_con_un_bulto_sin_guardar_es_dato_invalido(db):
    bulto = Bulto(None)
    bulto.agregar_item(1, 5)
    remito = Remito(None, CD, LOCAL_1)
    remito.agregar_bulto(bulto)
    with pytest.raises(DatoInvalido):
        DaoLogistica(db).guardar_remito(remito)


def test_obtener_un_remito_inexistente_es_no_encontrado(db):
    with pytest.raises(NoEncontrado):
        DaoLogistica(db).obtener_remito(999)


def test_un_remito_se_lee_bien_cuando_sus_bultos_ya_estan_en_transito(db):
    dao = DaoLogistica(db)
    bulto = bulto_precintado(dao, "PRE-001")
    remito = Remito(None, CD, LOCAL_1)
    remito.agregar_bulto(bulto)
    remito.cerrar()
    remito_id = dao.guardar_remito(remito)
    bulto.despachar()
    dao.guardar_bulto(bulto)
    leido = dao.obtener_remito(remito_id)
    assert leido.estado == "CERRADO"
    assert [b.estado for b in leido.bultos] == ["EN_TRANSITO"]