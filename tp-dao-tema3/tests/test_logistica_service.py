# Tests de los servicios de logística (pasos 7 a 10 de la orden de trabajo):
# pedido → orden → remito → bultos → precinto → despacho → recepción → verificación,
# con el stock moviéndose según el estado de los bultos. Se prueban contra un
# SQLite temporal por test (tmp_path), así se prueban también las tablas, el
# DAO (el estado del bulto vuelve a armarse desde el texto) y los triggers que
# hacen inmutable el historial. Acá NO se prueba la api.
import sqlite3
from types import SimpleNamespace

import pytest

from backend.dominio.excepciones import (
    DatoInvalido, EntidadDuplicada, NoEncontrado, StockInsuficiente, TransicionDeEstadoInvalida,
)
from backend.dominio.logistica import Remito
from backend.dominio.stock import TipoMovimiento
from backend.persistencia.conexion import crear_tablas, get_conexion
from backend.persistencia.dao_logistica import BultoDAO, OrdenDAO, PedidoDAO, RemitoDAO
from backend.persistencia.dao_maestros import CategoriaDAO, ProductoDAO, UbicacionDAO
from backend.persistencia.dao_stock import StockDAO
from backend.persistencia.dao_ventas import VentaDAO
from backend.servicios.maestros_service import CategoriaService, ProductoService, UbicacionService
from backend.servicios.recepcion_service import RecepcionService
from backend.servicios.reposicion_service import ReposicionService
from backend.servicios.stock_service import StockService
from backend.servicios.ventas_service import VentasService


@pytest.fixture
def e(tmp_path):
    """Un CD con stock, dos sucursales, dos productos y los services armados."""
    db = tmp_path / "test.db"
    crear_tablas(db)
    categoria = CategoriaService(CategoriaDAO(db)).crear("Bebidas")
    productos = ProductoService(ProductoDAO(db), CategoriaDAO(db))
    coca = productos.crear("BEB-1", "Coca", categoria.id, 1000, 600)
    agua = productos.crear("BEB-2", "Agua", categoria.id, 500, 200)
    ubicaciones = UbicacionService(UbicacionDAO(db))
    cd = ubicaciones.crear("CD", "CD Central", "Ruta 9")
    centro = ubicaciones.crear("SUCURSAL", "Local Centro", "Calle 1")
    norte = ubicaciones.crear("SUCURSAL", "Local Norte", "Calle 2")
    stock = StockService(StockDAO(db), ProductoDAO(db), UbicacionDAO(db))
    stock.ingresar(cd.id, coca.id, 100, TipoMovimiento.COMPRA, "Factura 1")
    stock.ingresar(cd.id, agua.id, 50, TipoMovimiento.COMPRA, "Factura 1")
    repo = ReposicionService(PedidoDAO(db), OrdenDAO(db), RemitoDAO(db), BultoDAO(db),
                             ProductoDAO(db), UbicacionDAO(db), stock)
    rec = RecepcionService(BultoDAO(db), RemitoDAO(db), stock)
    return SimpleNamespace(db=db, coca=coca, agua=agua, cd=cd, centro=centro, norte=norte,
                           ubicaciones=ubicaciones, productos=productos, stock=stock, repo=repo, rec=rec)


def cantidad(e, ubicacion, producto):
    return e.stock.obtener(ubicacion.id, producto.id).cantidad


def armar_remito(e, pedido_items, bultos, destino=None):
    """Pedido de la sucursal + orden + remito + bultos precintados (sin despachar)."""
    destino = destino or e.centro
    pedido = e.repo.crear_pedido(destino.id, pedido_items)
    orden = e.repo.crear_orden([pedido.id_pedido])
    remito = e.repo.crear_remito(orden.id_orden, destino.id)
    ids = []
    for i, items in enumerate(bultos, start=1):
        bulto = e.repo.agregar_bulto(remito.id_remito, items)
        e.repo.precintar(bulto.id_bulto, f"P-{remito.id_remito}-{i}")
        ids.append(bulto.id_bulto)
    return remito.id_remito, ids


def recibir_y_verificar(e, bulto_id, intacto=True, nro=None):
    e.rec.recibir(bulto_id)
    nro = nro if nro is not None else e.repo.obtener_bulto(bulto_id).nro_precinto
    return e.rec.verificar(bulto_id, nro, intacto)


# ------------------------------------------------------------ Circuito feliz

def test_circuito_completo_mueve_el_stock_segun_el_estado_del_bulto(e):
    remito_id, (bulto_id,) = armar_remito(e, [(e.coca.id, 10)], [[(e.coca.id, 10)]])
    assert cantidad(e, e.cd, e.coca) == 100  # preparar y precintar no descuenta

    e.repo.despachar(remito_id)
    assert cantidad(e, e.cd, e.coca) == 90   # al despachar sale del CD
    assert cantidad(e, e.centro, e.coca) == 0

    e.rec.recibir(bulto_id)
    assert cantidad(e, e.centro, e.coca) == 0  # recibido todavía no es disponible

    bulto, remito, ingreso = e.rec.verificar(bulto_id, f"P-{remito_id}-1", True)
    assert (bulto.estado, remito.estado, ingreso) == ("VERIFICADO", Remito.VERIFICADO, True)
    assert cantidad(e, e.centro, e.coca) == 10  # recién ahora es vendible


def test_el_historial_queda_guardado_completo_y_en_orden(e):
    remito_id, (bulto_id,) = armar_remito(e, [(e.coca.id, 5)], [[(e.coca.id, 5)]])
    e.repo.despachar(remito_id)
    recibir_y_verificar(e, bulto_id)
    leido = e.repo.obtener_bulto(bulto_id)  # se vuelve a leer de la base
    assert [(r.estado_anterior, r.estado_nuevo) for r in leido.historial] == [
        ("PREPARADO", "PRECINTADO"), ("PRECINTADO", "EN_TRANSITO"),
        ("EN_TRANSITO", "RECIBIDO"), ("RECIBIDO", "VERIFICADO"),
    ]


def test_el_estado_del_bulto_vuelve_a_armarse_desde_la_base(e):
    remito_id, (bulto_id,) = armar_remito(e, [(e.coca.id, 5)], [[(e.coca.id, 5)]])
    e.repo.despachar(remito_id)
    leido = e.repo.obtener_bulto(bulto_id)
    assert type(leido.estado_actual).__name__ == "EnTransito"
    with pytest.raises(TransicionDeEstadoInvalida):  # y el State sigue funcionando
        leido.despachar()


def test_despues_de_la_recepcion_se_puede_vender_y_antes_no(e):
    ventas = VentasService(VentaDAO(e.db), e.stock, ProductoDAO(e.db), UbicacionDAO(e.db))
    remito_id, (bulto_id,) = armar_remito(e, [(e.coca.id, 10)], [[(e.coca.id, 10)]])
    e.repo.despachar(remito_id)
    with pytest.raises(StockInsuficiente):
        ventas.vender(e.centro.id, [(e.coca.id, 2)], "DEBITO")
    recibir_y_verificar(e, bulto_id)
    ventas.vender(e.centro.id, [(e.coca.id, 2)], "DEBITO")
    assert cantidad(e, e.centro, e.coca) == 8


# ------------------------------------- Regla: remito y contenedor verificados

def test_el_stock_no_entra_hasta_que_se_verifica_todo_el_remito(e):
    remito_id, (b1, b2) = armar_remito(e, [(e.coca.id, 10)], [[(e.coca.id, 6)], [(e.coca.id, 4)]])
    e.repo.despachar(remito_id)
    _, remito, ingreso = recibir_y_verificar(e, b1)
    assert (remito.estado, ingreso) == (Remito.EN_TRANSITO, False)
    assert cantidad(e, e.centro, e.coca) == 0  # un bulto verificado no alcanza: falta el remito
    _, remito, ingreso = recibir_y_verificar(e, b2)
    assert (remito.estado, ingreso) == (Remito.VERIFICADO, True)
    assert cantidad(e, e.centro, e.coca) == 10


@pytest.mark.parametrize("intacto, nro", [(False, None), (True, "OTRO-NUMERO"), (True, "")])
def test_bulto_rechazado_no_suma_stock_y_queda_como_merma(e, intacto, nro):
    remito_id, (bueno, malo) = armar_remito(
        e, [(e.coca.id, 10), (e.agua.id, 5)], [[(e.coca.id, 10)], [(e.agua.id, 5)]],
    )
    e.repo.despachar(remito_id)
    recibir_y_verificar(e, bueno)
    bulto, remito, _ = recibir_y_verificar(e, malo, intacto=intacto, nro=nro)
    assert bulto.estado == "RECHAZADO"
    assert not bulto.habilita_venta()
    assert remito.estado == Remito.VERIFICADO_CON_RECHAZOS
    assert cantidad(e, e.centro, e.coca) == 10  # el bueno entra
    assert cantidad(e, e.centro, e.agua) == 0   # el rechazado no
    assert cantidad(e, e.cd, e.agua) == 45      # y no vuelve al CD (decisión provisoria: merma)


# ----------------------------------------------------- Validaciones: pedidos

def test_el_cd_no_puede_pedir_reposicion(e):
    with pytest.raises(DatoInvalido, match="no es una sucursal"):
        e.repo.crear_pedido(e.cd.id, [(e.coca.id, 1)])


def test_pedido_vacio(e):
    with pytest.raises(DatoInvalido):
        e.repo.crear_pedido(e.centro.id, [])


def test_pedido_de_un_producto_dado_de_baja(e):
    # Uno sin stock: con stock no se puede dar de baja
    jugo = e.productos.crear("BEB-3", "Jugo", e.coca.categoria_id, 800, 400)
    e.productos.dar_de_baja(jugo.id)
    with pytest.raises(DatoInvalido, match="dado de baja"):
        e.repo.crear_pedido(e.centro.id, [(jugo.id, 1)])


def test_pedido_de_una_sucursal_dada_de_baja(e):
    e.ubicaciones.dar_de_baja(e.norte.id)
    with pytest.raises(DatoInvalido, match="dada de baja"):
        e.repo.crear_pedido(e.norte.id, [(e.coca.id, 1)])


# ----------------------------------------------------- Validaciones: órdenes

def test_la_orden_consolida_pedidos_de_varias_sucursales(e):
    p1 = e.repo.crear_pedido(e.centro.id, [(e.coca.id, 3)])
    p2 = e.repo.crear_pedido(e.norte.id, [(e.coca.id, 4), (e.agua.id, 2)])
    orden = e.repo.crear_orden([p1.id_pedido, p2.id_pedido])
    assert orden.origen == e.cd.id
    assert orden.total_por_producto() == {e.coca.id: 7, e.agua.id: 2}
    assert {p.estado for p in e.repo.listar_pedidos()} == {"CONSOLIDADO"}


def test_un_pedido_no_se_consolida_dos_veces(e):
    pedido = e.repo.crear_pedido(e.centro.id, [(e.coca.id, 3)])
    e.repo.crear_orden([pedido.id_pedido])
    with pytest.raises(TransicionDeEstadoInvalida):
        e.repo.crear_orden([pedido.id_pedido])


def test_pedidos_repetidos_en_la_misma_orden(e):
    pedido = e.repo.crear_pedido(e.centro.id, [(e.coca.id, 3)])
    with pytest.raises(DatoInvalido, match="repetidos"):
        e.repo.crear_orden([pedido.id_pedido, pedido.id_pedido])


def test_orden_sin_cd_activo(e):
    pedido = e.repo.crear_pedido(e.centro.id, [(e.coca.id, 3)])
    e.ubicaciones.dar_de_baja(e.cd.id)
    with pytest.raises(NoEncontrado, match="Centro de Distribución"):
        e.repo.crear_orden([pedido.id_pedido])


# ----------------------------------------------- Validaciones: remito y bultos

def test_remito_para_una_sucursal_sin_pedidos_en_la_orden(e):
    pedido = e.repo.crear_pedido(e.centro.id, [(e.coca.id, 3)])
    orden = e.repo.crear_orden([pedido.id_pedido])
    with pytest.raises(DatoInvalido, match="no tiene pedidos"):
        e.repo.crear_remito(orden.id_orden, e.norte.id)


def test_un_solo_remito_por_destino_en_cada_orden(e):
    pedido = e.repo.crear_pedido(e.centro.id, [(e.coca.id, 3)])
    orden = e.repo.crear_orden([pedido.id_pedido])
    e.repo.crear_remito(orden.id_orden, e.centro.id)
    with pytest.raises(EntidadDuplicada):
        e.repo.crear_remito(orden.id_orden, e.centro.id)


def test_no_se_manda_algo_que_no_se_pidio(e):
    pedido = e.repo.crear_pedido(e.centro.id, [(e.coca.id, 3)])
    remito = e.repo.crear_remito(e.repo.crear_orden([pedido.id_pedido]).id_orden, e.centro.id)
    with pytest.raises(DatoInvalido, match="no fue pedido"):
        e.repo.agregar_bulto(remito.id_remito, [(e.agua.id, 1)])


def test_no_se_manda_mas_de_lo_pedido_sumando_todos_los_bultos(e):
    pedido = e.repo.crear_pedido(e.centro.id, [(e.coca.id, 10)])
    remito = e.repo.crear_remito(e.repo.crear_orden([pedido.id_pedido]).id_orden, e.centro.id)
    e.repo.agregar_bulto(remito.id_remito, [(e.coca.id, 7)])
    with pytest.raises(DatoInvalido, match="se pidieron 10"):
        e.repo.agregar_bulto(remito.id_remito, [(e.coca.id, 4)])


def test_el_precinto_no_se_puede_repetir(e):
    pedido = e.repo.crear_pedido(e.centro.id, [(e.coca.id, 10)])
    remito = e.repo.crear_remito(e.repo.crear_orden([pedido.id_pedido]).id_orden, e.centro.id)
    b1 = e.repo.agregar_bulto(remito.id_remito, [(e.coca.id, 5)])
    b2 = e.repo.agregar_bulto(remito.id_remito, [(e.coca.id, 5)])
    e.repo.precintar(b1.id_bulto, "P-777")
    with pytest.raises(EntidadDuplicada, match="ya está usado"):
        e.repo.precintar(b2.id_bulto, " P-777 ")


def test_no_se_despacha_con_bultos_sin_precintar(e):
    pedido = e.repo.crear_pedido(e.centro.id, [(e.coca.id, 10)])
    remito = e.repo.crear_remito(e.repo.crear_orden([pedido.id_pedido]).id_orden, e.centro.id)
    e.repo.agregar_bulto(remito.id_remito, [(e.coca.id, 5)])
    with pytest.raises(DatoInvalido, match="precintados"):
        e.repo.despachar(remito.id_remito)


def test_sin_stock_en_el_cd_no_se_despacha_nada(e):
    remito_id, ids = armar_remito(e, [(e.coca.id, 30), (e.agua.id, 60)],
                                  [[(e.coca.id, 30)], [(e.agua.id, 60)]])  # agua: hay 50
    with pytest.raises(StockInsuficiente, match="Agua"):
        e.repo.despachar(remito_id)
    # Se deshizo todo: ni la coca salió del CD ni cambiaron los estados
    assert cantidad(e, e.cd, e.coca) == 100
    assert e.repo.obtener_remito(remito_id).estado == Remito.ABIERTO
    assert {e.repo.obtener_bulto(i).estado for i in ids} == {"PRECINTADO"}


def test_no_se_despacha_dos_veces(e):
    remito_id, _ = armar_remito(e, [(e.coca.id, 5)], [[(e.coca.id, 5)]])
    e.repo.despachar(remito_id)
    with pytest.raises(TransicionDeEstadoInvalida):
        e.repo.despachar(remito_id)
    assert cantidad(e, e.cd, e.coca) == 95


def test_no_se_agregan_bultos_a_un_remito_despachado(e):
    remito_id, _ = armar_remito(e, [(e.coca.id, 10)], [[(e.coca.id, 5)]])
    e.repo.despachar(remito_id)
    with pytest.raises(TransicionDeEstadoInvalida):
        e.repo.agregar_bulto(remito_id, [(e.coca.id, 5)])


# ------------------------------------------------- Validaciones: recepción

def test_no_se_recibe_un_bulto_que_no_salio_del_cd(e):
    _, (bulto_id,) = armar_remito(e, [(e.coca.id, 5)], [[(e.coca.id, 5)]])
    with pytest.raises(TransicionDeEstadoInvalida):
        e.rec.recibir(bulto_id)


def test_no_se_verifica_un_bulto_sin_recibirlo(e):
    remito_id, (bulto_id,) = armar_remito(e, [(e.coca.id, 5)], [[(e.coca.id, 5)]])
    e.repo.despachar(remito_id)
    with pytest.raises(TransicionDeEstadoInvalida):
        e.rec.verificar(bulto_id, f"P-{remito_id}-1", True)


def test_un_bulto_verificado_no_se_vuelve_a_verificar(e):
    remito_id, (bulto_id,) = armar_remito(e, [(e.coca.id, 5)], [[(e.coca.id, 5)]])
    e.repo.despachar(remito_id)
    recibir_y_verificar(e, bulto_id)
    with pytest.raises(TransicionDeEstadoInvalida):
        e.rec.verificar(bulto_id, f"P-{remito_id}-1", True)
    assert cantidad(e, e.centro, e.coca) == 5  # no se sumó dos veces


# ------------------------------------------- Trazabilidad inmutable en la base

@pytest.mark.parametrize("sql", [
    "UPDATE historial_bultos SET estado_nuevo = 'VERIFICADO'",
    "DELETE FROM historial_bultos",
])
def test_la_base_no_deja_modificar_ni_borrar_el_historial(e, sql):
    remito_id, _ = armar_remito(e, [(e.coca.id, 5)], [[(e.coca.id, 5)]])
    e.repo.despachar(remito_id)
    with get_conexion(e.db) as cx:
        with pytest.raises(sqlite3.DatabaseError, match="inmutable"):
            cx.execute(sql)
