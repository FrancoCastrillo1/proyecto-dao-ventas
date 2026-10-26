# DAO de stock: lee y guarda la cantidad de cada producto en cada ubicación y
# el libro de movimientos. Acá NO se valida el negocio (eso lo hacen el dominio
# y el service), solo se lee y escribe en SQLite.
# Los métodos que reciben "cx" trabajan dentro de la transacción de quien los
# llama (ver conexion.transaccion), así un despacho o una venta pueden mover
# varios stocks y guardarse todo junto o nada.
from contextlib import nullcontext
from datetime import datetime

from backend.config import DB_PATH
from backend.dominio.stock import MovimientoStock, Stock, TipoMovimiento
from backend.persistencia.conexion import get_conexion, transaccion
from backend.persistencia.dao_maestros import ProductoDAO


class StockDAO:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    def _conn(self):
        return get_conexion(self.db_path)

    def transaccion(self):
        return transaccion(self.db_path)

    def obtener(self, producto_id, ubicacion_id, cx=None):
        """Arma el Stock del par producto-ubicación. Si todavía no tiene fila
        (nunca hubo movimientos) devuelve uno en 0, sin id. Si el producto no
        existe devuelve None."""
        with nullcontext(cx) if cx else self._conn() as cx:
            fila = cx.execute(
                "SELECT p.stock_minimo, s.id, s.cantidad FROM productos p "
                "LEFT JOIN stock s ON s.producto_id = p.id AND s.ubicacion_id = ? "
                "WHERE p.id = ?",
                (ubicacion_id, producto_id),
            ).fetchone()
        if fila is None:
            return None
        return Stock(producto_id, ubicacion_id, stock_minimo=fila["stock_minimo"],
                     cantidad=fila["cantidad"] or 0, id=fila["id"])

    def guardar(self, cx, stock, usuario_id=None):
        """Guarda la cantidad y agrega al libro los movimientos del objeto.
        Un Stock leído con obtener() arranca sin movimientos, así que los que
        tiene son los de esta operación: se guarda una vez por operación.
        Al libro solo se le hacen INSERT, nunca UPDATE ni DELETE.
        usuario_id es quién hizo la operación (None en las de antes de los usuarios)."""
        if stock.id is None:
            cur = cx.execute(
                "INSERT INTO stock (producto_id, ubicacion_id, cantidad) VALUES (?, ?, ?)",
                (stock.producto, stock.ubicacion, stock.cantidad),
            )
            stock.id = cur.lastrowid
        else:
            cx.execute("UPDATE stock SET cantidad = ? WHERE id = ?", (stock.cantidad, stock.id))
        cx.executemany(
            "INSERT INTO movimientos_stock (stock_id, fecha, cantidad, tipo, referencia, usuario_id) VALUES (?, ?, ?, ?, ?, ?)",
            [(stock.id, m.fecha.isoformat(sep=" ", timespec="seconds"), m.cantidad, m.tipo.value, m.referencia, usuario_id)
             for m in stock.movimientos],
        )
        return stock

    def listar_por_ubicacion(self, ubicacion_id):
        """Existencias de una ubicación: todos los productos activos (los que
        nunca tuvieron movimientos ahí aparecen en 0) y los dados de baja que
        todavía tienen algo. Devuelve pares (Producto, Stock)."""
        with self._conn() as cx:
            filas = cx.execute(
                "SELECT p.*, s.id AS stock_id, s.cantidad FROM productos p "
                "LEFT JOIN stock s ON s.producto_id = p.id AND s.ubicacion_id = ? "
                "WHERE p.activo = 1 OR s.cantidad > 0 "
                "ORDER BY p.nombre",
                (ubicacion_id,),
            ).fetchall()
        # El Producto se arma igual que en su propio DAO, para no repetir el mapeo
        a_producto = ProductoDAO(self.db_path)._a_objeto
        return [
            (a_producto(f), Stock(f["id"], ubicacion_id, stock_minimo=f["stock_minimo"],
                                  cantidad=f["cantidad"] or 0, id=f["stock_id"]))
            for f in filas
        ]

    def listar_movimientos(self, producto_id, ubicacion_id):
        with self._conn() as cx:
            filas = cx.execute(
                "SELECT m.fecha, m.cantidad, m.tipo, m.referencia FROM movimientos_stock m "
                "JOIN stock s ON s.id = m.stock_id "
                "WHERE s.producto_id = ? AND s.ubicacion_id = ? "
                "ORDER BY m.id",
                (producto_id, ubicacion_id),
            ).fetchall()
        return [
            MovimientoStock(datetime.fromisoformat(f["fecha"]), f["cantidad"], TipoMovimiento(f["tipo"]), f["referencia"])
            for f in filas
        ]
