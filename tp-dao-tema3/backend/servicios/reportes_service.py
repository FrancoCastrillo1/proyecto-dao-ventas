# Los reportes que pide el TP (ventas por período, stock por ubicación, etc.).
# Arma los datos para mostrar, apoyándose en los DAO.
# Acá NO se modifica nada: los reportes solo leen.
#
# El DAO hace las cuentas pesadas en SQL (SUM, GROUP BY); acá se validan los
# parámetros y se arman los totales, porcentajes y tasas. Cada reporte sale
# con su "resumen": las frases que dicen lo importante (servicios/resumenes.py).
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from backend.dominio.excepciones import DatoInvalido, NoEncontrado
from backend.persistencia.dao_maestros import UbicacionDAO
from backend.persistencia.dao_reportes import PERIODOS, ReporteDAO
from backend.servicios.informes import armar_informe
from backend.servicios.informes_pdf import dibujar_informe
from backend.servicios.resumenes import resumir

CERO = Decimal("0.00")


def porcentaje(parte, total):
    if not total:
        return None
    return round(float(parte) / float(total) * 100, 2)


class ReportesService:
    def __init__(self, dao=None, ubicacion_dao=None):
        self.dao = dao or ReporteDAO()
        self.ubicacion_dao = ubicacion_dao or UbicacionDAO()

    # ------------------------------------------------------------ Parámetros

    @staticmethod
    def rango(desde, hasta):
        """De fechas (date) inclusive a textos para filtrar en SQL:
        [desde 00:00, día siguiente a hasta 00:00)."""
        if desde and hasta and desde > hasta:
            raise DatoInvalido("La fecha desde no puede ser posterior a la fecha hasta")
        inicio = datetime.combine(desde, time.min).isoformat(sep=" ") if desde else None
        fin = datetime.combine(hasta + timedelta(days=1), time.min).isoformat(sep=" ") if hasta else None
        return inicio, fin

    def validar_ubicacion(self, ubicacion_id):
        if ubicacion_id is not None and self.ubicacion_dao.obtener_por_id(ubicacion_id) is None:
            raise NoEncontrado(f"No se encontro la ubicación {ubicacion_id}")

    def describir_filtros(self, desde=None, hasta=None, ubicacion_id=None, con_fechas=True):
        """Los filtros en palabras, para el encabezado del PDF de un reporte."""
        lineas = []
        if con_fechas:
            if desde and hasta:
                lineas.append(f"Período: del {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}")
            elif desde:
                lineas.append(f"Período: desde el {desde:%d/%m/%Y}")
            elif hasta:
                lineas.append(f"Período: hasta el {hasta:%d/%m/%Y}")
            else:
                lineas.append("Período: todo")
        ubicacion = self.ubicacion_dao.obtener_por_id(ubicacion_id) if ubicacion_id is not None else None
        lineas.append(f"Ubicación: {ubicacion.nombre}" if ubicacion else "Ubicación: toda la red")
        return lineas

    def pdf(self, clave, datos, filtros, quien, **opciones):
        """El PDF de un reporte ya calculado: (nombre del archivo, bytes).
        filtros: lo que devuelve describir_filtros; quien: el que lo descarga."""
        informe = armar_informe(clave, datos, filtros, quien, **opciones)
        return informe.nombre_archivo, dibujar_informe(informe)

    @staticmethod
    def con_resumen(clave, datos):
        """Le agrega a un reporte ya calculado sus frases de resumen."""
        datos["resumen"] = resumir(clave, datos)
        return datos

    # -------------------------------------- 1. Ventas e ingresos por período
    def ventas(self, desde=None, hasta=None, sucursal_id=None, agrupar="dia"):
        if agrupar not in PERIODOS:
            raise DatoInvalido(f"Agrupación '{agrupar}' inválida. Opciones: {', '.join(PERIODOS)}")
        self.validar_ubicacion(sucursal_id)
        filas = self.dao.ventas_por_periodo(*self.rango(desde, hasta), sucursal_id, agrupar)
        por_medio = {}
        for fila in filas:
            por_medio[fila["medio_pago"]] = por_medio.get(fila["medio_pago"], CERO) + fila["neto"]
        return self.con_resumen("ventas", {
            "filas": filas,
            "por_medio_pago": por_medio,
            "cantidad_ventas": sum(f["cantidad_ventas"] for f in filas),
            "total_vendido": sum((f["vendido"] for f in filas), CERO),
            "total_devuelto": sum((f["devuelto"] for f in filas), CERO),
            "total_neto": sum((f["neto"] for f in filas), CERO),
        })

    # ------------------------------------ 2. Productos más vendidos y margen
    def productos_mas_vendidos(self, desde=None, hasta=None, sucursal_id=None, limite=10):
        if not 1 <= limite <= 100:
            raise DatoInvalido("El límite tiene que estar entre 1 y 100")
        self.validar_ubicacion(sucursal_id)
        filas = self.dao.productos_mas_vendidos(*self.rango(desde, hasta), sucursal_id, limite)
        for fila in filas:
            fila["margen"] = fila["ingreso"] - fila["costo"]  # puede ser negativo: venta a pérdida
            fila["margen_porcentaje"] = porcentaje(fila["margen"], fila["ingreso"])
        return self.con_resumen("productos-mas-vendidos", {
            "filas": filas,
            "total_ingreso": sum((f["ingreso"] for f in filas), CERO),
            "total_margen": sum((f["margen"] for f in filas), CERO),
        })

    # ------------------------- 3. Existencias, bajo mínimo y valorización
    def existencias(self, ubicacion_id=None, solo_bajo_minimo=False, hoy=None):
        """Stock de cada producto en cada ubicación: si falta para el mínimo,
        cuánto vale y hace cuántos días no sale (stock parado). Es el detalle
        de "Stock" en el tablero de productos e inventario."""
        self.validar_ubicacion(ubicacion_id)
        hoy = hoy or date.today()
        filas = self.dao.existencias(ubicacion_id)
        for fila in filas:
            fila["bajo_minimo"] = fila["cantidad"] < fila["stock_minimo"]
            fila["faltante"] = max(fila["stock_minimo"] - fila["cantidad"], 0)
            salida = fila["ultima_salida"]
            fila["dias_sin_salir"] = (hoy - datetime.fromisoformat(salida).date()).days if salida else None
        valorizado = {}
        for fila in filas:
            valorizado[fila["ubicacion"]] = valorizado.get(fila["ubicacion"], CERO) + fila["valorizado"]
        if solo_bajo_minimo:
            filas = [f for f in filas if f["bajo_minimo"]]
        return self.con_resumen("existencias", {
            "filas": filas,
            "productos_bajo_minimo": sum(1 for f in filas if f["bajo_minimo"]),
            "valorizado_por_ubicacion": valorizado,
            "valorizado_total": sum(valorizado.values(), CERO),
        })

    # ---------------------------------------- 4. Bultos rechazados y mermas
    def mermas(self, desde=None, hasta=None, sucursal_id=None):
        self.validar_ubicacion(sucursal_id)
        inicio, fin = self.rango(desde, hasta)
        filas = self.dao.bultos_rechazados(inicio, fin, sucursal_id)
        resumen = {}
        for conteo in self.dao.bultos_verificados_y_rechazados(inicio, fin, sucursal_id):
            total = conteo["verificados"] + conteo["rechazados"]
            resumen[conteo["sucursal_id"]] = {
                "sucursal_id": conteo["sucursal_id"], "sucursal": conteo["sucursal"],
                "bultos_verificados": conteo["verificados"], "bultos_rechazados": conteo["rechazados"],
                "tasa_rechazo": porcentaje(conteo["rechazados"], total),
                "unidades_perdidas": 0, "valor_perdido": CERO,
            }
        for fila in filas:
            if fila["sucursal_id"] in resumen:
                resumen[fila["sucursal_id"]]["unidades_perdidas"] += fila["cantidad"]
                resumen[fila["sucursal_id"]]["valor_perdido"] += fila["valor_perdido"]
        return self.con_resumen("mermas", {
            "filas": filas,
            "por_sucursal": list(resumen.values()),
            "valor_perdido_total": sum((f["valor_perdido"] for f in filas), CERO),
        })

    # ---------------------------------- 5. Tiempo de tránsito CD → locales
    def tiempos_transito(self, desde=None, hasta=None, sucursal_id=None):
        self.validar_ubicacion(sucursal_id)
        filas = self.dao.tiempos_transito(*self.rango(desde, hasta), sucursal_id)
        for fila in filas:
            for campo in ("horas_promedio", "horas_minimo", "horas_maximo"):
                fila[campo] = round(fila[campo], 2)
        total_bultos = sum(f["bultos"] for f in filas)
        promedio_general = (
            round(sum(f["horas_promedio"] * f["bultos"] for f in filas) / total_bultos, 2) if total_bultos else None
        )
        return self.con_resumen("tiempos-transito",
                                {"filas": filas, "bultos": total_bultos, "horas_promedio_general": promedio_general})

    # ------------------------- 6. Productos más pedidos por los locales (CD)
    def productos_mas_pedidos(self, desde=None, hasta=None, sucursal_id=None, limite=10):
        """Lo que más piden los locales: le sirve al CD para saber qué comprar.
        falta_en_cd = lo que está pedido y sin preparar menos lo que hay en el CD
        (si da positivo, con lo que hay no alcanza)."""
        if not 1 <= limite <= 100:
            raise DatoInvalido("El límite tiene que estar entre 1 y 100")
        self.validar_ubicacion(sucursal_id)
        filas = self.dao.productos_mas_pedidos(*self.rango(desde, hasta), sucursal_id, limite)
        for fila in filas:
            fila["falta_en_cd"] = max(fila["sin_preparar"] - fila["stock_cd"], 0)
        return self.con_resumen("productos-mas-pedidos", {
            "filas": filas,
            "total_unidades": sum(f["unidades"] for f in filas),
            "total_sin_preparar": sum(f["sin_preparar"] for f in filas),
            "productos_que_faltan": sum(1 for f in filas if f["falta_en_cd"] > 0),
        })

    # --------------------------------- 7. Devoluciones por producto y motivo
    def devoluciones(self, desde=None, hasta=None, sucursal_id=None):
        """Qué se devuelve, cuánto y por qué. Por producto: unidades devueltas,
        lo reintegrado, qué parte de lo vendido en el período se devolvió y el
        motivo más repetido. Por motivo: cuántas devoluciones y cuánta plata."""
        self.validar_ubicacion(sucursal_id)
        inicio, fin = self.rango(desde, hasta)
        vendidas = self.dao.unidades_vendidas_por_producto(inicio, fin, sucursal_id)
        productos = {}
        for fila in self.dao.devoluciones_por_producto_y_motivo(inicio, fin, sucursal_id):
            producto = productos.setdefault(fila["producto_id"], {
                "producto_id": fila["producto_id"], "codigo": fila["codigo"], "nombre": fila["nombre"],
                "unidades": 0, "importe": CERO, "motivos": {},
            })
            producto["unidades"] += fila["unidades"]
            producto["importe"] += fila["importe"]
            producto["motivos"][fila["motivo"]] = producto["motivos"].get(fila["motivo"], 0) + fila["unidades"]
        for producto in productos.values():
            motivos = producto.pop("motivos")
            producto["motivo_principal"] = max(motivos, key=lambda motivo: (motivos[motivo], motivo))
            producto["vendidas"] = vendidas.get(producto["producto_id"], 0)
            producto["porcentaje_devuelto"] = porcentaje(producto["unidades"], producto["vendidas"])
        filas = sorted(productos.values(), key=lambda p: (-p["unidades"], -p["importe"], p["nombre"]))
        por_motivo = self.dao.devoluciones_por_motivo(inicio, fin, sucursal_id)
        return self.con_resumen("devoluciones", {
            "filas": filas,
            "por_motivo": por_motivo,
            "cantidad_devoluciones": sum(m["devoluciones"] for m in por_motivo),
            "unidades_devueltas": sum(f["unidades"] for f in filas),
            "total_reintegrado": sum((m["importe"] for m in por_motivo), CERO),
        })
