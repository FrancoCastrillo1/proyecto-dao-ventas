# Dibuja un documento comercial en PDF con fpdf2. Recibe un ContenidoDocumento
# del dominio (ya armado por el Template Method) y lo pone en la hoja: no sabe
# si es un comprobante, una nota de crédito o un remito, por eso sirve para todos.
# Acá NO se decide qué dice el documento (eso es dominio/documentos.py) ni se
# consulta la base.
from decimal import Decimal

from fpdf import FPDF

ANCHO_UTIL = 128   # mm: hoja A5 (148 mm) menos los márgenes


def pesos(valor):
    # Formato argentino: $ 1.234,56 (y el signo adelante si es negativo)
    texto = f"{abs(Decimal(valor)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-$ {texto}" if valor < 0 else f"$ {texto}"


def celda(valor):
    """Cómo se escribe un valor: la plata (Decimal) en pesos, una cuenta como
    número, un texto tal cual, y nada si no corresponde."""
    if valor is None:
        return ""
    if isinstance(valor, Decimal):
        return pesos(valor)
    return texto_seguro(valor)


def texto_seguro(texto):
    # Las fuentes básicas del PDF son Latin-1 (tildes y ñ sí; emojis no): lo
    # que no entra se reemplaza para que el PDF nunca falle por un nombre raro
    return str(texto).encode("latin-1", "replace").decode("latin-1")


def dibujar(contenido):
    """Devuelve los bytes del PDF. Sin comprimir: son documentos chicos y así
    los tests pueden buscar el texto adentro."""
    pdf = FPDF(format=(148, 210))   # A5 en mm
    pdf.set_compression(False)
    pdf.set_margins(10, 10, 10)
    pdf.set_auto_page_break(True, margin=12)
    pdf.add_page()

    # Encabezado: el comercio y el local
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(ANCHO_UTIL, 6, texto_seguro(contenido.encabezado[0]), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8)
    for linea in contenido.encabezado[1:]:
        pdf.cell(ANCHO_UTIL, 4, texto_seguro(linea), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Título, número y fecha
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(ANCHO_UTIL * 0.6, 8, texto_seguro(contenido.titulo))
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(ANCHO_UTIL * 0.4, 8, texto_seguro(f"N° {contenido.codigo}"), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(ANCHO_UTIL, 5, contenido.fecha.strftime("Fecha: %d/%m/%Y %H:%M"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # Renglones: descripción, cantidad y dos columnas que define cada documento
    # (precio e importe en el comprobante; bulto y precinto en el remito)
    anchos = (64, 14, 25, 25)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(238, 240, 243)
    for titulo, ancho, alineado in zip(contenido.columnas, anchos, ("L", "R", "R", "R")):
        pdf.cell(ancho, 6, texto_seguro(titulo), align=alineado, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    for renglon in contenido.renglones:
        pdf.cell(anchos[0], 6, texto_seguro(renglon.descripcion)[:42])
        pdf.cell(anchos[1], 6, str(renglon.cantidad), align="R")
        pdf.cell(anchos[2], 6, celda(renglon.precio_unitario), align="R")
        pdf.cell(anchos[3], 6, celda(renglon.importe), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.line(10, pdf.get_y() + 1, 10 + ANCHO_UTIL, pdf.get_y() + 1)
    pdf.ln(3)

    # Totales, alineados a la derecha; el destacado, más grande
    for total in contenido.totales:
        pdf.set_font("Helvetica", "B" if total.destacado else "", 12 if total.destacado else 9)
        alto = 8 if total.destacado else 5
        pdf.cell(ANCHO_UTIL - 35, alto, texto_seguro(total.etiqueta), align="R")
        pdf.cell(35, alto, celda(total.importe), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Notas al pie
    pdf.set_font("Helvetica", "", 8)
    for nota in contenido.notas:
        pdf.multi_cell(ANCHO_UTIL, 4, texto_seguro(nota), new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
