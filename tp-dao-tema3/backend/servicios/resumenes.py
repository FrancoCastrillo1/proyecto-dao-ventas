# El resumen de cada reporte: dos o tres frases que dicen lo importante de los
# números ("El más vendido fue X, el 40 % de las unidades"). Toma lo que ya
# calculó ReportesService y lo pone en palabras; la pantalla y el PDF muestran
# el mismo texto. Hay una función por reporte, elegida por su clave.
# Acá NO se consulta la base ni se hacen las cuentas del reporte (eso es
# reportes_service.py), ni se dibuja nada.
from backend.dominio.documentos import nombre_del_medio
from backend.servicios.documentos_pdf import pesos
from backend.servicios.informes import horas


def parte(valor, total):
    """Qué parte del total es valor, en palabras ("40 %", "menos del 1 %")."""
    if not total:
        return None
    proporcion = float(valor) / float(total) * 100
    # + 0.5 y truncar: el 12,5 % se lee 13 % (round() de Python daría 12)
    return "menos del 1 %" if 0 < proporcion < 1 else f"{int(proporcion + 0.5)} %"


def plural(cantidad, singular, en_plural):
    return f"{cantidad} {singular if cantidad == 1 else en_plural}"


def segun(cantidad, singular, en_plural):
    # El verbo que concuerda: "se hizo 1 venta", "se hicieron 3 ventas"
    return singular if cantidad == 1 else en_plural


def periodo_legible(periodo):
    # "2026-10-20" → "el 20/10/2026"; "2026-10" → "10/2026"
    anio, mes, *dia = periodo.split("-")
    return f"el {dia[0]}/{mes}/{anio}" if dia else f"{mes}/{anio}"


def lista(nombres, maximo=3):
    """ "A", "A y B", "A, B y C", y si hay más: "A, B, C y 2 más". """
    nombres = list(nombres)
    if len(nombres) > maximo:
        return f"{', '.join(nombres[:maximo])} y {len(nombres) - maximo} más"
    return nombres[0] if len(nombres) == 1 else f"{', '.join(nombres[:-1])} y {nombres[-1]}"


def mayor(montos):
    """La clave con el monto más grande de un diccionario {clave: monto}."""
    return max(montos, key=lambda clave: (montos[clave], str(clave)))


# --------------------------------------------------------- Un resumen por reporte
def resumen_ventas(datos):
    if not datos["cantidad_ventas"]:
        return ["No hubo ventas con estos filtros."]
    neto = datos["total_neto"]
    cantidad = datos["cantidad_ventas"]
    frases = [f"{segun(cantidad, 'Se hizo', 'Se hicieron')} {plural(cantidad, 'venta', 'ventas')} "
              f"por {pesos(datos['total_vendido'])}; "
              f"descontando lo devuelto ({pesos(datos['total_devuelto'])}), el ingreso neto fue {pesos(neto)}."]
    por_periodo, por_local = {}, {}
    for fila in datos["filas"]:
        por_periodo[fila["periodo"]] = por_periodo.get(fila["periodo"], 0) + fila["neto"]
        por_local[fila["sucursal"]] = por_local.get(fila["sucursal"], 0) + fila["neto"]
    if len(por_periodo) > 1:
        mejor = mayor(por_periodo)
        cuando = "día" if len(mejor) == 10 else "mes"
        frases.append(f"El mejor {cuando} fue {periodo_legible(mejor)}, con {pesos(por_periodo[mejor])} de ingreso neto.")
    if neto > 0 and datos["por_medio_pago"]:
        medio = mayor(datos["por_medio_pago"])
        frases.append(f"Lo que más se cobró fue con {nombre_del_medio(medio)} "
                      f"({parte(datos['por_medio_pago'][medio], neto)} del ingreso neto).")
    if neto > 0 and len(por_local) > 1:
        local = mayor(por_local)
        frases.append(f"El local que más vendió fue {local} ({parte(por_local[local], neto)} del ingreso neto).")
    return frases


def resumen_mas_vendidos(datos):
    filas = datos["filas"]
    if not filas:
        return ["No se vendió nada con estos filtros."]
    primero = filas[0]
    total_unidades = sum(f["unidades"] for f in filas)
    frases = [f"El más vendido fue {primero['nombre']}: {plural(primero['unidades'], 'unidad', 'unidades')}, "
              f"el {parte(primero['unidades'], total_unidades)} de las unidades del ranking."]
    mas_ganancia = max(filas, key=lambda f: f["margen"])
    if mas_ganancia["margen"] > 0:
        frases.append(f"El que más ganancia deja es {mas_ganancia['nombre']} ({pesos(mas_ganancia['margen'])}).")
    a_perdida = [f["nombre"] for f in filas if f["margen"] < 0]
    if a_perdida:
        frases.append(f"Se {'vende' if len(a_perdida) == 1 else 'venden'} a pérdida: {lista(a_perdida)}. "
                      "Conviene revisar su precio o su costo.")
    else:
        frases.append("Ningún producto del ranking se vende a pérdida.")
    return frases


def resumen_devoluciones(datos):
    filas = datos["filas"]
    if not filas:
        return ["No hubo devoluciones con estos filtros."]
    cantidad = datos["cantidad_devoluciones"]
    frases = [f"{segun(cantidad, 'Se hizo', 'Se hicieron')} {plural(cantidad, 'devolución', 'devoluciones')} "
              f"({plural(datos['unidades_devueltas'], 'unidad', 'unidades')}) y se reintegraron "
              f"{pesos(datos['total_reintegrado'])}."]
    primero = filas[0]
    sobre_vendido = parte(primero["unidades"], primero["vendidas"])
    frases.append(f"El más devuelto fue {primero['nombre']} ({plural(primero['unidades'], 'unidad', 'unidades')}"
                  + (f", el {sobre_vendido} de lo que se vendió)." if sobre_vendido else ")."))
    if datos["por_motivo"]:
        motivo = max(datos["por_motivo"], key=lambda m: (m["devoluciones"], m["importe"]))
        frases.append(f"El motivo más repetido es \"{motivo['motivo']}\" "
                      f"({plural(motivo['devoluciones'], 'devolución', 'devoluciones')}).")
    return frases


def resumen_mas_pedidos(datos):
    filas = datos["filas"]
    if not filas:
        return ["Los locales no hicieron pedidos con estos filtros."]
    primero = filas[0]
    frases = [f"El más pedido fue {primero['nombre']}: {plural(primero['unidades'], 'unidad', 'unidades')} "
              f"en {plural(primero['pedidos'], 'pedido', 'pedidos')} de "
              f"{plural(primero['locales'], 'local', 'locales')}."]
    sin_preparar = datos["total_sin_preparar"]
    if sin_preparar:
        frases.append(f"{segun(sin_preparar, 'Queda', 'Quedan')} "
                      f"{plural(sin_preparar, 'unidad pedida', 'unidades pedidas')} sin preparar.")
    faltan = [f"{f['nombre']} (faltan {f['falta_en_cd']})" for f in filas if f["falta_en_cd"] > 0]
    if faltan:
        frases.append(f"Con el stock del CD no alcanza para {lista(faltan)}: hay que comprar.")
    elif datos["total_sin_preparar"]:
        frases.append("El stock del CD alcanza para todo lo que falta preparar.")
    return frases


def resumen_existencias(datos):
    if not datos["valorizado_por_ubicacion"]:
        return ["No hay stock cargado con estos filtros."]
    total = datos["valorizado_total"]
    valorizado = datos["valorizado_por_ubicacion"]
    donde = ""
    if len(valorizado) > 1 and total > 0:
        ubicacion = mayor(valorizado)
        donde = f"; la mayor parte está en {ubicacion} ({parte(valorizado[ubicacion], total)})"
    frases = [f"El inventario vale {pesos(total)} al costo{donde}."]
    bajo_minimo = [f for f in datos["filas"] if f["bajo_minimo"]]
    if bajo_minimo:
        peor = max(bajo_minimo, key=lambda f: (f["faltante"], f["nombre"]))
        frases.append(f"Hay {plural(len(bajo_minimo), 'producto', 'productos')} por debajo del mínimo; "
                      f"el que más falta es {peor['nombre']} en {peor['ubicacion']} "
                      f"({plural(peor['faltante'], 'unidad', 'unidades')}).")
    else:
        frases.append("Ningún producto está por debajo del mínimo.")
    return frases


def resumen_mermas(datos):
    locales = datos["por_sucursal"]
    if not locales:
        return ["No hubo bultos verificados ni rechazados con estos filtros."]
    rechazados = sum(s["bultos_rechazados"] for s in locales)
    revisados = sum(s["bultos_verificados"] + s["bultos_rechazados"] for s in locales)
    if not rechazados:
        return [f"{segun(revisados, 'Se revisó', 'Se revisaron')} {plural(revisados, 'bulto', 'bultos')} "
                "y ninguno llegó con el precinto roto: no hubo mermas."]
    frases = [f"De {plural(revisados, 'bulto revisado', 'bultos revisados')}, {rechazados} "
              f"{segun(rechazados, 'llegó', 'llegaron')} con el precinto roto ({parte(rechazados, revisados)}): "
              f"se perdieron {pesos(datos['valor_perdido_total'])}."]
    if len(locales) > 1:
        peor = max(locales, key=lambda s: (s["valor_perdido"], s["bultos_rechazados"]))
        frases.append(f"El local con más pérdida es {peor['sucursal']} ({pesos(peor['valor_perdido'])}).")
    return frases


def resumen_tiempos_transito(datos):
    filas = datos["filas"]
    if not filas:
        return ["Todavía no se recibió ningún bulto con estos filtros."]
    frases = [f"En promedio, un bulto tarda {horas(datos['horas_promedio_general'])} del CD al local "
              f"({plural(datos['bultos'], 'bulto recibido', 'bultos recibidos')})."]
    rapido = min(filas, key=lambda f: f["horas_promedio"])
    lento = max(filas, key=lambda f: f["horas_promedio"])
    if horas(rapido["horas_promedio"]) != horas(lento["horas_promedio"]):   # si tardan lo mismo, no hay qué comparar
        frases.append(f"El más rápido es {rapido['sucursal']} ({horas(rapido['horas_promedio'])}) "
                      f"y el más lento, {lento['sucursal']} ({horas(lento['horas_promedio'])}).")
    return frases


RESUMENES = {
    "ventas": resumen_ventas,
    "productos-mas-vendidos": resumen_mas_vendidos,
    "existencias": resumen_existencias,
    "mermas": resumen_mermas,
    "tiempos-transito": resumen_tiempos_transito,
    "productos-mas-pedidos": resumen_mas_pedidos,
    "devoluciones": resumen_devoluciones,
}


def resumir(clave, datos):
    """Las frases del resumen de un reporte ya calculado."""
    return RESUMENES[clave](datos)
