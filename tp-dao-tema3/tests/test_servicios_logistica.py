# Tests de los servicios de logística: reposición (pedido, orden, remito y
# despacho que descuenta el stock del CD) y recepción (recibir, verificar y
# sumar stock al local solo si el bulto queda Verificado). Usa una base temporal.
import pytest

from backend.dominio.excepciones import (
    DatoInvalido, NoEncontrado, StockInsuficiente, TransicionDeEstadoInvalida,
)
from backend.dominio.logistica import Bulto, Remito
from backend.persistencia.conexion import crear_tablas, get_conexion
from backend.persistencia.dao_logistica import DaoLogistica
from backend.persistencia.dao_stock import DaoStock
from backend.servicios.recepcion_service import RecepcionService
from backend.servicios.reposicion_service import ReposicionService
from backend.servicios.stock_service import StockService

CD, LOCAL_1, LOCAL_2 = 1, 2, 3
PRECINTO = "PRE-001"


@pytest.fixture
def db(tmp_path, monkeypatch):
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
    # DaoStock abre la base real por su cuenta: se lo redirige a la temporal
    monkeypatch.setattr("backend.persistencia.dao_stock.get_conexion", lambda: get_conexion(ruta))
    DaoStock().guardar_o_actualizar(CD, 1, 100)
    DaoStock().guardar_o_actualizar(CD, 2, 50)
    return ruta


# ---------- helpers ----------

def consultar(db, sql, parametros=()):
    cx = get_conexion(db)
    try:
        return [tuple(fila) for fila in cx.execute(sql, parametros).fetchall()]
    finally:
        cx.close()


def cantidad(ubicacion, producto):
    return StockService().obtener_stock_ubicacion(ubicacion, producto)["cantidad"]


def servicios(db):
    dao = DaoLogistica(db)
    return ReposicionService(dao, StockService()), RecepcionService(dao, StockService())


def bulto(items, precinto=PRECINTO):
    return {"precinto": precinto, "items": items}


def despachado(db, rep, destino=LOCAL_1, items=((1, 10),), precinto=PRECINTO):
    """Arma un remito con un bulto, lo despacha y devuelve el id del bulto."""
    remito_id = rep.armar_remito(CD, destino, [bulto(list(items), precinto)])
    rep.despachar_remito(remito_id)
    return DaoLogistica(db).obtener_remito(remito_id).bultos[0].id_bulto


def estado_del_bulto(db, bulto_id):
    return DaoLogistica(db).obtener_bulto(bulto_id).estado


# ---------- pedidos y órdenes ----------

def test_crear_pedido_lo_guarda_pendiente_con_sus_lineas(db):
    rep, _ = servicios(db)
    pedido = DaoLogistica(db).obtener_pedido(rep.crear_pedido(LOCAL_1, [(1, 10), (2, 4)]))
    assert (pedido.local, pedido.estado) == (LOCAL_1, "PENDIENTE")
    assert [(d.producto, d.cantidad) for d in pedido.items] == [(1, 10), (2, 4)]


def test_consolidar_pedido_lo_deja_consolidado(db):
    rep, _ = servicios(db)
    pedido_id = rep.crear_pedido(LOCAL_1, [(1, 10)])
    rep.consolidar_pedido(pedido_id)
    assert DaoLogistica(db).obtener_pedido(pedido_id).estado == "CONSOLIDADO"


def test_consolidar_un_pedido_inexistente_es_no_encontrado(db):
    rep, _ = servicios(db)
    with pytest.raises(NoEncontrado):
        rep.consolidar_pedido(999)


def test_crear_orden_junta_pedidos_de_varios_locales_y_la_cierra(db):
    rep, _ = servicios(db)
    p1 = rep.crear_pedido(LOCAL_1, [(1, 10)])
    p2 = rep.crear_pedido(LOCAL_2, [(1, 5), (2, 4)])
    rep.consolidar_pedido(p1)
    rep.consolidar_pedido(p2)
    orden = DaoLogistica(db).obtener_orden(rep.crear_orden(CD, [p1, p2]))
    assert (orden.origen, orden.estado) == (CD, "CERRADA")
    assert orden.total_por_producto() == {1: 15, 2: 4}


def test_crear_orden_con_un_pedido_sin_consolidar_es_dato_invalido_y_no_guarda_nada(db):
    rep, _ = servicios(db)
    p1 = rep.crear_pedido(LOCAL_1, [(1, 10)])
    with pytest.raises(DatoInvalido):
        rep.crear_orden(CD, [p1])
    assert consultar(db, "SELECT COUNT(*) FROM ordenes_reposicion") == [(0,)]


def test_un_pedido_no_puede_ir_en_dos_ordenes(db):
    rep, _ = servicios(db)
    p1 = rep.crear_pedido(LOCAL_1, [(1, 10)])
    rep.consolidar_pedido(p1)
    rep.crear_orden(CD, [p1])
    with pytest.raises(DatoInvalido):
        rep.crear_orden(CD, [p1])
    assert consultar(db, "SELECT COUNT(*) FROM ordenes_reposicion") == [(1,)]


# ---------- armar el remito ----------

def test_armar_remito_precinta_los_bultos_y_cierra_el_remito(db):
    rep, _ = servicios(db)
    remito_id = rep.armar_remito(CD, LOCAL_1, [bulto([(1, 10)], "PRE-001"), bulto([(2, 4)], "PRE-002")])
    remito = DaoLogistica(db).obtener_remito(remito_id)
    assert (remito.origen, remito.destino, remito.estado) == (CD, LOCAL_1, "CERRADO")
    assert [b.estado for b in remito.bultos] == ["PRECINTADO", "PRECINTADO"]
    assert [b.nro_precinto for b in remito.bultos] == ["PRE-001", "PRE-002"]
    assert remito.total_por_producto() == {1: 10, 2: 4}


@pytest.mark.parametrize("bultos", [[], [bulto([], "PRE-001")], [bulto([(1, 10)], "")]])
def test_armar_remito_invalido_es_dato_invalido_y_no_guarda_nada(db, bultos):
    rep, _ = servicios(db)
    with pytest.raises(DatoInvalido):
        rep.armar_remito(CD, LOCAL_1, bultos)
    assert consultar(db, "SELECT COUNT(*) FROM bultos") == [(0,)]
    assert consultar(db, "SELECT COUNT(*) FROM remitos") == [(0,)]


def test_armar_remito_con_el_mismo_origen_y_destino_es_dato_invalido(db):
    rep, _ = servicios(db)
    with pytest.raises(DatoInvalido):
        rep.armar_remito(CD, CD, [bulto([(1, 10)])])
    assert consultar(db, "SELECT COUNT(*) FROM bultos") == [(0,)]


# ---------- despacho ----------

def test_despachar_pasa_los_bultos_a_en_transito_y_descuenta_el_stock_del_cd(db):
    rep, _ = servicios(db)
    bulto_id = despachado(db, rep, items=((1, 10), (2, 4)))
    assert estado_del_bulto(db, bulto_id) == "EN_TRANSITO"
    assert (cantidad(CD, 1), cantidad(CD, 2)) == (90, 46)
    assert cantidad(LOCAL_1, 1) == 0  # el local no recibe nada hasta verificar
    assert consultar(db, "SELECT tipo, cantidad FROM movimientos_stock ORDER BY id") == [
        ("DESPACHO", -10), ("DESPACHO", -4),
    ]


def test_despachar_con_stock_insuficiente_no_cambia_nada(db):
    rep, _ = servicios(db)
    remito_id = rep.armar_remito(CD, LOCAL_1, [bulto([(1, 101)])])
    with pytest.raises(StockInsuficiente):
        rep.despachar_remito(remito_id)
    assert cantidad(CD, 1) == 100
    assert DaoLogistica(db).obtener_remito(remito_id).bultos[0].estado == "PRECINTADO"
    assert consultar(db, "SELECT COUNT(*) FROM movimientos_stock") == [(0,)]


def test_despachar_valida_la_suma_de_los_bultos_y_no_cada_uno_por_separado(db):
    rep, _ = servicios(db)
    remito_id = rep.armar_remito(CD, LOCAL_1, [bulto([(1, 60)], "PRE-001"), bulto([(1, 60)], "PRE-002")])
    with pytest.raises(StockInsuficiente):
        rep.despachar_remito(remito_id)
    assert cantidad(CD, 1) == 100
    estados = [b.estado for b in DaoLogistica(db).obtener_remito(remito_id).bultos]
    assert estados == ["PRECINTADO", "PRECINTADO"]


def test_despachar_dos_veces_el_mismo_remito_no_descuenta_dos_veces(db):
    rep, _ = servicios(db)
    remito_id = rep.armar_remito(CD, LOCAL_1, [bulto([(1, 10)])])
    rep.despachar_remito(remito_id)
    with pytest.raises(TransicionDeEstadoInvalida):
        rep.despachar_remito(remito_id)
    assert cantidad(CD, 1) == 90


def test_despachar_un_remito_inexistente_es_no_encontrado(db):
    rep, _ = servicios(db)
    with pytest.raises(NoEncontrado):
        rep.despachar_remito(999)


def test_no_se_despacha_un_remito_que_no_esta_cerrado(db):
    rep, _ = servicios(db)
    dao = DaoLogistica(db)
    nuevo = Bulto(None)
    nuevo.agregar_item(1, 10)
    nuevo.precintar(PRECINTO)
    dao.guardar_bulto(nuevo)
    remito = Remito(None, CD, LOCAL_1)
    remito.agregar_bulto(nuevo)
    remito_id = dao.guardar_remito(remito)
    with pytest.raises(DatoInvalido):
        rep.despachar_remito(remito_id)
    assert cantidad(CD, 1) == 100


# ---------- recepción ----------

def test_recibir_pasa_a_recibido_y_todavia_no_suma_stock_al_local(db):
    rep, rec = servicios(db)
    bulto_id = despachado(db, rep)
    rec.recibir_bulto(bulto_id)
    assert estado_del_bulto(db, bulto_id) == "RECIBIDO"
    assert cantidad(LOCAL_1, 1) == 0


def test_recibir_un_bulto_que_no_fue_despachado_es_transicion_invalida(db):
    rep, rec = servicios(db)
    remito_id = rep.armar_remito(CD, LOCAL_1, [bulto([(1, 10)])])
    bulto_id = DaoLogistica(db).obtener_remito(remito_id).bultos[0].id_bulto
    with pytest.raises(TransicionDeEstadoInvalida):
        rec.recibir_bulto(bulto_id)


def test_recibir_un_bulto_inexistente_es_no_encontrado(db):
    _, rec = servicios(db)
    with pytest.raises(NoEncontrado):
        rec.recibir_bulto(999)


def test_verificar_con_precinto_intacto_suma_el_stock_al_local(db):
    rep, rec = servicios(db)
    bulto_id = despachado(db, rep, items=((1, 10), (2, 4)))
    rec.recibir_bulto(bulto_id)
    rec.verificar_bulto(bulto_id, PRECINTO, intacto=True)
    leido = DaoLogistica(db).obtener_bulto(bulto_id)
    assert leido.estado == "VERIFICADO"
    assert leido.habilita_venta() is True
    assert len(leido.historial) == 4
    assert (cantidad(LOCAL_1, 1), cantidad(LOCAL_1, 2)) == (10, 4)
    assert consultar(db, "SELECT tipo, cantidad FROM movimientos_stock WHERE tipo = 'RECEPCION' ORDER BY id") == [
        ("RECEPCION", 10), ("RECEPCION", 4),
    ]


def test_el_stock_se_suma_en_el_destino_del_remito(db):
    rep, rec = servicios(db)
    bulto_id = despachado(db, rep, destino=LOCAL_2)
    rec.recibir_bulto(bulto_id)
    rec.verificar_bulto(bulto_id, PRECINTO, intacto=True)
    assert (cantidad(LOCAL_2, 1), cantidad(LOCAL_1, 1)) == (10, 0)


@pytest.mark.parametrize("nro_leido, intacto", [(PRECINTO, False), ("OTRO-PRECINTO", True), (None, True)])
def test_un_bulto_rechazado_no_suma_stock_ni_vuelve_al_cd(db, nro_leido, intacto):
    rep, rec = servicios(db)
    bulto_id = despachado(db, rep)
    rec.recibir_bulto(bulto_id)
    rec.verificar_bulto(bulto_id, nro_leido, intacto=intacto)
    leido = DaoLogistica(db).obtener_bulto(bulto_id)
    assert leido.estado == "RECHAZADO"
    assert leido.habilita_venta() is False
    assert "Precinto" in leido.historial[-1].observacion
    assert cantidad(LOCAL_1, 1) == 0
    assert cantidad(CD, 1) == 90  # merma: no vuelve al CD (decisión provisoria)
    assert consultar(db, "SELECT COUNT(*) FROM movimientos_stock WHERE tipo = 'RECEPCION'") == [(0,)]


def test_verificar_un_bulto_que_no_fue_recibido_es_transicion_invalida(db):
    rep, rec = servicios(db)
    bulto_id = despachado(db, rep)
    with pytest.raises(TransicionDeEstadoInvalida):
        rec.verificar_bulto(bulto_id, PRECINTO, intacto=True)
    assert cantidad(LOCAL_1, 1) == 0


def test_verificar_dos_veces_no_suma_el_stock_dos_veces(db):
    rep, rec = servicios(db)
    bulto_id = despachado(db, rep)
    rec.recibir_bulto(bulto_id)
    rec.verificar_bulto(bulto_id, PRECINTO, intacto=True)
    with pytest.raises(TransicionDeEstadoInvalida):
        rec.verificar_bulto(bulto_id, PRECINTO, intacto=True)
    assert cantidad(LOCAL_1, 1) == 10
    