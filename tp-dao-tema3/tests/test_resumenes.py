# Tests del resumen de cada reporte (servicios/resumenes.py): se le pasan
# datos armados a mano, con la misma forma que devuelve ReportesService, y se
# mira qué frases salen. Que cada reporte real traiga su resumen y que el PDF
# lo muestre se prueba en test_reportes.py.
from decimal import Decimal

import pytest

from backend.servicios.resumenes import lista, parte, periodo_legible, resumir

D = Decimal


# ------------------------------------------------------------ Ayudas de texto

@pytest.mark.parametrize("valor, total, esperado", [
    (1, 4, "25 %"), (2, 3, "67 %"), (1, 8, "13 %"), (1, 1000, "menos del 1 %"), (0, 10, "0 %"), (5, 0, None),
])
def test_parte(valor, total, esperado):
    assert parte(valor, total) == esperado


def test_lista_con_y_y_con_los_que_sobran():
    assert lista(["A"]) == "A"
    assert lista(["A", "B"]) == "A y B"
    assert lista(["A", "B", "C"]) == "A, B y C"
    assert lista(["A", "B", "C", "D", "E"]) == "A, B, C y 2 más"


def test_periodo_legible():
    assert periodo_legible("2026-10-20") == "el 20/10/2026"
    assert periodo_legible("2026-10") == "10/2026"


# ------------------------------------------------------------------ Ventas

def fila_venta(periodo, sucursal, medio, neto):
    return {"periodo": periodo, "sucursal": sucursal, "medio_pago": medio, "neto": D(neto)}


def test_ventas_dice_el_total_el_mejor_dia_el_medio_y_el_local():
    datos = {
        "filas": [fila_venta("2026-10-20", "Centro", "EFECTIVO", 3000), fila_venta("2026-10-21", "Norte", "DEBITO", 1000)],
        "por_medio_pago": {"EFECTIVO": D(3000), "DEBITO": D(1000)},
        "cantidad_ventas": 5, "total_vendido": D(4500), "total_devuelto": D(500), "total_neto": D(4000),
    }
    frases = resumir("ventas", datos)
    assert frases[0] == ("Se hicieron 5 ventas por $ 4.500,00; descontando lo devuelto ($ 500,00), "
                         "el ingreso neto fue $ 4.000,00.")
    assert "El mejor día fue el 20/10/2026, con $ 3.000,00 de ingreso neto." in frases
    assert "Lo que más se cobró fue con Efectivo (75 % del ingreso neto)." in frases
    assert "El local que más vendió fue Centro (75 % del ingreso neto)." in frases


def test_ventas_de_un_solo_dia_y_un_solo_local_no_compara():
    datos = {
        "filas": [fila_venta("2026-10", "Centro", "DEBITO", 1000)],
        "por_medio_pago": {"DEBITO": D(1000)},
        "cantidad_ventas": 1, "total_vendido": D(1000), "total_devuelto": D(0), "total_neto": D(1000),
    }
    frases = resumir("ventas", datos)
    assert frases[0].startswith("Se hizo 1 venta por")
    assert not any("mejor" in f or "local" in f for f in frases)


def test_sin_ventas():
    datos = {"filas": [], "por_medio_pago": {}, "cantidad_ventas": 0,
             "total_vendido": D(0), "total_devuelto": D(0), "total_neto": D(0)}
    assert resumir("ventas", datos) == ["No hubo ventas con estos filtros."]


# ------------------------------------------------------------ Más vendidos

def vendido(nombre, unidades, margen):
    return {"nombre": nombre, "unidades": unidades, "margen": D(margen)}


def test_mas_vendidos_dice_el_primero_el_que_mas_gana_y_los_que_pierden():
    datos = {"filas": [vendido("Coca", 30, 1000), vendido("Agua", 10, 4000), vendido("Yogur", 10, -500)]}
    frases = resumir("productos-mas-vendidos", datos)
    assert frases[0] == "El más vendido fue Coca: 30 unidades, el 60 % de las unidades del ranking."
    assert "El que más ganancia deja es Agua ($ 4.000,00)." in frases
    assert "Se vende a pérdida: Yogur. Conviene revisar su precio o su costo." in frases


def test_mas_vendidos_sin_perdidas():
    frases = resumir("productos-mas-vendidos", {"filas": [vendido("Coca", 1, 100)]})
    assert frases[0] == "El más vendido fue Coca: 1 unidad, el 100 % de las unidades del ranking."
    assert frases[-1] == "Ningún producto del ranking se vende a pérdida."


# ------------------------------------------------------------ Devoluciones

def test_devoluciones_dice_cuanto_el_mas_devuelto_y_el_motivo():
    datos = {
        "filas": [{"nombre": "Coca", "unidades": 2, "vendidas": 8}],
        "por_motivo": [{"motivo": "Vencido", "devoluciones": 1, "importe": D(900)},
                       {"motivo": "Falla", "devoluciones": 2, "importe": D(500)}],
        "cantidad_devoluciones": 3, "unidades_devueltas": 2, "total_reintegrado": D(1400),
    }
    assert resumir("devoluciones", datos) == [
        "Se hicieron 3 devoluciones (2 unidades) y se reintegraron $ 1.400,00.",
        "El más devuelto fue Coca (2 unidades, el 25 % de lo que se vendió).",
        'El motivo más repetido es "Falla" (2 devoluciones).',
    ]


def test_devolucion_de_algo_vendido_en_otro_periodo():
    # en el período no se vendió: no se puede decir qué parte se devolvió
    datos = {"filas": [{"nombre": "Coca", "unidades": 1, "vendidas": 0}], "por_motivo": [],
             "cantidad_devoluciones": 1, "unidades_devueltas": 1, "total_reintegrado": D(100)}
    assert resumir("devoluciones", datos)[1] == "El más devuelto fue Coca (1 unidad)."


# ------------------------------------------------------------- Más pedidos

def pedido(nombre, unidades, falta):
    return {"nombre": nombre, "unidades": unidades, "pedidos": 2, "locales": 1, "falta_en_cd": falta}


def test_mas_pedidos_avisa_lo_que_no_alcanza():
    datos = {"filas": [pedido("Leche", 300, 91), pedido("Coca", 20, 0)], "total_sin_preparar": 300}
    assert resumir("productos-mas-pedidos", datos) == [
        "El más pedido fue Leche: 300 unidades en 2 pedidos de 1 local.",
        "Quedan 300 unidades pedidas sin preparar.",
        "Con el stock del CD no alcanza para Leche (faltan 91): hay que comprar.",
    ]


def test_mas_pedidos_cuando_el_cd_alcanza_o_ya_se_preparo_todo():
    alcanza = resumir("productos-mas-pedidos", {"filas": [pedido("Coca", 5, 0)], "total_sin_preparar": 5})
    assert alcanza[-1] == "El stock del CD alcanza para todo lo que falta preparar."
    preparado = resumir("productos-mas-pedidos", {"filas": [pedido("Coca", 5, 0)], "total_sin_preparar": 0})
    assert len(preparado) == 1


# ------------------------------------------------------------- Existencias

def test_existencias_dice_donde_esta_el_valor_y_que_falta():
    datos = {
        "filas": [{"nombre": "Agua", "ubicacion": "Norte", "bajo_minimo": True, "faltante": 8},
                  {"nombre": "Coca", "ubicacion": "Centro", "bajo_minimo": True, "faltante": 3},
                  {"nombre": "Leche", "ubicacion": "CD", "bajo_minimo": False, "faltante": 0}],
        "valorizado_por_ubicacion": {"CD": D(9000), "Norte": D(1000)}, "valorizado_total": D(10000),
    }
    assert resumir("existencias", datos) == [
        "El inventario vale $ 10.000,00 al costo; la mayor parte está en CD (90 %).",
        "Hay 2 productos por debajo del mínimo; el que más falta es Agua en Norte (8 unidades).",
    ]


def test_existencias_de_una_ubicacion_sin_faltantes():
    datos = {"filas": [{"nombre": "Coca", "ubicacion": "CD", "bajo_minimo": False, "faltante": 0}],
             "valorizado_por_ubicacion": {"CD": D(500)}, "valorizado_total": D(500)}
    assert resumir("existencias", datos) == ["El inventario vale $ 500,00 al costo.",
                                             "Ningún producto está por debajo del mínimo."]


# ------------------------------------------------------------------ Mermas

def local_merma(nombre, verificados, rechazados, perdido):
    return {"sucursal": nombre, "bultos_verificados": verificados, "bultos_rechazados": rechazados,
            "valor_perdido": D(perdido)}


def test_mermas_dice_la_tasa_y_el_local_con_mas_perdida():
    datos = {"por_sucursal": [local_merma("Centro", 3, 1, 200), local_merma("Sur", 4, 0, 0)],
             "valor_perdido_total": D(200)}
    assert resumir("mermas", datos) == [
        "De 8 bultos revisados, 1 llegó con el precinto roto (13 %): se perdieron $ 200,00.",
        "El local con más pérdida es Centro ($ 200,00).",
    ]


def test_sin_bultos_rechazados():
    datos = {"por_sucursal": [local_merma("Centro", 2, 0, 0)], "valor_perdido_total": D(0)}
    assert resumir("mermas", datos) == ["Se revisaron 2 bultos y ninguno llegó con el precinto roto: no hubo mermas."]


# ---------------------------------------------------------- Tiempos de envío

def test_tiempos_dice_el_promedio_el_mas_rapido_y_el_mas_lento():
    datos = {"filas": [{"sucursal": "Centro", "horas_promedio": 0.5}, {"sucursal": "Sur", "horas_promedio": 6.0}],
             "bultos": 4, "horas_promedio_general": 3.25}
    assert resumir("tiempos-transito", datos) == [
        "En promedio, un bulto tarda 3,25 h del CD al local (4 bultos recibidos).",
        "El más rápido es Centro (30 min) y el más lento, Sur (6,00 h).",
    ]


def test_tiempos_si_todos_tardan_lo_mismo_no_compara():
    datos = {"filas": [{"sucursal": "Centro", "horas_promedio": 2.0}, {"sucursal": "Sur", "horas_promedio": 2.0}],
             "bultos": 2, "horas_promedio_general": 2.0}
    assert resumir("tiempos-transito", datos) == ["En promedio, un bulto tarda 2,00 h del CD al local (2 bultos recibidos)."]


@pytest.mark.parametrize("clave, datos, frase", [
    ("productos-mas-vendidos", {"filas": []}, "No se vendió nada con estos filtros."),
    ("devoluciones", {"filas": []}, "No hubo devoluciones con estos filtros."),
    ("productos-mas-pedidos", {"filas": []}, "Los locales no hicieron pedidos con estos filtros."),
    ("existencias", {"filas": [], "valorizado_por_ubicacion": {}}, "No hay stock cargado con estos filtros."),
    ("mermas", {"por_sucursal": []}, "No hubo bultos verificados ni rechazados con estos filtros."),
    ("tiempos-transito", {"filas": []}, "Todavía no se recibió ningún bulto con estos filtros."),
])
def test_sin_datos_lo_dice_en_una_frase(clave, datos, frase):
    assert resumir(clave, datos) == [frase]
