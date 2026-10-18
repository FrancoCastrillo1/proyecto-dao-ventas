# Tests de stock: que los movimientos sumen/resten bien y que no se pueda
# vender o despachar más de lo que hay.
# Acá NO se prueba la base de datos ni la api.
from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from backend.dominio.excepciones import DatoInvalido, StockInsuficiente
from backend.dominio.stock import MovimientoStock, Stock, TipoMovimiento

COMPRA = TipoMovimiento.COMPRA
DESPACHO = TipoMovimiento.DESPACHO
RECEPCION = TipoMovimiento.RECEPCION
VENTA = TipoMovimiento.VENTA
DEVOLUCION = TipoMovimiento.DEVOLUCION
AJUSTE = TipoMovimiento.AJUSTE


def stock_con(cantidad):
    """Un stock del producto 1 en la ubicación 1 con esa cantidad de entrada."""
    stock = Stock(producto=1, ubicacion=1)
    if cantidad:
        stock.ingresar(cantidad, COMPRA, "carga inicial")
    return stock


# ---------- stock nuevo ----------

def test_stock_nuevo_arranca_en_cero_y_sin_movimientos():
    stock = Stock(producto=1, ubicacion=1)
    assert stock.cantidad == 0
    assert stock.stock_minimo == 0
    assert stock.movimientos == ()


def test_el_dao_puede_reconstruir_un_stock_con_cantidad_y_minimo():
    stock = Stock(producto=1, ubicacion=2, stock_minimo=5, cantidad=10, id=7)
    assert (stock.id, stock.cantidad, stock.stock_minimo) == (7, 10, 5)


@pytest.mark.parametrize("invalido", [-1, 2.5, "3", None, True])
def test_la_cantidad_inicial_invalida_es_dato_invalido(invalido):
    with pytest.raises(DatoInvalido):
        Stock(producto=1, ubicacion=1, cantidad=invalido)


@pytest.mark.parametrize("invalido", [-1, 2.5, "3", None, True])
def test_el_stock_minimo_invalido_es_dato_invalido(invalido):
    with pytest.raises(DatoInvalido):
        Stock(producto=1, ubicacion=1, stock_minimo=invalido)


# ---------- ingresar ----------

def test_ingresar_suma_a_la_cantidad_y_registra_un_movimiento_positivo():
    stock = Stock(producto=1, ubicacion=1)
    stock.ingresar(10, COMPRA, "Compra 55")
    assert stock.cantidad == 10

    (mov,) = stock.movimientos
    assert mov.cantidad == 10
    assert mov.tipo == COMPRA
    assert mov.referencia == "Compra 55"
    assert isinstance(mov.fecha, datetime)


def test_varios_ingresos_se_acumulan():
    stock = stock_con(10)
    stock.ingresar(5, RECEPCION, "Bulto 3")
    assert stock.cantidad == 15
    assert len(stock.movimientos) == 2


# ---------- egresar ----------

def test_egresar_resta_de_la_cantidad_y_registra_un_movimiento_negativo():
    stock = stock_con(10)
    stock.egresar(4, VENTA, "Venta 9")
    assert stock.cantidad == 6

    ultimo = stock.movimientos[-1]
    assert ultimo.cantidad == -4
    assert ultimo.tipo == VENTA
    assert ultimo.referencia == "Venta 9"


def test_se_puede_egresar_todo_lo_que_hay_y_queda_en_cero():
    stock = stock_con(10)
    stock.egresar(10, DESPACHO, "Bulto 1")
    assert stock.cantidad == 0


def test_egresar_mas_de_lo_que_hay_es_stock_insuficiente_y_no_modifica_nada():
    stock = stock_con(10)
    movimientos_antes = stock.movimientos

    with pytest.raises(StockInsuficiente):
        stock.egresar(11, VENTA, "Venta 9")

    assert stock.cantidad == 10
    assert stock.movimientos == movimientos_antes


def test_egresar_de_un_stock_vacio_es_stock_insuficiente():
    stock = Stock(producto=1, ubicacion=1)
    with pytest.raises(StockInsuficiente):
        stock.egresar(1, VENTA)
    assert stock.cantidad == 0


def test_el_mensaje_de_stock_insuficiente_dice_cuanto_hay_y_cuanto_se_pidio():
    stock = stock_con(3)
    with pytest.raises(StockInsuficiente, match="hay 3.*7"):
        stock.egresar(7, VENTA)


# ---------- validaciones de la cantidad y del tipo ----------

CANTIDADES_INVALIDAS = [0, -1, 1.5, "3", None, True]


@pytest.mark.parametrize("cantidad", CANTIDADES_INVALIDAS)
def test_ingresar_con_cantidad_invalida_es_dato_invalido(cantidad):
    stock = stock_con(10)
    with pytest.raises(DatoInvalido):
        stock.ingresar(cantidad, COMPRA)
    assert stock.cantidad == 10
    assert len(stock.movimientos) == 1


@pytest.mark.parametrize("cantidad", CANTIDADES_INVALIDAS)
def test_egresar_con_cantidad_invalida_es_dato_invalido(cantidad):
    stock = stock_con(10)
    with pytest.raises(DatoInvalido):
        stock.egresar(cantidad, VENTA)
    assert stock.cantidad == 10
    assert len(stock.movimientos) == 1


@pytest.mark.parametrize("tipo", ["VENTA", "COMPRA", None, 1])
def test_el_tipo_tiene_que_ser_un_tipo_de_movimiento(tipo):
    stock = stock_con(10)
    with pytest.raises(DatoInvalido):
        stock.ingresar(1, tipo)
    with pytest.raises(DatoInvalido):
        stock.egresar(1, tipo)
    assert stock.cantidad == 10


@pytest.mark.parametrize("tipo", [DESPACHO, VENTA])
def test_ingresar_con_un_tipo_de_egreso_es_dato_invalido(tipo):
    stock = stock_con(10)
    with pytest.raises(DatoInvalido):
        stock.ingresar(1, tipo)
    assert stock.cantidad == 10


@pytest.mark.parametrize("tipo", [COMPRA, RECEPCION, DEVOLUCION])
def test_egresar_con_un_tipo_de_ingreso_es_dato_invalido(tipo):
    stock = stock_con(10)
    with pytest.raises(DatoInvalido):
        stock.egresar(1, tipo)
    assert stock.cantidad == 10


@pytest.mark.parametrize("tipo", [COMPRA, RECEPCION, DEVOLUCION, AJUSTE])
def test_tipos_validos_para_ingresar(tipo):
    stock = Stock(producto=1, ubicacion=1)
    stock.ingresar(1, tipo)
    assert stock.cantidad == 1


@pytest.mark.parametrize("tipo", [DESPACHO, VENTA, AJUSTE])
def test_tipos_validos_para_egresar(tipo):
    stock = stock_con(5)
    stock.egresar(1, tipo)
    assert stock.cantidad == 4


# ---------- referencia ----------

def test_la_referencia_es_opcional_y_se_guarda_sin_espacios_sobrantes():
    stock = Stock(producto=1, ubicacion=1)
    stock.ingresar(1, COMPRA)
    stock.ingresar(1, COMPRA, "  Compra 7  ")
    assert [m.referencia for m in stock.movimientos] == ["", "Compra 7"]


# ---------- libro de movimientos: trazabilidad ----------

def test_la_cantidad_siempre_es_la_suma_de_los_movimientos():
    stock = Stock(producto=1, ubicacion=1)
    stock.ingresar(20, COMPRA)
    stock.egresar(5, DESPACHO)
    stock.ingresar(3, DEVOLUCION)
    stock.egresar(8, VENTA)
    stock.ingresar(2, AJUSTE)
    stock.egresar(1, AJUSTE)

    assert stock.cantidad == sum(m.cantidad for m in stock.movimientos) == 11


def test_los_movimientos_quedan_en_el_orden_en_que_ocurrieron():
    stock = Stock(producto=1, ubicacion=1)
    stock.ingresar(10, COMPRA)
    stock.egresar(3, VENTA)
    stock.ingresar(1, DEVOLUCION)
    assert [m.tipo for m in stock.movimientos] == [COMPRA, VENTA, DEVOLUCION]
    assert [m.cantidad for m in stock.movimientos] == [10, -3, 1]


def test_un_movimiento_no_se_puede_modificar():
    stock = stock_con(10)
    mov = stock.movimientos[0]
    assert isinstance(mov, MovimientoStock)
    with pytest.raises(FrozenInstanceError):
        mov.cantidad = 999


def test_los_movimientos_no_se_pueden_alterar_desde_afuera():
    stock = stock_con(10)
    with pytest.raises(AttributeError):
        stock.movimientos.append("movimiento falso")
    with pytest.raises(TypeError):
        stock.movimientos[0] = "movimiento falso"
    assert len(stock.movimientos) == 1


def test_la_cantidad_no_se_puede_pisar_a_mano():
    stock = stock_con(10)
    with pytest.raises(AttributeError):
        stock.cantidad = 999
    assert stock.cantidad == 10


# ---------- stock mínimo ----------

@pytest.mark.parametrize("cantidad, minimo, bajo", [
    (4, 5, True),     # por debajo del mínimo
    (5, 5, False),    # justo en el mínimo todavía no es "bajo"
    (6, 5, False),    # por encima
    (0, 5, True),     # sin stock y con mínimo
    (0, 0, False),    # sin mínimo definido nunca está bajo
])
def test_esta_bajo_minimo(cantidad, minimo, bajo):
    stock = Stock(producto=1, ubicacion=1, stock_minimo=minimo, cantidad=cantidad)
    assert stock.esta_bajo_minimo() is bajo


def test_egresar_puede_dejar_el_stock_bajo_el_minimo():
    stock = Stock(producto=1, ubicacion=1, stock_minimo=5, cantidad=6)
    assert not stock.esta_bajo_minimo()
    stock.egresar(2, VENTA)
    assert stock.esta_bajo_minimo()


def test_cambiar_el_stock_minimo_no_toca_la_cantidad_ni_genera_movimientos():
    stock = stock_con(10)
    stock.stock_minimo = 20
    assert stock.stock_minimo == 20
    assert stock.cantidad == 10
    assert len(stock.movimientos) == 1
    assert stock.esta_bajo_minimo()


@pytest.mark.parametrize("invalido", [-1, 2.5, "3", None])
def test_cambiar_el_stock_minimo_a_un_valor_invalido_es_dato_invalido(invalido):
    stock = Stock(producto=1, ubicacion=1, stock_minimo=5)
    with pytest.raises(DatoInvalido):
        stock.stock_minimo = invalido
    assert stock.stock_minimo == 5


# ---------- independencia entre stocks ----------

def test_cada_stock_lleva_su_propia_cantidad_y_sus_propios_movimientos():
    en_cd = Stock(producto=1, ubicacion="CD")
    en_local = Stock(producto=1, ubicacion="Local 1")
    en_cd.ingresar(10, COMPRA)
    en_local.ingresar(2, RECEPCION)

    assert (en_cd.cantidad, en_local.cantidad) == (10, 2)
    assert len(en_cd.movimientos) == len(en_local.movimientos) == 1