# Casos de uso de recepción en el local: recibir los bultos, verificar que llegó
# lo que decía el remito y, si está ok, impactar el stock del local.
# El armado y despacho NO van acá, van en reposicion_service.py.
#
# Regla de la consigna: el stock no queda disponible en la sucursal hasta que
# "el remito y el contenedor" estén verificados. Por eso el stock se suma recién
# cuando se termina de verificar el ÚLTIMO bulto del remito, y solo el de los
# bultos verificados (habilita_venta). Los rechazados quedan como merma: su
# mercadería ya salió del CD al despachar y no entra al local.
from backend.dominio.excepciones import NoEncontrado
from backend.dominio.stock import TipoMovimiento
from backend.persistencia.dao_logistica import BultoDAO, RemitoDAO
from backend.servicios.stock_service import StockService


class RecepcionService:
    def __init__(self, bulto_dao=None, remito_dao=None, stock_service=None):
        self.bulto_dao = bulto_dao or BultoDAO()
        self.remito_dao = remito_dao or RemitoDAO()
        self.stock_service = stock_service or StockService()

    def obtener_bulto(self, bulto_id, cx=None):
        bulto = self.bulto_dao.obtener(bulto_id, cx)
        if bulto is None:
            raise NoEncontrado(f"No se encontro el bulto {bulto_id}")
        return bulto

    def recibir(self, bulto_id, usuario_id=None):
        # El State valida que el bulto esté En tránsito
        with self.bulto_dao.transaccion() as cx:
            bulto = self.obtener_bulto(bulto_id, cx)
            bulto.recibir()
            return self.bulto_dao.guardar(cx, bulto, usuario_id)

    def verificar(self, bulto_id, nro_leido, intacto, usuario_id=None):
        """Verifica el precinto del bulto. Devuelve (bulto, remito, ingreso):
        ingreso es True si con este bulto se completó el remito y se sumó el
        stock al local."""
        with self.remito_dao.transaccion() as cx:
            remito_id = self.obtener_bulto(bulto_id, cx).remito_id
            remito = self.remito_dao.obtener(remito_id, cx)
            # Se trabaja con el bulto que está DENTRO del remito, para que el
            # remito vea su nuevo estado al decidir si se completó
            bulto = next(b for b in remito.bultos if b.id_bulto == bulto_id)
            bulto.verificar(nro_leido, intacto)  # el State decide Verificado o Rechazado

            ingreso = remito.registrar_verificacion()
            if ingreso:
                for verificado in remito.bultos_verificados():
                    for detalle in verificado.items:
                        self.stock_service.ingresar(
                            remito.destino, detalle.producto, detalle.cantidad, TipoMovimiento.RECEPCION,
                            f"Remito {remito.id_remito} · Bulto {verificado.id_bulto}", cx=cx, usuario_id=usuario_id,
                        )
            self.remito_dao.guardar(cx, remito, usuario_id)
        return bulto, remito, ingreso
