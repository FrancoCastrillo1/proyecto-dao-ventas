from backend.persistencia.conexion import get_conexion

class DaoStock:

    def obtener_stock(self, ubicacion_id: int, producto_id: int):
        conexion = get_conexion()
        cursor = conexion.cursor()
        
        # Buscamos en stock junto con el stock_minimo del producto
        cursor.execute(
            """
            SELECT s.id, s.cantidad, p.stock_minimo 
            FROM stock s
            JOIN productos p ON s.producto_id = p.id
            WHERE s.ubicacion_id = ? AND s.producto_id = ?
            """,
            (ubicacion_id, producto_id)
        )
        row = cursor.fetchone()
        
        if row:
            conexion.close()
            return {"id": row[0], "cantidad": row[1], "stock_minimo": row[2]}
        
        # Si el par ubicacion-producto aún no tiene registro en 'stock', buscamos stock_minimo en productos
        cursor.execute("SELECT stock_minimo FROM productos WHERE id = ?", (producto_id,))
        prod_row = cursor.fetchone()
        conexion.close()
        
        if not prod_row:
            raise ValueError(f"El producto con ID {producto_id} no existe.")
            
        return {"id": None, "cantidad": 0, "stock_minimo": prod_row[0]}

    def guardar_o_actualizar(self, ubicacion_id: int, producto_id: int, cantidad: int):
        conexion = get_conexion()
        cursor = conexion.cursor()
        
        cursor.execute(
            "SELECT id FROM stock WHERE ubicacion_id = ? AND producto_id = ?",
            (ubicacion_id, producto_id)
        )
        row = cursor.fetchone()
        
        if row:
            stock_id = row[0]
            cursor.execute("UPDATE stock SET cantidad = ? WHERE id = ?", (cantidad, stock_id))
        else:
            cursor.execute(
                "INSERT INTO stock (ubicacion_id, producto_id, cantidad) VALUES (?, ?, ?)",
                (ubicacion_id, producto_id, cantidad)
            )
            stock_id = cursor.lastrowid
            
        conexion.commit()
        conexion.close()
        return stock_id

    def registrar_movimiento(self, stock_id: int, cantidad: int, tipo: str, referencia: str):
        conexion = get_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            """
            INSERT INTO movimientos_stock (stock_id, fecha, cantidad, tipo, referencia)
            VALUES (?, datetime('now'), ?, ?, ?)
            """,
            (stock_id, cantidad, tipo, referencia)
        )
        conexion.commit()
        conexion.close()