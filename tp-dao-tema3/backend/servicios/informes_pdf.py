# Dibuja el PDF de un reporte o un tablero con fpdf2: encabezado, filtros, el
# resumen, tarjetas (con su comparación, si la hay), los gráficos (barras de
# una o varias series, líneas, mapa de calor y dispersión) y las tablas.
# Recibe un Informe ya armado (servicios/informes.py o informes_tableros.py) y
# no sabe de qué reporte es, así sirve para todos: cada tipo de gráfico tiene
# su función de dibujo (DIBUJOS, al final).
# Acá NO se decide qué dice el informe ni se consulta la base. Los colores son
# los del front (miel para las barras, rojo para lo negativo).
import math

from fpdf import FPDF

from backend.servicios.documentos_pdf import texto_seguro
from backend.servicios.informes import Barras, Dispersion, Grafico, Lineas, MapaDeCalor

MARGEN = 15
ANCHO_UTIL = 180          # A4 (210 mm) menos los márgenes
TINTA = (43, 32, 24)
TINTA_SUAVE = (107, 90, 73)
MIEL = (201, 138, 27)
ROJO = (178, 58, 58)
FONDO_SUAVE = (242, 234, 221)
BORDE = (220, 207, 186)
GRILLA = (236, 227, 211)
VERDE = (63, 122, 69)
NARANJA = (180, 82, 29)
CLARO_CALOR, OSCURO_CALOR = (251, 239, 213), (138, 90, 11)   # mapa de calor: miel de claro a oscuro


class HojaInforme(FPDF):
    def __init__(self, pie):
        super().__init__(format="A4")
        self.pie = pie

    def footer(self):
        # fpdf2 lo llama solo al terminar cada hoja
        self.set_y(-12)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*TINTA_SUAVE)
        self.cell(ANCHO_UTIL / 2, 5, texto_seguro(self.pie))
        self.cell(ANCHO_UTIL / 2, 5, f"Hoja {self.page_no()}", align="R")


def recortar(pdf, texto, ancho):
    """El texto tal cual si entra en el ancho; si no, cortado con "...". """
    texto = texto_seguro(texto)
    if pdf.get_string_width(texto) <= ancho - 2:
        return texto
    while texto and pdf.get_string_width(texto + "...") > ancho - 2:
        texto = texto[:-1]
    return texto + "..."


def dibujar_informe(informe):
    """Devuelve los bytes del PDF. Sin comprimir, como los comprobantes, para
    que los tests puedan buscar el texto adentro."""
    pdf = HojaInforme(informe.generado)
    pdf.set_compression(False)
    pdf.set_margins(MARGEN, MARGEN, MARGEN)
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_page()
    pdf.set_text_color(*TINTA)

    encabezado(pdf, informe)
    resumen(pdf, informe.resumen)
    tarjetas(pdf, informe.tarjetas)
    if informe.grafico:
        grafico(pdf, informe.grafico)
    for un_grafico in informe.graficos:
        DIBUJOS[type(un_grafico)](pdf, un_grafico)
    for tabla_del_informe in informe.tablas:
        tabla(pdf, tabla_del_informe)
    if informe.notas:
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*TINTA_SUAVE)
        for nota in informe.notas:
            pdf.multi_cell(ANCHO_UTIL, 4, texto_seguro(nota), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def encabezado(pdf, informe):
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*TINTA_SUAVE)
    pdf.cell(ANCHO_UTIL, 4, texto_seguro(informe.comercio), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*TINTA)
    pdf.cell(ANCHO_UTIL, 10, texto_seguro(f"Reporte: {informe.titulo}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*TINTA_SUAVE)
    pdf.cell(ANCHO_UTIL, 5, texto_seguro(informe.pregunta), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8.5)
    pdf.cell(ANCHO_UTIL, 5, texto_seguro("  ·  ".join(informe.filtros)), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*BORDE)
    pdf.line(MARGEN, pdf.get_y() + 2, MARGEN + ANCHO_UTIL, pdf.get_y() + 2)
    pdf.ln(5)


def resumen(pdf, frases):
    # Las frases que dicen lo importante, con una raya miel a la izquierda
    if not frases:
        return
    y_inicio = pdf.get_y()
    pdf.set_x(MARGEN + 4)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*TINTA)
    pdf.cell(ANCHO_UTIL - 4, 5, "Resumen", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for frase in frases:
        pdf.set_x(MARGEN + 4)
        pdf.multi_cell(ANCHO_UTIL - 4, 4.6, texto_seguro(frase), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*MIEL)
    pdf.set_line_width(0.8)
    pdf.line(MARGEN + 0.4, y_inicio, MARGEN + 0.4, pdf.get_y())
    pdf.set_line_width(0.2)
    pdf.ln(5)


def tarjetas(pdf, lista):
    """Una fila de cajas con los totales; la última, destacada (como en el
    front). Una tarjeta con comparación trae dos datos más: el cambio escrito
    y si mejoró (verde), empeoró (naranja) o no se sabe (gris)."""
    if not lista:
        return
    # Hasta 4 entran en una fila; con 5 o 6, dos filas de 3 (si no, se cortan los textos)
    por_fila = len(lista) if len(lista) <= 4 else math.ceil(len(lista) / 2)
    for inicio in range(0, len(lista), por_fila):
        fila_de_tarjetas(pdf, lista[inicio:inicio + por_fila], por_fila, ultima_fila=inicio + por_fila >= len(lista))


def fila_de_tarjetas(pdf, lista, por_fila, ultima_fila):
    separacion = 3
    ancho = (ANCHO_UTIL - separacion * (por_fila - 1)) / por_fila
    alto = 20 if any(len(t) > 2 for t in lista) else 15
    y = pdf.get_y()
    for i, tarjeta in enumerate(lista):
        etiqueta, valor = tarjeta[0], tarjeta[1]
        x = MARGEN + i * (ancho + separacion)
        ultima = ultima_fila and i == len(lista) - 1 and alto == 15
        pdf.set_fill_color(*(FONDO_SUAVE if ultima else (255, 255, 255)))
        pdf.set_draw_color(*BORDE)
        pdf.rect(x, y, ancho, alto, style="DF")
        pdf.set_xy(x + 3, y + 2)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*TINTA_SUAVE)
        pdf.cell(ancho - 6, 4, recortar(pdf, etiqueta, ancho - 6))
        pdf.set_xy(x + 3, y + 7)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*TINTA)
        pdf.cell(ancho - 6, 6, recortar(pdf, valor, ancho - 6))
        if len(tarjeta) > 2:
            cambio, mejoro = tarjeta[2], tarjeta[3]
            pdf.set_xy(x + 3, y + 13.5)
            pdf.set_font("Helvetica", "B", 6.8)
            pdf.set_text_color(*(TINTA_SUAVE if mejoro is None else VERDE if mejoro else NARANJA))
            pdf.cell(ancho - 6, 4, recortar(pdf, cambio, ancho - 6))
    pdf.set_xy(MARGEN, y + alto + 6)


def hacer_lugar(pdf, alto):
    # Un gráfico no se corta entre dos hojas: si no entra, va a la siguiente
    if pdf.get_y() + alto > pdf.page_break_trigger:
        pdf.add_page()


def leyenda(pdf, series, y):
    """Un cuadradito de color y el nombre de cada serie, en una fila."""
    pdf.set_font("Helvetica", "", 7.5)
    x = MARGEN
    for nombre, color in series:
        pdf.set_fill_color(*color)
        pdf.rect(x, y + 1.3, 2.6, 2.6, style="F")
        pdf.set_xy(x + 3.6, y)
        pdf.set_text_color(*TINTA_SUAVE)
        texto = texto_seguro(nombre)
        pdf.cell(pdf.get_string_width(texto) + 1, 5, texto)
        x += pdf.get_string_width(texto) + 10


def marcas(minimo, maximo, cantidad=4):
    """Valores redondos para un eje (1, 2, 2,5 o 5 por una potencia de 10),
    siempre con el 0."""
    minimo, maximo = min(0, minimo), max(0, maximo) or 1
    crudo = (maximo - minimo) / cantidad
    potencia = 10 ** math.floor(math.log10(crudo))
    paso = next(m * potencia for m in (1, 2, 2.5, 5, 10) if m * potencia >= crudo)
    inicio = math.floor(minimo / paso) * paso
    return [inicio + i * paso for i in range(int(math.ceil((maximo - inicio) / paso - 1e-9)) + 1)]


def eje_corto(valor):
    # En un eje no entra "$ 1.234.567,00": 1,2 M, 250 mil
    absoluto = abs(valor)
    if absoluto >= 1_000_000:
        return f"{valor / 1_000_000:.1f} M".replace(".", ",").replace(",0 M", " M")
    if absoluto >= 10_000:
        return f"{valor / 1000:.0f} mil"
    return f"{valor:g}".replace(".", ",")


def lineas(pdf, datos):
    """Una línea por serie (la punteada, para la que se compara), con el eje y
    en valores redondos y las etiquetas del eje x salteadas si son muchas."""
    alto, ancho_eje = 52, 18
    hacer_lugar(pdf, 7 + alto + 14)
    titulo_de_seccion(pdf, datos.titulo)
    valores = [v for _, serie, _, _ in datos.series for v in serie if v is not None]
    escala = marcas(min(valores, default=0), max(valores, default=1))
    x0, x1 = MARGEN + ancho_eje, MARGEN + ANCHO_UTIL
    y0 = pdf.get_y() + 2
    y_de = lambda v: y0 + alto - (v - escala[0]) / (escala[-1] - escala[0]) * alto   # noqa: E731
    pdf.set_font("Helvetica", "", 6.5)
    for marca in escala:
        pdf.set_draw_color(*GRILLA)
        pdf.line(x0, y_de(marca), x1, y_de(marca))
        pdf.set_xy(MARGEN, y_de(marca) - 2)
        pdf.set_text_color(*TINTA_SUAVE)
        pdf.cell(ancho_eje - 2, 4, eje_corto(marca), align="R")
    cantidad = len(datos.etiquetas)
    paso_x = (x1 - x0) / max(cantidad - 1, 1)
    salto = max(1, math.ceil(cantidad / 12))
    for i, etiqueta in enumerate(datos.etiquetas):
        if i % salto == 0:
            pdf.set_xy(x0 + i * paso_x - 8, y0 + alto + 1)
            pdf.cell(16, 4, texto_seguro(etiqueta), align="C")
    for _, serie, color, punteada in datos.series:
        pdf.set_draw_color(*color)
        pdf.set_line_width(0.55)
        if punteada:
            pdf.set_dash_pattern(dash=1.4, gap=1.1)
        for i in range(1, len(serie)):
            if serie[i - 1] is not None and serie[i] is not None:
                pdf.line(x0 + (i - 1) * paso_x, y_de(serie[i - 1]), x0 + i * paso_x, y_de(serie[i]))
        pdf.set_dash_pattern()
    pdf.set_line_width(0.2)
    if len(datos.series) > 1:
        leyenda(pdf, [(nombre, color) for nombre, _, color, _ in datos.series], y0 + alto + 6)
    pdf.set_xy(MARGEN, y0 + alto + 13)


def barras(pdf, datos):
    """Barras acostadas de varias series: una debajo de la otra en cada fila,
    o apiladas (con el total en la punta)."""
    if not datos.nombres:
        return
    cantidad_series = len(datos.series)
    alto_barra = 4.2 if datos.apiladas else 3.4
    alto_fila = alto_barra + 3 if datos.apiladas else alto_barra * cantidad_series + 3
    ancho_nombre, ancho_valor = 45, 26
    ancho_barras = ANCHO_UTIL - ancho_nombre - ancho_valor
    if datos.apiladas:
        totales = [sum(serie[i] for _, serie, _ in datos.series) for i in range(len(datos.nombres))]
    else:
        totales = [v for _, serie, _ in datos.series for v in serie]
    maximo = max(totales, default=0) or 1
    hacer_lugar(pdf, 7 + alto_fila * len(datos.nombres) + 9)
    titulo_de_seccion(pdf, datos.titulo)
    x0 = MARGEN + ancho_nombre
    y = y_inicio = pdf.get_y()
    for i, nombre in enumerate(datos.nombres):
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*TINTA)
        pdf.set_xy(MARGEN, y + alto_fila / 2 - 2.5)
        pdf.cell(ancho_nombre - 2, 5, recortar(pdf, nombre, ancho_nombre - 2), align="R")
        x = x0
        for j, (_, serie, color) in enumerate(datos.series):
            largo = ancho_barras * max(serie[i], 0) / maximo
            pdf.set_fill_color(*color)
            if datos.apiladas:
                if largo > 0:
                    pdf.rect(x, y + 1.5, largo, alto_barra, style="F")
                x += largo
            else:
                y_barra = y + 1.5 + j * alto_barra
                if largo > 0:
                    pdf.rect(x0, y_barra, largo, alto_barra - 0.6, style="F")
                pdf.set_font("Helvetica", "", 6.3)
                pdf.set_text_color(*TINTA_SUAVE)
                pdf.set_xy(x0 + largo + 1, y_barra - 0.6)
                pdf.cell(ancho_valor, alto_barra, texto_seguro(datos.texto(serie[i])))
        if datos.apiladas:
            pdf.set_font("Helvetica", "", 6.5)
            pdf.set_text_color(*TINTA_SUAVE)
            pdf.set_xy(x + 1, y + 1.5)
            pdf.cell(ancho_valor, alto_barra, texto_seguro(datos.texto(totales[i])))
        y += alto_fila
    pdf.set_draw_color(*BORDE)
    pdf.line(x0, y_inicio, x0, y)
    leyenda(pdf, [(nombre, color) for nombre, _, color in datos.series], y + 1)
    pdf.set_xy(MARGEN, y + 9)


def mapa_calor(pdf, datos):
    """Una grilla de celdas: cuanto más vendió, más oscuro el miel; adentro, el
    texto de la celda (la cantidad de tickets)."""
    valores = [v for _, fila, _ in datos.filas for v in fila]
    maximo = max(valores, default=0)
    if not maximo:
        return
    ancho_rotulo, alto_celda = 22, 6.5
    ancho_celda = (ANCHO_UTIL - ancho_rotulo) / len(datos.columnas)
    hacer_lugar(pdf, 7 + alto_celda * (len(datos.filas) + 1) + 10)
    titulo_de_seccion(pdf, datos.titulo)
    y = pdf.get_y()
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_text_color(*TINTA_SUAVE)
    for i, columna in enumerate(datos.columnas):
        pdf.set_xy(MARGEN + ancho_rotulo + i * ancho_celda, y)
        pdf.cell(ancho_celda, 5, texto_seguro(columna), align="C")
    y += 5.5
    for nombre, fila, textos in datos.filas:
        pdf.set_font("Helvetica", "", 6.8)
        pdf.set_text_color(*TINTA_SUAVE)
        pdf.set_xy(MARGEN, y)
        pdf.cell(ancho_rotulo - 1, alto_celda, texto_seguro(nombre))
        for i, valor in enumerate(fila):
            proporcion = valor / maximo
            if valor:
                color = tuple(round(c + (o - c) * (0.12 + 0.88 * proporcion)) for c, o in zip(CLARO_CALOR, OSCURO_CALOR))
            else:
                color = FONDO_SUAVE
            pdf.set_fill_color(*color)
            pdf.rect(MARGEN + ancho_rotulo + i * ancho_celda + 0.5, y + 0.4, ancho_celda - 1, alto_celda - 0.8, style="F")
            pdf.set_xy(MARGEN + ancho_rotulo + i * ancho_celda, y)
            pdf.set_font("Helvetica", "B", 6.5)
            pdf.set_text_color(*((255, 253, 249) if proporcion > 0.55 else OSCURO_CALOR))
            pdf.cell(ancho_celda, alto_celda, texto_seguro(textos[i]), align="C")
        y += alto_celda
    if datos.nota:
        pdf.set_xy(MARGEN, y + 1)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*TINTA_SUAVE)
        pdf.cell(ANCHO_UTIL, 4, texto_seguro(datos.nota))
    pdf.set_xy(MARGEN, y + 9)


def dispersion(pdf, datos):
    """Cada punto, un círculo (más grande cuanto más vale) con su rótulo; las
    líneas de corte punteadas separan los cuadrantes."""
    if not datos.puntos:
        return
    alto, ancho_eje = 68, 16
    hacer_lugar(pdf, 7 + alto + 14)
    titulo_de_seccion(pdf, datos.titulo)
    xs = [p[1] for p in datos.puntos]
    ys = [p[2] for p in datos.puntos]
    escala_x = marcas(0, max(xs))
    escala_y = marcas(min(ys), max(ys))
    x0, x1 = MARGEN + ancho_eje, MARGEN + ANCHO_UTIL - 4
    y0 = pdf.get_y() + 2
    x_de = lambda v: x0 + (v - escala_x[0]) / (escala_x[-1] - escala_x[0]) * (x1 - x0)   # noqa: E731
    y_de = lambda v: y0 + alto - (v - escala_y[0]) / (escala_y[-1] - escala_y[0]) * alto  # noqa: E731
    pdf.set_font("Helvetica", "", 6.5)
    pdf.set_text_color(*TINTA_SUAVE)
    pdf.set_draw_color(*GRILLA)
    for marca in escala_y:
        pdf.line(x0, y_de(marca), x1, y_de(marca))
        pdf.set_xy(MARGEN, y_de(marca) - 2)
        pdf.cell(ancho_eje - 2, 4, f"{marca:g} %".replace(".", ","), align="R")
    for marca in escala_x:
        pdf.line(x_de(marca), y0, x_de(marca), y0 + alto)
        pdf.set_xy(x_de(marca) - 8, y0 + alto + 1)
        pdf.cell(16, 4, f"{marca:g}", align="C")
    pdf.set_draw_color(*TINTA_SUAVE)
    pdf.set_dash_pattern(dash=1.2, gap=1)
    pdf.line(x_de(datos.corte_x), y0, x_de(datos.corte_x), y0 + alto)
    pdf.line(x0, y_de(datos.corte_y), x1, y_de(datos.corte_y))
    pdf.set_dash_pattern()
    mayor = max((p[3] for p in datos.puntos), default=0) or 1
    for rotulo, x, y, tamano, color in sorted(datos.puntos, key=lambda p: -p[3]):
        radio = 1.1 + 3.2 * math.sqrt(tamano / mayor)
        pdf.set_fill_color(*color)
        pdf.set_draw_color(255, 253, 249)
        pdf.ellipse(x_de(x) - radio, y_de(y) - radio, 2 * radio, 2 * radio, style="DF")
        pdf.set_font("Helvetica", "", 5.8)
        pdf.set_text_color(*TINTA)
        pdf.set_xy(x_de(x) + radio + 0.4, y_de(y) - 2)
        pdf.cell(20, 4, texto_seguro(rotulo))
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*TINTA_SUAVE)
    pdf.set_xy(x0, y0 + alto + 5)
    pdf.cell(x1 - x0, 4, texto_seguro(f"{datos.titulo_x} ->   (eje vertical: {datos.titulo_y})"), align="C")
    pdf.set_xy(MARGEN, y0 + alto + 12)


def grafico(pdf, datos):
    """Barras acostadas: el nombre a la izquierda, la barra desde el 0 y el
    valor escrito en la punta. Si hay negativos, el 0 se corre a la derecha y
    esas barras crecen hacia la izquierda, en rojo."""
    ancho_nombre, ancho_valor, alto_fila = 52, 28, 7
    ancho_barras = ANCHO_UTIL - ancho_nombre - ancho_valor
    valores = [valor for _, valor, _ in datos.barras]
    minimo, maximo = min(0, *valores), max(0, *valores)
    rango = (maximo - minimo) or 1
    x_cero = MARGEN + ancho_nombre + ancho_barras * (-minimo / rango)

    alto_total = 9 + alto_fila * len(datos.barras) + 3
    if pdf.get_y() + alto_total > pdf.page_break_trigger:
        pdf.add_page()
    titulo_de_seccion(pdf, datos.titulo)
    y_inicio = pdf.get_y()
    pdf.set_font("Helvetica", "", 8)
    for nombre, valor, texto in datos.barras:
        y = pdf.get_y()
        pdf.set_text_color(*TINTA)
        pdf.cell(ancho_nombre, alto_fila, recortar(pdf, nombre, ancho_nombre), align="R")
        largo = ancho_barras * abs(valor) / rango
        pdf.set_fill_color(*(ROJO if valor < 0 else MIEL))
        if largo > 0:
            pdf.rect(x_cero - largo if valor < 0 else x_cero, y + 1.5, max(largo, 0.6), alto_fila - 3, style="F")
        # el valor, pegado a la punta (en las negativas, del lado del 0)
        pdf.set_xy((x_cero + largo if valor > 0 else x_cero) + 1.5, y)
        pdf.set_text_color(*TINTA_SUAVE)
        pdf.cell(ancho_valor, alto_fila, texto_seguro(texto), new_x="LMARGIN", new_y="NEXT")
    # la línea del 0, de punta a punta de las barras
    pdf.set_draw_color(*BORDE)
    pdf.line(x_cero, y_inicio, x_cero, pdf.get_y())
    pdf.ln(5)


def con_aire(texto, alineado, columna):
    # Una columna de texto (a la izquierda) que viene después de un número (a la
    # derecha) quedaría pegada: se le deja un espacio adelante
    return f"  {texto}" if alineado == "L" and columna > 0 else texto


def titulo_de_seccion(pdf, texto):
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.set_text_color(*TINTA)
    pdf.cell(ANCHO_UTIL, 7, texto_seguro(texto), new_x="LMARGIN", new_y="NEXT")


def tabla(pdf, datos):
    total = sum(ancho for _, ancho, _ in datos.columnas)
    anchos = [ANCHO_UTIL * ancho / total for _, ancho, _ in datos.columnas]
    alto_fila = 6

    def cabecera():
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.set_fill_color(*FONDO_SUAVE)
        pdf.set_text_color(*TINTA_SUAVE)
        for i, ((titulo, _, alineado), ancho) in enumerate(zip(datos.columnas, anchos)):
            pdf.cell(ancho, alto_fila, con_aire(recortar(pdf, titulo, ancho), alineado, i), align=alineado, fill=True)
        pdf.ln()
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*TINTA)

    # el título no queda solo al pie de una hoja: si no entran unas filas, hoja nueva
    if pdf.get_y() + 7 + alto_fila * 3 > pdf.page_break_trigger:
        pdf.add_page()
    titulo_de_seccion(pdf, datos.titulo)
    if not datos.filas:
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*TINTA_SUAVE)
        pdf.cell(ANCHO_UTIL, 6, "No hay datos para estos filtros.", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
        return
    cabecera()
    pdf.set_draw_color(*BORDE)
    for fila in datos.filas:
        if pdf.get_y() + alto_fila > pdf.page_break_trigger:
            pdf.add_page()
            cabecera()       # en cada hoja nueva se repiten los títulos de las columnas
        for i, (valor, (_, _, alineado), ancho) in enumerate(zip(fila, datos.columnas, anchos)):
            pdf.cell(ancho, alto_fila, con_aire(recortar(pdf, valor, ancho), alineado, i), align=alineado)
        pdf.ln()
        pdf.line(MARGEN, pdf.get_y(), MARGEN + ANCHO_UTIL, pdf.get_y())
    pdf.ln(5)


# Cómo se dibuja cada tipo de gráfico de un informe
DIBUJOS = {Grafico: grafico, Lineas: lineas, Barras: barras, MapaDeCalor: mapa_calor, Dispersion: dispersion}
