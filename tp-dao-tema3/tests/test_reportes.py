# Tests de los reportes. Se arma un escenario completo a través de los services
# (compras, reposición con un bulto rechazado, ventas con distintos medios de
# pago y una devolución) y se verifica cada número contra la cuenta a mano.
# Acá NO se prueba la api.
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.dominio.excepciones import DatoInvalido, NoEncontrado
from backend.dominio.stock import TipoMovimiento
from backend.persistencia.conexion import crear_tablas, get_conexion
from backend.persistencia.dao_logistica import BultoDAO, OrdenDAO, PedidoDAO, RemitoDAO
from backend.persistencia.dao_maestros import CategoriaDAO, ProductoDAO, UbicacionDAO
from backend.persistencia.dao_reportes import ReporteDAO
from backend.persistencia.dao_stock import StockDAO
from backend.persistencia.dao_ventas import VentaDAO
from backend.servicios.maestros_service import CategoriaService, ProductoService, UbicacionService
from backend.servicios.recepcion_service import RecepcionService
from backend.servicios.reportes_service import ReportesService
from backend.servicios.reposicion_service import ReposicionService
from backend.servicios.stock_service import StockService
from backend.servicios.ventas_service import VentasService

HOY = date.today()


@pytest.fixture
def r(tmp_path):
    """
    Coca: precio 1000, costo 600, mínimo 5. Agua: precio 500, costo 200, mínimo 10.
    CD compra 100 cocas y 50 aguas. Al Local Centro se le mandan 2 bultos:
    10 cocas (verificado) y 5 aguas (rechazado por precinto roto).
    Ventas en el centro: 2 cocas con débito, 3 con efectivo (-15%), 1 con
    crédito (+10%). Se devuelve 1 coca de la venta en efectivo.
    """
    db = tmp_path / "test.db"
    crear_tablas(db)
    categoria = CategoriaService(CategoriaDAO(db)).crear("Bebidas")
    productos = ProductoService(ProductoDAO(db), CategoriaDAO(db))
    coca = productos.crear("BEB-1", "Coca", categoria.id, 1000, 600, 5)
    agua = productos.crear("BEB-2", "Agua", categoria.id, 500, 200, 10)
    ubicaciones = UbicacionService(UbicacionDAO(db))
    cd = ubicaciones.crear("CD", "CD Central", "Ruta 9")
    centro = ubicaciones.crear("SUCURSAL", "Local Centro", "Calle 1")
    norte = ubicaciones.crear("SUCURSAL", "Local Norte", "Calle 2")
    stock = StockService(StockDAO(db), ProductoDAO(db), UbicacionDAO(db))
    stock.ingresar(cd.id, coca.id, 100, TipoMovimiento.COMPRA)
    stock.ingresar(cd.id, agua.id, 50, TipoMovimiento.COMPRA)

    repo = ReposicionService(PedidoDAO(db), OrdenDAO(db), RemitoDAO(db), BultoDAO(db),
                             ProductoDAO(db), UbicacionDAO(db), stock)
    rec = RecepcionService(BultoDAO(db), RemitoDAO(db), stock)
    pedido = repo.crear_pedido(centro.id, [(coca.id, 10), (agua.id, 5)])
    remito = repo.crear_remito(repo.crear_orden([pedido.id_pedido]).id_orden, centro.id)
    b1 = repo.agregar_bulto(remito.id_remito, [(coca.id, 10)])
    b2 = repo.agregar_bulto(remito.id_remito, [(agua.id, 5)])
    repo.precintar(b1.id_bulto, "P-1")
    repo.precintar(b2.id_bulto, "P-2")
    repo.despachar(remito.id_remito)
    for bulto_id, intacto in ((b1.id_bulto, True), (b2.id_bulto, False)):
        rec.recibir(bulto_id)
        rec.verificar(bulto_id, f"P-{bulto_id}", intacto)

    ventas = VentasService(VentaDAO(db), stock, ProductoDAO(db), UbicacionDAO(db))
    ventas.vender(centro.id, [(coca.id, 2)], "DEBITO")
    efectivo = ventas.vender(centro.id, [(coca.id, 3)], "EFECTIVO")
    ventas.vender(centro.id, [(coca.id, 1)], "CREDITO")
    ventas.devolver(efectivo.id, [(coca.id, 1)], "Falla")

    service = ReportesService(ReporteDAO(db), UbicacionDAO(db))
    return SimpleNamespace(db=db, coca=coca, agua=agua, cd=cd, centro=centro, norte=norte, service=service)


# ------------------------------------- 1. Ventas e ingresos por período

def test_ventas_por_medio_de_pago_netas_de_devoluciones(r):
    reporte = r.service.ventas(agrupar="total")
    por_medio = {f["medio_pago"]: f for f in reporte["filas"]}
    assert por_medio["DEBITO"]["neto"] == Decimal("2000.00")
    assert por_medio["EFECTIVO"]["vendido"] == Decimal("2550.00")   # 3000 con -15%
    assert por_medio["EFECTIVO"]["devuelto"] == Decimal("850.00")   # 1 coca con -15%
    assert por_medio["EFECTIVO"]["neto"] == Decimal("1700.00")
    assert por_medio["CREDITO"]["neto"] == Decimal("1100.00")       # 1000 con +10%
    assert reporte["cantidad_ventas"] == 3
    assert reporte["total_neto"] == Decimal("4800.00")


def test_ventas_agrupadas_por_dia_y_por_mes(r):
    assert {f["periodo"] for f in r.service.ventas(agrupar="dia")["filas"]} == {HOY.isoformat()}
    assert {f["periodo"] for f in r.service.ventas(agrupar="mes")["filas"]} == {HOY.isoformat()[:7]}


def test_ventas_filtradas_por_fecha_y_sucursal(r):
    ayer = HOY - timedelta(days=1)
    assert r.service.ventas(hasta=ayer)["filas"] == []
    assert r.service.ventas(desde=HOY, hasta=HOY)["cantidad_ventas"] == 3
    assert r.service.ventas(sucursal_id=r.norte.id)["filas"] == []


@pytest.mark.parametrize("parametros", [
    {"agrupar": "semana"},
    {"desde": HOY, "hasta": HOY - timedelta(days=1)},
])
def test_ventas_parametros_invalidos(r, parametros):
    with pytest.raises(DatoInvalido):
        r.service.ventas(**parametros)


def test_ventas_de_una_sucursal_que_no_existe(r):
    with pytest.raises(NoEncontrado):
        r.service.ventas(sucursal_id=999)


# ---------------------------------- 2. Productos más vendidos y margen

def test_productos_mas_vendidos_con_margen_neto_de_devoluciones(r):
    (coca,) = r.service.productos_mas_vendidos()["filas"]
    assert coca["codigo"] == "BEB-1"
    assert coca["unidades"] == 5                         # 6 vendidas - 1 devuelta
    assert coca["ingreso"] == Decimal("4800.00")         # 2000 + 2550 + 1100 - 850
    assert coca["costo"] == Decimal("3000.00")           # 5 x 600
    assert coca["margen"] == Decimal("1800.00")
    assert coca["margen_porcentaje"] == 37.5


def test_limite_del_ranking_fuera_de_rango(r):
    with pytest.raises(DatoInvalido):
        r.service.productos_mas_vendidos(limite=0)


# ------------------------- 3. Existencias, bajo mínimo y valorización

def test_existencias_del_local(r):
    reporte = r.service.existencias(r.centro.id)
    filas = {f["codigo"]: f for f in reporte["filas"]}
    assert (filas["BEB-1"]["cantidad"], filas["BEB-1"]["bajo_minimo"]) == (5, False)  # 10 - 6 + 1, mínimo 5
    assert (filas["BEB-2"]["cantidad"], filas["BEB-2"]["bajo_minimo"]) == (0, True)   # el agua se rechazó
    assert filas["BEB-2"]["faltante"] == 10


def test_productos_sin_movimientos_aparecen_en_cero_y_bajo_minimo(r):
    reporte = r.service.existencias(r.norte.id, solo_bajo_minimo=True)
    assert {f["codigo"] for f in reporte["filas"]} == {"BEB-1", "BEB-2"}


def test_valorizacion_del_cd_a_costo(r):
    reporte = r.service.existencias(r.cd.id)
    assert reporte["valorizado_total"] == Decimal("63000.00")  # 90 x 600 + 45 x 200


# ------------------------------------- 4. Bultos rechazados y mermas

def test_mermas_por_bulto_rechazado(r):
    reporte = r.service.mermas()
    (fila,) = reporte["filas"]
    assert (fila["codigo"], fila["cantidad"], fila["valor_perdido"]) == ("BEB-2", 5, Decimal("1000.00"))
    assert "Precinto" in fila["observacion"]
    (centro,) = reporte["por_sucursal"]
    assert (centro["bultos_verificados"], centro["bultos_rechazados"], centro["tasa_rechazo"]) == (1, 1, 50.0)
    assert reporte["valor_perdido_total"] == Decimal("1000.00")


# ---------------------------------- 5. Tiempo de tránsito CD → locales

def test_tiempos_de_transito_cuenta_los_bultos_recibidos(r):
    reporte = r.service.tiempos_transito()
    (centro,) = reporte["filas"]
    assert centro["bultos"] == 2
    assert centro["horas_promedio"] >= 0


def test_tiempo_promedio_con_fechas_conocidas(tmp_path):
    # Se insertan bultos con horarios fijos para controlar la cuenta exacta
    db = tmp_path / "test.db"
    crear_tablas(db)
    with get_conexion(db) as cx:
        cx.execute("INSERT INTO ubicaciones (id, tipo, nombre, nombre_normalizado, direccion) "
                   "VALUES (1, 'CD', 'CD', 'cd', 'x'), (2, 'SUCURSAL', 'Local', 'local', 'x')")
        cx.execute("INSERT INTO ordenes_reposicion (id, origen_id, fecha, estado) VALUES (1, 1, '2026-10-01 08:00:00', 'CERRADA')")
        cx.execute("INSERT INTO remitos (id, orden_id, origen_id, destino_id, fecha, estado) "
                   "VALUES (1, 1, 1, 2, '2026-10-01 08:00:00', 'VERIFICADO')")
        for bulto_id, sale, llega in ((1, "2026-10-01 08:00:00", "2026-10-01 12:00:00"),
                                      (2, "2026-10-01 08:00:00", "2026-10-01 16:00:00")):
            cx.execute("INSERT INTO bultos (id, remito_id, nro_precinto, estado) VALUES (?, 1, ?, 'VERIFICADO')",
                       (bulto_id, f"P-{bulto_id}"))
            cx.execute("INSERT INTO historial_bultos (bulto_id, fecha_hora, estado_anterior, estado_nuevo) "
                       "VALUES (?, ?, 'PRECINTADO', 'EN_TRANSITO'), (?, ?, 'EN_TRANSITO', 'RECIBIDO')",
                       (bulto_id, sale, bulto_id, llega))
    reporte = ReportesService(ReporteDAO(db), UbicacionDAO(db)).tiempos_transito()
    (local,) = reporte["filas"]
    assert (local["horas_promedio"], local["horas_minimo"], local["horas_maximo"]) == (6.0, 4.0, 8.0)
    assert reporte["horas_promedio_general"] == 6.0
