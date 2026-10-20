# DAO de logística: guarda y lee bultos, pedidos, órdenes y remitos. El estado
# se guarda como texto y al leer se reconstruye el objeto. El historial del
# bulto solo se inserta, nunca se modifica ni se borra (la base además lo
# refuerza con triggers).
# Acá NO van reglas de negocio ni movimientos de stock: eso es del servicio.
import sqlite3
from datetime import datetime

from backend.config import DB_PATH
from backend.dominio.excepciones import DatoInvalido, NoEncontrado
from backend.dominio.logistica import (
    Bulto, CambioEstadoBulto, DetalleBulto, DetallePedido,
    OrdenReposicion, PedidoReposicion, Remito,
)
from backend.persistencia.conexion import get_conexion


class DaoLogistica:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    # ---------- bultos ----------

    def guardar_bulto(self, bulto):
        cx = get_conexion(self.db_path)
        try:
            # "with cx" es una sola transacción: o se guarda todo o no se guarda nada
            with cx:
                if bulto.id_bulto is None:
                    bulto_id = cx.execute(
                        "INSERT INTO bultos (estado, nro_precinto) VALUES (?, ?)",
                        (bulto.estado, bulto.nro_precinto),
                    ).lastrowid
                else:
                    bulto_id = bulto.id_bulto
                    actualizadas = cx.execute(
                        "UPDATE bultos SET estado = ?, nro_precinto = ? WHERE id = ?",
                        (bulto.estado, bulto.nro_precinto, bulto_id),
                    ).rowcount
                    if actualizadas == 0:
                        raise NoEncontrado(f"El bulto {bulto_id} no existe")

                # Las líneas se reemplazan por las actuales
                cx.execute("DELETE FROM detalles_bulto WHERE bulto_id = ?", (bulto_id,))
                cx.executemany(
                    "INSERT INTO detalles_bulto (bulto_id, producto_id, cantidad) VALUES (?, ?, ?)",
                    [(bulto_id, d.producto, d.cantidad) for d in bulto.items],
                )

                # El historial solo se inserta: se agregan los registros que
                # todavía no están guardados (el de la base siempre es un
                # prefijo del que tiene el bulto)
                guardados = cx.execute(
                    "SELECT COUNT(*) FROM historial_bulto WHERE bulto_id = ?", (bulto_id,)
                ).fetchone()[0]
                for cambio in bulto.historial[guardados:]:
                    cx.execute(
                        "INSERT INTO historial_bulto "
                        "(bulto_id, fecha_hora, estado_anterior, estado_nuevo, observacion) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (bulto_id, cambio.fecha_hora.isoformat(sep=" "),
                         cambio.estado_anterior, cambio.estado_nuevo, cambio.observacion),
                    )
            bulto.id_bulto = bulto_id
            return bulto_id
        finally:
            cx.close()

    def obtener_bulto(self, bulto_id):
        cx = get_conexion(self.db_path)
        try:
            return self._leer_bulto(cx, bulto_id)
        finally:
            cx.close()

    @staticmethod
    def _leer_bulto(cx, bulto_id):
        fila = cx.execute(
            "SELECT id, estado, nro_precinto FROM bultos WHERE id = ?", (bulto_id,)
        ).fetchone()
        if fila is None:
            raise NoEncontrado(f"El bulto {bulto_id} no existe")
        items = [
            DetalleBulto(f["producto_id"], f["cantidad"])
            for f in cx.execute(
                "SELECT producto_id, cantidad FROM detalles_bulto WHERE bulto_id = ? ORDER BY id",
                (bulto_id,),
            )
        ]
        historial = tuple(
            CambioEstadoBulto(
                datetime.fromisoformat(f["fecha_hora"]),
                f["estado_anterior"], f["estado_nuevo"], f["observacion"],
            )
            for f in cx.execute(
                "SELECT fecha_hora, estado_anterior, estado_nuevo, observacion "
                "FROM historial_bulto WHERE bulto_id = ? ORDER BY id",
                (bulto_id,),
            )
        )
        return Bulto.reconstruir(fila["id"], fila["estado"], fila["nro_precinto"], items, historial)

    # ---------- pedidos ----------

    def guardar_pedido(self, pedido):
        # pedido.local tiene que ser el id de la ubicación (sucursal) que pide
        cx = get_conexion(self.db_path)
        try:
            with cx:
                if pedido.id_pedido is None:
                    pedido_id = cx.execute(
                        "INSERT INTO pedidos_reposicion (ubicacion_id, estado) VALUES (?, ?)",
                        (pedido.local, pedido.estado),
                    ).lastrowid
                else:
                    pedido_id = pedido.id_pedido
                    actualizadas = cx.execute(
                        "UPDATE pedidos_reposicion SET ubicacion_id = ?, estado = ? WHERE id = ?",
                        (pedido.local, pedido.estado, pedido_id),
                    ).rowcount
                    if actualizadas == 0:
                        raise NoEncontrado(f"El pedido {pedido_id} no existe")
                cx.execute("DELETE FROM detalles_pedido WHERE pedido_id = ?", (pedido_id,))
                cx.executemany(
                    "INSERT INTO detalles_pedido (pedido_id, producto_id, cantidad) VALUES (?, ?, ?)",
                    [(pedido_id, d.producto, d.cantidad) for d in pedido.items],
                )
            pedido.id_pedido = pedido_id
            return pedido_id
        finally:
            cx.close()

    def obtener_pedido(self, pedido_id):
        cx = get_conexion(self.db_path)
        try:
            return self._leer_pedido(cx, pedido_id)
        finally:
            cx.close()

    @staticmethod
    def _leer_pedido(cx, pedido_id):
        fila = cx.execute(
            "SELECT id, ubicacion_id, estado FROM pedidos_reposicion WHERE id = ?", (pedido_id,)
        ).fetchone()
        if fila is None:
            raise NoEncontrado(f"El pedido {pedido_id} no existe")
        items = [
            DetallePedido(f["producto_id"], f["cantidad"])
            for f in cx.execute(
                "SELECT producto_id, cantidad FROM detalles_pedido WHERE pedido_id = ? ORDER BY id",
                (pedido_id,),
            )
        ]
        return PedidoReposicion.reconstruir(fila["id"], fila["ubicacion_id"], fila["estado"], items)

    # ---------- órdenes ----------

    def guardar_orden(self, orden):
        if any(pedido.id_pedido is None for pedido in orden.pedidos):
            raise DatoInvalido("Hay que guardar los pedidos antes de guardar la orden")
        cx = get_conexion(self.db_path)
        try:
            with cx:
                if orden.id_orden is None:
                    orden_id = cx.execute(
                        "INSERT INTO ordenes_reposicion (origen_id, estado) VALUES (?, ?)",
                        (orden.origen, orden.estado),
                    ).lastrowid
                else:
                    orden_id = orden.id_orden
                    actualizadas = cx.execute(
                        "UPDATE ordenes_reposicion SET origen_id = ?, estado = ? WHERE id = ?",
                        (orden.origen, orden.estado, orden_id),
                    ).rowcount
                    if actualizadas == 0:
                        raise NoEncontrado(f"La orden {orden_id} no existe")
                cx.execute("DELETE FROM orden_pedido WHERE orden_id = ?", (orden_id,))
                for pedido in orden.pedidos:
                    try:
                        cx.execute(
                            "INSERT INTO orden_pedido (orden_id, pedido_id) VALUES (?, ?)",
                            (orden_id, pedido.id_pedido),
                        )
                    except sqlite3.IntegrityError:
                        # pedido_id es clave primaria: un pedido va en UNA sola orden.
                        # Al salir con error, "with cx" deshace también la orden.
                        raise DatoInvalido(
                            f"El pedido {pedido.id_pedido} ya está en otra orden o no existe"
                        )
            orden.id_orden = orden_id
            return orden_id
        finally:
            cx.close()

    def obtener_orden(self, orden_id):
        cx = get_conexion(self.db_path)
        try:
            fila = cx.execute(
                "SELECT id, origen_id, estado FROM ordenes_reposicion WHERE id = ?", (orden_id,)
            ).fetchone()
            if fila is None:
                raise NoEncontrado(f"La orden {orden_id} no existe")
            pedidos = [
                self._leer_pedido(cx, f["pedido_id"])
                for f in cx.execute(
                    "SELECT pedido_id FROM orden_pedido WHERE orden_id = ? ORDER BY pedido_id",
                    (orden_id,),
                ).fetchall()
            ]
            return OrdenReposicion.reconstruir(fila["id"], fila["origen_id"], fila["estado"], pedidos)
        finally:
            cx.close()

    # ---------- remitos ----------

    def guardar_remito(self, remito):
        # Los bultos se guardan antes (guardar_bulto); acá solo se los asigna al remito
        if any(bulto.id_bulto is None for bulto in remito.bultos):
            raise DatoInvalido("Hay que guardar los bultos antes de guardar el remito")
        cx = get_conexion(self.db_path)
        try:
            with cx:
                if remito.id_remito is None:
                    remito_id = cx.execute(
                        "INSERT INTO remitos (origen_id, destino_id, estado) VALUES (?, ?, ?)",
                        (remito.origen, remito.destino, remito.estado),
                    ).lastrowid
                else:
                    remito_id = remito.id_remito
                    actualizadas = cx.execute(
                        "UPDATE remitos SET origen_id = ?, destino_id = ?, estado = ? WHERE id = ?",
                        (remito.origen, remito.destino, remito.estado, remito_id),
                    ).rowcount
                    if actualizadas == 0:
                        raise NoEncontrado(f"El remito {remito_id} no existe")
                for bulto in remito.bultos:
                    cx.execute("UPDATE bultos SET remito_id = ? WHERE id = ?", (remito_id, bulto.id_bulto))
            remito.id_remito = remito_id
            return remito_id
        finally:
            cx.close()

    def obtener_remito(self, remito_id):
        cx = get_conexion(self.db_path)
        try:
            fila = cx.execute(
                "SELECT id, origen_id, destino_id, estado FROM remitos WHERE id = ?", (remito_id,)
            ).fetchone()
            if fila is None:
                raise NoEncontrado(f"El remito {remito_id} no existe")
            bultos = [
                self._leer_bulto(cx, f["id"])
                for f in cx.execute(
                    "SELECT id FROM bultos WHERE remito_id = ? ORDER BY id", (remito_id,)
                ).fetchall()
            ]
            return Remito.reconstruir(
                fila["id"], fila["origen_id"], fila["destino_id"], fila["estado"], bultos
            )
        finally:
            cx.close()
    def obtener_destino_del_bulto(self, bulto_id):
        """Id de la ubicación a la que viaja el bulto (el destino de su remito)."""
        cx = get_conexion(self.db_path)
        try:
            fila = cx.execute(
                "SELECT r.destino_id FROM bultos b JOIN remitos r ON b.remito_id = r.id WHERE b.id = ?",
                (bulto_id,),
            ).fetchone()
            if fila is None:
                raise NoEncontrado(f"El bulto {bulto_id} no existe o no está en ningún remito")
            return fila["destino_id"]
        finally:
            cx.close()