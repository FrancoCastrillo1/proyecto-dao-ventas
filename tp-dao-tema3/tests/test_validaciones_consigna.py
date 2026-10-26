# Las 5 validaciones de negocio de la consigna, una por sección, probadas de
# punta a punta con los services reales y una base temporal. Sirve como mapa
# para la defensa: cada test dice qué regla cumple y dónde se aplica.
# (Los casos borde de cada regla están en los tests de cada módulo.)
import sqlite3
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from backend.dominio.excepciones import (
    DatoInvalido, EntidadDuplicada, NoEncontrado, StockInsuficiente, TransicionDeEstadoInvalida,
)
from backend.dominio.stock import TipoMovimiento
from backend.persistencia.conexion import crear_tablas, get_conexion
from backend.persistencia.dao_logistica import BultoDAO, OrdenDAO, PedidoDAO, RemitoDAO
from backend.persistencia.dao_maestros import CategoriaDAO, ProductoDAO, ProveedorDAO, UbicacionDAO
from backend.persistencia.dao_stock import StockDAO
from backend.persistencia.dao_ventas import VentaDAO
from backend.servicios.maestros_service import CategoriaService, ProductoService, ProveedorService, UbicacionService
from backend.servicios.recepcion_service import RecepcionService
from backend.servicios.reposicion_service import ReposicionService
from backend.servicios.stock_service import StockService
from backend.servicios.ventas_service import VentasService


@pytest.fixture
def s(tmp_path):
    db = tmp_path / "test.db"
    crear_tablas(db)
    categoria = CategoriaService(CategoriaDAO(db)).crear("Bebidas")
    productos = ProductoService(ProductoDAO(db), CategoriaDAO(db))
    coca = productos.crear("BEB-1", "Coca", categoria.id, 1000, 600)
    ubicaciones = UbicacionService(UbicacionDAO(db))
    cd = ubicaciones.crear("CD", "CD Central", "Ruta 9")
    local = ubicaciones.crear("SUCURSAL", "Local Centro", "Calle 1")
    stock = StockService(StockDAO(db), ProductoDAO(db), UbicacionDAO(db))
    stock.ingresar(cd.id, coca.id, 100, TipoMovimiento.COMPRA)
    repo = ReposicionService(PedidoDAO(db), OrdenDAO(db), RemitoDAO(db), BultoDAO(db),
                             ProductoDAO(db), UbicacionDAO(db), stock)
    return SimpleNamespace(
        db=db, coca=coca, cd=cd, local=local, stock=stock, productos=productos, repo=repo,
        rec=RecepcionService(BultoDAO(db), RemitoDAO(db), stock),
        ventas=VentasService(VentaDAO(db), stock, ProductoDAO(db), UbicacionDAO(db)),
        proveedores=ProveedorService(ProveedorDAO(db), ProductoDAO(db)),
    )


def bulto_despachado(s, cantidad=10):
    pedido = s.repo.crear_pedido(s.local.id, [(s.coca.id, cantidad)])
    remito = s.repo.crear_remito(s.repo.crear_orden([pedido.id_pedido]).id_orden, s.local.id)
    bulto = s.repo.agregar_bulto(remito.id_remito, [(s.coca.id, cantidad)])
    s.repo.precintar(bulto.id_bulto, f"P-{bulto.id_bulto}")
    s.repo.despachar(remito.id_remito, datetime.now() + timedelta(days=1))
    return bulto.id_bulto


def disponible_en_local(s):
    return s.stock.obtener(s.local.id, s.coca.id).cantidad


# 1) "El stock no impacta como Disponible en la sucursal destino hasta que el
#    remito y el contenedor pasen a estado Verificado; si el precinto llega roto
#    pasa a Rechazado y no habilita venta."
#    → recepcion_service.verificar + Remito.registrar_verificacion + habilita_venta (State)

def test_1_el_stock_solo_es_disponible_con_remito_y_bulto_verificados(s):
    bulto_id = bulto_despachado(s)
    assert disponible_en_local(s) == 0          # en tránsito
    s.rec.recibir(bulto_id)
    assert disponible_en_local(s) == 0          # recibido, todavía no verificado
    s.rec.verificar(bulto_id, f"P-{bulto_id}", True)
    assert disponible_en_local(s) == 10         # verificado: disponible


def test_1_precinto_roto_rechaza_y_no_habilita_venta(s):
    bulto_id = bulto_despachado(s)
    s.rec.recibir(bulto_id)
    bulto, _, _ = s.rec.verificar(bulto_id, f"P-{bulto_id}", False)
    assert bulto.estado == "RECHAZADO" and not bulto.habilita_venta()
    assert disponible_en_local(s) == 0
    with pytest.raises(StockInsuficiente):
        s.ventas.vender(s.local.id, [(s.coca.id, 1)], "DEBITO")


def test_1_no_se_puede_meter_stock_vendible_al_local_salteando_los_bultos(s):
    with pytest.raises(DatoInvalido):  # validar_ubicacion_para: la compra entra solo al CD
        s.stock.ingresar(s.local.id, s.coca.id, 5, TipoMovimiento.COMPRA)


# 2) "Mantener trazabilidad inmutable de estados del bulto (Preparado,
#    Precintado, En tránsito, Recibido, Verificado/Rechazado)."
#    → patrón State (estados_bulto.py) + historial_bultos con triggers

def test_2_el_bulto_recorre_los_estados_en_orden_y_queda_registrado(s):
    bulto_id = bulto_despachado(s)
    s.rec.recibir(bulto_id)
    s.rec.verificar(bulto_id, f"P-{bulto_id}", True)
    historial = s.repo.obtener_bulto(bulto_id).historial
    assert [r.estado_nuevo for r in historial] == ["PRECINTADO", "EN_TRANSITO", "RECIBIDO", "VERIFICADO"]


def test_2_no_se_puede_saltear_un_estado(s):
    pedido = s.repo.crear_pedido(s.local.id, [(s.coca.id, 5)])
    remito = s.repo.crear_remito(s.repo.crear_orden([pedido.id_pedido]).id_orden, s.local.id)
    bulto = s.repo.agregar_bulto(remito.id_remito, [(s.coca.id, 5)])
    with pytest.raises(TransicionDeEstadoInvalida):  # recibir sin precintar ni despachar
        s.rec.recibir(bulto.id_bulto)


@pytest.mark.parametrize("tabla", ["historial_bultos", "movimientos_stock"])
def test_2_la_base_no_deja_reescribir_la_historia(s, tabla):
    bulto_despachado(s)
    with get_conexion(s.db) as cx:
        with pytest.raises(sqlite3.DatabaseError, match="inmutable"):
            cx.execute(f"DELETE FROM {tabla}")


# 3) "No vender cantidades superiores al stock disponible y verificado."
#    → Stock.egresar (dominio) dentro de la transacción de ventas_service.vender

def test_3_no_se_vende_mas_de_lo_disponible(s):
    bulto_id = bulto_despachado(s, cantidad=10)
    s.rec.recibir(bulto_id)
    s.rec.verificar(bulto_id, f"P-{bulto_id}", True)
    with pytest.raises(StockInsuficiente):
        s.ventas.vender(s.local.id, [(s.coca.id, 11)], "DEBITO")
    s.ventas.vender(s.local.id, [(s.coca.id, 10)], "DEBITO")
    assert disponible_en_local(s) == 0


# 4) "Evitar productos o proveedores duplicados según identificadores definidos."
#    → código (SKU) del producto y CUIT del proveedor, en el service y con UNIQUE en la base

def test_4_producto_duplicado_por_codigo(s):
    with pytest.raises(EntidadDuplicada):
        s.productos.crear("beb-1", "Otra Coca", s.coca.categoria_id, 1000, 600)


def test_4_proveedor_duplicado_por_cuit(s):
    s.proveedores.crear("20-12345678-6", "Distribuidora Sur SA")
    with pytest.raises(EntidadDuplicada):
        s.proveedores.crear("20123456786", "Otro nombre")


# 5) "No aceptar devoluciones que no correspondan a una venta registrada o que
#    incumplan las reglas establecidas."
#    → Venta.devolver (dominio) y ventas_service.devolver

def test_5_no_se_devuelve_algo_de_una_venta_inexistente(s):
    with pytest.raises(NoEncontrado):
        s.ventas.devolver(999, [(s.coca.id, 1)], "No existe")


def test_5_no_se_devuelve_mas_de_lo_vendido(s):
    bulto_id = bulto_despachado(s)
    s.rec.recibir(bulto_id)
    s.rec.verificar(bulto_id, f"P-{bulto_id}", True)
    venta = s.ventas.vender(s.local.id, [(s.coca.id, 2)], "DEBITO")
    with pytest.raises(DatoInvalido):
        s.ventas.devolver(venta.id, [(s.coca.id, 3)], "Más de lo vendido")
