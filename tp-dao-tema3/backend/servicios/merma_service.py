# Casos de uso de los bultos en merma: cuando el local rechaza un bulto
# (precinto roto o que no coincide), el bulto vuelve directo al CD como merma.
# Acá el CD revisa en qué estado llegó la mercadería y decide, por el bulto
# entero, si vuelve a su stock (REINTEGRO) o se tira (no mueve stock: ya salió
# del CD al despachar).
# Qué transiciones valen lo decide el patrón State (Rechazado → Reintegrado o
# Descartado). Acá NO va SQL (usa los DAO) ni nada de HTTP.
from backend.dominio.excepciones import NoEncontrado
from backend.dominio.stock import TipoMovimiento
from backend.persistencia.dao_logistica import BultoDAO, RemitoDAO
from backend.servicios.stock_service import StockService

EN_MERMA = "RECHAZADO"


class MermaService:
    def __init__(self, bulto_dao=None, remito_dao=None, stock_service=None):
        self.bulto_dao = bulto_dao or BultoDAO()
        self.remito_dao = remito_dao or RemitoDAO(self.bulto_dao.db_path)
        self.stock_service = stock_service or StockService()

    def listar(self):
        """Los bultos en merma que el CD todavía no revisó, cada uno con su
        remito (de qué local volvió)."""
        return [(bulto, self.remito_dao.obtener(bulto.remito_id)) for bulto in self.bulto_dao.listar_por_estado(EN_MERMA)]

    def obtener_bulto(self, bulto_id, cx=None):
        bulto = self.bulto_dao.obtener(bulto_id, cx)
        if bulto is None:
            raise NoEncontrado(f"No se encontro el bulto {bulto_id}")
        return bulto

    def reintegrar(self, bulto_id, observacion, usuario_id=None):
        """La mercadería estaba bien: todo el bulto vuelve al stock del CD que
        lo despachó, en la misma transacción que el cambio de estado."""
        with self.bulto_dao.transaccion() as cx:
            bulto = self.obtener_bulto(bulto_id, cx)
            bulto.reintegrar(observacion)   # el State valida que esté en merma
            remito = self.remito_dao.obtener(bulto.remito_id, cx)
            for detalle in bulto.items:
                self.stock_service.ingresar(
                    remito.origen, detalle.producto, detalle.cantidad, TipoMovimiento.REINTEGRO,
                    f"Merma · Remito {remito.id_remito} · Bulto {bulto.id_bulto}", cx=cx, usuario_id=usuario_id,
                )
            return self.bulto_dao.guardar(cx, bulto, usuario_id)

    def descartar(self, bulto_id, observacion, usuario_id=None):
        """La mercadería no sirve: se tira todo el bulto. Queda en el historial
        con lo que vio el CD."""
        with self.bulto_dao.transaccion() as cx:
            bulto = self.obtener_bulto(bulto_id, cx)
            bulto.descartar(observacion)
            return self.bulto_dao.guardar(cx, bulto, usuario_id)
