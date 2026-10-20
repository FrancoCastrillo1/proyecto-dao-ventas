from backend.dominio.excepciones import ErrorDeNegocio
from backend.dominio.stock import TipoMovimiento
from backend.persistencia.conexion import crear_tablas, get_conexion
from backend.servicios.stock_service import StockService

def cargar_datos_prueba():
    crear_tablas()  # por si se corre antes de levantar el backend por primera vez
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

    cursor.execute("""
        INSERT OR IGNORE INTO productos (id, codigo, nombre, categoria_id, precio_venta, costo, stock_minimo, activo)
        VALUES (2, 'PROD-002', 'Agua Mineral 1.5L', 1, 800.0, 450.0, 10, 1)
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
    cargar_stock_prueba()
    print("¡Datos de prueba (Seed) cargados con éxito!")


# Stock inicial por el service (así deja sus movimientos). Solo se carga si
# está en 0, para que correr el seed dos veces no lo duplique.
# PROVISORIO: al local se le carga como RECEPCION para poder probar ventas
# desde /docs mientras no esté el circuito de bultos (bloque B). Cuando esté,
# el stock del local tiene que entrar solo por bultos verificados.
def cargar_stock_prueba():
    stock = StockService()
    cargas = [
        (1, TipoMovimiento.COMPRA, 100, "Seed: compra inicial al CD"),
        (2, TipoMovimiento.RECEPCION, 30, "Seed: stock inicial del local (provisorio)"),
    ]
    for producto_id in (1, 2):
        for ubicacion_id, tipo, cantidad, referencia in cargas:
            try:
                if stock.obtener(ubicacion_id, producto_id).cantidad == 0:
                    stock.ingresar(ubicacion_id, producto_id, cantidad, tipo, referencia)
            except ErrorDeNegocio as error:
                # Pasa si la base ya tenía otros datos con esos ids (ej. el id 2 es el CD)
                print(f"No se cargó stock del producto {producto_id} en la ubicación {ubicacion_id}: {error}")

if __name__ == "__main__":
    cargar_datos_prueba()