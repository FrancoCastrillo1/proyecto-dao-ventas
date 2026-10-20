# Tests del remito: el documento de despacho que agrupa los bultos que viajan
# del Centro de Distribución a un mismo local.
import pytest

from backend.dominio.excepciones import DatoInvalido, TransicionDeEstadoInvalida
from backend.dominio.logistica import Bulto, Remito

CD = "cd-1"
LOCAL = "local-1"


def bulto_preparado(id_bulto, items):
    bulto = Bulto(id_bulto)
    for producto, cantidad in items:
        bulto.agregar_item(producto, cantidad)
    return bulto


def bulto_precintado(id_bulto, items):
    bulto = bulto_preparado(id_bulto, items)
    bulto.precintar(f"PRE-{id_bulto}")
    return bulto


def bulto_en_transito(id_bulto, items):
    bulto = bulto_precintado(id_bulto, items)
    bulto.despachar()
    return bulto


def remito_con_bulto_precintado():
    remito = Remito(1, CD, LOCAL)
    remito.agregar_bulto(bulto_precintado(1, [("prod-1", 10)]))
    return remito


def test_remito_nuevo_nace_abierto_y_sin_bultos():
    remito = Remito(1, CD, LOCAL)
    assert remito.estado == "ABIERTO"
    assert remito.origen == CD
    assert remito.destino == LOCAL
    assert remito.bultos == []


@pytest.mark.parametrize("invalido", [None, "", "   "])
def test_remito_sin_origen_es_dato_invalido(invalido):
    with pytest.raises(DatoInvalido):
        Remito(1, invalido, LOCAL)


@pytest.mark.parametrize("invalido", [None, "", "   "])
def test_remito_sin_destino_es_dato_invalido(invalido):
    with pytest.raises(DatoInvalido):
        Remito(1, CD, invalido)


def test_remito_con_el_mismo_origen_y_destino_es_dato_invalido():
    with pytest.raises(DatoInvalido):
        Remito(1, CD, CD)


def test_se_pueden_agregar_bultos_preparados_y_precintados():
    remito = Remito(1, CD, LOCAL)
    b1 = bulto_preparado(1, [("prod-1", 10)])
    b2 = bulto_precintado(2, [("prod-2", 4)])
    remito.agregar_bulto(b1)
    remito.agregar_bulto(b2)
    assert remito.bultos == [b1, b2]


def test_no_se_puede_agregar_un_bulto_que_ya_salio_del_cd():
    remito = Remito(1, CD, LOCAL)
    with pytest.raises(DatoInvalido):
        remito.agregar_bulto(bulto_en_transito(1, [("prod-1", 10)]))
    assert remito.bultos == []


def test_no_se_puede_agregar_el_mismo_bulto_dos_veces():
    remito = Remito(1, CD, LOCAL)
    bulto = bulto_precintado(1, [("prod-1", 10)])
    remito.agregar_bulto(bulto)
    with pytest.raises(DatoInvalido):
        remito.agregar_bulto(bulto)
    assert remito.bultos == [bulto]


def test_cerrar_un_remito_sin_bultos_es_dato_invalido():
    remito = Remito(1, CD, LOCAL)
    with pytest.raises(DatoInvalido):
        remito.cerrar()
    assert remito.estado == "ABIERTO"


def test_cerrar_con_un_bulto_sin_precintar_es_dato_invalido():
    remito = Remito(1, CD, LOCAL)
    remito.agregar_bulto(bulto_precintado(1, [("prod-1", 10)]))
    remito.agregar_bulto(bulto_preparado(2, [("prod-2", 4)]))
    with pytest.raises(DatoInvalido):
        remito.cerrar()
    assert remito.estado == "ABIERTO"


def test_cerrar_con_todos_los_bultos_precintados_pasa_a_cerrado():
    remito = remito_con_bulto_precintado()
    remito.cerrar()
    assert remito.estado == "CERRADO"


@pytest.mark.parametrize("accion", [
    lambda r: r.agregar_bulto(bulto_precintado(9, [("prod-9", 1)])),
    lambda r: r.cerrar(),
])
def test_un_remito_cerrado_no_se_puede_modificar(accion):
    remito = remito_con_bulto_precintado()
    remito.cerrar()
    with pytest.raises(TransicionDeEstadoInvalida):
        accion(remito)
    assert remito.estado == "CERRADO"
    assert len(remito.bultos) == 1


def test_total_por_producto_suma_lo_que_lleva_cada_bulto():
    remito = Remito(1, CD, LOCAL)
    remito.agregar_bulto(bulto_precintado(1, [("prod-1", 10), ("prod-2", 4)]))
    remito.agregar_bulto(bulto_precintado(2, [("prod-1", 5)]))
    assert remito.total_por_producto() == {"prod-1": 15, "prod-2": 4}


def test_total_por_producto_de_un_remito_vacio_es_vacio():
    assert Remito(1, CD, LOCAL).total_por_producto() == {}