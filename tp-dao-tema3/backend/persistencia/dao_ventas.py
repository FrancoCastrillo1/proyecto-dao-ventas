# DAO de ventas: guardar y consultar ventas, detalles, pagos, comprobantes y devoluciones.
# Acá NO se calculan totales ni se aplican medios de pago, eso es del dominio.
# Los métodos que reciben "cx" trabajan dentro de la transacción de quien los
# llama (ver conexion.transaccion): la venta, el stock y la caja se guardan
# juntos o nada.
from contextlib import nullcontext
from datetime import datetime
from decimal import Decimal

from backend.dominio.dinero import CENTAVO
from backend.dominio.medios_pago import crear_medio_pago
from backend.dominio.ventas import (
    Comprobante, DetalleDevolucion, DetalleVenta, Devolucion, MovimientoCaja, Pago, Venta,
)
from backend.persistencia.conexion import BaseDeDatos


# Los montos se guardan en centavos (ver esquema.sql). Un Decimal del dominio
# siempre tiene 2 decimales, así que la conversión es exacta.
def a_centavos(monto):
    return int(monto * 100)


def desde_centavos(centavos):
    return (Decimal(centavos) / 100).quantize(CENTAVO)


def a_texto(fecha):
    return fecha.isoformat(sep=" ", timespec="seconds")


class VentaDAO:
    def __init__(self, db_path=None):
        self.db_path = db_path

    def _conn(self):
        return BaseDeDatos.instancia().conexion(self.db_path)

    def transaccion(self):
        return BaseDeDatos.instancia().transaccion(self.db_path)

    # ---------------------------------------------------------------- Escritura

    def siguiente_numero_comprobante(self, cx, sucursal_id):
        # Dentro de la transacción (BEGIN IMMEDIATE) nadie más puede insertar
        # una venta entre esta consulta y el INSERT: no se repiten números
        fila = cx.execute(
            "SELECT COALESCE(MAX(nro_comprobante), 0) + 1 FROM ventas WHERE sucursal_id = ?", (sucursal_id,)
        ).fetchone()
        return fila[0]

    # Las notas de crédito se numeran aparte, también correlativas por local.
    # El local de una devolución es el de su venta.
    def siguiente_numero_nota_credito(self, cx, sucursal_id):
        fila = cx.execute(
            "SELECT COALESCE(MAX(d.nro_nota_credito), 0) + 1 FROM devoluciones d "
            "JOIN ventas v ON v.id = d.venta_id WHERE v.sucursal_id = ?", (sucursal_id,)
        ).fetchone()
        return fila[0]

    def crear(self, cx, venta, usuario_id=None):
        pago = venta.pago
        cur = cx.execute(
            "INSERT INTO ventas (sucursal_id, fecha, medio_pago, porcentaje_ajuste, subtotal, total, vuelto, "
            "nro_comprobante, usuario_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (venta.sucursal_id, a_texto(venta.fecha), pago.medio.nombre, str(pago.porcentaje_ajuste),
             a_centavos(venta.subtotal), a_centavos(pago.monto), a_centavos(pago.vuelto), venta.comprobante.numero,
             usuario_id),
        )
        venta.id = cur.lastrowid
        cx.executemany(
            "INSERT INTO detalles_venta (venta_id, producto_id, cantidad, precio_unitario, costo_unitario) "
            "VALUES (?, ?, ?, ?, ?)",
            [(venta.id, d.producto_id, d.cantidad, a_centavos(d.precio_unitario), a_centavos(d.costo_unitario))
             for d in venta.detalles],
        )
        return venta

    def crear_devolucion(self, cx, devolucion, usuario_id=None):
        cur = cx.execute(
            "INSERT INTO devoluciones (venta_id, fecha, motivo, importe, usuario_id, nro_nota_credito) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (devolucion.venta_id, a_texto(devolucion.fecha), devolucion.motivo, a_centavos(devolucion.importe),
             usuario_id, devolucion.nota_credito.numero if devolucion.nota_credito else None),
        )
        devolucion.id = cur.lastrowid
        cx.executemany(
            "INSERT INTO detalles_devolucion (devolucion_id, producto_id, cantidad, importe) VALUES (?, ?, ?, ?)",
            [(devolucion.id, d.producto_id, d.cantidad, a_centavos(d.importe)) for d in devolucion.detalles],
        )
        return devolucion

    def registrar_movimiento_caja(self, cx, movimiento):
        # Solo INSERT: la caja, como el libro de stock, no se edita
        cx.execute(
            "INSERT INTO movimientos_caja (sucursal_id, fecha, tipo, medio_pago, importe, referencia) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (movimiento.sucursal_id, a_texto(movimiento.fecha), movimiento.tipo, movimiento.medio_pago,
             a_centavos(movimiento.importe), movimiento.referencia),
        )

    # ------------------------------------------------------------------ Lectura

    def obtener(self, id, cx=None):
        """La venta completa (detalles, pago, comprobante y devoluciones) o None."""
        with nullcontext(cx) if cx else self._conn() as cx:
            fila = cx.execute("SELECT * FROM ventas WHERE id = ?", (id,)).fetchone()
            return self._a_objeto(cx, fila) if fila else None

    def listar(self, sucursal_id=None, desde=None, hasta=None):
        """desde inclusive, hasta exclusive (datetimes)."""
        condiciones, parametros = self._filtros(sucursal_id, desde, hasta)
        with self._conn() as cx:
            filas = cx.execute(f"SELECT * FROM ventas{condiciones} ORDER BY fecha, id", parametros).fetchall()
            return [self._a_objeto(cx, f) for f in filas]

    def listar_caja(self, sucursal_id, desde=None, hasta=None):
        condiciones, parametros = self._filtros(sucursal_id, desde, hasta)
        with self._conn() as cx:
            filas = cx.execute(f"SELECT * FROM movimientos_caja{condiciones} ORDER BY fecha, id", parametros).fetchall()
        return [
            MovimientoCaja(datetime.fromisoformat(f["fecha"]), f["sucursal_id"], f["tipo"], f["medio_pago"],
                           desde_centavos(f["importe"]), f["referencia"])
            for f in filas
        ]

    def _filtros(self, sucursal_id, desde, hasta):
        # Las fechas se guardan como "AAAA-MM-DD HH:MM:SS": compararlas como
        # texto da el mismo orden que compararlas como fechas
        condiciones, parametros = [], []
        if sucursal_id is not None:
            condiciones.append("sucursal_id = ?")
            parametros.append(sucursal_id)
        if desde is not None:
            condiciones.append("fecha >= ?")
            parametros.append(a_texto(desde))
        if hasta is not None:
            condiciones.append("fecha < ?")
            parametros.append(a_texto(hasta))
        return (" WHERE " + " AND ".join(condiciones) if condiciones else ""), parametros

    def _a_objeto(self, cx, fila):
        # Materializar: de las filas de 4 tablas a una Venta con todo adentro
        detalles = [
            DetalleVenta(d["producto_id"], d["cantidad"], desde_centavos(d["precio_unitario"]),
                         desde_centavos(d["costo_unitario"]))
            for d in cx.execute(
                "SELECT * FROM detalles_venta WHERE venta_id = ? ORDER BY rowid", (fila["id"],)
            ).fetchall()
        ]
        fecha = datetime.fromisoformat(fila["fecha"])
        pago = Pago(crear_medio_pago(fila["medio_pago"]), Decimal(fila["porcentaje_ajuste"]),
                    desde_centavos(fila["total"]), desde_centavos(fila["vuelto"]))
        comprobante = Comprobante(fila["sucursal_id"], fila["nro_comprobante"], fecha)
        devoluciones = [self._devolucion_a_objeto(cx, d, fila) for d in cx.execute(
            "SELECT * FROM devoluciones WHERE venta_id = ? ORDER BY id", (fila["id"],)
        ).fetchall()]
        return Venta(fila["sucursal_id"], fecha, fila["id"], detalles, pago, comprobante, devoluciones)

    def _devolucion_a_objeto(self, cx, fila, venta):
        detalles = [
            DetalleDevolucion(d["producto_id"], d["cantidad"], desde_centavos(d["importe"]))
            for d in cx.execute(
                "SELECT * FROM detalles_devolucion WHERE devolucion_id = ? ORDER BY rowid", (fila["id"],)
            ).fetchall()
        ]
        fecha = datetime.fromisoformat(fila["fecha"])
        nota_credito = (Comprobante(venta["sucursal_id"], fila["nro_nota_credito"], fecha)
                        if fila["nro_nota_credito"] else None)
        return Devolucion(fila["venta_id"], venta["sucursal_id"], venta["medio_pago"], fila["motivo"], detalles,
                          fecha, fila["id"], nota_credito)

    # Nombre de quien hizo la venta o la devolución (para el comprobante), o
    # None si se hizo antes de que hubiera usuarios
    def quien_hizo(self, tabla, id):
        if tabla not in ("ventas", "devoluciones"):
            raise ValueError(f"Tabla inesperada: {tabla}")
        with self._conn() as cx:
            fila = cx.execute(
                f"SELECT u.nombre_completo FROM {tabla} t JOIN usuarios u ON u.id = t.usuario_id WHERE t.id = ?", (id,)
            ).fetchone()
        return fila[0] if fila else None
