# DAO de los tableros: dos consultas de solo lectura (lo demás lo traen los
# reportes, que son su detalle). La principal son las "líneas de venta": una fila por producto
# de cada venta, ya neta de devoluciones (como una tabla de hechos de BI). El
# service agrupa esas mismas filas por día, hora, local, categoría o producto,
# así todos los gráficos de ventas suman lo mismo.
# Acá NO se decide nada del negocio (estados, cuadrantes, variaciones).
# Montos de ventas en centavos en la base → Decimal; el costo de productos es REAL.
from backend.persistencia.conexion import BaseDeDatos
from backend.persistencia.dao_reportes import donde, filtro_fechas
from backend.persistencia.dao_ventas import desde_centavos


class TableroDAO:
    def __init__(self, db_path=None):
        self.db_path = db_path

    def consultar(self, sql, parametros):
        with BaseDeDatos.instancia().conexion(self.db_path) as cx:
            return [dict(fila) for fila in cx.execute(sql, parametros).fetchall()]

    def lineas_de_venta(self, desde=None, hasta=None, sucursal_id=None):
        """Una fila por producto de cada venta del período (según la fecha de la
        venta), con unidades, ingreso y costo NETOS de lo que se devolvió de esa
        línea. El ingreso aplica el descuento/recargo del medio de pago y el
        costo es el del momento de la venta: igual que el reporte de más vendidos."""
        condiciones, parametros = [], []
        filtro_fechas("v.fecha", desde, hasta, condiciones, parametros)
        if sucursal_id is not None:
            condiciones.append("v.sucursal_id = ?")
            parametros.append(sucursal_id)
        filas = self.consultar(
            "WITH devuelto AS ("
            "  SELECT de.venta_id, dd.producto_id, SUM(dd.cantidad) AS unidades, SUM(dd.importe) AS importe"
            "  FROM detalles_devolucion dd JOIN devoluciones de ON de.id = dd.devolucion_id"
            "  GROUP BY de.venta_id, dd.producto_id)"
            " SELECT v.id AS venta_id, v.fecha, v.sucursal_id, u.nombre AS sucursal,"
            "  p.id AS producto_id, p.codigo, p.nombre, c.nombre AS categoria,"
            "  d.cantidad - COALESCE(dv.unidades, 0) AS unidades,"
            "  ROUND(d.cantidad * d.precio_unitario * (100 + CAST(v.porcentaje_ajuste AS REAL)) / 100)"
            "    - COALESCE(dv.importe, 0) AS ingreso,"
            "  (d.cantidad - COALESCE(dv.unidades, 0)) * d.costo_unitario AS costo"
            " FROM detalles_venta d"
            " JOIN ventas v ON v.id = d.venta_id"
            " JOIN ubicaciones u ON u.id = v.sucursal_id"
            " JOIN productos p ON p.id = d.producto_id"
            " JOIN categorias c ON c.id = p.categoria_id"
            " LEFT JOIN devuelto dv ON dv.venta_id = v.id AND dv.producto_id = d.producto_id"
            f"{donde(condiciones)} ORDER BY v.fecha, v.id",
            parametros,
        )
        for fila in filas:
            fila["ingreso"] = desde_centavos(int(fila["ingreso"]))
            fila["costo"] = desde_centavos(int(fila["costo"]))
        return filas

    def pedidos(self, desde=None, hasta=None, sucursal_id=None):
        """Cada pedido de reposición del período (según su fecha) con lo que le
        pasó después: el remito que lo lleva (el de su orden y su local), cuándo
        debía llegar y cuándo se terminó de verificar el último bulto."""
        condiciones, parametros = [], []
        filtro_fechas("pr.fecha", desde, hasta, condiciones, parametros)
        if sucursal_id is not None:
            condiciones.append("pr.sucursal_id = ?")
            parametros.append(sucursal_id)
        return self.consultar(
            "SELECT pr.id AS pedido_id, pr.fecha, pr.sucursal_id, u.nombre AS sucursal, pr.estado AS estado_pedido,"
            " (SELECT SUM(d.cantidad) FROM detalles_pedido d WHERE d.pedido_id = pr.id) AS unidades,"
            " r.id AS remito_id, r.estado AS estado_remito, r.llegada_estimada,"
            " (SELECT MAX(h.fecha_hora) FROM historial_bultos h JOIN bultos b ON b.id = h.bulto_id"
            "   WHERE b.remito_id = r.id AND h.estado_nuevo IN ('VERIFICADO', 'RECHAZADO')) AS verificado"
            " FROM pedidos_reposicion pr"
            " JOIN ubicaciones u ON u.id = pr.sucursal_id"
            " LEFT JOIN remitos r ON r.orden_id = pr.orden_id AND r.destino_id = pr.sucursal_id"
            f"{donde(condiciones)} ORDER BY pr.fecha DESC, pr.id DESC",
            parametros,
        )
