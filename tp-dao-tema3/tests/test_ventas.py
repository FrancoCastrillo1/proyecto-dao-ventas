# Tests de ventas: totales, medios de pago (Strategy), comprobantes y devoluciones.
# Acá NO se prueba la base de datos ni la api.
from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from backend.dominio.excepciones import DatoInvalido, PagoInsuficiente, TransicionDeEstadoInvalida
from backend.dominio.maestros import Producto
from backend.dominio.medios_pago import Credito, Debito, Efectivo
from backend.dominio.ventas import DetalleVenta, Venta

D = Decimal


def producto(id=1, precio=1000, costo=600, activo=True):
    return Producto(f"P-{id}", f"Producto {id}", 1, precio, costo, id=id, activo=activo)


def venta_con(*items, sucursal_id=2):
    """items: pares (producto, cantidad)."""
    venta = Venta(sucursal_id)
    for prod, cantidad in items:
        venta.agregar_item(prod, cantidad)
    return venta


# ---------- armar la venta ----------

def test_venta_nueva_arranca_vacia_y_sin_cobrar():
    venta = Venta(2)
    assert venta.detalles == ()
    assert venta.subtotal == D("0.00")
    assert not venta.esta_cobrada()
    assert venta.total is None


def test_agregar_item_copia_el_precio_y_el_costo_del_producto():
    venta = venta_con((producto(precio=1500.5, costo=900), 2))
    [detalle] = venta.detalles
    assert (detalle.producto_id, detalle.cantidad) == (1, 2)
    assert (detalle.precio_unitario, detalle.costo_unitario) == (D("1500.50"), D("900.00"))


def test_el_precio_queda_fijo_aunque_despues_cambie_el_del_producto():
    prod = producto(precio=1000)
    venta = venta_con((prod, 1))
    prod.precio_venta = 5000
    assert venta.detalles[0].precio_unitario == D("1000.00")


def test_el_mismo_producto_dos_veces_suma_a_la_misma_linea():
    prod = producto()
    venta = venta_con((prod, 2), (prod, 3))
    assert [(d.producto_id, d.cantidad) for d in venta.detalles] == [(1, 5)]


def test_subtotal_y_costo_suman_todas_las_lineas():
    venta = venta_con((producto(1, 1000, 600), 2), (producto(2, 250.25, 100), 4))
    assert venta.subtotal == D("3001.00")
    assert venta.costo_total == D("1600.00")


@pytest.mark.parametrize("cantidad", [0, -1, 1.5, "2", None, True])
def test_cantidad_invalida(cantidad):
    with pytest.raises(DatoInvalido):
        Venta(2).agregar_item(producto(), cantidad)


def test_no_se_vende_un_producto_dado_de_baja():
    with pytest.raises(DatoInvalido):
        Venta(2).agregar_item(producto(activo=False), 1)


def test_los_detalles_no_se_pueden_modificar_desde_afuera():
    venta = venta_con((producto(), 1))
    with pytest.raises(AttributeError):
        venta.detalles.append("algo")
    with pytest.raises(FrozenInstanceError):
        venta.detalles[0].cantidad = 100


@pytest.mark.parametrize("precio, costo", [(0, 10), (-5, 10), (10, -1), ("caro", 10)])
def test_detalle_con_montos_invalidos(precio, costo):
    with pytest.raises(DatoInvalido):
        DetalleVenta(1, 1, precio, costo)


# ---------- cobrar (Strategy) ----------

@pytest.mark.parametrize("medio, total", [
    (Efectivo(), D("1700.00")), (Debito(), D("2000.00")), (Credito(), D("2200.00")),
])
def test_el_total_lo_calcula_el_medio_de_pago(medio, total):
    venta = venta_con((producto(precio=1000), 2))
    venta.cobrar(medio)
    assert venta.total == total
    assert venta.pago.medio is medio
    assert venta.pago.porcentaje_ajuste == medio.porcentaje_ajuste


def test_cobrar_en_efectivo_calcula_el_vuelto():
    venta = venta_con((producto(precio=1000), 1))
    venta.cobrar(Efectivo(), 1000)
    assert (venta.total, venta.pago.vuelto) == (D("850.00"), D("150.00"))


def test_efectivo_que_no_alcanza_no_deja_la_venta_cobrada():
    venta = venta_con((producto(precio=1000), 1))
    with pytest.raises(PagoInsuficiente):
        venta.cobrar(Efectivo(), 500)
    assert not venta.esta_cobrada()


def test_no_se_cobra_una_venta_vacia():
    with pytest.raises(DatoInvalido):
        Venta(2).cobrar(Debito())


def test_no_se_cobra_dos_veces():
    venta = venta_con((producto(), 1))
    venta.cobrar(Debito())
    with pytest.raises(TransicionDeEstadoInvalida):
        venta.cobrar(Credito())


def test_una_venta_cobrada_no_se_modifica():
    venta = venta_con((producto(), 1))
    venta.cobrar(Debito())
    with pytest.raises(TransicionDeEstadoInvalida):
        venta.agregar_item(producto(2), 1)


def test_la_ganancia_usa_lo_cobrado_y_puede_ser_negativa():
    # Precio 1000, costo 900: en efectivo se cobra 850, se pierde 50
    venta = venta_con((producto(precio=1000, costo=900), 1))
    venta.cobrar(Efectivo())
    assert venta.ganancia == D("-50.00")


# ---------- comprobante y caja ----------

def test_el_comprobante_se_numera_por_punto_de_venta():
    venta = venta_con((producto(), 1), sucursal_id=2)
    venta.cobrar(Debito())
    venta.emitir_comprobante(15)
    assert venta.comprobante.codigo == "0002-00000015"


def test_no_se_emite_comprobante_sin_cobrar():
    with pytest.raises(TransicionDeEstadoInvalida):
        venta_con((producto(), 1)).emitir_comprobante(1)


def test_no_se_emite_dos_veces_el_comprobante():
    venta = venta_con((producto(), 1))
    venta.cobrar(Debito())
    venta.emitir_comprobante(1)
    with pytest.raises(TransicionDeEstadoInvalida):
        venta.emitir_comprobante(2)


def test_la_venta_genera_una_entrada_de_caja_por_lo_cobrado():
    venta = venta_con((producto(precio=1000), 1), sucursal_id=2)
    venta.cobrar(Credito())
    venta.emitir_comprobante(7)
    movimiento = venta.movimiento_caja()
    assert (movimiento.tipo, movimiento.medio_pago, movimiento.importe) == ("VENTA", "CREDITO", D("1100.00"))
    assert (movimiento.sucursal_id, movimiento.referencia) == (2, "Venta 0002-00000007")


def test_una_venta_sin_cobrar_no_mueve_la_caja():
    with pytest.raises(TransicionDeEstadoInvalida):
        venta_con((producto(), 1)).movimiento_caja()
