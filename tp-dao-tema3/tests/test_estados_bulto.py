# Tests del patrón State del bulto: que las transiciones válidas anden y que las
# inválidas tiren la excepción que corresponde. También el historial inmutable
# y la regla de que solo un bulto Verificado habilita la venta.
# Acá NO se prueba la base de datos ni la api.
#
# QUÉ QUEDÓ AFUERA Y POR QUÉ
#
# 1) Está en Modelo_Tema_3_DAO pero todavía no existe en el código:
#    - tiempo_transito() del bulto (se calcularía con el historial).
#    - agregar_item(producto, cantidad) con su DetalleBulto: hoy el item puede
#      ser cualquier objeto, porque todavía no hay Producto.
#
# 2) Depende de partes que todavía están vacías:
#    - Guardar y leer el bulto y su historial en la base (dao_logistica.py),
#      incluida la conversión del texto del estado de vuelta al objeto estado.
#    - Remito, Orden y Pedido de reposición: hoy el bulto no se asigna a
#      ningún remito.
#    - Que al verificarse un bulto se sume stock al local (recepcion_service.py).
#
# 3) Decisiones de alcance de este archivo:
#    - Se prueba siempre con los métodos públicos del bulto (agregar_item,
#      precintar, despachar, ...) y no llamando a cambiar_estado() directo,
#      porque así lo va a usar el resto del sistema.
#    - agregar_item() no valida el contenido del item, ni se valida el id del
#      bulto: el código no lo hace.
#    - De los mensajes de error se chequea que uno nombre el estado y que el
#      rechazo deje una observación que mencione el precinto. El resto del
#      texto se puede reescribir sin romper los tests.
#    - El historial no registra la creación del bulto (nace en Preparado sin
#      registro): solo guarda los cambios de estado, como en el modelo.
#
# 4) Preguntas abiertas para el profe que NO cambian estos tests, porque
#    afectan a los servicios y no al bulto: si un bulto rechazado bloquea el
#    remito completo, y si la mercadería rechazada vuelve al CD o se da de baja
#    como merma.
from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from backend.dominio.excepciones import DatoInvalido, TransicionDeEstadoInvalida
from backend.dominio.logistica import Bulto, CambioEstadoBulto

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
    bulto.verificar(PRECINTO, intacto=True)
    return bulto


def bulto_rechazado():
    bulto = bulto_recibido()
    bulto.verificar("OTRO-PRECINTO", intacto=True)
    return bulto


# ---------- estado inicial ----------

def test_bulto_nuevo_nace_preparado_y_vacio():
    bulto = Bulto(1)
    assert bulto.estado == "PREPARADO"
    assert bulto.items == []
    assert bulto.nro_precinto is None
    assert bulto.historial == ()


# ---------- PREPARADO: agregar y quitar items ----------

def test_en_preparado_se_pueden_agregar_items():
    bulto = bulto_preparado()
    bulto.agregar_item("item-1")
    bulto.agregar_item("item-2")
    assert bulto.items == ["item-1", "item-2"]
    assert bulto.estado == "PREPARADO"


def test_en_preparado_se_puede_quitar_un_item():
    bulto = bulto_preparado()
    bulto.agregar_item("item-1")
    bulto.agregar_item("item-2")
    bulto.quitar_item("item-1")
    assert bulto.items == ["item-2"]
    assert bulto.estado == "PREPARADO"


def test_quitar_un_item_que_no_esta_es_dato_invalido():
    bulto = bulto_con_items()
    with pytest.raises(DatoInvalido):
        bulto.quitar_item("item-que-no-esta")
    assert bulto.items == ["item-1"]


def test_agregar_y_quitar_items_no_genera_historial():
    bulto = bulto_preparado()
    bulto.agregar_item("item-1")
    bulto.quitar_item("item-1")
    assert bulto.historial == ()


# ---------- PREPARADO: precintar ----------

def test_precintar_un_bulto_vacio_es_dato_invalido_y_no_cambia_de_estado():
    bulto = bulto_preparado()
    with pytest.raises(DatoInvalido):
        bulto.precintar(PRECINTO)
    assert bulto.estado == "PREPARADO"
    assert bulto.nro_precinto is None
    assert bulto.historial == ()


def test_no_se_puede_precintar_si_se_quitaron_todos_los_items():
    bulto = bulto_con_items()
    bulto.quitar_item("item-1")
    with pytest.raises(DatoInvalido):
        bulto.precintar(PRECINTO)
    assert bulto.estado == "PREPARADO"


@pytest.mark.parametrize("precinto_invalido", [None, "", "   "])
def test_precintar_con_precinto_vacio_es_dato_invalido(precinto_invalido):
    bulto = bulto_con_items()
    with pytest.raises(DatoInvalido):
        bulto.precintar(precinto_invalido)
    assert bulto.estado == "PREPARADO"
    assert bulto.nro_precinto is None
    assert bulto.historial == ()


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
    bulto.verificar(PRECINTO, intacto=True)
    assert bulto.estado == "VERIFICADO"


# ---------- verificación del precinto en RECIBIDO ----------

def test_verificar_con_precinto_intacto_y_mismo_numero_pasa_a_verificado():
    bulto = bulto_recibido()
    bulto.verificar(PRECINTO, intacto=True)
    assert bulto.estado == "VERIFICADO"


def test_verificar_ignora_espacios_alrededor_del_numero_leido():
    bulto = bulto_recibido()
    bulto.verificar("  PRE-001 ", intacto=True)
    assert bulto.estado == "VERIFICADO"


def test_verificar_con_precinto_roto_pasa_a_rechazado_aunque_el_numero_coincida():
    # El caso que importa: el número es el correcto pero el precinto llegó violado
    bulto = bulto_recibido()
    bulto.verificar(PRECINTO, intacto=False)
    assert bulto.estado == "RECHAZADO"


def test_verificar_con_otro_numero_pasa_a_rechazado_aunque_este_intacto():
    bulto = bulto_recibido()
    bulto.verificar("OTRO-PRECINTO", intacto=True)
    assert bulto.estado == "RECHAZADO"


@pytest.mark.parametrize("nro_leido", [None, "", "   "])
def test_verificar_sin_numero_pasa_a_rechazado(nro_leido):
    bulto = bulto_recibido()
    bulto.verificar(nro_leido, intacto=True)
    assert bulto.estado == "RECHAZADO"


def test_verificar_roto_y_con_otro_numero_pasa_a_rechazado():
    bulto = bulto_recibido()
    bulto.verificar("OTRO-PRECINTO", intacto=False)
    assert bulto.estado == "RECHAZADO"


# ---------- solo VERIFICADO habilita la venta ----------

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


# ---------- transiciones inválidas ----------
# Cada fila: (cómo llegar al estado, nombre del estado, acciones que NO están permitidas)

ACCIONES = {
    "agregar_item": lambda b: b.agregar_item("item-x"),
    "quitar_item": lambda b: b.quitar_item("item-1"),
    "precintar": lambda b: b.precintar("PRE-999"),
    "despachar": lambda b: b.despachar(),
    "recibir": lambda b: b.recibir(),
    "verificar": lambda b: b.verificar(PRECINTO, intacto=True),
}

INVALIDAS = [
    (bulto_preparado, "PREPARADO", ["despachar", "recibir", "verificar"]),
    (bulto_precintado, "PRECINTADO", ["agregar_item", "quitar_item", "precintar", "recibir", "verificar"]),
    (bulto_en_transito, "EN_TRANSITO", ["agregar_item", "quitar_item", "precintar", "despachar", "verificar"]),
    (bulto_recibido, "RECIBIDO", ["agregar_item", "quitar_item", "precintar", "despachar", "recibir"]),
    (bulto_verificado, "VERIFICADO", ["agregar_item", "quitar_item", "precintar", "despachar", "recibir", "verificar"]),
    (bulto_rechazado, "RECHAZADO", ["agregar_item", "quitar_item", "precintar", "despachar", "recibir", "verificar"]),
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
    historial_antes = bulto.historial

    with pytest.raises(TransicionDeEstadoInvalida):
        ACCIONES[accion](bulto)

    assert bulto.estado == estado
    assert bulto.historial == historial_antes  # un intento fallido no deja rastro


def test_agregar_item_fuera_de_preparado_no_modifica_los_items():
    bulto = bulto_precintado()
    with pytest.raises(TransicionDeEstadoInvalida):
        bulto.agregar_item("item-tarde")
    assert bulto.items == ["item-1"]


def test_quitar_item_fuera_de_preparado_no_modifica_los_items():
    bulto = bulto_precintado()
    with pytest.raises(TransicionDeEstadoInvalida):
        bulto.quitar_item("item-1")
    assert bulto.items == ["item-1"]


def test_el_mensaje_del_error_dice_en_que_estado_estaba():
    bulto = bulto_en_transito()
    with pytest.raises(TransicionDeEstadoInvalida, match="EN_TRANSITO"):
        bulto.despachar()


# ---------- historial: trazabilidad inmutable ----------

def test_cada_transicion_agrega_un_registro_al_historial_en_orden():
    bulto = bulto_verificado()
    pasos = [(c.estado_anterior, c.estado_nuevo) for c in bulto.historial]
    assert pasos == [
        ("PREPARADO", "PRECINTADO"),
        ("PRECINTADO", "EN_TRANSITO"),
        ("EN_TRANSITO", "RECIBIDO"),
        ("RECIBIDO", "VERIFICADO"),
    ]


def test_los_registros_del_historial_tienen_fecha_y_estan_ordenados_en_el_tiempo():
    bulto = bulto_verificado()
    fechas = [c.fecha_hora for c in bulto.historial]
    assert all(isinstance(f, datetime) for f in fechas)
    assert fechas == sorted(fechas)


def test_el_rechazo_deja_registrada_la_observacion():
    bulto = bulto_rechazado()
    ultimo = bulto.historial[-1]
    assert ultimo.estado_anterior == "RECIBIDO"
    assert ultimo.estado_nuevo == "RECHAZADO"
    assert "Precinto" in ultimo.observacion


def test_un_registro_del_historial_no_se_puede_modificar():
    bulto = bulto_precintado()
    registro = bulto.historial[0]
    assert isinstance(registro, CambioEstadoBulto)
    with pytest.raises(FrozenInstanceError):
        registro.estado_nuevo = "VERIFICADO"


def test_el_historial_no_se_puede_alterar_desde_afuera():
    bulto = bulto_precintado()
    with pytest.raises(AttributeError):
        bulto.historial.append("registro falso")
    with pytest.raises(TypeError):
        bulto.historial[0] = "registro falso"
    with pytest.raises(AttributeError):
        bulto.historial = ()
    assert len(bulto.historial) == 1


def test_los_registros_anteriores_no_cambian_cuando_hay_nuevas_transiciones():
    bulto = bulto_precintado()
    primero = bulto.historial[0]
    bulto.despachar()
    bulto.recibir()
    assert bulto.historial[0] == primero
    assert len(bulto.historial) == 3


# ---------- texto del bulto ----------

def test_str_del_bulto_muestra_estado_precinto_e_items():
    bulto = bulto_precintado()
    texto = str(bulto)
    assert "PRECINTADO" in texto
    assert PRECINTO in texto
    assert "Items: 1" in texto