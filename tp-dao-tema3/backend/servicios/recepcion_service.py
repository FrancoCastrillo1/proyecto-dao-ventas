
# Servicio de recepción (lado del local): recibir el bulto y verificar el precinto.
# La regla de oro de la consigna se cumple en UN solo punto: el stock solo
# ingresa al local si el bulto habilita la venta (queda Verificado).
# Acá NO se repite ninguna regla del bulto: este servicio solo le pregunta al estado.
from backend.dominio.stock import TipoMovimiento
from backend.persistencia.dao_logistica import DaoLogistica
from backend.servicios.stock_service import StockService


class RecepcionService:
    def __init__(self, dao=None, stock_service=None):
        self.dao = dao or DaoLogistica()
        self.stock = stock_service or StockService()

    def recibir_bulto(self, bulto_id):
        bulto = self.dao.obtener_bulto(bulto_id)
        bulto.recibir()
        self.dao.guardar_bulto(bulto)

    def obtener_bulto(self, bulto_id):
        return self.dao.obtener_bulto(bulto_id)

    def verificar_bulto(self, bulto_id, nro_leido, intacto):
        bulto = self.dao.obtener_bulto(bulto_id)
        destino = self.dao.obtener_destino_del_bulto(bulto_id)

        # Si el bulto no está Recibido (o ya fue verificado) esto falla acá,
        # antes de tocar nada: así no se puede sumar el stock dos veces.
        bulto.verificar(nro_leido, intacto)

        # Primero el estado y después el stock: si algo fallara en el medio,
        # queda stock de menos y no de más.
        self.dao.guardar_bulto(bulto)

        if bulto.habilita_venta():
            referencia = f"Bulto {bulto.id_bulto}"
            for detalle in bulto.items:
                self.stock.ingresar_stock(
                    destino, detalle.producto, detalle.cantidad,
                    TipoMovimiento.RECEPCION, referencia,
                )
        # Si quedó Rechazado no se suma nada: es merma y no vuelve al CD
        # (decisión provisoria, a confirmar con el profe)