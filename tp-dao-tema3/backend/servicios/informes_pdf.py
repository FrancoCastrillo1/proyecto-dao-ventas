# Dibuja el PDF de un reporte con fpdf2: encabezado, filtros, tarjetas de
# totales, un gráfico de barras y las tablas. Recibe un Informe ya armado
# (servicios/informes.py) y no sabe de qué reporte es, así sirve para todos.
# Acá NO se decide qué dice el informe ni se consulta la base. Los colores son
# los del front (miel para las barras, rojo para lo negativo).
from fpdf import FPDF

from backend.servicios.documentos_pdf import texto_seguro

MARGEN = 15
ANCHO_UTIL = 180          # A4 (210 mm) menos los márgenes
TINTA = (43, 32, 24)
TINTA_SUAVE = (107, 90, 73)
MIEL = (201, 138, 27)
ROJO = (178, 58, 58)
FONDO_SUAVE = (242, 234, 221)
BORDE = (220, 207, 186)


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
    tarjetas(pdf, informe.tarjetas)
    if informe.grafico:
        grafico(pdf, informe.grafico)
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


def tarjetas(pdf, lista):
    # Una fila de cajas con los totales; la última, destacada (como en el front)
    if not lista:
        return
    separacion = 3
    ancho = (ANCHO_UTIL - separacion * (len(lista) - 1)) / len(lista)
    y = pdf.get_y()
    for i, (etiqueta, valor) in enumerate(lista):
        x = MARGEN + i * (ancho + separacion)
        ultima = i == len(lista) - 1
        pdf.set_fill_color(*(FONDO_SUAVE if ultima else (255, 255, 255)))
        pdf.set_draw_color(*BORDE)
        pdf.rect(x, y, ancho, 15, style="DF")
        pdf.set_xy(x + 3, y + 2)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*TINTA_SUAVE)
        pdf.cell(ancho - 6, 4, recortar(pdf, etiqueta, ancho - 6))
        pdf.set_xy(x + 3, y + 7)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*TINTA)
        pdf.cell(ancho - 6, 6, recortar(pdf, valor, ancho - 6))
    pdf.set_xy(MARGEN, y + 15 + 6)


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
