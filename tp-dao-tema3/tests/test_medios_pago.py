# Tests del patrón Strategy de los medios de pago: cada estrategia calcula el
# total y el vuelto a su manera, y la fábrica arma la clase según el nombre.
# También los helpers de dinero (Decimal, redondeo comercial).
# Acá NO se prueba la Venta (test_ventas.py) ni la base.
from decimal import Decimal

import pytest

from backend.dominio.dinero import a_dinero, aplicar_porcentaje
from backend.dominio.excepciones import DatoInvalido, PagoInsuficiente
from backend.dominio.medios_pago import (
    MEDIOS_PAGO, Credito, Debito, Efectivo, MedioPago, Transferencia, crear_medio_pago,
)

D = Decimal


# ---------- dinero ----------

@pytest.mark.parametrize("valor, esperado", [
    (1500, D("1500.00")), (0.1, D("0.10")), ("99.999", D("100.00")), (" 12.5 ", D("12.50")),
    (D("0.005"), D("0.01")),   # redondeo comercial: 0.005 sube
])
def test_a_dinero_convierte_y_redondea_a_centavos(valor, esperado):
    assert a_dinero(valor) == esperado


@pytest.mark.parametrize("invalido", [None, True, "abc", "", "nan", "inf"])
def test_a_dinero_rechaza_lo_que_no_es_un_numero(invalido):
    with pytest.raises(DatoInvalido):
        a_dinero(invalido)


def test_float_no_arrastra_error_de_redondeo():
    assert a_dinero(0.1) + a_dinero(0.2) == D("0.30")


# ---------- cada estrategia ----------

@pytest.mark.parametrize("medio, porcentaje, total", [
    (Efectivo(), D("-15"), D("850.00")),
    (Debito(), D("0"), D("1000.00")),
    (Transferencia(), D("0"), D("1000.00")),
    (Credito(), D("10"), D("1100.00")),
])
def test_cada_medio_calcula_su_total(medio, porcentaje, total):
    assert medio.porcentaje_ajuste == porcentaje
    assert medio.calcular_total(D("1000.00")) == total


@pytest.mark.parametrize("medio, subtotal, total", [
    (Efectivo(), D("999.99"), D("849.99")),    # 849.9915
    (Efectivo(), D("0.10"), D("0.09")),        # 0.085 sube a 0.09
    (Credito(), D("33.33"), D("36.66")),       # 36.663
    (Credito(), D("0.05"), D("0.06")),         # 0.055 sube a 0.06
])
def test_los_totales_se_redondean_a_centavos(medio, subtotal, total):
    assert medio.calcular_total(subtotal) == total


def test_medio_pago_es_abstracto():
    with pytest.raises(TypeError):
        MedioPago()


# ---------- vuelto ----------

def test_efectivo_calcula_el_vuelto():
    assert Efectivo().calcular_vuelto(D("850.00"), 1000) == D("150.00")


def test_efectivo_con_el_monto_justo_no_tiene_vuelto():
    assert Efectivo().calcular_vuelto(D("850.00"), "850") == D("0.00")


def test_efectivo_sin_informar_lo_entregado_asume_pago_justo():
    assert Efectivo().calcular_vuelto(D("850.00")) == D("0.00")


def test_efectivo_que_no_alcanza_es_pago_insuficiente():
    with pytest.raises(PagoInsuficiente):
        Efectivo().calcular_vuelto(D("850.00"), D("849.99"))


def test_efectivo_con_monto_entregado_invalido():
    with pytest.raises(DatoInvalido):
        Efectivo().calcular_vuelto(D("850.00"), "mucho")


@pytest.mark.parametrize("medio", [Debito(), Transferencia(), Credito()])
def test_los_otros_medios_cobran_justo_y_no_dan_vuelto(medio):
    assert medio.calcular_vuelto(D("1000.00"), 5000) == D("0.00")


# ---------- fábrica ----------

@pytest.mark.parametrize("nombre, clase", [
    ("EFECTIVO", Efectivo), ("debito", Debito), (" Credito ", Credito), ("TRANSFERENCIA", Transferencia),
])
def test_la_fabrica_arma_la_clase_segun_el_nombre(nombre, clase):
    assert type(crear_medio_pago(nombre)) is clase


@pytest.mark.parametrize("nombre", ["CHEQUE", "", None])
def test_la_fabrica_rechaza_medios_invalidos(nombre):
    with pytest.raises(DatoInvalido):
        crear_medio_pago(nombre)


def test_la_fabrica_conoce_los_cuatro_medios():
    assert set(MEDIOS_PAGO) == {"EFECTIVO", "DEBITO", "TRANSFERENCIA", "CREDITO"}


def test_aplicar_porcentaje_cero_no_cambia_el_monto():
    assert aplicar_porcentaje(D("123.45"), D("0")) == D("123.45")
