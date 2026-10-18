from backend.persistencia.dao_stock import DaoStock
from backend.dominio.stock import Stock, TipoMovimiento

class StockService:
    def __init__(self):
        self.dao = DaoStock()

    def obtener_stock_ubicacion(self, ubicacion_id: int, producto_id: int):
        res = self.dao.obtener_stock(ubicacion_id, producto_id)
        return {"cantidad": res["cantidad"], "stock_minimo": res["stock_minimo"]}

    def ingresar_stock(self, ubicacion_id: int, producto_id: int, cantidad: int, tipo: TipoMovimiento, referencia: str):
        datos_actuales = self.dao.obtener_stock(ubicacion_id, producto_id)
        cantidad_actual = datos_actuales["cantidad"]
        stock_minimo = datos_actuales["stock_minimo"]

        # Pasamos None para producto y ubicacion, y agregamos 'tipo' en ingresar
        stock_dominio = Stock(None, None, cantidad=cantidad_actual, stock_minimo=stock_minimo)
        stock_dominio.ingresar(cantidad, tipo)

        stock_id = self.dao.guardar_o_actualizar(ubicacion_id, producto_id, stock_dominio.cantidad)
        tipo_str = tipo.value if hasattr(tipo, 'value') else str(tipo)
        self.dao.registrar_movimiento(stock_id, cantidad, tipo_str, referencia)

    def egresar_stock(self, ubicacion_id: int, producto_id: int, cantidad: int, tipo: TipoMovimiento, referencia: str):
        datos_actuales = self.dao.obtener_stock(ubicacion_id, producto_id)
        if datos_actuales["cantidad"] < cantidad:
            raise ValueError("No hay suficiente stock para realizar el egreso.")

        cantidad_actual = datos_actuales["cantidad"]
        stock_minimo = datos_actuales["stock_minimo"]

        stock_dominio = Stock(None, None, cantidad=cantidad_actual, stock_minimo=stock_minimo)
        stock_dominio.egresar(cantidad, tipo)

        stock_id = self.dao.guardar_o_actualizar(ubicacion_id, producto_id, stock_dominio.cantidad)
        tipo_str = tipo.value if hasattr(tipo, 'value') else str(tipo)
        self.dao.registrar_movimiento(stock_id, -cantidad, tipo_str, referencia)