# DAO de logística: guardar y consultar pedidos, órdenes de reposición, remitos y bultos
# (incluido el estado actual de cada bulto).
# Acá NO se hacen las transiciones de estado, eso es del dominio (estados_bulto.py).
#
# Los métodos de escritura reciben "cx": trabajan dentro de la transacción de
# quien los llama (ver conexion.transaccion). Así un despacho guarda el remito,
# los bultos, su historial y el descuento de stock todo junto o nada.
# En el dominio "producto" es el id del producto (igual que en Stock).
from contextlib import nullcontext
from datetime import datetime

from backend.dominio.estados_bulto import crear_estado
from backend.dominio.logistica import (
    Bulto, CambioEstadoBulto, DetalleBulto, DetallePedido, OrdenReposicion, PedidoReposicion, Remito,
)
from backend.persistencia.conexion import BaseDeDatos


def a_texto(fecha):
    return fecha.isoformat(sep=" ", timespec="seconds")


class DAOBase:
    def __init__(self, db_path=None):
        self.db_path = db_path

    def _conn(self, cx=None):
        # Si ya hay una transacción abierta se usa esa; si no, una conexión nueva
        return nullcontext(cx) if cx else BaseDeDatos.instancia().conexion(self.db_path)

    def transaccion(self):
        return BaseDeDatos.instancia().transaccion(self.db_path)


# --------------------------------------------------------------------- Pedidos

class PedidoDAO(DAOBase):
    def _a_objeto(self, cx, fila):
        pedido = PedidoReposicion(fila["id"], fila["sucursal_id"])
        pedido.estado = fila["estado"]
        pedido.orden_id = fila["orden_id"]
        pedido.fecha = datetime.fromisoformat(fila["fecha"])
        detalles = cx.execute(
            "SELECT producto_id, cantidad FROM detalles_pedido WHERE pedido_id = ? ORDER BY producto_id", (fila["id"],)
        ).fetchall()
        pedido.items = [DetallePedido(d["producto_id"], d["cantidad"]) for d in detalles]
        return pedido

    def crear(self, cx, pedido, usuario_id=None):
        cur = cx.execute(
            "INSERT INTO pedidos_reposicion (sucursal_id, fecha, estado, orden_id, usuario_id) VALUES (?, ?, ?, ?, ?)",
            (pedido.local, a_texto(pedido.fecha), pedido.estado, pedido.orden_id, usuario_id),
        )
        pedido.id_pedido = cur.lastrowid
        cx.executemany(
            "INSERT INTO detalles_pedido (pedido_id, producto_id, cantidad) VALUES (?, ?, ?)",
            [(pedido.id_pedido, d.producto, d.cantidad) for d in pedido.items],
        )
        return pedido

    # Lo único que cambia de un pedido guardado es su estado y la orden
    def actualizar(self, cx, pedido):
        cx.execute(
            "UPDATE pedidos_reposicion SET estado = ?, orden_id = ? WHERE id = ?",
            (pedido.estado, pedido.orden_id, pedido.id_pedido),
        )
        return pedido

    def obtener(self, id, cx=None):
        with self._conn(cx) as cx:
            fila = cx.execute("SELECT * FROM pedidos_reposicion WHERE id = ?", (id,)).fetchone()
            return self._a_objeto(cx, fila) if fila else None

    def listar(self, sucursal_id=None, estado=None, orden_id=None, cx=None):
        sql = "SELECT * FROM pedidos_reposicion WHERE 1 = 1"
        parametros = []
        for columna, valor in (("sucursal_id", sucursal_id), ("estado", estado), ("orden_id", orden_id)):
            if valor is not None:
                sql += f" AND {columna} = ?"
                parametros.append(valor)
        sql += " ORDER BY id"
        with self._conn(cx) as cx:
            return [self._a_objeto(cx, f) for f in cx.execute(sql, parametros).fetchall()]


# ------------------------------------------------------------------- Órdenes

class OrdenDAO(DAOBase):
    def __init__(self, db_path=None):
        super().__init__(db_path)
        self.pedido_dao = PedidoDAO(db_path)

    def _a_objeto(self, cx, fila):
        orden = OrdenReposicion(fila["id"], fila["origen_id"])
        orden.estado = fila["estado"]
        orden.fecha = datetime.fromisoformat(fila["fecha"])
        orden.pedidos = self.pedido_dao.listar(orden_id=fila["id"], cx=cx)
        return orden

    def crear(self, cx, orden, usuario_id=None):
        cur = cx.execute(
            "INSERT INTO ordenes_reposicion (origen_id, fecha, estado, usuario_id) VALUES (?, ?, ?, ?)",
            (orden.origen, a_texto(orden.fecha), orden.estado, usuario_id),
        )
        orden.id_orden = cur.lastrowid
        return orden

    def obtener(self, id, cx=None):
        with self._conn(cx) as cx:
            fila = cx.execute("SELECT * FROM ordenes_reposicion WHERE id = ?", (id,)).fetchone()
            return self._a_objeto(cx, fila) if fila else None

    def listar(self):
        with self._conn() as cx:
            filas = cx.execute("SELECT * FROM ordenes_reposicion ORDER BY id").fetchall()
            return [self._a_objeto(cx, f) for f in filas]


# -------------------------------------------------------------------- Bultos

class BultoDAO(DAOBase):
    def _a_objeto(self, cx, fila):
        """Vuelve a armar el Bulto tal como estaba: el estado se reconstruye
        con la fábrica del patrón State a partir del texto guardado, y el
        historial se carga entero (sin pasar por cambiar_estado, que agregaría
        registros nuevos)."""
        bulto = Bulto(fila["id"])
        bulto.remito_id = fila["remito_id"]
        bulto.nro_precinto = fila["nro_precinto"]
        bulto.estado_actual = crear_estado(fila["estado"])
        detalles = cx.execute(
            "SELECT producto_id, cantidad FROM detalles_bulto WHERE bulto_id = ? ORDER BY producto_id", (fila["id"],)
        ).fetchall()
        bulto.items = [DetalleBulto(d["producto_id"], d["cantidad"]) for d in detalles]
        historial = cx.execute(
            "SELECT * FROM historial_bultos WHERE bulto_id = ? ORDER BY id", (fila["id"],)
        ).fetchall()
        bulto.registros_historial = [
            CambioEstadoBulto(datetime.fromisoformat(h["fecha_hora"]), h["estado_anterior"], h["estado_nuevo"],
                              h["observacion"])
            for h in historial
        ]
        return bulto

    def guardar(self, cx, bulto, usuario_id=None):
        """Inserta o actualiza el bulto. Los detalles se reemplazan (solo
        cambian mientras está Preparado). Del historial se insertan solo los
        registros nuevos: los que ya estaban no se tocan (la base lo prohíbe).
        usuario_id es quién hizo el cambio de estado: lo graba el DAO y no el
        patrón State, que no sabe de usuarios."""
        if bulto.id_bulto is None:
            cur = cx.execute(
                "INSERT INTO bultos (remito_id, nro_precinto, estado) VALUES (?, ?, ?)",
                (bulto.remito_id, bulto.nro_precinto, bulto.estado),
            )
            bulto.id_bulto = cur.lastrowid
        else:
            cx.execute(
                "UPDATE bultos SET nro_precinto = ?, estado = ? WHERE id = ?",
                (bulto.nro_precinto, bulto.estado, bulto.id_bulto),
            )
            cx.execute("DELETE FROM detalles_bulto WHERE bulto_id = ?", (bulto.id_bulto,))
        cx.executemany(
            "INSERT INTO detalles_bulto (bulto_id, producto_id, cantidad) VALUES (?, ?, ?)",
            [(bulto.id_bulto, d.producto, d.cantidad) for d in bulto.items],
        )
        guardados = cx.execute(
            "SELECT COUNT(*) FROM historial_bultos WHERE bulto_id = ?", (bulto.id_bulto,)
        ).fetchone()[0]
        cx.executemany(
            "INSERT INTO historial_bultos (bulto_id, fecha_hora, estado_anterior, estado_nuevo, observacion, usuario_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(bulto.id_bulto, a_texto(r.fecha_hora), r.estado_anterior, r.estado_nuevo, r.observacion, usuario_id)
             for r in bulto.historial[guardados:]],
        )
        return bulto

    def obtener(self, id, cx=None):
        with self._conn(cx) as cx:
            fila = cx.execute("SELECT * FROM bultos WHERE id = ?", (id,)).fetchone()
            return self._a_objeto(cx, fila) if fila else None

    def listar_por_remito(self, remito_id, cx=None):
        with self._conn(cx) as cx:
            filas = cx.execute("SELECT * FROM bultos WHERE remito_id = ? ORDER BY id", (remito_id,)).fetchall()
            return [self._a_objeto(cx, f) for f in filas]

    def obtener_por_precinto(self, nro_precinto, cx=None):
        with self._conn(cx) as cx:
            fila = cx.execute("SELECT * FROM bultos WHERE nro_precinto = ?", (nro_precinto,)).fetchone()
            return self._a_objeto(cx, fila) if fila else None


# ------------------------------------------------------------------- Remitos

class RemitoDAO(DAOBase):
    def __init__(self, db_path=None):
        super().__init__(db_path)
        self.bulto_dao = BultoDAO(db_path)

    def _a_objeto(self, cx, fila):
        remito = Remito(fila["id"], fila["origen_id"], fila["destino_id"], fila["orden_id"])
        remito.estado = fila["estado"]
        remito.fecha = datetime.fromisoformat(fila["fecha"])
        if fila["llegada_estimada"]:
            remito.llegada_estimada = datetime.fromisoformat(fila["llegada_estimada"])
        remito.bultos = self.bulto_dao.listar_por_remito(fila["id"], cx)
        return remito

    def crear(self, cx, remito, usuario_id=None):
        cur = cx.execute(
            "INSERT INTO remitos (orden_id, origen_id, destino_id, fecha, estado, usuario_id) VALUES (?, ?, ?, ?, ?, ?)",
            (remito.orden_id, remito.origen, remito.destino, a_texto(remito.fecha), remito.estado, usuario_id),
        )
        remito.id_remito = cur.lastrowid
        return remito

    # Guarda el estado del remito y el de todos sus bultos
    def guardar(self, cx, remito, usuario_id=None):
        llegada = a_texto(remito.llegada_estimada) if remito.llegada_estimada else None
        cx.execute("UPDATE remitos SET estado = ?, llegada_estimada = ? WHERE id = ?",
                   (remito.estado, llegada, remito.id_remito))
        for bulto in remito.bultos:
            bulto.remito_id = remito.id_remito
            self.bulto_dao.guardar(cx, bulto, usuario_id)
        return remito

    def obtener(self, id, cx=None):
        with self._conn(cx) as cx:
            fila = cx.execute("SELECT * FROM remitos WHERE id = ?", (id,)).fetchone()
            return self._a_objeto(cx, fila) if fila else None

    # Nombre de quien armó el remito (para el documento), o None si no se sabe
    def quien_lo_armo(self, remito_id):
        with self._conn() as cx:
            fila = cx.execute(
                "SELECT u.nombre_completo FROM remitos r JOIN usuarios u ON u.id = r.usuario_id WHERE r.id = ?",
                (remito_id,),
            ).fetchone()
        return fila[0] if fila else None

    def obtener_por_orden_y_destino(self, orden_id, destino_id, cx=None):
        with self._conn(cx) as cx:
            fila = cx.execute(
                "SELECT * FROM remitos WHERE orden_id = ? AND destino_id = ?", (orden_id, destino_id)
            ).fetchone()
            return self._a_objeto(cx, fila) if fila else None

    def listar(self, destino_id=None, estado=None, orden_id=None):
        sql = "SELECT * FROM remitos WHERE 1 = 1"
        parametros = []
        for columna, valor in (("destino_id", destino_id), ("estado", estado), ("orden_id", orden_id)):
            if valor is not None:
                sql += f" AND {columna} = ?"
                parametros.append(valor)
        sql += " ORDER BY id"
        with self._conn() as cx:
            return [self._a_objeto(cx, f) for f in cx.execute(sql, parametros).fetchall()]
