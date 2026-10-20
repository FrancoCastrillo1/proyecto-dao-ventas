# Tests de ventas contra un SQLite temporal por test (tmp_path): que una venta
# guardada vuelva igual al leerla, y (en el service) que vender y devolver
# muevan el stock y la caja, todo junto o nada. Acá NO se prueba la api.
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from backend.dominio.excepciones import DatoInvalido, NoEncontrado, PagoInsuficiente, StockInsuficiente
from backend.dominio.maestros import Categoria, CentroDistribucion, Producto, Sucursal
from backend.dominio.medios_pago import Credito, Efectivo
from backend.dominio.stock import TipoMovimiento
from backend.dominio.ventas import Venta
from backend.persistencia.conexion import crear_tablas
from backend.persistencia.dao_maestros import CategoriaDAO, ProductoDAO, UbicacionDAO
from backend.persistencia.dao_stock import StockDAO
from backend.persistencia.dao_ventas import VentaDAO, a_centavos, desde_centavos
from backend.servicios.stock_service import StockService
from backend.servicios.ventas_service import VentasService

D = Decimal
RECEPCION = TipoMovimiento.RECEPCION
VENTA = TipoMovimiento.VENTA
DEVOLUCION = TipoMovimiento.DEVOLUCION


@pytest.fixture
def db(tmp_path):
    ruta = tmp_path / "test.db"
    crear_tablas(ruta)
    return ruta


@pytest.fixture
def datos(db):
    """Un CD, dos sucursales y dos productos."""
    categoria = CategoriaDAO(db).crear(Categoria("Bebidas"))
    productos = ProductoDAO(db)
    coca = productos.crear(Producto("BEB-001", "Coca 500ml", categoria.id, 1000, 600, stock_minimo=5))
    agua = productos.crear(Producto("BEB-002", "Agua 1L", categoria.id, 500.5, 200))
    ubicaciones = UbicacionDAO(db)
    cd = ubicaciones.crear(CentroDistribucion("CD Central", "Ruta 9 km 5"))
    centro = ubicaciones.crear(Sucursal("Local Centro", "San Martín 100"))
    norte = ubicaciones.crear(Sucursal("Local Norte", "Belgrano 900"))
    return {"coca": coca, "agua": agua, "cd": cd.id, "centro": centro.id, "norte": norte.id}


# ---------------------------------------------------------------------- DAO

@pytest.mark.parametrize("monto, centavos", [(D("1500.50"), 150050), (D("0.01"), 1), (D("-850.00"), -85000)])
def test_conversion_a_centavos_es_exacta_ida_y_vuelta(monto, centavos):
    assert a_centavos(monto) == centavos
    assert desde_centavos(centavos) == monto


def guardar_venta(db, venta, medio, entregado=None):
    dao = VentaDAO(db)
    venta.cobrar(medio, entregado)
    with dao.transaccion() as cx:
        venta.emitir_comprobante(dao.siguiente_numero_comprobante(cx, venta.sucursal_id))
        dao.crear(cx, venta)
    return venta


def test_una_venta_guardada_vuelve_igual_al_leerla(db, datos):
    venta = Venta(datos["centro"])
    venta.agregar_item(datos["coca"], 2)
    venta.agregar_item(datos["agua"], 3)
    guardar_venta(db, venta, Efectivo(), 5000)

    leida = VentaDAO(db).obtener(venta.id)
    assert (leida.id, leida.sucursal_id, leida.fecha) == (venta.id, venta.sucursal_id, venta.fecha)
    assert leida.detalles == venta.detalles
    assert (leida.subtotal, leida.total, leida.costo_total) == (D("3501.50"), D("2976.28"), D("1800.00"))
    assert type(leida.pago.medio) is Efectivo
    assert (leida.pago.porcentaje_ajuste, leida.pago.vuelto) == (D("-15"), D("2023.72"))
    assert leida.comprobante == venta.comprobante


def test_obtener_una_venta_inexistente_devuelve_none(db):
    assert VentaDAO(db).obtener(999) is None


def test_el_comprobante_es_correlativo_por_sucursal(db, datos):
    numeros = []
    for sucursal in ("centro", "centro", "norte", "centro"):
        venta = Venta(datos[sucursal])
        venta.agregar_item(datos["coca"], 1)
        numeros.append(guardar_venta(db, venta, Credito()).comprobante.codigo)
    assert numeros == [f"{datos['centro']:04d}-00000001", f"{datos['centro']:04d}-00000002",
                       f"{datos['norte']:04d}-00000001", f"{datos['centro']:04d}-00000003"]


def test_una_devolucion_guardada_vuelve_con_la_venta(db, datos):
    venta = Venta(datos["centro"])
    venta.agregar_item(datos["coca"], 3)
    guardar_venta(db, venta, Credito())
    dao = VentaDAO(db)
    devolucion = venta.devolver([(datos["coca"].id, 1)], "Falla")
    with dao.transaccion() as cx:
        dao.crear_devolucion(cx, devolucion)

    [leida] = dao.obtener(venta.id).devoluciones
    assert (leida.id, leida.motivo, leida.importe, leida.medio_pago) == (devolucion.id, "Falla", D("1100.00"), "CREDITO")
    assert leida.detalles == devolucion.detalles
    assert dao.obtener(venta.id).cantidad_devolvible(datos["coca"].id) == 2


def test_listar_filtra_por_sucursal_y_por_fechas(db, datos):
    for sucursal, fecha in (("centro", datetime(2026, 10, 1, 9)), ("centro", datetime(2026, 10, 5, 18)),
                            ("norte", datetime(2026, 10, 5, 12))):
        venta = Venta(datos[sucursal], fecha=fecha)
        venta.agregar_item(datos["coca"], 1)
        guardar_venta(db, venta, Credito())

    dao = VentaDAO(db)
    assert len(dao.listar()) == 3
    assert len(dao.listar(sucursal_id=datos["centro"])) == 2
    assert len(dao.listar(desde=datetime(2026, 10, 5), hasta=datetime(2026, 10, 6))) == 2
    assert len(dao.listar(datos["centro"], datetime(2026, 10, 2), datetime(2026, 10, 6))) == 1


# ------------------------------------------------------------------ Service

@pytest.fixture
def stock(db):
    return StockService(StockDAO(db), ProductoDAO(db), UbicacionDAO(db))


@pytest.fixture
def service(db, stock):
    return VentasService(VentaDAO(db), stock, ProductoDAO(db), UbicacionDAO(db))


@pytest.fixture
def con_stock(datos, stock):
    """10 Coca y 5 Agua en el Local Centro (entraron por recepción de un bulto)."""
    stock.ingresar(datos["centro"], datos["coca"].id, 10, RECEPCION, "Bulto 1")
    stock.ingresar(datos["centro"], datos["agua"].id, 5, RECEPCION, "Bulto 1")
    return datos


def cantidad(stock, datos, producto="coca", sucursal="centro"):
    return stock.obtener(datos[sucursal], datos[producto].id).cantidad


def test_vender_guarda_la_venta_descuenta_stock_y_suma_a_la_caja(service, stock, con_stock):
    d = con_stock
    venta = service.vender(d["centro"], [(d["coca"].id, 3), (d["agua"].id, 2)], "credito")

    assert service.obtener(venta.id).total == D("4401.10")    # (3000 + 1001) * 1.10
    assert (cantidad(stock, d), cantidad(stock, d, "agua")) == (7, 3)
    [movimiento] = service.caja(d["centro"])[0]
    assert (movimiento.tipo, movimiento.medio_pago, movimiento.importe) == ("VENTA", "CREDITO", D("4401.10"))


def test_el_movimiento_de_stock_queda_referenciado_al_comprobante(service, stock, con_stock):
    d = con_stock
    venta = service.vender(d["centro"], [(d["coca"].id, 1)], "DEBITO")
    ultimo = stock.listar_movimientos(d["centro"], d["coca"].id)[-1]
    assert (ultimo.tipo, ultimo.cantidad) == (VENTA, -1)
    assert ultimo.referencia == f"Venta {venta.comprobante.codigo}"


def test_si_un_producto_no_alcanza_no_se_guarda_nada(service, stock, con_stock):
    d = con_stock
    with pytest.raises(StockInsuficiente, match="Agua 1L"):
        service.vender(d["centro"], [(d["coca"].id, 2), (d["agua"].id, 6)], "DEBITO")   # hay 5 de agua

    assert (cantidad(stock, d), cantidad(stock, d, "agua")) == (10, 5)   # tampoco se descontó la coca
    assert service.listar() == []
    assert service.caja(d["centro"]) == ([], {})
    # El número de comprobante no se consumió
    venta = service.vender(d["centro"], [(d["coca"].id, 1)], "DEBITO")
    assert venta.comprobante.numero == 1


def test_no_se_vende_sin_stock_en_ese_local(service, con_stock):
    # Hay stock en el Centro, pero no en el Norte
    with pytest.raises(StockInsuficiente):
        service.vender(con_stock["norte"], [(con_stock["coca"].id, 1)], "DEBITO")


def test_no_se_vende_en_el_centro_de_distribucion(service, con_stock):
    with pytest.raises(DatoInvalido):
        service.vender(con_stock["cd"], [(con_stock["coca"].id, 1)], "DEBITO")


@pytest.mark.parametrize("cambio, error", [
    ({"sucursal_id": 999}, NoEncontrado),
    ({"items": [(999, 1)]}, NoEncontrado),
    ({"items": []}, DatoInvalido),
    ({"medio_pago": "CHEQUE"}, DatoInvalido),
    ({"medio_pago": "EFECTIVO", "monto_entregado": 100}, PagoInsuficiente),
])
def test_ventas_invalidas_no_guardan_nada(service, stock, con_stock, cambio, error):
    d = con_stock
    datos_venta = {"sucursal_id": d["centro"], "items": [(d["coca"].id, 1)], "medio_pago": "DEBITO"}
    datos_venta.update(cambio)
    with pytest.raises(error):
        service.vender(**datos_venta)
    assert service.listar() == []
    assert cantidad(stock, d) == 10


def test_el_precio_de_una_venta_no_cambia_si_cambia_el_del_producto(db, service, con_stock):
    d = con_stock
    venta = service.vender(d["centro"], [(d["coca"].id, 1)], "DEBITO")
    coca = d["coca"]
    coca.precio_venta = 9999
    ProductoDAO(db).actualizar(coca)
    assert service.obtener(venta.id).total == D("1000.00")


def test_devolver_reingresa_el_stock_y_saca_de_la_caja(service, stock, con_stock):
    d = con_stock
    venta = service.vender(d["centro"], [(d["coca"].id, 4)], "EFECTIVO", 5000)   # cobra 3400
    devolucion = service.devolver(venta.id, [(d["coca"].id, 1)], "Falla de fábrica")

    assert devolucion.importe == D("850.00")
    assert cantidad(stock, d) == 7        # 10 - 4 + 1
    ultimo = stock.listar_movimientos(d["centro"], d["coca"].id)[-1]
    assert (ultimo.tipo, ultimo.cantidad) == (DEVOLUCION, 1)
    movimientos, por_medio = service.caja(d["centro"])
    assert [m.importe for m in movimientos] == [D("3400.00"), D("-850.00")]
    assert por_medio == {"EFECTIVO": D("2550.00")}


def test_no_se_devuelve_una_venta_que_no_esta_registrada(service, con_stock):
    with pytest.raises(NoEncontrado):
        service.devolver(999, [(con_stock["coca"].id, 1)], "Error")


def test_las_devoluciones_guardadas_cuentan_para_las_siguientes(service, stock, con_stock):
    d = con_stock
    venta = service.vender(d["centro"], [(d["coca"].id, 3)], "DEBITO")
    service.devolver(venta.id, [(d["coca"].id, 2)], "Primera")
    with pytest.raises(DatoInvalido):
        service.devolver(venta.id, [(d["coca"].id, 2)], "Segunda")   # queda 1 por devolver
    assert cantidad(stock, d) == 9    # 10 - 3 + 2: la segunda no movió nada
    assert len(service.obtener(venta.id).devoluciones) == 1


def test_listar_por_fechas_incluye_todo_el_dia_hasta(service, con_stock):
    d = con_stock
    service.vender(d["centro"], [(d["coca"].id, 1)], "DEBITO")
    hoy = date.today()
    assert len(service.listar(d["centro"], hoy, hoy)) == 1
    assert service.listar(d["centro"], hoy + timedelta(days=1)) == []


def test_desde_posterior_a_hasta_es_invalido(service):
    with pytest.raises(DatoInvalido):
        service.listar(desde=date(2026, 10, 5), hasta=date(2026, 10, 1))


def test_la_caja_separa_por_medio_de_pago(service, con_stock):
    d = con_stock
    service.vender(d["centro"], [(d["coca"].id, 1)], "EFECTIVO")
    service.vender(d["centro"], [(d["coca"].id, 1)], "CREDITO")
    service.vender(d["centro"], [(d["coca"].id, 1)], "credito")
    _, por_medio = service.caja(d["centro"])
    assert por_medio == {"EFECTIVO": D("850.00"), "CREDITO": D("2200.00")}
