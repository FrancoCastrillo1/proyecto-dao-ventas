# Tests de las dos piezas del dominio que necesita el DAO para leer un bulto:
# convertir el texto del estado en el objeto State, y reconstruir un bulto ya
# en su estado sin generar historial nuevo.
from datetime import datetime

import pytest

from backend.dominio.estados_bulto import estado_desde_nombre
from backend.dominio.excepciones import DatoInvalido
from backend.dominio.logistica import Bulto, CambioEstadoBulto, DetalleBulto

NOMBRES = ["PREPARADO", "PRECINTADO", "EN_TRANSITO", "RECIBIDO", "VERIFICADO", "RECHAZADO"]


def historial_de_ejemplo():
    return (
        CambioEstadoBulto(datetime(2026, 10, 20, 10, 0, 0), "PREPARADO", "PRECINTADO"),
        CambioEstadoBulto(datetime(2026, 10, 20, 11, 0, 0), "PRECINTADO", "EN_TRANSITO"),
    )


def bulto_reconstruido():
    return Bulto.reconstruir(7, "EN_TRANSITO", "PRE-001", [DetalleBulto(1, 5)], historial_de_ejemplo())


@pytest.mark.parametrize("nombre", NOMBRES)
def test_estado_desde_nombre_devuelve_el_estado_con_ese_nombre(nombre):
    assert estado_desde_nombre(nombre).nombre == nombre


@pytest.mark.parametrize("invalido", ["INVENTADO", "", None, "precintado"])
def test_estado_desde_nombre_invalido_es_dato_invalido(invalido):
    with pytest.raises(DatoInvalido):
        estado_desde_nombre(invalido)


def test_reconstruir_deja_el_bulto_tal_como_estaba():
    bulto = bulto_reconstruido()
    assert bulto.id_bulto == 7
    assert bulto.estado == "EN_TRANSITO"
    assert bulto.nro_precinto == "PRE-001"
    assert bulto.items == [DetalleBulto(1, 5)]
    assert bulto.historial == historial_de_ejemplo()


def test_reconstruir_no_genera_historial_nuevo():
    assert len(bulto_reconstruido().historial) == 2


def test_un_bulto_reconstruido_sigue_el_ciclo_de_vida_agregando_al_historial():
    bulto = bulto_reconstruido()
    bulto.recibir()
    assert bulto.estado == "RECIBIDO"
    assert len(bulto.historial) == 3
    assert bulto.historial[:2] == historial_de_ejemplo()


def test_un_bulto_reconstruido_en_transito_no_se_puede_precintar():
    from backend.dominio.excepciones import TransicionDeEstadoInvalida
    with pytest.raises(TransicionDeEstadoInvalida):
        bulto_reconstruido().precintar("PRE-999")


@pytest.mark.parametrize("estado, habilita", [("VERIFICADO", True), ("RECHAZADO", False)])
def test_un_bulto_reconstruido_respeta_habilita_venta(estado, habilita):
    bulto = Bulto.reconstruir(1, estado, "PRE-001", [DetalleBulto(1, 5)], ())
    assert bulto.habilita_venta() is habilita


def test_reconstruir_no_comparte_la_lista_de_items_con_quien_la_paso():
    items = [DetalleBulto(1, 5)]
    bulto = Bulto.reconstruir(1, "PREPARADO", None, items, ())
    items.append(DetalleBulto(2, 1))
    assert bulto.items == [DetalleBulto(1, 5)]


def test_reconstruir_con_estado_invalido_es_dato_invalido():
    with pytest.raises(DatoInvalido):
        Bulto.reconstruir(1, "INVENTADO", None, [], ())