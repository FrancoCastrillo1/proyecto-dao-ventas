# DAO de logística: guardar y consultar pedidos, órdenes de reposición, remitos y bultos
# (incluido el estado actual de cada bulto).
# Acá NO se hacen las transiciones de estado, eso es del dominio (estados_bulto.py).
# DAO de logística: guarda y lee bultos. El estado se guarda como texto y al
# leer se reconstruye el objeto State. El historial solo se inserta, nunca se
# modifica ni se borra (la base además lo refuerza con triggers).
# Acá NO van reglas de negocio ni movimientos de stock: eso es del servicio.
from datetime import datetime

from backend.config import DB_PATH
from backend.dominio.excepciones import NoEncontrado
from backend.dominio.logistica import Bulto, CambioEstadoBulto, DetalleBulto
from backend.persistencia.conexion import get_conexion


class DaoLogistica:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

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
                # todavía no están guardados (el historial de la base siempre
                # es un prefijo del del bulto)
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
        finally:
            cx.close()