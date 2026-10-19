# Tests de DetalleBulto: una línea del bulto (producto + cantidad).
from dataclasses import FrozenInstanceError

import pytest

from backend.dominio.excepciones import DatoInvalido
from backend.dominio.logistica import DetalleBulto


def test_detalle_guarda_producto_y_cantidad():
    detalle = DetalleBulto(producto="prod-1", cantidad=12)
    assert detalle.producto == "prod-1"
    assert detalle.cantidad == 12


@pytest.mark.parametrize("cantidad_invalida", [0, -1, -50])
def test_cantidad_cero_o_negativa_es_dato_invalido(cantidad_invalida):
    with pytest.raises(DatoInvalido):
        DetalleBulto(producto="prod-1", cantidad=cantidad_invalida)


@pytest.mark.parametrize("cantidad_invalida", [1.5, "3", None])
def test_cantidad_no_entera_es_dato_invalido(cantidad_invalida):
    with pytest.raises(DatoInvalido):
        DetalleBulto(producto="prod-1", cantidad=cantidad_invalida)


def test_un_detalle_no_se_puede_modificar():
    detalle = DetalleBulto(producto="prod-1", cantidad=12)
    with pytest.raises(FrozenInstanceError):
        detalle.cantidad = 99