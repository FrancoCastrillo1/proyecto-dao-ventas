from backend.persistencia.conexion import get_conexion

def cargar_datos_prueba():
    conexion = get_conexion()
    cursor = conexion.cursor()

    # 1. Categoría de prueba
    cursor.execute("""
        INSERT OR IGNORE INTO categorias (id, nombre, nombre_normalizado, activo)
        VALUES (1, 'Bebidas', 'bebidas', 1)
    """)

    # 2. Producto de prueba (con stock_minimo)
    cursor.execute("""
        INSERT OR IGNORE INTO productos (id, codigo, nombre, categoria_id, precio_venta, costo, stock_minimo, activo)
        VALUES (1, 'PROD-001', 'Gaseosa Cola 2L', 1, 1500.0, 1000.0, 20, 1)
    """)

    # 3. Ubicaciones (Centro de Distribución y Sucursal)
    cursor.execute("""
        INSERT OR IGNORE INTO ubicaciones (id, tipo, nombre, nombre_normalizado, direccion, activo)
        VALUES (1, 'CD', 'Centro de Distribucion Central', 'centro de distribucion central', 'Av. Colon 1000', 1)
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO ubicaciones (id, tipo, nombre, nombre_normalizado, direccion, activo)
        VALUES (2, 'SUCURSAL', 'Sucursal Centro', 'sucursal centro', 'San Martin 250', 1)
    """)

    conexion.commit()
    conexion.close()
    print("¡Datos de prueba (Seed) cargados con éxito!")

if __name__ == "__main__":
    cargar_datos_prueba()