# Los reportes que pide el TP (ventas por período, stock por ubicación, etc.).
# Arma los datos para mostrar, apoyándose en los DAO.
# Acá NO se modifica nada: los reportes solo leen.
#
# El DAO hace las cuentas pesadas en SQL (SUM, GROUP BY); acá se validan los
# parámetros y se arman los resúmenes (totales, porcentajes, tasas).
from datetime import datetime, time, timedelta
from decimal import Decimal

from backend.dominio.excepciones import DatoInvalido, NoEncontrado
from backend.persistencia.dao_maestros import UbicacionDAO
from backend.persistencia.dao_reportes import PERIODOS, ReporteDAO

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

    # -------------------------------------- 1. Ventas e ingresos por período
    def ventas(self, desde=None, hasta=None, sucursal_id=None, agrupar="dia"):
        if agrupar not in PERIODOS:
            raise DatoInvalido(f"Agrupación '{agrupar}' inválida. Opciones: {', '.join(PERIODOS)}")
        self.validar_ubicacion(sucursal_id)
        filas = self.dao.ventas_por_periodo(*self.rango(desde, hasta), sucursal_id, agrupar)
        por_medio = {}
        for fila in filas:
            por_medio[fila["medio_pago"]] = por_medio.get(fila["medio_pago"], CERO) + fila["neto"]
        return {
            "filas": filas,
            "por_medio_pago": por_medio,
            "cantidad_ventas": sum(f["cantidad_ventas"] for f in filas),
            "total_vendido": sum((f["vendido"] for f in filas), CERO),
            "total_devuelto": sum((f["devuelto"] for f in filas), CERO),
            "total_neto": sum((f["neto"] for f in filas), CERO),
        }

    # ------------------------------------ 2. Productos más vendidos y margen
    def productos_mas_vendidos(self, desde=None, hasta=None, sucursal_id=None, limite=10):
        if not 1 <= limite <= 100:
            raise DatoInvalido("El límite tiene que estar entre 1 y 100")
        self.validar_ubicacion(sucursal_id)
        filas = self.dao.productos_mas_vendidos(*self.rango(desde, hasta), sucursal_id, limite)
        for fila in filas:
            fila["margen"] = fila["ingreso"] - fila["costo"]  # puede ser negativo: venta a pérdida
            fila["margen_porcentaje"] = porcentaje(fila["margen"], fila["ingreso"])
        return {
            "filas": filas,
            "total_ingreso": sum((f["ingreso"] for f in filas), CERO),
            "total_margen": sum((f["margen"] for f in filas), CERO),
        }

    # ------------------------- 3. Existencias, bajo mínimo y valorización
    def existencias(self, ubicacion_id=None, solo_bajo_minimo=False):
        self.validar_ubicacion(ubicacion_id)
        filas = self.dao.existencias(ubicacion_id)
        for fila in filas:
            fila["bajo_minimo"] = fila["cantidad"] < fila["stock_minimo"]
            fila["faltante"] = max(fila["stock_minimo"] - fila["cantidad"], 0)
        valorizado = {}
        for fila in filas:
            valorizado[fila["ubicacion"]] = valorizado.get(fila["ubicacion"], CERO) + fila["valorizado"]
        if solo_bajo_minimo:
            filas = [f for f in filas if f["bajo_minimo"]]
        return {
            "filas": filas,
            "productos_bajo_minimo": sum(1 for f in filas if f["bajo_minimo"]),
            "valorizado_por_ubicacion": valorizado,
            "valorizado_total": sum(valorizado.values(), CERO),
        }

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
        return {
            "filas": filas,
            "por_sucursal": list(resumen.values()),
            "valor_perdido_total": sum((f["valor_perdido"] for f in filas), CERO),
        }

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
        return {"filas": filas, "bultos": total_bultos, "horas_promedio_general": promedio_general}
