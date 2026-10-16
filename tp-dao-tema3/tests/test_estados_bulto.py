# Tests del patrón State del bulto: que las transiciones válidas anden y que las
# inválidas tiren la excepción que corresponde.
# Acá NO se prueba la base de datos ni la api.
#
# QUÉ QUEDÓ AFUERA Y POR QUÉ
#
# 1) Todavía no existe en el código (está en Modelo_Tema_3_DAO pero falta
#    implementarlo). Cuando se agregue, se suman sus tests:
#    - Historial inmutable de cambios de estado: hoy cambiar_estado() solo
#      reemplaza el estado y no guarda nada.
#    - verificar(nro_leido, intacto): hoy verificar() solo recibe el número
#      leído, así que un precinto roto con el mismo número se aprobaría y ese
#      caso no se puede probar. Cuando cambie la firma, hay que actualizar
#      también los tests de verificación de este archivo.
#    - quitar_item() en el estado Preparado.
#
# 2) Depende de partes que todavía están vacías:
#    - Guardar y leer el bulto en la base (dao_logistica.py), incluida la
#      conversión del texto del estado de vuelta al objeto estado.
#    - Remito, Orden y Pedido de reposición: hoy el bulto no se asigna a
#      ningún remito.
#    - Que al verificarse un bulto se sume stock al local (recepcion_service.py).
#
# 3) Decisiones de alcance de este archivo:
#    - Se prueba siempre con los métodos públicos del bulto (agregar_item,
#      precintar, despachar, ...) y no llamando a cambiar_estado() directo,
#      porque así lo va a usar el resto del sistema.
#    - agregar_item() acepta cualquier objeto como item (todavía no hay
#      Producto ni cantidad), así que no se prueban validaciones del contenido.
#      Tampoco se valida el id del bulto: el código no lo valida.
#    - De los mensajes de error se chequea uno solo (que nombre el estado), para
#      poder reescribirlos sin romper los tests.
#
# 4) Preguntas abiertas para el profe que NO cambian estos tests, porque
#    afectan a los servicios y no al bulto: si un bulto rechazado bloquea el
#    remito completo, y si la mercadería rechazada vuelve al CD o se da de baja
#    como merma.
import pytest

from backend.dominio.excepciones import DatoInvalido, TransicionDeEstadoInvalida
from backend.dominio.logistica import Bulto

PRECINTO = "PRE-001"


# ---------- helpers: llevan un bulto nuevo hasta el estado que se quiere probar ----------

def bulto_preparado():
    return Bulto(1)


def bulto_con_items():
    bulto = Bulto(1)
    bulto.agregar_item("item-1")
    return bulto


def bulto_precintado():
    bulto = bulto_con_items()
    bulto.precintar(PRECINTO)
    return bulto


def bulto_en_transito():
    bulto = bulto_precintado()
    bulto.despachar()
    return bulto


def bulto_recibido():
    bulto = bulto_en_transito()
    bulto.recibir()
    return bulto


def bulto_verificado():
    bulto = bulto_recibido()
    bulto.verificar(PRECINTO)
    return bulto


def bulto_rechazado():
    bulto = bulto_recibido()
    bulto.verificar("OTRO-PRECINTO")
    return bulto


# ---------- estado inicial ----------

def test_bulto_nuevo_nace_preparado_y_vacio():
    bulto = Bulto(1)
    assert bulto.estado == "PREPARADO"
    assert bulto.items == []
    assert bulto.nro_precinto is None


# ---------- PREPARADO ----------

def test_en_preparado_se_pueden_agregar_items():
    bulto = bulto_preparado()
    bulto.agregar_item("item-1")
    bulto.agregar_item("item-2")
    assert bulto.items == ["item-1", "item-2"]
    assert bulto.estado == "PREPARADO"


def test_precintar_un_bulto_vacio_es_dato_invalido_y_no_cambia_de_estado():
    bulto = bulto_preparado()
    with pytest.raises(DatoInvalido):
        bulto.precintar(PRECINTO)
    assert bulto.estado == "PREPARADO"
    assert bulto.nro_precinto is None


@pytest.mark.parametrize("precinto_invalido", [None, "", "   "])
def test_precintar_con_precinto_vacio_es_dato_invalido(precinto_invalido):
    bulto = bulto_con_items()
    with pytest.raises(DatoInvalido):
        bulto.precintar(precinto_invalido)
    assert bulto.estado == "PREPARADO"
    assert bulto.nro_precinto is None


def test_precintar_pasa_a_precintado_y_guarda_el_precinto_sin_espacios():
    bulto = bulto_con_items()
    bulto.precintar("  PRE-001  ")
    assert bulto.estado == "PRECINTADO"
    assert bulto.nro_precinto == "PRE-001"


# ---------- flujo completo ----------

def test_flujo_completo_termina_en_verificado():
    bulto = bulto_preparado()
    assert bulto.estado == "PREPARADO"
    bulto.agregar_item("item-1")
    bulto.precintar(PRECINTO)
    assert bulto.estado == "PRECINTADO"
    bulto.despachar()
    assert bulto.estado == "EN_TRANSITO"
    bulto.recibir()
    assert bulto.estado == "RECIBIDO"
    bulto.verificar(PRECINTO)
    assert bulto.estado == "VERIFICADO"


# ---------- verificación del precinto en RECIBIDO ----------

def test_verificar_con_el_mismo_precinto_pasa_a_verificado():
    bulto = bulto_recibido()
    bulto.verificar(PRECINTO)
    assert bulto.estado == "VERIFICADO"


def test_verificar_ignora_espacios_alrededor_del_precinto_leido():
    bulto = bulto_recibido()
    bulto.verificar("  PRE-001 ")
    assert bulto.estado == "VERIFICADO"


def test_verificar_con_otro_precinto_pasa_a_rechazado():
    bulto = bulto_recibido()
    bulto.verificar("OTRO-PRECINTO")
    assert bulto.estado == "RECHAZADO"


@pytest.mark.parametrize("precinto_leido", [None, "", "   "])
def test_verificar_sin_precinto_pasa_a_rechazado(precinto_leido):
    bulto = bulto_recibido()
    bulto.verificar(precinto_leido)
    assert bulto.estado == "RECHAZADO"


# ---------- habilita_venta: solo VERIFICADO permite vender ----------

ESTADOS = [
    (bulto_preparado, "PREPARADO", False),
    (bulto_precintado, "PRECINTADO", False),
    (bulto_en_transito, "EN_TRANSITO", False),
    (bulto_recibido, "RECIBIDO", False),
    (bulto_verificado, "VERIFICADO", True),
    (bulto_rechazado, "RECHAZADO", False),
]


@pytest.mark.parametrize(
    "armar, estado, habilita",
    [pytest.param(armar, estado, habilita, id=estado) for armar, estado, habilita in ESTADOS],
)
def test_solo_un_bulto_verificado_habilita_la_venta(armar, estado, habilita):
    bulto = armar()
    assert bulto.estado == estado
    assert bulto.habilita_venta() is habilita


def test_la_venta_se_habilita_recien_al_verificar():
    bulto = bulto_preparado()
    bulto.agregar_item("item-1")
    assert not bulto.habilita_venta()
    bulto.precintar(PRECINTO)
    assert not bulto.habilita_venta()
    bulto.despachar()
    assert not bulto.habilita_venta()
    bulto.recibir()
    assert not bulto.habilita_venta()  # recibido todavía no es vendible
    bulto.verificar(PRECINTO)
    assert bulto.habilita_venta()


# ---------- transiciones inválidas ----------
# Cada fila: (cómo llegar al estado, nombre del estado, acciones que NO están permitidas)

ACCIONES = {
    "agregar_item": lambda b: b.agregar_item("item-x"),
    "precintar": lambda b: b.precintar("PRE-999"),
    "despachar": lambda b: b.despachar(),
    "recibir": lambda b: b.recibir(),
    "verificar": lambda b: b.verificar(PRECINTO),
}

INVALIDAS = [
    (bulto_preparado, "PREPARADO", ["despachar", "recibir", "verificar"]),
    (bulto_precintado, "PRECINTADO", ["agregar_item", "precintar", "recibir", "verificar"]),
    (bulto_en_transito, "EN_TRANSITO", ["agregar_item", "precintar", "despachar", "verificar"]),
    (bulto_recibido, "RECIBIDO", ["agregar_item", "precintar", "despachar", "recibir"]),
    (bulto_verificado, "VERIFICADO", ["agregar_item", "precintar", "despachar", "recibir", "verificar"]),
    (bulto_rechazado, "RECHAZADO", ["agregar_item", "precintar", "despachar", "recibir", "verificar"]),
]

CASOS_INVALIDOS = [
    pytest.param(armar, estado, accion, id=f"{estado}-{accion}")
    for armar, estado, acciones in INVALIDAS
    for accion in acciones
]


@pytest.mark.parametrize("armar, estado, accion", CASOS_INVALIDOS)
def test_transicion_invalida_lanza_error_y_no_cambia_el_estado(armar, estado, accion):
    bulto = armar()
    assert bulto.estado == estado

    with pytest.raises(TransicionDeEstadoInvalida):
        ACCIONES[accion](bulto)

    assert bulto.estado == estado


def test_agregar_item_fuera_de_preparado_no_modifica_los_items():
    bulto = bulto_precintado()
    with pytest.raises(TransicionDeEstadoInvalida):
        bulto.agregar_item("item-tarde")
    assert bulto.items == ["item-1"]


def test_el_mensaje_del_error_dice_en_que_estado_estaba():
    bulto = bulto_en_transito()
    with pytest.raises(TransicionDeEstadoInvalida, match="EN_TRANSITO"):
        bulto.despachar()


def test_str_del_bulto_muestra_estado_precinto_e_items():
    bulto = bulto_precintado()
    texto = str(bulto)
    assert "PRECINTADO" in texto
    assert PRECINTO in texto
    assert "Items: 1" in texto