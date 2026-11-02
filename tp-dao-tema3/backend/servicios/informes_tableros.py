# El contenido del PDF de cada uno de los tres tableros (ejecutivo, ventas del
# local y abastecimiento): los indicadores con su comparación y
# TODOS sus gráficos (líneas, barras de varias series, mapa de calor), más
# las tablas chicas. Toma lo que ya devolvió TablerosService
# y decide qué se muestra y cómo se escribe; los colores son los de la
# pantalla. Hay una función por tablero, elegida por su clave.
# Acá NO se dibuja (eso es informes_pdf.py, el mismo que dibuja los reportes)
# ni se consulta la base.
from backend.servicios.documentos_pdf import pesos
from backend.servicios.informes import (
    Barras, Lineas, MapaDeCalor, Tabla, grafico, horas, porcentaje,
)

MIEL = (201, 138, 27)
PETROLEO = (0, 130, 160)
GRIS = (179, 165, 143)
COLOR_ESTADO = {"Pendiente": (180, 82, 29), "En preparación": (224, 168, 58), "En camino": (0, 130, 160),
                "Recibido": (92, 158, 71), "Recibido con rechazos": (147, 57, 58)}
COMPARACIONES = {"anterior": "el período anterior", "anio": "el mismo período del año pasado"}


def numero(valor):
    entero = f"{valor:,.0f}".replace(",", ".") if float(valor).is_integer() else f"{valor:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return entero


def escrito(tipo, valor):
    if valor is None:
        return "-"
    if tipo == "pesos":
        return pesos(valor)
    if tipo == "porcentaje":
        return f"{valor:.1f} %".replace(".", ",")
    if tipo == "horas":
        return horas(valor)
    return numero(valor)


def tarjetas_de(indicadores):
    """Cada indicador como tarjeta; si se compara, con su cambio: "+31,6 % vs.
    $ 1.501.375,00" (o "sin datos para comparar" si antes no hubo nada)."""
    tarjetas = []
    for i in indicadores:
        valor = escrito(i["tipo"], i["valor"])
        if i["anterior"] is None:
            tarjetas.append((i["titulo"], valor))
        elif i["cambio"] is None:
            tarjetas.append((i["titulo"], valor, "Sin datos para comparar", None))
        else:
            signo = "+" if i["cambio"] > 0 else ""
            unidad = " pts" if i["en_puntos"] else " %"
            cambio = f"{signo}{i['cambio']:.1f}".replace(".", ",") + unidad
            tarjetas.append((i["titulo"], valor, f"{cambio} vs. {escrito(i['tipo'], i['anterior'])}",
                             None if i["cambio"] == 0 else i["cambio"] > 0))
    return tuple(tarjetas)


def unidades(n):
    return f"{numero(n)} u."


# ------------------------------------------------- El stock (en abastecimiento)
def partes_del_stock(stock):
    """El stock por antigüedad de su última salida y lo que falta reponer."""
    graficos = (
        grafico("Valor del stock según su última salida", stock["tramos"], lambda t: t["tramo"],
                lambda t: t["valor"], lambda t: pesos(t["valor"]), ordenar=False),
        grafico("Lo que más falta reponer (unidades)", stock["para_reponer"],
                lambda f: f"{f['nombre']} ({f['ubicacion']})", lambda f: f["faltante"],
                lambda f: unidades(f["faltante"])),
    )
    tabla = Tabla("Para reponer", (("Ubicación", 3, "L"), ("Producto", 5, "L"), ("Hay", 1.3, "R"),
                                   ("Mínimo", 1.5, "R"), ("Falta", 1.3, "R")),
                  tuple((f["ubicacion"], f["nombre"], str(f["cantidad"]), str(f["stock_minimo"]), str(f["faltante"]))
                        for f in stock["para_reponer"]))
    nota = ("Stock de hoy. Última salida: la última venta en un local o el último despacho en el CD. El detalle "
            "completo está en el reporte de existencias.")
    return graficos, (tabla,), (nota,)


# --------------------------------------------------------------- Un tablero cada uno
def tablero_ejecutivo(datos):
    evolucion = datos["evolucion"]
    contra = COMPARACIONES[datos["periodo"]["comparar"]]
    return dict(
        titulo="Tablero ejecutivo", pregunta="¿Cómo le va a la empresa: cuánto vende, cuánto gana y qué local rinde más?",
        tarjetas=tarjetas_de(datos["indicadores"]), grafico=None,
        graficos=(
            Lineas(f"Ventas netas por {'día' if evolucion['agrupado'] == 'dia' else 'semana'} contra {contra}",
                   tuple(p["etiqueta"] for p in evolucion["puntos"]),
                   (("Este período", tuple(float(p["actual"]) for p in evolucion["puntos"]), MIEL, False),
                    ("Comparado", tuple(float(p["anterior"]) for p in evolucion["puntos"]), GRIS, True)), pesos),
            Barras("Ranking de locales: ventas y ganancia", tuple(l["sucursal"] for l in datos["locales"]),
                   (("Ventas netas", tuple(float(l["ventas"]) for l in datos["locales"]), MIEL),
                    ("Ganancia bruta", tuple(float(l["ganancia"]) for l in datos["locales"]), PETROLEO)), pesos),
            Barras("Ventas y ganancia por categoría", tuple(c["categoria"] for c in datos["categorias"]),
                   (("Ventas netas", tuple(float(c["ventas"]) for c in datos["categorias"]), MIEL),
                    ("Ganancia bruta", tuple(float(c["ganancia"]) for c in datos["categorias"]), PETROLEO)), pesos),
        ),
        tablas=(
            Tabla("Locales", (("Local", 4, "L"), ("Ventas netas", 2.5, "R"), ("Participación", 2, "R"),
                              ("Ganancia bruta", 2.5, "R"), ("Margen", 1.6, "R"), ("Tickets", 1.4, "R")),
                  tuple((l["sucursal"], pesos(l["ventas"]), porcentaje(l["participacion"]), pesos(l["ganancia"]),
                         porcentaje(l["margen"]), str(l["tickets"])) for l in datos["locales"])),
            Tabla("Categorías", (("Categoría", 4, "L"), ("Ventas netas", 2.5, "R"), ("Participación", 2, "R"),
                                 ("Ganancia bruta", 2.5, "R"), ("Margen", 1.6, "R")),
                  tuple((c["categoria"], pesos(c["ventas"]), porcentaje(c["participacion"]), pesos(c["ganancia"]),
                         porcentaje(c["margen"])) for c in datos["categorias"])),
        ),
        notas=("Ventas netas de devoluciones; ganancia bruta = ventas netas - costo de lo vendido (al costo del "
               "momento de cada venta). El margen se compara en puntos.",),
    )


def tablero_ventas(datos):
    dias = datos["por_dia"]
    mapa = datos["mapa_calor"]
    devoluciones = datos["devoluciones"]
    return dict(
        titulo="Tablero de ventas", pregunta="¿Cuándo se vende más, cuánto deja cada ticket y qué se devuelve?",
        tarjetas=tarjetas_de(datos["indicadores"]), grafico=None,
        graficos=tuple(g for g in (
            Lineas("Ventas netas por día", tuple(d["etiqueta"] for d in dias),
                   (("Ventas netas", tuple(float(d["ventas"]) for d in dias), MIEL, False),), pesos),
            Lineas("Ticket promedio por día", tuple(d["etiqueta"] for d in dias),
                   (("Ticket promedio", tuple(None if d["ticket_promedio"] is None else float(d["ticket_promedio"])
                                               for d in dias), PETROLEO, False),), pesos),
            MapaDeCalor("¿Cuándo se vende? Ventas por día y horario", tuple(mapa["dias"]),
                        tuple((f["franja"], tuple(float(v) for v in f["ventas"]),
                               tuple(str(t) if t else "" for t in f["tickets"])) for f in mapa["filas"]),
                        "Más oscuro = más ventas en pesos. El número de cada celda es la cantidad de tickets."),
            grafico("Ventas netas por categoría", datos["categorias"], lambda c: c["categoria"],
                    lambda c: c["ventas"], lambda c: pesos(c["ventas"])),
            grafico("Lo que más se devuelve (unidades)", devoluciones["productos"], lambda p: p["nombre"],
                    lambda p: p["unidades"], lambda p: unidades(p["unidades"])),
        ) if g),           # un gráfico de barras con menos de dos barras no se arma (None)
        tablas=(
            Tabla("Categorías", (("Categoría", 4, "L"), ("Ventas netas", 2.5, "R"), ("Unidades", 1.8, "R"),
                                 ("Participación", 2, "R")),
                  tuple((c["categoria"], pesos(c["ventas"]), numero(c["unidades"]), porcentaje(c["participacion"]))
                        for c in datos["categorias"])),
            Tabla(f"Devoluciones: {devoluciones['cantidad']} por {pesos(devoluciones['reintegrado'])}",
                  (("Producto", 5, "L"), ("Devueltas", 1.8, "R"), ("% de lo vendido", 2.2, "R"), ("Motivo principal", 4, "L")),
                  tuple((p["nombre"], str(p["unidades"]), porcentaje(p["porcentaje_devuelto"]), p["motivo_principal"])
                        for p in devoluciones["productos"])),
        ),
    )


def tablero_abastecimiento(datos):
    estados = [e for e in datos["estados"] if any(f[e] for f in datos["por_estado"])]
    graficos = [
        Barras("Pedidos por estado y local", tuple(f["sucursal"] for f in datos["por_estado"]),
               tuple((e, tuple(f[e] for f in datos["por_estado"]), COLOR_ESTADO[e]) for e in estados),
               lambda n: f"{numero(n)}", apiladas=True) if estados else None,
    ]
    # Si todos tardaron menos de un minuto (ej. los datos de prueba), no hay barras que comparar
    if any(t["horas_promedio"] >= 1 / 60 for t in datos["tiempos"]):
        graficos.append(grafico("Tiempo de reposición: del pedido a la mercadería verificada", datos["tiempos"],
                                lambda t: t["sucursal"], lambda t: t["horas_promedio"], lambda t: horas(t["horas_promedio"])))
    if datos["demanda"]:
        graficos.append(grafico("Lo que más piden los locales (unidades)", datos["demanda"], lambda f: f["nombre"],
                                lambda f: f["unidades"], lambda f: unidades(f["unidades"])))
    graficos_stock, tablas_stock, notas_stock = partes_del_stock(datos["stock"])
    return dict(
        titulo="Tablero de abastecimiento",
        pregunta="¿En qué estado están los pedidos, cuánto tarda en llegar la mercadería y qué stock falta o está parado?",
        tarjetas=tarjetas_de(datos["indicadores"]), grafico=None,
        graficos=tuple(g for g in (*graficos, *graficos_stock) if g),
        tablas=(Tabla("Pedidos", (("Pedido", 1.3, "L"), ("Fecha", 2.6, "L"), ("Local", 3, "L"), ("Unidades", 1.6, "R"),
                                  ("Estado", 3.2, "L"), ("Tardó", 1.6, "R")),
                      tuple((f"#{p['pedido_id']}", p["fecha"][:16], p["sucursal"], str(p["unidades"]), p["estado"],
                             horas(p["horas"])) for p in datos["pedidos"])),
                *tablas_stock),
        notas=("Tiempo de reposición: desde que el local hace el pedido hasta que termina de verificar los bultos "
               "(recién ahí la mercadería se puede vender).", *notas_stock),
    )


ARMADOS_TABLEROS = {
    "tablero-ejecutivo": tablero_ejecutivo,
    "tablero-ventas": tablero_ventas,
    "tablero-abastecimiento": tablero_abastecimiento,
}
