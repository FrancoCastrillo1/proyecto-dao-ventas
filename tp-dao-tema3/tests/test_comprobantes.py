# Tests del paso 5: documentos descargables.
# - Template Method: DocumentoComercial arma todos los documentos igual y cada
#   hija (ComprobanteVenta, NotaCredito) completa solo lo suyo.
# - Notas de crédito numeradas por local (dominio, service, trigger, migración).
# - El PDF se genera y dice lo que tiene que decir.
# Acá NO se prueba la api (está en test_api_comprobantes.py).
import sqlite3
from datetime import datetime
from decimal import Decimal

import pytest

from backend.dominio.documentos import (
    ComprobanteVenta, ContextoDocumento, DatosComercio, DocumentoComercial, NotaCredito, Total,
)
from backend.dominio.excepciones import DatoInvalido, TransicionDeEstadoInvalida
from backend.dominio.stock import TipoMovimiento
from backend.persistencia.conexion import crear_tablas, get_conexion
from backend.persistencia.dao_maestros import CategoriaDAO, ProductoDAO, UbicacionDAO
from backend.persistencia.dao_stock import StockDAO
from backend.persistencia.dao_ventas import VentaDAO
from backend.servicios.comprobantes_service import ComprobantesService
from backend.servicios.documentos_pdf import dibujar, pesos, texto_seguro
from backend.servicios.maestros_service import CategoriaService, ProductoService, UbicacionService
from backend.servicios.stock_service import StockService
from backend.servicios.ventas_service import VentasService

COMERCIO = DatosComercio("Comercio de Prueba S.A.", "30-71111111-1", "Calle 1")


@pytest.fixture
def red(tmp_path):
    """Dos locales con stock de agua y coca, y el service de ventas."""
    db = tmp_path / "test.db"
    crear_tablas(db)
    categoria = CategoriaService(CategoriaDAO(db)).crear("Bebidas")
    productos = ProductoService(ProductoDAO(db))
    agua = productos.crear("BEB-001", "Agua 1L", categoria.id, 1000, 500)
    coca = productos.crear("BEB-002", "Coca 500ml", categoria.id, 2000, 1200)
    ubicaciones = UbicacionService(UbicacionDAO(db))
    ubicaciones.crear("CD", "CD Central", "Ruta 9")
    centro = ubicaciones.crear("SUCURSAL", "Local Centro", "San Martín 1")
    norte = ubicaciones.crear("SUCURSAL", "Local Norte", "Belgrano 2")
    stock = StockService(StockDAO(db), ProductoDAO(db), UbicacionDAO(db))
    for local in (centro, norte):
        for producto in (agua, coca):
            stock.ingresar(local.id, producto.id, 50, TipoMovimiento.RECEPCION, "Bulto de prueba")
    ventas = VentasService(VentaDAO(db), stock, ProductoDAO(db), UbicacionDAO(db))
    comprobantes = ComprobantesService(VentaDAO(db))
    return dict(db=db, agua=agua, coca=coca, centro=centro, norte=norte, ventas=ventas, comprobantes=comprobantes)


def contexto(atendio="Lucía"):
    return ContextoDocumento(COMERCIO, "Local Centro", "San Martín 1", atendio, {})


# ============================================== Template Method en el dominio

def test_el_comprobante_de_una_venta_en_efectivo(red):
    venta = red["ventas"].vender(red["centro"].id, [(red["agua"].id, 2), (red["coca"].id, 1)], "EFECTIVO", 5000)
    ctx = ContextoDocumento(COMERCIO, "Local Centro", "San Martín 1", "Lucía", {red["agua"].id: "Agua 1L"})
    contenido = ComprobanteVenta(venta, ctx).armar()

    assert (contenido.titulo, contenido.codigo) == ("Comprobante de venta", venta.comprobante.codigo)
    assert contenido.nombre_archivo == f"comprobante-{venta.comprobante.codigo}.pdf"
    assert contenido.encabezado == ("Comercio de Prueba S.A.", "CUIT 30-71111111-1 · Calle 1", "Local Centro · San Martín 1")
    assert [(r.descripcion, r.cantidad, r.importe) for r in contenido.renglones] == \
        [("Agua 1L", 2, Decimal("2000.00")), (f"Producto {red['coca'].id}", 1, Decimal("2000.00"))]
    assert [(t.etiqueta, t.importe, t.destacado) for t in contenido.totales] == [
        ("Subtotal", Decimal("4000.00"), False),
        ("Descuento 15% (Efectivo)", Decimal("-600.00"), False),
        ("Total", Decimal("3400.00"), True),
    ]                                                       # el vuelto no va en el comprobante
    assert contenido.notas == ("Pagado con Efectivo", "Atendió: Lucía")


def test_sin_ajuste_no_hay_renglon_de_descuento_y_el_credito_tiene_recargo(red):
    debito = red["ventas"].vender(red["centro"].id, [(red["agua"].id, 1)], "DEBITO")
    credito = red["ventas"].vender(red["centro"].id, [(red["agua"].id, 1)], "CREDITO")
    assert [t.etiqueta for t in ComprobanteVenta(debito, contexto()).armar().totales] == ["Subtotal", "Total"]
    assert "Recargo 10% (Crédito)" in [t.etiqueta for t in ComprobanteVenta(credito, contexto()).armar().totales]


def test_la_nota_de_credito_de_una_devolucion(red):
    venta = red["ventas"].vender(red["centro"].id, [(red["agua"].id, 3)], "EFECTIVO")
    devolucion = red["ventas"].devolver(venta.id, [(red["agua"].id, 1)], "Envase roto")
    contenido = NotaCredito(devolucion, venta, contexto(atendio=None)).armar()

    assert (contenido.titulo, contenido.codigo) == ("Nota de crédito", devolucion.nota_credito.codigo)
    assert contenido.nombre_archivo.startswith("nota-credito-")
    assert [(r.cantidad, r.precio_unitario, r.importe) for r in contenido.renglones] == [(1, None, Decimal("850.00"))]
    assert [(t.etiqueta, t.importe) for t in contenido.totales] == [("Total reintegrado", Decimal("850.00"))]
    assert contenido.notas == (f"Por la devolución de la venta {venta.comprobante.codigo}", "Motivo: Envase roto",
                               "Se reintegra en Efectivo")   # sin "Atendió" si no se sabe quién


def test_el_metodo_plantilla_fija_el_orden_y_las_hijas_solo_completan_pasos():
    # Un documento nuevo solo define los pasos: armar() (la plantilla) es el mismo
    class Presupuesto(DocumentoComercial):
        def titulo(self): return "Presupuesto"
        def codigo(self): return "P-1"
        def fecha(self): return datetime(2026, 10, 23)
        def renglones(self): return []
        def totales(self): return [Total("Total", Decimal("0"), destacado=True)]
        def prefijo_archivo(self): return "presupuesto"

    contenido = Presupuesto(contexto()).armar()
    assert (contenido.titulo, contenido.nombre_archivo) == ("Presupuesto", "presupuesto-P-1.pdf")
    assert contenido.encabezado[0] == "Comercio de Prueba S.A."   # paso común, heredado
    assert contenido.notas == ("Atendió: Lucía",)                  # gancho sin redefinir + nota común
    with pytest.raises(TypeError):
        DocumentoComercial(contexto())                             # la plantilla sola no se instancia


def test_sin_comprobante_ni_nota_no_hay_documento():
    from backend.dominio.ventas import Devolucion, Venta
    with pytest.raises(DatoInvalido, match="no tiene comprobante"):
        ComprobanteVenta(Venta(1), contexto())
    with pytest.raises(DatoInvalido, match="no tiene nota de crédito"):
        NotaCredito(Devolucion(1, 1, "EFECTIVO", "x", []), Venta(1), contexto())


# ================================================ Numeración de notas de crédito

def test_las_notas_de_credito_son_correlativas_por_local(red):
    ventas = red["ventas"]
    en_centro = ventas.vender(red["centro"].id, [(red["agua"].id, 5)], "DEBITO")
    en_norte = ventas.vender(red["norte"].id, [(red["agua"].id, 5)], "DEBITO")
    c1 = ventas.devolver(en_centro.id, [(red["agua"].id, 1)], "Uno")
    n1 = ventas.devolver(en_norte.id, [(red["agua"].id, 1)], "Uno")
    c2 = ventas.devolver(en_centro.id, [(red["agua"].id, 1)], "Dos")
    centro, norte = red["centro"].id, red["norte"].id
    assert [c1.nota_credito.codigo, c2.nota_credito.codigo, n1.nota_credito.codigo] == \
        [f"{centro:04d}-00000001", f"{centro:04d}-00000002", f"{norte:04d}-00000001"]
    # Y se guardan: la venta leída de la base trae sus notas de crédito
    leida = VentaDAO(red["db"]).obtener(en_centro.id)
    assert [d.nota_credito.numero for d in leida.devoluciones] == [1, 2]
    # El movimiento de caja nombra la nota de crédito
    with get_conexion(red["db"]) as cx:
        referencias = [f[0] for f in cx.execute("SELECT referencia FROM movimientos_caja WHERE tipo = 'DEVOLUCION'")]
    assert referencias[0].startswith(f"Nota de crédito {centro:04d}-00000001")


def test_una_devolucion_no_tiene_dos_notas_de_credito(red):
    venta = red["ventas"].vender(red["centro"].id, [(red["agua"].id, 2)], "DEBITO")
    devolucion = red["ventas"].devolver(venta.id, [(red["agua"].id, 1)], "Uno")
    with pytest.raises(TransicionDeEstadoInvalida, match="ya tiene nota de crédito"):
        devolucion.emitir_nota_credito(7)


def test_la_base_no_repite_el_numero_de_nota_de_credito_en_un_local(red):
    venta = red["ventas"].vender(red["centro"].id, [(red["agua"].id, 2)], "DEBITO")
    red["ventas"].devolver(venta.id, [(red["agua"].id, 1)], "Uno")
    with get_conexion(red["db"]) as cx, pytest.raises(sqlite3.IntegrityError, match="ya existe en este local"):
        cx.execute("INSERT INTO devoluciones (venta_id, fecha, motivo, importe, nro_nota_credito) "
                   "VALUES (?, '2026-10-23 10:00:00', 'x', 100, 1)", (venta.id,))


def test_migra_las_devoluciones_de_antes_numerandolas_por_local(red):
    ventas = red["ventas"]
    en_centro = ventas.vender(red["centro"].id, [(red["agua"].id, 5)], "DEBITO")
    en_norte = ventas.vender(red["norte"].id, [(red["agua"].id, 5)], "DEBITO")
    for venta in (en_centro, en_norte, en_centro):
        ventas.devolver(venta.id, [(red["agua"].id, 1)], "Vieja")
    # Se deja la tabla como estaba antes: sin la columna del número ni su trigger
    with sqlite3.connect(red["db"]) as cx:
        cx.execute("DROP TRIGGER notas_credito_unicas_por_local")
        cx.execute("ALTER TABLE devoluciones DROP COLUMN nro_nota_credito")

    crear_tablas(red["db"])   # lo que hace la app al arrancar

    with get_conexion(red["db"]) as cx:
        numeros = cx.execute("SELECT v.sucursal_id, d.nro_nota_credito FROM devoluciones d "
                             "JOIN ventas v ON v.id = d.venta_id ORDER BY d.id").fetchall()
    assert [tuple(f) for f in numeros] == [(red["centro"].id, 1), (red["norte"].id, 1), (red["centro"].id, 2)]


# ================================================================ El PDF

def test_el_service_arma_el_pdf_con_el_numero_y_quien_atendio(red):
    venta = red["ventas"].vender(red["centro"].id, [(red["agua"].id, 2)], "EFECTIVO", 2000)
    nombre, contenido = red["comprobantes"].comprobante_de_venta(red["comprobantes"].obtener_venta(venta.id))
    assert nombre == f"comprobante-{venta.comprobante.codigo}.pdf"
    assert contenido.startswith(b"%PDF")
    for texto in (venta.comprobante.codigo, "Agua 1L", "Local Centro", "Total", "1.700,00"):
        assert texto.encode("latin-1") in contenido, texto


def test_la_nota_de_credito_tiene_que_ser_de_esa_venta(red):
    from backend.dominio.excepciones import NoEncontrado
    venta = red["ventas"].vender(red["centro"].id, [(red["agua"].id, 2)], "DEBITO")
    with pytest.raises(NoEncontrado, match="no es de la venta"):
        red["comprobantes"].nota_de_credito(red["comprobantes"].obtener_venta(venta.id), 999)


def test_pesos_con_formato_argentino():
    assert pesos(Decimal("1234567.5")) == "$ 1.234.567,50"
    assert pesos(Decimal("-600")) == "-$ 600,00"


def test_un_nombre_con_caracteres_raros_no_rompe_el_pdf():
    assert texto_seguro("Café ñandú 🍺") == "Café ñandú ?"
    venta_contexto = ContextoDocumento(COMERCIO, "Local 🏬", "Calle", None, {})

    class Simple(DocumentoComercial):
        def titulo(self): return "Prueba"
        def codigo(self): return "1"
        def fecha(self): return datetime(2026, 10, 23)
        def renglones(self): return []
        def totales(self): return []
        def prefijo_archivo(self): return "prueba"

    assert dibujar(Simple(venta_contexto).armar()).startswith(b"%PDF")
