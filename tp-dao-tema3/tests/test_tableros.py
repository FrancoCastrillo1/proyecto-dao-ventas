# Tests de los tableros: el período y los indicadores (dominio) y cada tablero
# con ventas de fechas y horas conocidas (service), para comprobar las cuentas
# a mano. Las fechas son relativas a hoy (así las devoluciones siguen dentro
# del plazo). Los permisos de cada perfil se prueban en test_api_tableros.py.
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.dominio.excepciones import DatoInvalido
from backend.dominio.periodo import Periodo, diferencia, margen, proporcion, variacion
from backend.dominio.stock import TipoMovimiento
from backend.persistencia.conexion import crear_tablas
from backend.persistencia.dao_logistica import BultoDAO, OrdenDAO, PedidoDAO, RemitoDAO
from backend.persistencia.dao_maestros import CategoriaDAO, ProductoDAO, UbicacionDAO
from backend.persistencia.dao_reportes import ReporteDAO
from backend.persistencia.dao_stock import StockDAO
from backend.persistencia.dao_tableros import TableroDAO
from backend.persistencia.dao_ventas import VentaDAO
from backend.servicios.maestros_service import CategoriaService, ProductoService, UbicacionService
from backend.servicios.recepcion_service import RecepcionService
from backend.servicios.reportes_service import ReportesService
from backend.servicios.reposicion_service import ReposicionService
from backend.servicios.stock_service import StockService
from backend.servicios.tableros_service import (
    TablerosService, cuadrante, estado_del_pedido, tramo_de,
)
from backend.servicios.ventas_service import VentasService

D = Decimal
HOY = date.today()
INICIO = HOY - timedelta(days=15)       # el período de los tests: 10 días desde acá


# ------------------------------------------------------------------ Período

def test_sin_fechas_son_los_ultimos_30_dias():
    periodo = Periodo.elegido(hoy=date(2026, 10, 29))
    assert (periodo.desde, periodo.hasta, periodo.dias) == (date(2026, 9, 30), date(2026, 10, 29), 30)


def test_el_periodo_anterior_tiene_los_mismos_dias_justo_antes():
    anterior = Periodo(date(2026, 10, 1), date(2026, 10, 29)).comparado("anterior")
    assert (anterior.desde, anterior.hasta) == (date(2026, 9, 2), date(2026, 9, 30))


def test_el_mismo_periodo_del_anio_anterior():
    anterior = Periodo(date(2028, 2, 1), date(2028, 2, 29)).comparado("anio")
    assert (anterior.desde, anterior.hasta) == (date(2027, 2, 1), date(2027, 2, 28))   # 2027 no es bisiesto


@pytest.mark.parametrize("hacer", [
    lambda: Periodo(date(2026, 10, 2), date(2026, 10, 1)),
    lambda: Periodo(date(2024, 1, 1), date(2026, 1, 1)),
    lambda: Periodo(date(2026, 10, 1), date(2026, 10, 2)).comparado("semana"),
])
def test_periodos_invalidos(hacer):
    with pytest.raises(DatoInvalido):
        hacer()


@pytest.mark.parametrize("actual, anterior, esperado", [
    (150, 100, 50.0), (50, 100, -50.0), (100, 0, None), (100, None, None), (0, 100, -100.0),
])
def test_variacion_sin_porcentajes_enganosos(actual, anterior, esperado):
    assert variacion(actual, anterior) == esperado


def test_margen_proporcion_y_diferencia_en_puntos():
    assert margen(D(300), D(1000)) == 30.0
    assert margen(D(10), D(0)) is None
    assert proporcion(1, 4) == 25.0 and proporcion(1, 0) is None
    assert diferencia(25.0, 20.0) == 5.0 and diferencia(25.0, None) is None


# ---------------------------------------------------------- Reglas sueltas

@pytest.mark.parametrize("dias, tramo", [
    (0, "0 a 30 días"), (30, "0 a 30 días"), (31, "31 a 60 días"), (90, "61 a 90 días"),
    (91, "Más de 90 días"), (None, "Nunca salió"),
])
def test_tramo_de_la_ultima_salida(dias, tramo):
    assert tramo_de(dias) == tramo


@pytest.mark.parametrize("unidades, margen_producto, esperado", [
    (10, 40, "Estrellas"), (10, 10, "Mucho volumen, poco margen"),
    (2, 40, "Buen margen, poca venta"), (2, 10, "A revisar"), (10, None, "Mucho volumen, poco margen"),
])
def test_cuadrante_de_la_matriz(unidades, margen_producto, esperado):
    assert cuadrante(unidades, margen_producto, corte_unidades=5, corte_margen=30) == esperado


@pytest.mark.parametrize("pedido, estado", [
    ({"estado_pedido": "PENDIENTE", "estado_remito": None}, "Pendiente"),
    ({"estado_pedido": "CONSOLIDADO", "estado_remito": None}, "En preparación"),
    ({"estado_pedido": "CONSOLIDADO", "estado_remito": "CERRADO"}, "En preparación"),
    ({"estado_pedido": "CONSOLIDADO", "estado_remito": "EN_TRANSITO"}, "En camino"),
    ({"estado_pedido": "CONSOLIDADO", "estado_remito": "VERIFICADO"}, "Recibido"),
    ({"estado_pedido": "CONSOLIDADO", "estado_remito": "VERIFICADO_CON_RECHAZOS"}, "Recibido con rechazos"),
])
def test_estado_de_un_pedido(pedido, estado):
    assert estado_del_pedido(pedido) == estado


# ------------------------------------------------------------- Con una base

def momento(dias_desde_el_inicio, hora, minuto=0):
    return datetime.combine(INICIO + timedelta(days=dias_desde_el_inicio), time(hora, minuto))


@pytest.fixture
def t(tmp_path):
    """
    Coca (Bebidas): precio 1000, costo 600. Fideos (Almacén): precio 500, costo 400.
    El CD manda a Centro 50 cocas y 50 fideos, y a Norte 20 cocas y 10 fideos.
    Ventas con débito (sin recargo), en el período [INICIO, INICIO + 9]:
      Centro día 1 10:30  2 cocas   → 2000 (costo 1200)
      Centro día 1 11:15  4 fideos  → 2000 (costo 1600); después se devuelve 1 fideo (500)
      Centro día 4 19:00  1 coca    → 1000 (costo 600)
      Norte  día 2 12:00  3 cocas   → 3000 (costo 1800)
    Y antes del período (día -5, 10:00): Centro 1 coca → 1000 (costo 600).
    Norte nunca vende los fideos.
    """
    db = tmp_path / "test.db"
    crear_tablas(db)
    categorias = CategoriaService(CategoriaDAO(db))
    productos = ProductoService(ProductoDAO(db), CategoriaDAO(db))
    coca = productos.crear("BEB-1", "Coca", categorias.crear("Bebidas").id, 1000, 600, 5)
    fideos = productos.crear("ALM-1", "Fideos", categorias.crear("Almacén").id, 500, 400, 5)
    ubicaciones = UbicacionService(UbicacionDAO(db))
    cd = ubicaciones.crear("CD", "CD Central", "Ruta 9")
    centro = ubicaciones.crear("SUCURSAL", "Local Centro", "Calle 1")
    norte = ubicaciones.crear("SUCURSAL", "Local Norte", "Calle 2")
    stock = StockService(StockDAO(db), ProductoDAO(db), UbicacionDAO(db))
    stock.ingresar(cd.id, coca.id, 100, TipoMovimiento.COMPRA)
    stock.ingresar(cd.id, fideos.id, 100, TipoMovimiento.COMPRA)

    repo = ReposicionService(PedidoDAO(db), OrdenDAO(db), RemitoDAO(db), BultoDAO(db),
                             ProductoDAO(db), UbicacionDAO(db), stock)
    rec = RecepcionService(BultoDAO(db), RemitoDAO(db), stock)
    envios = {centro.id: [(coca.id, 50), (fideos.id, 50)], norte.id: [(coca.id, 20), (fideos.id, 10)]}
    pedidos = [repo.crear_pedido(local, items).id_pedido for local, items in envios.items()]
    orden = repo.crear_orden(pedidos)
    for i, (local, items) in enumerate(envios.items()):
        remito = repo.crear_remito(orden.id_orden, local)
        bulto = repo.agregar_bulto(remito.id_remito, items)
        repo.precintar(bulto.id_bulto, f"P-{i}")
        repo.despachar(remito.id_remito, datetime.now() + timedelta(days=1))
        rec.recibir(bulto.id_bulto)
        rec.verificar(bulto.id_bulto, f"P-{i}", True)

    ventas = VentasService(VentaDAO(db), stock, ProductoDAO(db), UbicacionDAO(db))
    ventas.vender(centro.id, [(coca.id, 2)], "DEBITO", fecha=momento(1, 10, 30))
    con_fideos = ventas.vender(centro.id, [(fideos.id, 4)], "DEBITO", fecha=momento(1, 11, 15))
    ventas.vender(centro.id, [(coca.id, 1)], "DEBITO", fecha=momento(4, 19))
    ventas.vender(norte.id, [(coca.id, 3)], "DEBITO", fecha=momento(2, 12))
    ventas.vender(centro.id, [(coca.id, 1)], "DEBITO", fecha=momento(-5, 10))
    ventas.devolver(con_fideos.id, [(fideos.id, 1)], "Paquete roto")

    service = TablerosService(TableroDAO(db), UbicacionDAO(db), ReportesService(ReporteDAO(db), UbicacionDAO(db)))
    return SimpleNamespace(db=db, service=service, coca=coca, fideos=fideos, cd=cd, centro=centro, norte=norte)


def del_periodo(t, tablero, **opciones):
    return getattr(t.service, tablero)(INICIO, INICIO + timedelta(days=9), **opciones)


def por_titulo(datos):
    return {i["titulo"]: i for i in datos["indicadores"]}


# ----------------------------------------------------------------- Ejecutivo

def test_ejecutivo_indicadores_contra_el_periodo_anterior(t):
    indicadores = por_titulo(del_periodo(t, "ejecutivo"))
    ventas = indicadores["Ventas netas"]
    assert (ventas["valor"], ventas["anterior"], ventas["cambio"]) == (D("7500.00"), D("1000.00"), 650.0)
    assert indicadores["Ganancia bruta"]["valor"] == D("2700.00")          # 7500 - (1200 + 1200 + 600 + 1800)
    margen_bruto = indicadores["Margen bruto"]
    assert (margen_bruto["valor"], margen_bruto["anterior"], margen_bruto["cambio"]) == (36.0, 40.0, -4.0)
    assert margen_bruto["en_puntos"]
    assert (indicadores["Tickets"]["valor"], indicadores["Tickets"]["cambio"]) == (4, 300.0)


def test_ejecutivo_ranking_de_locales_y_categorias(t):
    datos = del_periodo(t, "ejecutivo")
    assert [(l["sucursal"], l["ventas"], l["participacion"]) for l in datos["locales"]] == [
        ("Local Centro", D("4500.00"), 60.0), ("Local Norte", D("3000.00"), 40.0)]
    assert [(c["categoria"], c["ventas"], c["ganancia"]) for c in datos["categorias"]] == [
        ("Bebidas", D("6000.00"), D("2400.00")), ("Almacén", D("1500.00"), D("300.00"))]


def test_ejecutivo_evolucion_dia_por_dia_contra_el_anterior(t):
    evolucion = del_periodo(t, "ejecutivo")["evolucion"]
    assert evolucion["agrupado"] == "dia" and len(evolucion["puntos"]) == 10
    assert evolucion["puntos"][1]["actual"] == D("3500.00")     # día 1: coca + fideos menos la devolución
    assert evolucion["puntos"][5]["anterior"] == D("1000.00")   # el día -5 es el 6.º del período anterior


def test_ejecutivo_de_un_local_y_contra_el_anio_anterior(t):
    datos = del_periodo(t, "ejecutivo", comparar="anio", sucursal_id=t.norte.id)
    ventas = por_titulo(datos)["Ventas netas"]
    assert (ventas["valor"], ventas["anterior"], ventas["cambio"]) == (D("3000.00"), D("0.00"), None)
    assert datos["periodo"]["comparar"] == "anio"


def test_ejecutivo_por_semana_en_periodos_largos(t):
    datos = t.service.ejecutivo(HOY - timedelta(days=89), HOY)
    assert datos["evolucion"]["agrupado"] == "semana" and len(datos["evolucion"]["puntos"]) == 13


# ----------------------------------------------------------- Ventas del local

def test_ventas_del_local_tickets_y_ticket_promedio(t):
    indicadores = por_titulo(del_periodo(t, "ventas_local", sucursal_id=t.centro.id))
    assert indicadores["Tickets"]["valor"] == 3
    assert indicadores["Ticket promedio"]["valor"] == D("1500.00")           # 4500 / 3
    assert indicadores["Unidades vendidas"]["valor"] == 6                    # 2 + 3 + 1
    assert indicadores["Artículos por ticket"]["valor"] == 2.0


def test_mapa_de_calor_por_dia_de_la_semana_y_franja(t):
    mapa = del_periodo(t, "ventas_local", sucursal_id=t.centro.id)["mapa_calor"]
    filas = {f["franja"]: f for f in mapa["filas"]}
    assert list(filas)[0] == "08 a 10 h" and list(filas)[-1] == "20 a 22 h"
    dia = momento(1, 10).weekday()
    assert filas["10 a 12 h"]["ventas"][dia] == D("3500.00")
    assert filas["10 a 12 h"]["tickets"][dia] == 2
    assert filas["18 a 20 h"]["ventas"][momento(4, 19).weekday()] == D("1000.00")
    assert mapa["maximo"] == D("3500.00")


def test_ventas_por_dia_categorias_y_devoluciones(t):
    datos = del_periodo(t, "ventas_local", sucursal_id=t.centro.id)
    assert len(datos["por_dia"]) == 10
    assert (datos["por_dia"][4]["ventas"], datos["por_dia"][4]["tickets"]) == (D("1000.00"), 1)
    assert {c["categoria"]: c["unidades"] for c in datos["categorias"]} == {"Bebidas": 3, "Almacén": 3}
    # Las devoluciones salen del reporte de devoluciones (su detalle): se cuentan cuando se hicieron (hoy)
    devoluciones = t.service.ventas_local(sucursal_id=t.centro.id)["devoluciones"]
    assert (devoluciones["cantidad"], devoluciones["unidades"], devoluciones["reintegrado"]) == (1, 1, D("500.00"))
    assert [p["codigo"] for p in devoluciones["productos"]] == ["ALM-1"]
    assert "productos" not in datos          # el ranking está en el tablero de productos


# ------------------------------------------------------ Productos e inventario

def test_matriz_volumen_por_margen(t):
    matriz = del_periodo(t, "productos")["matriz"]
    puntos = {p["codigo"]: p for p in matriz["puntos"]}
    assert (puntos["BEB-1"]["unidades"], puntos["BEB-1"]["margen"]) == (6, 40.0)
    assert (puntos["ALM-1"]["unidades"], puntos["ALM-1"]["margen"]) == (3, 20.0)
    assert (matriz["corte_unidades"], matriz["corte_margen"]) == (4.5, 36.0)
    assert (puntos["BEB-1"]["cuadrante"], puntos["ALM-1"]["cuadrante"]) == ("Estrellas", "A revisar")


def test_ranking_de_los_mas_vendidos_con_margen(t):
    ranking = del_periodo(t, "productos")["ranking"]
    assert [(f["codigo"], f["unidades"], f["margen"]) for f in ranking] == [
        ("BEB-1", 6, D("2400.00")), ("ALM-1", 3, D("300.00"))]


def test_sin_rentabilidad_no_hay_matriz_ni_ranking(t):
    datos = del_periodo(t, "productos", con_rentabilidad=False)
    assert datos["matriz"] is None and datos["ranking"] is None
    assert "Margen bruto" not in por_titulo(datos)


def test_stock_parado_por_la_ultima_salida(t):
    stock = del_periodo(t, "productos", hoy=HOY + timedelta(days=40))["stock"]
    tramos = {t_["tramo"]: t_ for t_ in stock["tramos"]}
    assert (tramos["Nunca salió"]["productos"], tramos["Nunca salió"]["valor"]) == (1, D("4000.00"))  # 10 fideos de Norte
    assert tramos["0 a 30 días"]["productos"] == 0
    assert tramos["31 a 60 días"]["productos"] == 5      # lo demás salió hace entre 40 y 54 días


def test_el_detalle_del_stock_es_el_reporte_de_existencias(t):
    filas = {(f["ubicacion"], f["codigo"]): f for f in t.service.reportes.existencias(hoy=HOY + timedelta(days=40))["filas"]}
    assert filas[("Local Centro", "ALM-1")]["dias_sin_salir"] == 40 + 14       # se vendió en el día 1 (hace 14)
    assert filas[("CD Central", "BEB-1")]["dias_sin_salir"] == 40               # salió despachado hoy
    assert filas[("Local Norte", "ALM-1")]["dias_sin_salir"] is None            # nunca salió


def test_inventario_de_una_sola_ubicacion(t):
    indicadores = por_titulo(del_periodo(t, "productos", ubicacion_id=t.cd.id))
    assert indicadores["Inventario valorizado"]["valor"] == D("34000.00")       # 30 cocas x 600 + 40 fideos x 400
    assert indicadores["Productos para reponer"]["valor"] == 0


# ------------------------------------------------------------- Abastecimiento

def test_abastecimiento_estados_y_tiempos(t):
    datos = t.service.abastecimiento()
    assert [(f["sucursal"], f["Recibido"]) for f in datos["por_estado"]] == [("Local Centro", 1), ("Local Norte", 1)]
    assert {f["sucursal"] for f in datos["tiempos"]} == {"Local Centro", "Local Norte"}
    assert all(p["horas"] is not None and p["horas"] >= 0 for p in datos["pedidos"])
    assert por_titulo(datos)["Pedidos"]["valor"] == 2
    assert por_titulo(datos)["Perdido en bultos rechazados"]["valor"] == D("0.00")
    assert {m["sucursal"] for m in datos["mermas"]} == {"Local Centro", "Local Norte"}
    assert datos["demanda"] is None                        # lo más pedido de la red, solo si se pide


def test_abastecimiento_con_lo_mas_pedido_de_la_red(t):
    demanda = t.service.abastecimiento(con_demanda=True)["demanda"]
    assert [(f["codigo"], f["unidades"]) for f in demanda] == [("BEB-1", 70), ("ALM-1", 60)]


# ---------------------------------------------------------------------- PDF

@pytest.mark.parametrize("clave, metodo, textos", [
    ("ejecutivo", "ejecutivo", [b"Tablero ejecutivo", b"vs. $ 1.000,00", b"Ranking de locales"]),
    ("ventas", "ventas_local", [b"Tablero de ventas", b"Ventas netas por d", b"Ticket promedio por d", b"Lun"]),
    ("productos", "productos", [b"Matriz volumen x margen", b"Valor del stock"]),
    ("abastecimiento", "abastecimiento", [b"Tablero de abastecimiento", b"Pedidos por estado y local"]),
])
def test_cada_tablero_sale_en_pdf_con_sus_graficos(t, clave, metodo, textos):
    # Los pedidos del fixture son de hoy: abastecimiento mira los últimos 30 días
    datos = t.service.abastecimiento() if metodo == "abastecimiento" else del_periodo(t, metodo)
    nombre, contenido = t.service.pdf(clave, datos, "Dora", t.centro.id)
    assert nombre.startswith(f"reporte-tablero-{clave}-") and contenido.startswith(b"%PDF")
    assert b"Local Centro" in contenido and b"por Dora" in contenido
    for texto in textos:
        assert texto in contenido, texto


def test_abastecimiento_de_un_local_y_un_pedido_pendiente(t):
    repo = ReposicionService(PedidoDAO(t.db), OrdenDAO(t.db), RemitoDAO(t.db), BultoDAO(t.db),
                             ProductoDAO(t.db), UbicacionDAO(t.db),
                             StockService(StockDAO(t.db), ProductoDAO(t.db), UbicacionDAO(t.db)))
    repo.crear_pedido(t.norte.id, [(t.coca.id, 5)])
    datos = t.service.abastecimiento(sucursal_id=t.norte.id)
    assert [p["estado"] for p in datos["pedidos"]] == ["Pendiente", "Recibido"]
    assert por_titulo(datos)["Sin preparar"]["valor"] == 1
    assert {f["sucursal"] for f in datos["por_estado"]} == {"Local Norte"}
