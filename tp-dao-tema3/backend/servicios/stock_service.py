# Casos de uso del stock: consultar existencias e ingresar/egresar mercadería.
# Lo usan la api (compras al CD) y los otros services (despacho, recepción,
# venta y devolución), que le pasan su conexión para que todo quede en una
# sola transacción. Acá NO va SQL (usa dao_stock) ni nada de endpoints.
from backend.dominio.excepciones import DatoInvalido, NoEncontrado
from backend.dominio.stock import TipoMovimiento, validar_ubicacion_para
from backend.persistencia.dao_maestros import ProductoDAO, UbicacionDAO
from backend.persistencia.dao_stock import StockDAO


class StockService:
    def __init__(self, dao=None, producto_dao=None, ubicacion_dao=None):
        self.dao = dao or StockDAO()
        self.producto_dao = producto_dao or ProductoDAO()
        self.ubicacion_dao = ubicacion_dao or UbicacionDAO()

    def obtener_producto(self, producto_id):
        producto = self.producto_dao.obtener_por_id(producto_id)
        if producto is None:
            raise NoEncontrado(f"No se encontro el producto {producto_id}")
        return producto

    def obtener_ubicacion(self, ubicacion_id):
        ubicacion = self.ubicacion_dao.obtener_por_id(ubicacion_id)
        if ubicacion is None:
            raise NoEncontrado(f"No se encontro la ubicación {ubicacion_id}")
        return ubicacion

    def obtener(self, ubicacion_id, producto_id):
        self.obtener_ubicacion(ubicacion_id)
        self.obtener_producto(producto_id)
        return self.dao.obtener(producto_id, ubicacion_id)

    def listar_por_ubicacion(self, ubicacion_id):
        self.obtener_ubicacion(ubicacion_id)
        return self.dao.listar_por_ubicacion(ubicacion_id)

    def listar_movimientos(self, ubicacion_id, producto_id):
        self.obtener_ubicacion(ubicacion_id)
        self.obtener_producto(producto_id)
        return self.dao.listar_movimientos(producto_id, ubicacion_id)

    # cx: la conexión de una transacción ya abierta por otro service. Si no
    # viene, la operación abre y cierra la suya.
    # usuario_id: quién hizo la operación, queda en el libro de movimientos.
    # fecha: la de la operación que causa el movimiento (la venta); si no, ahora.
    def ingresar(self, ubicacion_id, producto_id, cantidad, tipo, referencia="", cx=None, usuario_id=None, fecha=None):
        return self._mover(ubicacion_id, producto_id, cantidad, tipo, referencia, cx, usuario_id, True, fecha)

    def egresar(self, ubicacion_id, producto_id, cantidad, tipo, referencia="", cx=None, usuario_id=None, fecha=None):
        return self._mover(ubicacion_id, producto_id, cantidad, tipo, referencia, cx, usuario_id, False, fecha)

    def _mover(self, ubicacion_id, producto_id, cantidad, tipo, referencia, cx, usuario_id, ingreso, fecha=None):
        # Primero se valida todo lo que no depende de la cantidad actual
        producto = self.obtener_producto(producto_id)
        if tipo == TipoMovimiento.COMPRA and not producto.activo:
            raise DatoInvalido(f"El producto '{producto.nombre}' está dado de baja: no se puede comprar")
        validar_ubicacion_para(tipo, self.obtener_ubicacion(ubicacion_id))

        if cx is None:
            with self.dao.transaccion() as cx:
                return self._mover_en(cx, ubicacion_id, producto_id, cantidad, tipo, referencia, usuario_id, ingreso, fecha)
        return self._mover_en(cx, ubicacion_id, producto_id, cantidad, tipo, referencia, usuario_id, ingreso, fecha)

    def _mover_en(self, cx, ubicacion_id, producto_id, cantidad, tipo, referencia, usuario_id, ingreso, fecha=None):
        # La cantidad se lee dentro de la transacción, y la regla de "no
        # egresar más de lo que hay" la aplica el dominio (StockInsuficiente)
        stock = self.dao.obtener(producto_id, ubicacion_id, cx)
        if ingreso:
            stock.ingresar(cantidad, tipo, referencia, fecha)
        else:
            stock.egresar(cantidad, tipo, referencia, fecha)
        return self.dao.guardar(cx, stock, usuario_id)
