# Servicio de reposición (lado del CD): pedido, orden, remito y despacho.
# Combina el dominio, el DAO de logística y el servicio de stock.
# Principio: se valida TODO en memoria antes de tocar la base, y ante la duda
# se prefiere que falte stock y no que sobre (nunca vender lo que no existe).
# Acá NO van reglas propias de cada pieza (eso es del dominio) ni SQL (del DAO).
from backend.dominio.excepciones import DatoInvalido, StockInsuficiente
from backend.dominio.logistica import Bulto, OrdenReposicion, PedidoReposicion, Remito
from backend.dominio.stock import TipoMovimiento
from backend.persistencia.dao_logistica import DaoLogistica
from backend.servicios.stock_service import StockService


class ReposicionService:
    def __init__(self, dao=None, stock_service=None):
        self.dao = dao or DaoLogistica()
        self.stock = stock_service or StockService()

    def crear_pedido(self, local_id, items):
        """items: lista de (producto_id, cantidad)."""
        pedido = PedidoReposicion(None, local_id)
        for producto, cantidad in items:
            pedido.agregar_item(producto, cantidad)
        return self.dao.guardar_pedido(pedido)

    def consolidar_pedido(self, pedido_id):
        pedido = self.dao.obtener_pedido(pedido_id)
        pedido.consolidar()
        self.dao.guardar_pedido(pedido)

    def crear_orden(self, origen_id, pedido_ids):
        if len(set(pedido_ids)) != len(pedido_ids):
            raise DatoInvalido("Hay pedidos repetidos en la orden")
        orden = OrdenReposicion(None, origen_id)
        for pedido_id in pedido_ids:
            orden.agregar_pedido(self.dao.obtener_pedido(pedido_id))  # solo consolidados
        orden.cerrar()
        # Si algún pedido ya está en otra orden, el DAO lo rechaza y no guarda nada
        return self.dao.guardar_orden(orden)

    def armar_remito(self, origen_id, destino_id, bultos):
        """bultos: lista de {"precinto": str, "items": [(producto_id, cantidad), ...]}."""
        remito = Remito(None, origen_id, destino_id)
        armados = []
        for datos in bultos:
            bulto = Bulto(None)
            for producto, cantidad in datos["items"]:
                bulto.agregar_item(producto, cantidad)
            bulto.precintar(datos["precinto"])
            remito.agregar_bulto(bulto)
            armados.append(bulto)
        remito.cerrar()
        # Recién acá, con todo validado, se guarda: un remito inválido no deja bultos huérfanos
        for bulto in armados:
            self.dao.guardar_bulto(bulto)
        return self.dao.guardar_remito(remito)

    def despachar_remito(self, remito_id):
        remito = self.dao.obtener_remito(remito_id)
        if remito.estado != Remito.CERRADO:
            raise DatoInvalido("Solo se puede despachar un remito cerrado")

        # 1) Validar en memoria: cada bulto tiene que poder despacharse. Esto
        #    también frena un segundo despacho del mismo remito.
        for bulto in remito.bultos:
            bulto.despachar()

        # 2) Validar el stock del CD contra el TOTAL del remito, no bulto por bulto
        for producto, total in remito.total_por_producto().items():
            disponible = self.stock.obtener_stock_ubicacion(remito.origen, producto)["cantidad"]
            if disponible < total:
                raise StockInsuficiente(
                    f"Producto {producto}: hay {disponible} en el origen y el remito lleva {total}"
                )

        # 3) Recién ahora se toca la base. Primero el stock y después el estado:
        #    si algo fallara en el medio, queda stock de menos y no de más.
        for bulto in remito.bultos:
            referencia = f"Remito {remito.id_remito}, bulto {bulto.id_bulto}"
            for detalle in bulto.items:
                self.stock.egresar_stock(
                    remito.origen, detalle.producto, detalle.cantidad,
                    TipoMovimiento.DESPACHO, referencia,
                )
            self.dao.guardar_bulto(bulto)