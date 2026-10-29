# Los cuatro tableros de la pantalla Reportes: Ejecutivo, Ventas del local,
# Productos e inventario, y Abastecimiento. Cada uno junta indicadores con su
# comparación y los datos de sus gráficos, ya calculados; cada gráfico tiene
# un "Ver detalle" que abre uno de los 7 reportes (ReportesService).
# Los gráficos de ventas salen de las MISMAS líneas de venta (una consulta),
# agrupadas acá de distintas formas: así los números cierran entre sí. Lo que
# ya calcula un reporte (más vendidos, existencias, devoluciones, mermas, más
# pedidos) se le pide a ReportesService, no se vuelve a calcular.
# El período y las cuentas de los indicadores son del dominio (Periodo,
# variacion, margen...).
# Acá NO se decide quién ve qué (eso lo controla la api con las capacidades)
# ni se dibuja nada.
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from statistics import median

from backend.dominio.excepciones import NoEncontrado
from backend.dominio.periodo import Periodo, diferencia, margen, proporcion, variacion
from backend.persistencia.dao_maestros import UbicacionDAO
from backend.persistencia.dao_tableros import TableroDAO
from backend.servicios.informes import armar_informe
from backend.servicios.informes_pdf import dibujar_informe
from backend.servicios.informes_tableros import ARMADOS_TABLEROS
from backend.servicios.reportes_service import ReportesService

CERO = Decimal("0.00")
EN_EL_TABLERO = 8          # cuántos productos o motivos entran en un gráfico del tablero (el resto, en el detalle)
DIAS_DE_LA_SEMANA = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
HORAS_POR_FRANJA = 2
FRANJA_INICIAL, FRANJA_FINAL = 8, 22          # el mapa de calor muestra al menos de 8 a 22
DIAS_POR_PUNTO_DIARIO = 62                    # hasta 62 días, la evolución va por día; si no, por semana

# Antigüedad de la última salida: (hasta cuántos días, nombre del tramo)
TRAMOS_SIN_MOVIMIENTO = [(30, "0 a 30 días"), (60, "31 a 60 días"), (90, "61 a 90 días"), (None, "Más de 90 días")]
SIN_SALIDAS = "Nunca salió"

# Cómo se ve un pedido según lo que le pasó (en el orden en que avanza)
ESTADOS_PEDIDO = ["Pendiente", "En preparación", "En camino", "Recibido", "Recibido con rechazos"]


# ------------------------------------------------------------ Cuentas sueltas

def totales(lineas):
    """Lo que suman unas líneas de venta: ventas, costo, ganancia, margen,
    unidades y tickets (ventas distintas)."""
    ventas = sum((l["ingreso"] for l in lineas), CERO)
    costo = sum((l["costo"] for l in lineas), CERO)
    tickets = len({l["venta_id"] for l in lineas})
    unidades = sum(l["unidades"] for l in lineas)
    return {
        "ventas": ventas, "costo": costo, "ganancia": ventas - costo, "margen": margen(ventas - costo, ventas),
        "unidades": unidades, "tickets": tickets,
        "ticket_promedio": (ventas / tickets).quantize(CERO) if tickets else None,
        "articulos_por_ticket": round(unidades / tickets, 1) if tickets else None,
    }


def indicador(titulo, tipo, actual, anterior, en_puntos=False):
    """Una tarjeta: el valor, el del período comparado y cuánto cambió (en % o,
    para porcentajes como el margen, en puntos). tipo: cómo se muestra
    (pesos, numero, porcentaje)."""
    cambio = diferencia(actual, anterior) if en_puntos else (
        None if actual is None else variacion(actual, anterior))
    return {"titulo": titulo, "tipo": tipo, "valor": actual, "anterior": anterior,
            "cambio": cambio, "en_puntos": en_puntos}


def agrupar_por(lineas, clave):
    """{valor de la clave: [líneas]} respetando el orden en que aparecen."""
    grupos = {}
    for linea in lineas:
        grupos.setdefault(clave(linea), []).append(linea)
    return grupos


def fecha_de(linea):
    return datetime.fromisoformat(linea["fecha"])


def horas_entre(desde, hasta):
    return round((datetime.fromisoformat(hasta) - datetime.fromisoformat(desde)).total_seconds() / 3600, 2)


def estado_del_pedido(pedido):
    """Dónde está un pedido: sin consolidar, armándose en el CD, viajando o
    recibido (con o sin bultos rechazados)."""
    if pedido["estado_pedido"] == "PENDIENTE":
        return "Pendiente"
    remito = pedido["estado_remito"]
    if remito == "EN_TRANSITO":
        return "En camino"
    if remito == "VERIFICADO":
        return "Recibido"
    if remito == "VERIFICADO_CON_RECHAZOS":
        return "Recibido con rechazos"
    return "En preparación"          # consolidado: el remito todavía no salió (o ni se armó)


def tramo_de(dias):
    if dias is None:
        return SIN_SALIDAS
    return next(nombre for limite, nombre in TRAMOS_SIN_MOVIMIENTO if limite is None or dias <= limite)


def cuadrante(unidades, margen_producto, corte_unidades, corte_margen):
    """Matriz volumen × margen: de qué lado de los dos cortes cae un producto."""
    vende_mucho = unidades >= corte_unidades
    deja_mucho = margen_producto is not None and margen_producto >= corte_margen
    if vende_mucho and deja_mucho:
        return "Estrellas"
    if vende_mucho:
        return "Mucho volumen, poco margen"
    if deja_mucho:
        return "Buen margen, poca venta"
    return "A revisar"


class TablerosService:
    def __init__(self, dao=None, ubicacion_dao=None, reportes=None):
        self.dao = dao or TableroDAO()
        self.ubicacion_dao = ubicacion_dao or UbicacionDAO()
        self.reportes = reportes or ReportesService(ubicacion_dao=self.ubicacion_dao)

    # ------------------------------------------------------------------- PDF
    def describir_filtros(self, datos, ubicacion_id=None):
        """Los filtros en palabras, para el encabezado del PDF de un tablero."""
        periodo = datos["periodo"]
        lineas = [f"Período: del {periodo['desde']:%d/%m/%Y} al {periodo['hasta']:%d/%m/%Y} ({periodo['dias']} días)"]
        if periodo.get("comparar"):
            lineas.append(f"Comparado con: del {periodo['comparado_desde']:%d/%m/%Y} al {periodo['comparado_hasta']:%d/%m/%Y}")
        ubicacion = self.ubicacion_dao.obtener_por_id(ubicacion_id) if ubicacion_id is not None else None
        lineas.append(f"Ubicación: {ubicacion.nombre}" if ubicacion else "Ubicación: toda la red")
        return lineas

    def pdf(self, clave, datos, quien, ubicacion_id=None):
        """El PDF de un tablero ya calculado, con todos sus gráficos:
        (nombre del archivo, bytes)."""
        informe = armar_informe(f"tablero-{clave}", datos, self.describir_filtros(datos, ubicacion_id), quien,
                                armados=ARMADOS_TABLEROS)
        return informe.nombre_archivo, dibujar_informe(informe)

    # ------------------------------------------------------------ Parámetros
    def validar_ubicacion(self, ubicacion_id):
        if ubicacion_id is not None and self.ubicacion_dao.obtener_por_id(ubicacion_id) is None:
            raise NoEncontrado(f"No se encontro la ubicación {ubicacion_id}")

    @staticmethod
    def rango(periodo):
        """Del período (fechas inclusive) a textos para filtrar en SQL."""
        return (datetime.combine(periodo.desde, time.min).isoformat(sep=" "),
                datetime.combine(periodo.hasta + timedelta(days=1), time.min).isoformat(sep=" "))

    @staticmethod
    def describir(periodo, comparado=None, como=None):
        datos = {"desde": periodo.desde, "hasta": periodo.hasta, "dias": periodo.dias}
        if comparado:
            datos.update(comparado_desde=comparado.desde, comparado_hasta=comparado.hasta, comparar=como)
        return datos

    def lineas(self, periodo, sucursal_id):
        return self.dao.lineas_de_venta(*self.rango(periodo), sucursal_id)

    # ------------------------------------------- Gráficos que comparten tableros
    @staticmethod
    def evolucion(lineas, lineas_antes, periodo, comparado):
        """Ventas punto a punto del período y, al lado, las del período con que se
        compara (el día 1 con el día 1, el 2 con el 2...). Hasta 62 días va por
        día; si no, por semana (7 días desde el inicio)."""
        tamano = 1 if periodo.dias <= DIAS_POR_PUNTO_DIARIO else 7
        cantidad = -(-periodo.dias // tamano)    # división hacia arriba

        def sumar(filas, desde):
            montos = [CERO] * cantidad
            for linea in filas:
                indice = (fecha_de(linea).date() - desde).days // tamano
                if 0 <= indice < cantidad:
                    montos[indice] += linea["ingreso"]
            return montos

        actuales, anteriores = sumar(lineas, periodo.desde), sumar(lineas_antes, comparado.desde)
        puntos = []
        for i in range(cantidad):
            dia = periodo.dia(i * tamano)
            puntos.append({"etiqueta": f"{dia:%d/%m}" if tamano == 1 else f"sem. {dia:%d/%m}", "fecha": dia,
                           "actual": actuales[i], "anterior": anteriores[i]})
        return {"agrupado": "dia" if tamano == 1 else "semana", "puntos": puntos}

    @staticmethod
    def por_categoria(lineas):
        total = sum((l["ingreso"] for l in lineas), CERO)
        filas = []
        for categoria, grupo in agrupar_por(lineas, lambda l: l["categoria"]).items():
            suma = totales(grupo)
            filas.append({"categoria": categoria, "ventas": suma["ventas"], "ganancia": suma["ganancia"],
                          "margen": suma["margen"], "unidades": suma["unidades"],
                          "participacion": proporcion(suma["ventas"], total)})
        return sorted(filas, key=lambda f: -f["ventas"])

    # ------------------------------------------------------- 1. Ejecutivo (admin)
    def ejecutivo(self, desde=None, hasta=None, comparar="anterior", sucursal_id=None):
        """Toda la empresa (o un local): cuánto se vendió y ganó contra el
        período comparado, cómo evolucionó, qué local y qué categoría aportan más."""
        self.validar_ubicacion(sucursal_id)
        periodo = Periodo.elegido(desde, hasta)
        comparado = periodo.comparado(comparar)
        lineas, lineas_antes = self.lineas(periodo, sucursal_id), self.lineas(comparado, sucursal_id)
        ahora, antes = totales(lineas), totales(lineas_antes)

        total_ventas = ahora["ventas"]
        locales = []
        for (sucursal_id_local, nombre), grupo in agrupar_por(lineas, lambda l: (l["sucursal_id"], l["sucursal"])).items():
            suma = totales(grupo)
            locales.append({"sucursal_id": sucursal_id_local, "sucursal": nombre, "ventas": suma["ventas"],
                            "ganancia": suma["ganancia"], "margen": suma["margen"], "tickets": suma["tickets"],
                            "participacion": proporcion(suma["ventas"], total_ventas)})
        return {
            "periodo": self.describir(periodo, comparado, comparar),
            "indicadores": [
                indicador("Ventas netas", "pesos", ahora["ventas"], antes["ventas"]),
                indicador("Ganancia bruta", "pesos", ahora["ganancia"], antes["ganancia"]),
                indicador("Margen bruto", "porcentaje", ahora["margen"], antes["margen"], en_puntos=True),
                indicador("Tickets", "numero", ahora["tickets"], antes["tickets"]),
            ],
            "evolucion": self.evolucion(lineas, lineas_antes, periodo, comparado),
            "locales": sorted(locales, key=lambda l: -l["ventas"]),
            "categorias": self.por_categoria(lineas),
        }

    # ------------------------------------------- 2. Ventas del local (admin y local)
    def ventas_local(self, desde=None, hasta=None, comparar="anterior", sucursal_id=None):
        """Cómo vende un local (o todos): tickets, ticket promedio, cuándo se
        vende más (día y hora), qué categorías y qué se devuelve. El ranking de
        productos está en el tablero de productos (no se repite acá)."""
        self.validar_ubicacion(sucursal_id)
        periodo = Periodo.elegido(desde, hasta)
        comparado = periodo.comparado(comparar)
        lineas, lineas_antes = self.lineas(periodo, sucursal_id), self.lineas(comparado, sucursal_id)
        ahora, antes = totales(lineas), totales(lineas_antes)

        por_dia = agrupar_por(lineas, lambda l: fecha_de(l).date())
        dias = []
        for i in range(periodo.dias):
            dia = periodo.dia(i)
            suma = totales(por_dia.get(dia, []))
            dias.append({"fecha": dia, "etiqueta": f"{dia:%d/%m}", "ventas": suma["ventas"],
                         "unidades": suma["unidades"], "tickets": suma["tickets"],
                         "ticket_promedio": suma["ticket_promedio"]})

        devoluciones = self.reportes.devoluciones(periodo.desde, periodo.hasta, sucursal_id)
        return {
            "periodo": self.describir(periodo, comparado, comparar),
            "indicadores": [
                indicador("Ventas netas", "pesos", ahora["ventas"], antes["ventas"]),
                indicador("Tickets", "numero", ahora["tickets"], antes["tickets"]),
                indicador("Ticket promedio", "pesos", ahora["ticket_promedio"], antes["ticket_promedio"]),
                indicador("Unidades vendidas", "numero", ahora["unidades"], antes["unidades"]),
                indicador("Artículos por ticket", "decimal", ahora["articulos_por_ticket"], antes["articulos_por_ticket"]),
            ],
            "por_dia": dias,
            "mapa_calor": self.mapa_calor(lineas),
            "categorias": self.por_categoria(lineas),
            "devoluciones": {
                "cantidad": devoluciones["cantidad_devoluciones"], "unidades": devoluciones["unidades_devueltas"],
                "reintegrado": devoluciones["total_reintegrado"], "productos": devoluciones["filas"][:EN_EL_TABLERO],
            },
        }

    @staticmethod
    def mapa_calor(lineas):
        """Ventas por día de la semana (columnas) y franja horaria de 2 horas
        (filas). Muestra de 8 a 22, y más si hubo ventas fuera de ese horario."""
        ventas, tickets = {}, {}
        for venta_id, grupo in agrupar_por(lineas, lambda l: l["venta_id"]).items():
            momento = fecha_de(grupo[0])
            celda = (momento.hour // HORAS_POR_FRANJA, momento.weekday())
            ventas[celda] = ventas.get(celda, CERO) + sum((l["ingreso"] for l in grupo), CERO)
            tickets[celda] = tickets.get(celda, 0) + 1
        franjas_con_ventas = [franja for franja, _ in ventas]
        primera = min([FRANJA_INICIAL // HORAS_POR_FRANJA, *franjas_con_ventas])
        ultima = max([FRANJA_FINAL // HORAS_POR_FRANJA - 1, *franjas_con_ventas])
        filas = []
        for franja in range(primera, ultima + 1):
            inicio = franja * HORAS_POR_FRANJA
            filas.append({"franja": f"{inicio:02d} a {inicio + HORAS_POR_FRANJA:02d} h",
                          "ventas": [ventas.get((franja, dia), CERO) for dia in range(7)],
                          "tickets": [tickets.get((franja, dia), 0) for dia in range(7)]})
        return {"dias": DIAS_DE_LA_SEMANA, "filas": filas, "maximo": max(ventas.values(), default=CERO)}

    # ---------------------------------- 3 y 4. Productos e inventario (todos)
    def productos(self, desde=None, hasta=None, ubicacion_id=None, con_rentabilidad=True, hoy=None):
        """Productos: el ranking de los más vendidos (con margen) y la matriz
        volumen × margen, si quien mira ve ventas. Stock (todos): qué falta
        reponer y cuánto está parado según su última salida; las dos cosas
        salen del reporte de existencias, que es su detalle.
        con_rentabilidad: lo decide la api según la capacidad ve_ventas."""
        self.validar_ubicacion(ubicacion_id)
        periodo = Periodo.elegido(desde, hasta)
        hoy = hoy or date.today()
        respuesta = {"periodo": self.describir(periodo), "matriz": None, "ranking": None}
        indicadores = []
        if con_rentabilidad:
            lineas = self.lineas(periodo, ubicacion_id)
            suma = totales(lineas)
            respuesta["matriz"] = self.matriz(lineas)
            respuesta["ranking"] = self.reportes.productos_mas_vendidos(
                periodo.desde, periodo.hasta, ubicacion_id, limite=EN_EL_TABLERO + 2)["filas"]
            indicadores += [
                indicador("Productos con ventas", "numero", len(respuesta["matriz"]["puntos"]), None),
                indicador("Ganancia bruta", "pesos", suma["ganancia"], None),
                indicador("Margen bruto", "porcentaje", suma["margen"], None, en_puntos=True),
            ]
        existencias = self.reportes.existencias(ubicacion_id, hoy=hoy)
        con_stock = [f for f in existencias["filas"] if f["cantidad"] > 0]
        parado = self.sin_movimiento(con_stock, hoy)
        mas_de_30 = [t for t in parado["tramos"] if t["tramo"] != TRAMOS_SIN_MOVIMIENTO[0][1]]
        para_reponer = sorted((f for f in existencias["filas"] if f["bajo_minimo"]),
                              key=lambda f: (-f["faltante"], f["nombre"]))
        respuesta["stock"] = {"tramos": parado["tramos"], "para_reponer": para_reponer[:EN_EL_TABLERO]}
        indicadores += [
            indicador("Inventario valorizado", "pesos", existencias["valorizado_total"], None),
            indicador("Productos para reponer", "numero", existencias["productos_bajo_minimo"], None),
            indicador("Valor parado (más de 30 días)", "pesos", sum((t["valor"] for t in mas_de_30), CERO), None),
        ]
        respuesta["indicadores"] = indicadores
        return respuesta

    @staticmethod
    def matriz(lineas):
        """Cada producto vendido como un punto: unidades (x), margen % (y) y
        ganancia (tamaño). Los cortes son la mediana de unidades y el margen de
        todo lo vendido: separan los cuatro cuadrantes."""
        puntos = []
        for (producto_id, codigo, nombre), grupo in agrupar_por(
                lineas, lambda l: (l["producto_id"], l["codigo"], l["nombre"])).items():
            suma = totales(grupo)
            if suma["unidades"] <= 0:
                continue            # todo lo vendido se devolvió: no hay margen que mirar
            puntos.append({"producto_id": producto_id, "codigo": codigo, "nombre": nombre, "unidades": suma["unidades"],
                           "ventas": suma["ventas"], "ganancia": suma["ganancia"], "margen": suma["margen"]})
        corte_unidades = median([p["unidades"] for p in puntos]) if puntos else 0
        corte_margen = totales(lineas)["margen"] or 0
        for punto in puntos:
            punto["cuadrante"] = cuadrante(punto["unidades"], punto["margen"], corte_unidades, corte_margen)
        return {"puntos": sorted(puntos, key=lambda p: -p["ganancia"]),
                "corte_unidades": corte_unidades, "corte_margen": corte_margen}

    @staticmethod
    def sin_movimiento(filas, hoy):
        """Cuánto stock lleva tiempo sin salir, por tramo de antigüedad de su
        última salida, y la lista de lo más viejo primero."""
        tramos = {nombre: {"tramo": nombre, "productos": 0, "unidades": 0, "valor": CERO}
                  for nombre in [n for _, n in TRAMOS_SIN_MOVIMIENTO] + [SIN_SALIDAS]}
        for fila in filas:
            salida = fila["ultima_salida"]
            fila["dias"] = (hoy - datetime.fromisoformat(salida).date()).days if salida else None
            fila["tramo"] = tramo_de(fila["dias"])
            tramo = tramos[fila["tramo"]]
            tramo["productos"] += 1
            tramo["unidades"] += fila["cantidad"]
            tramo["valor"] += fila["valorizado"]
        # Primero lo que nunca salió, después lo que hace más tiempo que no sale
        filas.sort(key=lambda f: (f["dias"] is not None, -(f["dias"] or 0), -f["valorizado"]))
        return {"tramos": list(tramos.values()), "filas": filas}

    # ------------------------------------------------ 5. Abastecimiento (todos)
    def abastecimiento(self, desde=None, hasta=None, sucursal_id=None, con_demanda=False):
        """Los pedidos de reposición del período: en qué estado está cada uno,
        cuánto tardó cada local desde que pidió hasta que terminó de verificar
        (recién ahí la mercadería se puede vender) y cuánto se perdió en bultos
        rechazados. con_demanda: lo más pedido de toda la red (CD y
        administrador; lo decide la api según ve_toda_la_red)."""
        self.validar_ubicacion(sucursal_id)
        periodo = Periodo.elegido(desde, hasta)
        pedidos = self.dao.pedidos(*self.rango(periodo), sucursal_id)
        for pedido in pedidos:
            pedido["estado"] = estado_del_pedido(pedido)
            recibido = pedido["estado"].startswith("Recibido") and pedido["verificado"]
            pedido["horas"] = horas_entre(pedido["fecha"], pedido["verificado"]) if recibido else None

        por_estado, tiempos = [], []
        for (sucursal_id_local, nombre), grupo in agrupar_por(pedidos, lambda p: (p["sucursal_id"], p["sucursal"])).items():
            cuenta = {estado: sum(1 for p in grupo if p["estado"] == estado) for estado in ESTADOS_PEDIDO}
            por_estado.append({"sucursal_id": sucursal_id_local, "sucursal": nombre, **cuenta})
            horas = [p["horas"] for p in grupo if p["horas"] is not None]
            if horas:
                tiempos.append({"sucursal_id": sucursal_id_local, "sucursal": nombre, "pedidos": len(horas),
                                "horas_promedio": round(sum(horas) / len(horas), 2),
                                "horas_minimo": min(horas), "horas_maximo": max(horas)})
        todas = [p["horas"] for p in pedidos if p["horas"] is not None]

        def cuantos(*estados):
            return sum(1 for p in pedidos if p["estado"] in estados)

        mermas = self.reportes.mermas(periodo.desde, periodo.hasta, sucursal_id)
        demanda = (self.reportes.productos_mas_pedidos(periodo.desde, periodo.hasta, sucursal_id,
                                                       limite=EN_EL_TABLERO)["filas"] if con_demanda else None)
        return {
            "periodo": self.describir(periodo),
            "indicadores": [
                indicador("Pedidos", "numero", len(pedidos), None),
                indicador("Sin preparar", "numero", cuantos("Pendiente"), None),
                indicador("En preparación o en camino", "numero", cuantos("En preparación", "En camino"), None),
                indicador("Reposición promedio", "horas", round(sum(todas) / len(todas), 2) if todas else None, None),
                indicador("Perdido en bultos rechazados", "pesos", mermas["valor_perdido_total"], None),
            ],
            "estados": ESTADOS_PEDIDO,
            "por_estado": sorted(por_estado, key=lambda f: f["sucursal"]),
            "tiempos": sorted(tiempos, key=lambda f: -f["horas_promedio"]),
            "mermas": mermas["por_sucursal"],
            "demanda": demanda,
            "pedidos": pedidos,
        }
