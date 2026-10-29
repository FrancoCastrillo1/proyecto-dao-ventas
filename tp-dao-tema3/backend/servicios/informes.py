# El contenido del PDF de cada reporte: título, filtros, tarjetas con los
# totales, un gráfico de barras y las tablas. Toma lo que ya devolvió
# ReportesService (las cuentas están hechas) y decide qué se muestra y cómo se
# escribe cada valor. Hay una función por reporte, elegida por su clave.
# Acá NO se dibuja (eso es informes_pdf.py, que dibuja cualquier informe sin
# saber cuál es) ni se consulta la base.
from dataclasses import dataclass, field
from datetime import datetime

from backend.config import COMERCIO
from backend.dominio.documentos import nombre_del_medio
from backend.servicios.documentos_pdf import pesos

MAXIMO_BARRAS = 15   # en el PDF el gráfico muestra los primeros; la tabla, todo


@dataclass(frozen=True)
class Grafico:
    titulo: str
    barras: tuple             # (nombre, valor numérico, texto del valor)


@dataclass(frozen=True)
class Tabla:
    titulo: str
    columnas: tuple           # (título, ancho relativo, "L" o "R")
    filas: tuple              # cada fila: tupla de textos, una por columna


@dataclass(frozen=True)
class Informe:
    comercio: str
    titulo: str
    pregunta: str             # lo que responde el reporte
    filtros: tuple            # renglones de texto ("Período: ...", "Ubicación: ...")
    generado: str             # cuándo y quién
    tarjetas: tuple           # (etiqueta, valor ya escrito)
    grafico: Grafico | None
    tablas: tuple
    nombre_archivo: str
    notas: tuple = field(default_factory=tuple)


# ------------------------------------------------------------ Cómo se escribe
def porcentaje(valor):
    return "-" if valor is None else f"{valor:.2f} %".replace(".", ",")


def horas(valor):
    if valor is None:
        return "-"
    return f"{round(valor * 60)} min" if valor < 1 else f"{valor:.2f} h".replace(".", ",")


def grafico(titulo, filas, nombre, valor, texto, ordenar=True):
    """Las barras de un gráfico a partir de las filas del reporte. Ordenadas
    de mayor a menor (salvo el tiempo, que va en su orden) y como mucho
    MAXIMO_BARRAS. Con menos de dos barras no hay nada que comparar: None."""
    barras = [(str(nombre(f)), float(valor(f)), texto(f)) for f in filas]
    if ordenar:
        barras.sort(key=lambda barra: -barra[1])
    return Grafico(titulo, tuple(barras[:MAXIMO_BARRAS])) if len(barras) >= 2 else None


# --------------------------------------------------------- Un armado por reporte
def informe_ventas(datos, agrupar="dia"):
    por_tiempo = agrupar != "total"
    if por_tiempo:
        netos = {}
        for f in datos["filas"]:
            netos[f["periodo"]] = netos.get(f["periodo"], 0) + f["neto"]
        barras = [{"nombre": periodo, "neto": neto} for periodo, neto in netos.items()]
        titulo_grafico = f"Ingreso neto por {'día' if agrupar == 'dia' else 'mes'}"
    else:
        barras = [{"nombre": nombre_del_medio(medio), "neto": neto} for medio, neto in datos["por_medio_pago"].items()]
        titulo_grafico = "Ingreso neto por medio de pago"
    return dict(
        titulo="Ventas", pregunta="¿Cuánto se vendió, dónde y cómo se cobró?",
        tarjetas=(("Ventas", str(datos["cantidad_ventas"])), ("Vendido", pesos(datos["total_vendido"])),
                  ("Devuelto", pesos(datos["total_devuelto"])), ("Ingreso neto", pesos(datos["total_neto"]))),
        grafico=grafico(titulo_grafico, barras, lambda b: b["nombre"], lambda b: b["neto"],
                        lambda b: pesos(b["neto"]), ordenar=not por_tiempo),
        tablas=(Tabla("Detalle", (("Período", 2, "L"), ("Local", 3, "L"), ("Medio de pago", 3, "L"), ("Ventas", 1.5, "R"),
                                  ("Vendido", 2.5, "R"), ("Devuelto", 2.5, "R"), ("Neto", 2.5, "R")),
                      tuple((f["periodo"], f["sucursal"], nombre_del_medio(f["medio_pago"]), str(f["cantidad_ventas"]),
                             pesos(f["vendido"]), pesos(f["devuelto"]), pesos(f["neto"])) for f in datos["filas"])),),
    )


def informe_mas_vendidos(datos):
    return dict(
        titulo="Productos más vendidos", pregunta="¿Qué productos se venden más y cuánto dejan?",
        tarjetas=(("Ingreso", pesos(datos["total_ingreso"])), ("Ganancia (margen)", pesos(datos["total_margen"]))),
        grafico=grafico("Unidades vendidas por producto", datos["filas"], lambda f: f["nombre"],
                        lambda f: f["unidades"], lambda f: f"{f['unidades']} u."),
        tablas=(Tabla("Ranking", (("#", 0.7, "R"), ("Producto", 5, "L"), ("Unidades", 1.8, "R"), ("Ingreso", 2.5, "R"),
                                  ("Costo", 2.5, "R"), ("Ganancia", 2.5, "R"), ("Margen", 1.8, "R")),
                      tuple((str(i), f["nombre"], str(f["unidades"]), pesos(f["ingreso"]), pesos(f["costo"]),
                             pesos(f["margen"]), porcentaje(f["margen_porcentaje"]))
                            for i, f in enumerate(datos["filas"], start=1))),),
        notas=("Unidades e ingreso netos de devoluciones. Una ganancia negativa es un producto que se vende a pérdida.",),
    )


def informe_existencias(datos):
    valorizado = datos["valorizado_por_ubicacion"]
    return dict(
        titulo="Existencias", pregunta="¿Cuánto hay, cuánto vale y qué falta reponer?",
        tarjetas=(("Productos para reponer", str(datos["productos_bajo_minimo"])),
                  ("Inventario valorizado", pesos(datos["valorizado_total"]))),
        grafico=grafico("Inventario valorizado por ubicación", list(valorizado.items()), lambda u: u[0],
                        lambda u: u[1], lambda u: pesos(u[1])),
        tablas=(Tabla("Stock por ubicación", (("Ubicación", 3, "L"), ("Producto", 5, "L"), ("Hay", 1.3, "R"),
                                              ("Mínimo", 1.5, "R"), ("Falta", 1.3, "R"), ("Valor", 2.5, "R")),
                      tuple((f["ubicacion"], f["nombre"], str(f["cantidad"]), str(f["stock_minimo"]),
                             str(f["faltante"]) if f["faltante"] else "-", pesos(f["valorizado"]))
                            for f in datos["filas"])),),
        notas=("Valorizado al costo actual de cada producto.",),
    )


def informe_mermas(datos):
    return dict(
        titulo="Mermas", pregunta="¿Cuántos bultos llegaron con el precinto roto y cuánto se perdió?",
        tarjetas=(("Bultos rechazados", str(sum(s["bultos_rechazados"] for s in datos["por_sucursal"]))),
                  ("Valor perdido", pesos(datos["valor_perdido_total"]))),
        grafico=grafico("Valor perdido por local", datos["por_sucursal"], lambda s: s["sucursal"],
                        lambda s: s["valor_perdido"], lambda s: pesos(s["valor_perdido"])),
        tablas=(
            Tabla("Por local", (("Local", 4, "L"), ("Verificados", 2, "R"), ("Rechazados", 2, "R"), ("% rechazo", 2, "R"),
                                ("Unidades perdidas", 2.5, "R"), ("Valor perdido", 2.5, "R")),
                  tuple((s["sucursal"], str(s["bultos_verificados"]), str(s["bultos_rechazados"]),
                         porcentaje(s["tasa_rechazo"]), str(s["unidades_perdidas"]), pesos(s["valor_perdido"]))
                        for s in datos["por_sucursal"])),
            Tabla("Qué se perdió", (("Fecha", 2.2, "L"), ("Local", 3, "L"), ("Bulto", 1.3, "R"), ("Producto", 4, "L"),
                                    ("Cant.", 1.2, "R"), ("Valor", 2.2, "R"), ("Motivo", 3.5, "L")),
                  tuple((f["fecha_rechazo"][:16], f["sucursal"], f"#{f['bulto_id']}", f["nombre"], str(f["cantidad"]),
                         pesos(f["valor_perdido"]), f["observacion"] or "") for f in datos["filas"])),
        ),
    )


def informe_tiempos_transito(datos):
    return dict(
        titulo="Tiempos de envío", pregunta="¿Cuánto tarda un bulto del CD a cada local?",
        tarjetas=(("Bultos recibidos", str(datos["bultos"])), ("Promedio general", horas(datos["horas_promedio_general"]))),
        grafico=grafico("Tiempo promedio del CD a cada local", datos["filas"], lambda f: f["sucursal"],
                        lambda f: f["horas_promedio"], lambda f: horas(f["horas_promedio"])),
        tablas=(Tabla("Por local", (("Local", 4, "L"), ("Bultos", 1.5, "R"), ("Promedio", 2, "R"),
                                    ("Más rápido", 2, "R"), ("Más lento", 2, "R")),
                      tuple((f["sucursal"], str(f["bultos"]), horas(f["horas_promedio"]), horas(f["horas_minimo"]),
                             horas(f["horas_maximo"])) for f in datos["filas"])),),
        notas=("Desde que el bulto sale del CD hasta que el local lo marca como recibido, según el historial del bulto.",),
    )


def informe_mas_pedidos(datos):
    return dict(
        titulo="Productos más pedidos", pregunta="¿Qué piden más los locales y alcanza lo que hay en el CD?",
        tarjetas=(("Unidades pedidas", str(datos["total_unidades"])), ("Sin preparar", str(datos["total_sin_preparar"])),
                  ("Productos que faltan en el CD", str(datos["productos_que_faltan"]))),
        grafico=grafico("Unidades pedidas por producto", datos["filas"], lambda f: f["nombre"],
                        lambda f: f["unidades"], lambda f: f"{f['unidades']} u."),
        tablas=(Tabla("Ranking", (("#", 0.7, "R"), ("Producto", 5, "L"), ("Pedidas", 1.6, "R"), ("Pedidos", 1.6, "R"),
                                  ("Locales", 1.6, "R"), ("Sin preparar", 2, "R"), ("En el CD", 1.8, "R"),
                                  ("Falta", 1.4, "R")),
                      tuple((str(i), f["nombre"], str(f["unidades"]), str(f["pedidos"]), str(f["locales"]),
                             str(f["sin_preparar"]), str(f["stock_cd"]), str(f["falta_en_cd"]) if f["falta_en_cd"] else "-")
                            for i, f in enumerate(datos["filas"], start=1))),),
        notas=("Falta: lo pedido que todavía no se preparó y no alcanza con lo que hay hoy en el CD.",),
    )


def informe_devoluciones(datos):
    return dict(
        titulo="Devoluciones", pregunta="¿Qué se devuelve, cuánto y por qué?",
        tarjetas=(("Devoluciones", str(datos["cantidad_devoluciones"])),
                  ("Unidades devueltas", str(datos["unidades_devueltas"])),
                  ("Reintegrado", pesos(datos["total_reintegrado"]))),
        grafico=grafico("Unidades devueltas por producto", datos["filas"], lambda f: f["nombre"],
                        lambda f: f["unidades"], lambda f: f"{f['unidades']} u."),
        tablas=(
            Tabla("Por producto", (("Producto", 5, "L"), ("Devueltas", 1.8, "R"), ("Vendidas", 1.8, "R"),
                                   ("% devuelto", 2, "R"), ("Reintegrado", 2.5, "R"), ("Motivo principal", 3.5, "L")),
                  tuple((f["nombre"], str(f["unidades"]), str(f["vendidas"]), porcentaje(f["porcentaje_devuelto"]),
                         pesos(f["importe"]), f["motivo_principal"]) for f in datos["filas"])),
            Tabla("Por motivo", (("Motivo", 6, "L"), ("Devoluciones", 2, "R"), ("Reintegrado", 2.5, "R")),
                  tuple((m["motivo"], str(m["devoluciones"]), pesos(m["importe"])) for m in datos["por_motivo"])),
        ),
        notas=("Las devoluciones se cuentan en el período en que se hicieron; lo vendido, en el de la venta.",),
    )


ARMADOS = {
    "ventas": informe_ventas,
    "productos-mas-vendidos": informe_mas_vendidos,
    "existencias": informe_existencias,
    "mermas": informe_mermas,
    "tiempos-transito": informe_tiempos_transito,
    "productos-mas-pedidos": informe_mas_pedidos,
    "devoluciones": informe_devoluciones,
}


def armar_informe(clave, datos, filtros, quien, ahora=None, **opciones):
    """El Informe de un reporte. opciones: lo que cambia la forma (ej: agrupar
    en ventas). quien: el nombre de quien lo pide, para el pie."""
    ahora = ahora or datetime.now()
    partes = ARMADOS[clave](datos, **opciones)
    return Informe(
        comercio=COMERCIO["razon_social"],
        filtros=tuple(filtros),
        generado=f"Generado el {ahora:%d/%m/%Y %H:%M} por {quien}",
        nombre_archivo=f"reporte-{clave}-{ahora:%Y%m%d-%H%M}.pdf",
        **partes,
    )
