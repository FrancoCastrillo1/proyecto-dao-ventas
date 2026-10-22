# Casos de uso de ventas en el local: registrar una venta, cobrarla (con el medio
# de pago que corresponda), emitir comprobante, hacer devoluciones y mover el stock.
# Acá NO va SQL directo ni lógica de endpoints.
from datetime import datetime, time, timedelta

from backend.dominio.dinero import CERO
from backend.dominio.excepciones import DatoInvalido, NoEncontrado, PagoInsuficiente, StockInsuficiente
from backend.dominio.medios_pago import MEDIOS_PAGO, crear_medio_pago
from backend.dominio.stock import TipoMovimiento, validar_ubicacion_para
from backend.dominio.ventas import Venta
from backend.persistencia.dao_maestros import ProductoDAO, UbicacionDAO
from backend.persistencia.dao_ventas import VentaDAO
from backend.servicios.stock_service import StockService


class VentasService:
    def __init__(self, dao=None, stock_service=None, producto_dao=None, ubicacion_dao=None):
        self.dao = dao or VentaDAO()
        self.stock_service = stock_service or StockService()
        self.producto_dao = producto_dao or ProductoDAO()
        self.ubicacion_dao = ubicacion_dao or UbicacionDAO()

    def medios_pago(self):
        return [clase() for clase in MEDIOS_PAGO.values()]

    def obtener_ubicacion(self, ubicacion_id):
        ubicacion = self.ubicacion_dao.obtener_por_id(ubicacion_id)
        if ubicacion is None:
            raise NoEncontrado(f"No se encontro la ubicación {ubicacion_id}")
        return ubicacion

    def obtener_producto(self, producto_id):
        producto = self.producto_dao.obtener_por_id(producto_id)
        if producto is None:
            raise NoEncontrado(f"No se encontro el producto {producto_id}")
        return producto

    def obtener(self, venta_id):
        venta = self.dao.obtener(venta_id)
        if venta is None:
            raise NoEncontrado(f"No se encontro la venta {venta_id}")
        return venta

    def armar_venta(self, sucursal_id, items, medio_pago):
        """Arma la venta en memoria con todas las reglas del dominio, sin
        cobrarla ni guardarla. La usan vender() y cotizar(), así las dos
        calculan exactamente igual. Devuelve (venta, medio, nombres)."""
        # Solo se vende en una sucursal activa: la misma regla que usa el stock
        validar_ubicacion_para(TipoMovimiento.VENTA, self.obtener_ubicacion(sucursal_id))
        medio = crear_medio_pago(medio_pago)
        venta = Venta(sucursal_id)
        nombres = {}
        for producto_id, cantidad in items:
            producto = self.obtener_producto(producto_id)
            nombres[producto.id] = producto.nombre
            venta.agregar_item(producto, cantidad)
        return venta, medio, nombres

    def cotizar(self, sucursal_id, items, medio_pago, monto_entregado=None):
        """Lo que costaría la venta, para mostrarlo ANTES de confirmar: mismo
        cálculo que vender() (Strategy del medio de pago), pero sin guardar
        nada ni mover stock ni caja. Si el monto entregado no alcanza no falla:
        devuelve alcanza_pago=False, porque el cajero puede estar tipeándolo.
        Devuelve (venta cobrada, {producto_id: disponible en el local}, alcanza_pago)."""
        venta, medio, _ = self.armar_venta(sucursal_id, items, medio_pago)
        alcanza_pago = True
        try:
            venta.cobrar(medio, monto_entregado)
        except PagoInsuficiente:
            # El dominio no llegó a cobrar: se cotiza sin el monto entregado
            alcanza_pago = False
            venta.cobrar(medio)
        disponible = {
            d.producto_id: self.stock_service.obtener(sucursal_id, d.producto_id).cantidad for d in venta.detalles
        }
        return venta, disponible, alcanza_pago

    def vender(self, sucursal_id, items, medio_pago, monto_entregado=None):
        """items: pares (producto_id, cantidad). Primero se arma y se cobra la
        venta en memoria (el dominio valida todo); recién después se abre la
        transacción que guarda la venta, descuenta el stock y registra la caja.
        Si un producto no alcanza, no se guarda nada."""
        venta, medio, nombres = self.armar_venta(sucursal_id, items, medio_pago)
        venta.cobrar(medio, monto_entregado)

        with self.dao.transaccion() as cx:
            venta.emitir_comprobante(self.dao.siguiente_numero_comprobante(cx, sucursal_id))
            self.dao.crear(cx, venta)
            for detalle in venta.detalles:
                try:
                    self.stock_service.egresar(sucursal_id, detalle.producto_id, detalle.cantidad,
                                               TipoMovimiento.VENTA, venta.referencia(), cx=cx)
                except StockInsuficiente as error:
                    # En una venta con varios productos hay que decir cuál no alcanza
                    raise StockInsuficiente(f"{nombres[detalle.producto_id]}: {error}") from error
            self.dao.registrar_movimiento_caja(cx, venta.movimiento_caja())
        return venta

    def devolver(self, venta_id, items, motivo):
        """items: pares (producto_id, cantidad). Reingresa el stock al local de
        la venta y saca de la caja lo que se reintegra, todo junto o nada."""
        with self.dao.transaccion() as cx:
            # La venta se lee DENTRO de la transacción: así dos devoluciones al
            # mismo tiempo no pueden pasarse entre las dos de lo vendido
            venta = self.dao.obtener(venta_id, cx)
            if venta is None:
                raise NoEncontrado(f"La venta {venta_id} no está registrada: no se puede devolver")
            devolucion = venta.devolver(items, motivo)
            self.dao.crear_devolucion(cx, devolucion)
            for detalle in devolucion.detalles:
                self.stock_service.ingresar(venta.sucursal_id, detalle.producto_id, detalle.cantidad,
                                            TipoMovimiento.DEVOLUCION,
                                            f"Devolución {devolucion.id} de {venta.referencia()}", cx=cx)
            self.dao.registrar_movimiento_caja(cx, devolucion.movimiento_caja())
        return devolucion

    def listar(self, sucursal_id=None, desde=None, hasta=None):
        """desde y hasta son fechas (date), las dos inclusive."""
        if sucursal_id is not None:
            self.obtener_ubicacion(sucursal_id)
        return self.dao.listar(sucursal_id, *self._rango(desde, hasta))

    def caja(self, sucursal_id, desde=None, hasta=None):
        """Los movimientos de caja del local y el total por medio de pago."""
        self.obtener_ubicacion(sucursal_id)
        movimientos = self.dao.listar_caja(sucursal_id, *self._rango(desde, hasta))
        por_medio = {}
        for movimiento in movimientos:
            por_medio[movimiento.medio_pago] = por_medio.get(movimiento.medio_pago, CERO) + movimiento.importe
        return movimientos, por_medio

    @staticmethod
    def _rango(desde, hasta):
        # De fechas inclusive a [desde 00:00, día siguiente a hasta 00:00), que
        # es como filtra el DAO: así "hasta el 5" incluye todo el día 5
        if desde and hasta and desde > hasta:
            raise DatoInvalido("La fecha desde no puede ser posterior a la fecha hasta")
        inicio = datetime.combine(desde, time.min) if desde else None
        fin = datetime.combine(hasta + timedelta(days=1), time.min) if hasta else None
        return inicio, fin
