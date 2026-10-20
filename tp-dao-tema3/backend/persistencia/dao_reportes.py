# DAO de reportes: consultas agregadas (SUM, GROUP BY) de solo lectura sobre
# ventas, caja, stock y logística. Devuelve filas simples (diccionarios): un
# reporte es una vista de los datos, no una entidad del dominio.
# Acá NO se modifica nada ni se decide nada del negocio.
# Los montos de ventas y caja están en centavos en la base (ver dao_ventas) y
# se devuelven como Decimal; el costo de los productos es REAL.
from decimal import Decimal

from backend.config import DB_PATH
from backend.persistencia.conexion import get_conexion
from backend.persistencia.dao_ventas import desde_centavos

# Agrupaciones de período permitidas. Se arma el SQL con estas expresiones
# fijas (nunca con texto que venga de afuera).
PERIODOS = {
    "dia": "substr({col}, 1, 10)",
    "mes": "substr({col}, 1, 7)",
    "total": "'total'",
}


def filtro_fechas(columna, desde, hasta, condiciones, parametros):
    # desde/hasta: textos 'YYYY-MM-DD HH:MM:SS' (hasta excluido)
    if desde:
        condiciones.append(f"{columna} >= ?")
        parametros.append(desde)
    if hasta:
        condiciones.append(f"{columna} < ?")
        parametros.append(hasta)


def donde(condiciones):
    return (" WHERE " + " AND ".join(condiciones)) if condiciones else ""


def a_dinero(valor):
    return Decimal(str(round(valor or 0, 2))).quantize(Decimal("0.01"))


class ReporteDAO:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    def _consultar(self, sql, parametros):
        with get_conexion(self.db_path) as cx:
            return [dict(fila) for fila in cx.execute(sql, parametros).fetchall()]

    # ------------------------------------------- 1. Ventas e ingresos por período
    def ventas_por_periodo(self, desde=None, hasta=None, sucursal_id=None, agrupar="dia"):
        """Sale de la caja: cada venta suma y cada devolución resta, por
        período, local y medio de pago."""
        periodo = PERIODOS[agrupar].format(col="mc.fecha")
        condiciones, parametros = [], []
        filtro_fechas("mc.fecha", desde, hasta, condiciones, parametros)
        if sucursal_id is not None:
            condiciones.append("mc.sucursal_id = ?")
            parametros.append(sucursal_id)
        filas = self._consultar(
            f"SELECT {periodo} AS periodo, mc.sucursal_id, u.nombre AS sucursal, mc.medio_pago, "
            "SUM(CASE WHEN mc.tipo = 'VENTA' THEN 1 ELSE 0 END) AS cantidad_ventas, "
            "SUM(CASE WHEN mc.tipo = 'VENTA' THEN mc.importe ELSE 0 END) AS vendido, "
            "-SUM(CASE WHEN mc.tipo = 'DEVOLUCION' THEN mc.importe ELSE 0 END) AS devuelto, "
            "SUM(mc.importe) AS neto "
            "FROM movimientos_caja mc JOIN ubicaciones u ON u.id = mc.sucursal_id"
            f"{donde(condiciones)} "
            "GROUP BY periodo, mc.sucursal_id, mc.medio_pago "
            "ORDER BY periodo, u.nombre, mc.medio_pago",
            parametros,
        )
        for fila in filas:
            for campo in ("vendido", "devuelto", "neto"):
                fila[campo] = desde_centavos(fila[campo])
        return filas

    # ------------------------------------ 2. Productos más vendidos y margen
    def productos_mas_vendidos(self, desde=None, hasta=None, sucursal_id=None, limite=10):
        """Unidades, ingreso y costo NETOS de devoluciones, con el precio y el
        costo del momento de la venta. El ingreso de cada línea aplica el
        descuento/recargo del medio de pago. Las devoluciones se cuentan en el
        período de la venta a la que pertenecen."""
        condiciones, parametros = [], []
        filtro_fechas("v.fecha", desde, hasta, condiciones, parametros)
        if sucursal_id is not None:
            condiciones.append("v.sucursal_id = ?")
            parametros.append(sucursal_id)
        filtro = donde(condiciones)
        filas = self._consultar(
            "WITH vendidos AS ("
            "  SELECT d.producto_id, SUM(d.cantidad) AS unidades,"
            "    SUM(ROUND(d.cantidad * d.precio_unitario * (100 + CAST(v.porcentaje_ajuste AS REAL)) / 100)) AS ingreso,"
            "    SUM(d.cantidad * d.costo_unitario) AS costo"
            f"  FROM detalles_venta d JOIN ventas v ON v.id = d.venta_id{filtro}"
            "  GROUP BY d.producto_id),"
            " devueltos AS ("
            "  SELECT dd.producto_id, SUM(dd.cantidad) AS unidades, SUM(dd.importe) AS importe,"
            "    SUM(dd.cantidad * dv.costo_unitario) AS costo"
            "  FROM detalles_devolucion dd"
            "  JOIN devoluciones de ON de.id = dd.devolucion_id"
            "  JOIN ventas v ON v.id = de.venta_id"
            "  JOIN detalles_venta dv ON dv.venta_id = v.id AND dv.producto_id = dd.producto_id"
            f"  {filtro}"
            "  GROUP BY dd.producto_id)"
            " SELECT p.id AS producto_id, p.codigo, p.nombre,"
            "  vd.unidades - COALESCE(dv.unidades, 0) AS unidades,"
            "  vd.ingreso - COALESCE(dv.importe, 0) AS ingreso,"
            "  vd.costo - COALESCE(dv.costo, 0) AS costo"
            " FROM vendidos vd JOIN productos p ON p.id = vd.producto_id"
            " LEFT JOIN devueltos dv ON dv.producto_id = vd.producto_id"
            " ORDER BY unidades DESC, ingreso DESC LIMIT ?",
            parametros + parametros + [limite],
        )
        for fila in filas:
            fila["ingreso"] = desde_centavos(int(fila["ingreso"]))
            fila["costo"] = desde_centavos(int(fila["costo"]))
        return filas

    # ------------------------ 3. Existencias, bajo mínimo y valorización
    def existencias(self, ubicacion_id=None):
        """Cada producto en cada ubicación activa, aunque nunca haya tenido
        movimientos (aparece en 0: puede estar bajo mínimo)."""
        condiciones = ["u.activo = 1", "(p.activo = 1 OR COALESCE(s.cantidad, 0) > 0)"]
        parametros = []
        if ubicacion_id is not None:
            condiciones.append("u.id = ?")
            parametros.append(ubicacion_id)
        filas = self._consultar(
            "SELECT u.id AS ubicacion_id, u.nombre AS ubicacion, u.tipo, p.id AS producto_id, p.codigo, "
            "p.nombre, COALESCE(s.cantidad, 0) AS cantidad, p.stock_minimo, p.costo "
            "FROM ubicaciones u CROSS JOIN productos p "
            "LEFT JOIN stock s ON s.producto_id = p.id AND s.ubicacion_id = u.id"
            f"{donde(condiciones)} "
            "ORDER BY u.tipo, u.nombre, p.nombre",
            parametros,
        )
        for fila in filas:
            fila["valorizado"] = a_dinero(fila["cantidad"] * fila["costo"])
            fila["costo"] = a_dinero(fila["costo"])
        return filas

    # ----------------------------------- 4. Bultos rechazados y mermas
    def bultos_rechazados(self, desde=None, hasta=None, sucursal_id=None):
        """Una fila por producto de cada bulto rechazado (merma), con la fecha
        y el motivo del rechazo tomados del historial."""
        condiciones, parametros = ["b.estado = 'RECHAZADO'"], []
        filtro_fechas("h.fecha_hora", desde, hasta, condiciones, parametros)
        if sucursal_id is not None:
            condiciones.append("r.destino_id = ?")
            parametros.append(sucursal_id)
        filas = self._consultar(
            "SELECT b.id AS bulto_id, b.nro_precinto, r.id AS remito_id, r.destino_id AS sucursal_id, "
            "u.nombre AS sucursal, h.fecha_hora AS fecha_rechazo, h.observacion, "
            "db.producto_id, p.codigo, p.nombre, db.cantidad, p.costo "
            "FROM bultos b "
            "JOIN remitos r ON r.id = b.remito_id "
            "JOIN ubicaciones u ON u.id = r.destino_id "
            "JOIN historial_bultos h ON h.bulto_id = b.id AND h.estado_nuevo = 'RECHAZADO' "
            "JOIN detalles_bulto db ON db.bulto_id = b.id "
            "JOIN productos p ON p.id = db.producto_id"
            f"{donde(condiciones)} "
            "ORDER BY h.fecha_hora, b.id, p.nombre",
            parametros,
        )
        for fila in filas:
            fila["valor_perdido"] = a_dinero(fila["cantidad"] * fila["costo"])
            fila["costo"] = a_dinero(fila["costo"])
        return filas

    def bultos_verificados_y_rechazados(self, desde=None, hasta=None, sucursal_id=None):
        """Por sucursal: cuántos bultos terminaron verificados y cuántos rechazados."""
        condiciones, parametros = ["h.estado_nuevo IN ('VERIFICADO', 'RECHAZADO')"], []
        filtro_fechas("h.fecha_hora", desde, hasta, condiciones, parametros)
        if sucursal_id is not None:
            condiciones.append("r.destino_id = ?")
            parametros.append(sucursal_id)
        return self._consultar(
            "SELECT r.destino_id AS sucursal_id, u.nombre AS sucursal, "
            "SUM(h.estado_nuevo = 'VERIFICADO') AS verificados, SUM(h.estado_nuevo = 'RECHAZADO') AS rechazados "
            "FROM historial_bultos h "
            "JOIN bultos b ON b.id = h.bulto_id "
            "JOIN remitos r ON r.id = b.remito_id "
            "JOIN ubicaciones u ON u.id = r.destino_id"
            f"{donde(condiciones)} "
            "GROUP BY r.destino_id ORDER BY u.nombre",
            parametros,
        )

    # ------------------------------ 5. Tiempo de tránsito CD → locales
    def tiempos_transito(self, desde=None, hasta=None, sucursal_id=None):
        """Horas entre que el bulto sale del CD (EN_TRANSITO) y llega al local
        (RECIBIDO), según el historial, promediadas por sucursal destino."""
        condiciones, parametros = [], []
        filtro_fechas("sale.fecha_hora", desde, hasta, condiciones, parametros)
        if sucursal_id is not None:
            condiciones.append("r.destino_id = ?")
            parametros.append(sucursal_id)
        return self._consultar(
            "SELECT r.destino_id AS sucursal_id, u.nombre AS sucursal, COUNT(*) AS bultos, "
            "AVG((julianday(llega.fecha_hora) - julianday(sale.fecha_hora)) * 24) AS horas_promedio, "
            "MIN((julianday(llega.fecha_hora) - julianday(sale.fecha_hora)) * 24) AS horas_minimo, "
            "MAX((julianday(llega.fecha_hora) - julianday(sale.fecha_hora)) * 24) AS horas_maximo "
            "FROM bultos b "
            "JOIN remitos r ON r.id = b.remito_id "
            "JOIN ubicaciones u ON u.id = r.destino_id "
            "JOIN historial_bultos sale ON sale.bulto_id = b.id AND sale.estado_nuevo = 'EN_TRANSITO' "
            "JOIN historial_bultos llega ON llega.bulto_id = b.id AND llega.estado_nuevo = 'RECIBIDO'"
            f"{donde(condiciones)} "
            "GROUP BY r.destino_id ORDER BY u.nombre",
            parametros,
        )
