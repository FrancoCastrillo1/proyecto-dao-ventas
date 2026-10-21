-- Acá van los CREATE TABLE de todas las tablas del sistema (maestros, stock,
-- logística y ventas), con sus claves primarias, foráneas y restricciones.
-- Acá NO van datos de prueba: eso lo carga backend/datos/seed.py.
CREATE TABLE IF NOT EXISTS categorias (
id INTEGER PRIMARY KEY AUTOINCREMENT,
nombre TEXT NOT NULL UNIQUE COLLATE NOCASE,
nombre_normalizado TEXT,
activo INTEGER NOT NULL DEFAULT 1
);

-- nombre_normalizado = nombre sin mayúsculas, tildes ni espacios de más (lo
-- completa el DAO). El índice único hace que "Lácteos" y "lacteos " choquen.
-- Va como índice aparte (y no UNIQUE en la columna) porque las bases que ya
-- existían reciben la columna con ALTER TABLE, que no admite UNIQUE.
CREATE UNIQUE INDEX IF NOT EXISTS categorias_nombre_normalizado
ON categorias (nombre_normalizado);

-- El código (SKU) es el identificador del producto: único sin distinguir
-- mayúsculas. El precio puede ser menor al costo (venta a pérdida).
CREATE TABLE IF NOT EXISTS productos (
id INTEGER PRIMARY KEY AUTOINCREMENT,
codigo TEXT NOT NULL UNIQUE COLLATE NOCASE,
nombre TEXT NOT NULL,
categoria_id INTEGER NOT NULL REFERENCES categorias(id),
precio_venta REAL NOT NULL CHECK (precio_venta > 0),
costo REAL NOT NULL CHECK (costo >= 0),
stock_minimo INTEGER NOT NULL DEFAULT 0 CHECK (stock_minimo >= 0),
activo INTEGER NOT NULL DEFAULT 1
);

-- El CUIT es el identificador del proveedor: se guarda solo con los 11 dígitos.
CREATE TABLE IF NOT EXISTS proveedores (
id INTEGER PRIMARY KEY AUTOINCREMENT,
cuit TEXT NOT NULL UNIQUE CHECK (length(cuit) = 11),
razon_social TEXT NOT NULL,
telefono TEXT,
email TEXT,
activo INTEGER NOT NULL DEFAULT 1
);

-- Relación muchos a muchos: un producto se le compra a varios proveedores
-- y un proveedor vende muchos productos. La clave compuesta evita duplicados.
CREATE TABLE IF NOT EXISTS producto_proveedor (
producto_id INTEGER NOT NULL REFERENCES productos(id),
proveedor_id INTEGER NOT NULL REFERENCES proveedores(id),
PRIMARY KEY (producto_id, proveedor_id)
);

-- Sucursales y Centro de Distribución en una sola tabla (Single Table
-- Inheritance): "tipo" indica qué clase del dominio se arma al leer.
-- Stock, remitos y ventas apuntan a esta tabla.
CREATE TABLE IF NOT EXISTS ubicaciones (
id INTEGER PRIMARY KEY AUTOINCREMENT,
tipo TEXT NOT NULL CHECK (tipo IN ('CD', 'SUCURSAL')),
nombre TEXT NOT NULL UNIQUE COLLATE NOCASE,
nombre_normalizado TEXT,
direccion TEXT NOT NULL,
activo INTEGER NOT NULL DEFAULT 1
);

-- Igual que en categorías: nombres que solo difieren en tildes/espacios chocan
CREATE UNIQUE INDEX IF NOT EXISTS ubicaciones_nombre_normalizado
ON ubicaciones (nombre_normalizado);

-- Red de seguridad: un solo CD activo (los dados de baja no cuentan)
CREATE UNIQUE INDEX IF NOT EXISTS un_solo_cd_activo
ON ubicaciones (tipo) WHERE tipo = 'CD' AND activo = 1;

-- ================================================================= Usuarios
-- Cada usuario pertenece a una ubicación y su perfil define qué puede hacer
-- (UsuarioCD o UsuarioSucursal en el dominio; "perfil" decide la clase al leer).
-- El nombre de usuario es único sin distinguir mayúsculas. Baja lógica.
CREATE TABLE IF NOT EXISTS usuarios (
id INTEGER PRIMARY KEY AUTOINCREMENT,
perfil TEXT NOT NULL CHECK (perfil IN ('CD', 'SUCURSAL')),
nombre_usuario TEXT NOT NULL UNIQUE COLLATE NOCASE,
nombre_completo TEXT NOT NULL,
ubicacion_id INTEGER NOT NULL REFERENCES ubicaciones(id),
activo INTEGER NOT NULL DEFAULT 1
);

-- Red de seguridad: el perfil tiene que coincidir con el tipo de la ubicación
-- (un usuario CD en el CD, uno de sucursal en una sucursal). Los nombres son
-- los mismos a propósito, así la regla es una simple comparación.
CREATE TRIGGER IF NOT EXISTS usuarios_perfil_segun_ubicacion_alta
BEFORE INSERT ON usuarios
WHEN (SELECT tipo FROM ubicaciones WHERE id = NEW.ubicacion_id) IS NOT NEW.perfil
BEGIN
    SELECT RAISE(ABORT, 'El perfil del usuario no corresponde al tipo de su ubicación');
END;

CREATE TRIGGER IF NOT EXISTS usuarios_perfil_segun_ubicacion_cambio
BEFORE UPDATE OF perfil, ubicacion_id ON usuarios
WHEN (SELECT tipo FROM ubicaciones WHERE id = NEW.ubicacion_id) IS NOT NEW.perfil
BEGIN
    SELECT RAISE(ABORT, 'El perfil del usuario no corresponde al tipo de su ubicación');
END;


-- Cantidad de cada producto en cada ubicación (CD o sucursal): una fila por
-- par producto-ubicación. La cantidad nunca puede ser negativa. El stock
-- mínimo no se repite acá: se toma de productos.stock_minimo.
CREATE TABLE IF NOT EXISTS stock (
id INTEGER PRIMARY KEY AUTOINCREMENT,
producto_id INTEGER NOT NULL REFERENCES productos(id),
ubicacion_id INTEGER NOT NULL REFERENCES ubicaciones(id),
cantidad INTEGER NOT NULL DEFAULT 0 CHECK (cantidad >= 0),
UNIQUE (producto_id, ubicacion_id)
);

-- Libro de movimientos: solo se insertan filas, nunca se modifican ni se
-- borran. La cantidad lleva signo (positiva entra, negativa sale).
CREATE TABLE IF NOT EXISTS movimientos_stock (
id INTEGER PRIMARY KEY AUTOINCREMENT,
stock_id INTEGER NOT NULL REFERENCES stock(id),
fecha TEXT NOT NULL,
cantidad INTEGER NOT NULL CHECK (cantidad <> 0),
tipo TEXT NOT NULL CHECK (tipo IN ('COMPRA', 'DESPACHO', 'RECEPCION', 'VENTA', 'DEVOLUCION', 'AJUSTE')),
referencia TEXT NOT NULL DEFAULT '',
usuario_id INTEGER REFERENCES usuarios(id)
);

CREATE INDEX IF NOT EXISTS movimientos_stock_por_stock
ON movimientos_stock (stock_id);

-- ================================================================== Ventas
-- Todos los montos se guardan en CENTAVOS (INTEGER): $1500.50 → 150050.
-- Así los SUM de los reportes dan exactos (con REAL aparecen diferencias
-- de centavos). El DAO convierte entre Decimal y centavos.

-- Una venta ya cobrada. El medio y el porcentaje se guardan tal como se
-- aplicaron: si después cambia el descuento del efectivo, esta venta no cambia.
-- El comprobante es correlativo por sucursal (punto de venta).
CREATE TABLE IF NOT EXISTS ventas (
id INTEGER PRIMARY KEY AUTOINCREMENT,
sucursal_id INTEGER NOT NULL REFERENCES ubicaciones(id),
fecha TEXT NOT NULL,
medio_pago TEXT NOT NULL CHECK (medio_pago IN ('EFECTIVO', 'DEBITO', 'TRANSFERENCIA', 'CREDITO')),
porcentaje_ajuste TEXT NOT NULL,
subtotal INTEGER NOT NULL CHECK (subtotal > 0),
total INTEGER NOT NULL CHECK (total > 0),
vuelto INTEGER NOT NULL DEFAULT 0 CHECK (vuelto >= 0),
nro_comprobante INTEGER NOT NULL CHECK (nro_comprobante > 0),
usuario_id INTEGER REFERENCES usuarios(id),
UNIQUE (sucursal_id, nro_comprobante)
);

CREATE INDEX IF NOT EXISTS ventas_por_sucursal_y_fecha
ON ventas (sucursal_id, fecha);

-- Precio y costo DEL MOMENTO de la venta (no se leen de productos)
CREATE TABLE IF NOT EXISTS detalles_venta (
venta_id INTEGER NOT NULL REFERENCES ventas(id),
producto_id INTEGER NOT NULL REFERENCES productos(id),
cantidad INTEGER NOT NULL CHECK (cantidad > 0),
precio_unitario INTEGER NOT NULL CHECK (precio_unitario > 0),
costo_unitario INTEGER NOT NULL CHECK (costo_unitario >= 0),
PRIMARY KEY (venta_id, producto_id)
);

-- Solo de ventas registradas (la clave foránea lo exige también en la base)
CREATE TABLE IF NOT EXISTS devoluciones (
id INTEGER PRIMARY KEY AUTOINCREMENT,
venta_id INTEGER NOT NULL REFERENCES ventas(id),
fecha TEXT NOT NULL,
motivo TEXT NOT NULL,
importe INTEGER NOT NULL CHECK (importe >= 0),
usuario_id INTEGER REFERENCES usuarios(id)
);

CREATE TABLE IF NOT EXISTS detalles_devolucion (
devolucion_id INTEGER NOT NULL REFERENCES devoluciones(id),
producto_id INTEGER NOT NULL REFERENCES productos(id),
cantidad INTEGER NOT NULL CHECK (cantidad > 0),
importe INTEGER NOT NULL CHECK (importe >= 0),
PRIMARY KEY (devolucion_id, producto_id)
);

-- Caja de cada local: como el libro de stock, solo se insertan filas. El
-- importe lleva signo (venta entra, devolución sale).
CREATE TABLE IF NOT EXISTS movimientos_caja (
id INTEGER PRIMARY KEY AUTOINCREMENT,
sucursal_id INTEGER NOT NULL REFERENCES ubicaciones(id),
fecha TEXT NOT NULL,
tipo TEXT NOT NULL CHECK (tipo IN ('VENTA', 'DEVOLUCION')),
medio_pago TEXT NOT NULL,
importe INTEGER NOT NULL,
referencia TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS movimientos_caja_por_sucursal_y_fecha
ON movimientos_caja (sucursal_id, fecha);

-- ===================================================== Logística CD → locales

-- Lo que consolida el CD juntando pedidos de varias sucursales
CREATE TABLE IF NOT EXISTS ordenes_reposicion (
id INTEGER PRIMARY KEY AUTOINCREMENT,
origen_id INTEGER NOT NULL REFERENCES ubicaciones(id),
fecha TEXT NOT NULL,
estado TEXT NOT NULL CHECK (estado IN ('ABIERTA', 'CERRADA')),
usuario_id INTEGER REFERENCES usuarios(id)
);

-- Lo que pide cada sucursal. orden_id queda vacío hasta que se consolida.
CREATE TABLE IF NOT EXISTS pedidos_reposicion (
id INTEGER PRIMARY KEY AUTOINCREMENT,
sucursal_id INTEGER NOT NULL REFERENCES ubicaciones(id),
fecha TEXT NOT NULL,
estado TEXT NOT NULL CHECK (estado IN ('PENDIENTE', 'CONSOLIDADO')),
orden_id INTEGER REFERENCES ordenes_reposicion(id),
usuario_id INTEGER REFERENCES usuarios(id)
);

CREATE TABLE IF NOT EXISTS detalles_pedido (
pedido_id INTEGER NOT NULL REFERENCES pedidos_reposicion(id),
producto_id INTEGER NOT NULL REFERENCES productos(id),
cantidad INTEGER NOT NULL CHECK (cantidad > 0),
PRIMARY KEY (pedido_id, producto_id)
);

-- Un remito por destino dentro de cada orden: agrupa los bultos que viajan
-- del CD a esa sucursal
CREATE TABLE IF NOT EXISTS remitos (
id INTEGER PRIMARY KEY AUTOINCREMENT,
orden_id INTEGER NOT NULL REFERENCES ordenes_reposicion(id),
origen_id INTEGER NOT NULL REFERENCES ubicaciones(id),
destino_id INTEGER NOT NULL REFERENCES ubicaciones(id),
fecha TEXT NOT NULL,
estado TEXT NOT NULL CHECK (estado IN ('ABIERTO', 'CERRADO', 'EN_TRANSITO', 'VERIFICADO', 'VERIFICADO_CON_RECHAZOS')),
usuario_id INTEGER REFERENCES usuarios(id),
CHECK (origen_id <> destino_id),
UNIQUE (orden_id, destino_id)
);

-- El estado se guarda como texto y el DAO vuelve a armar el objeto del
-- patrón State al leerlo. El precinto es único: dos bultos con el mismo
-- precinto harían inútil la verificación (los NULL, sin precintar, no chocan).
CREATE TABLE IF NOT EXISTS bultos (
id INTEGER PRIMARY KEY AUTOINCREMENT,
remito_id INTEGER NOT NULL REFERENCES remitos(id),
nro_precinto TEXT UNIQUE,
estado TEXT NOT NULL CHECK (estado IN ('PREPARADO', 'PRECINTADO', 'EN_TRANSITO', 'RECIBIDO', 'VERIFICADO', 'RECHAZADO'))
);

CREATE TABLE IF NOT EXISTS detalles_bulto (
bulto_id INTEGER NOT NULL REFERENCES bultos(id),
producto_id INTEGER NOT NULL REFERENCES productos(id),
cantidad INTEGER NOT NULL CHECK (cantidad > 0),
PRIMARY KEY (bulto_id, producto_id)
);

-- Trazabilidad inmutable de estados del bulto (validación de la consigna):
-- solo se insertan filas. Los triggers hacen que la BASE rechace cualquier
-- UPDATE o DELETE, aunque alguien se saltee el sistema.
CREATE TABLE IF NOT EXISTS historial_bultos (
id INTEGER PRIMARY KEY AUTOINCREMENT,
bulto_id INTEGER NOT NULL REFERENCES bultos(id),
fecha_hora TEXT NOT NULL,
estado_anterior TEXT NOT NULL,
estado_nuevo TEXT NOT NULL,
observacion TEXT NOT NULL DEFAULT '',
usuario_id INTEGER REFERENCES usuarios(id)
);

CREATE INDEX IF NOT EXISTS historial_bultos_por_bulto
ON historial_bultos (bulto_id);

CREATE TRIGGER IF NOT EXISTS historial_bultos_no_se_modifica
BEFORE UPDATE ON historial_bultos
BEGIN
    SELECT RAISE(ABORT, 'El historial de estados de un bulto es inmutable: no se puede modificar');
END;

CREATE TRIGGER IF NOT EXISTS historial_bultos_no_se_borra
BEFORE DELETE ON historial_bultos
BEGIN
    SELECT RAISE(ABORT, 'El historial de estados de un bulto es inmutable: no se puede borrar');
END;

-- Los libros de stock y de caja ya eran "solo INSERT" por convención: con
-- estos triggers lo garantiza la base, igual que el historial de bultos.
-- Una corrección se hace con un movimiento nuevo (AJUSTE), nunca editando.
CREATE TRIGGER IF NOT EXISTS movimientos_stock_no_se_modifican
BEFORE UPDATE ON movimientos_stock
BEGIN
    SELECT RAISE(ABORT, 'Los movimientos de stock son inmutables: se corrigen con un AJUSTE');
END;

CREATE TRIGGER IF NOT EXISTS movimientos_stock_no_se_borran
BEFORE DELETE ON movimientos_stock
BEGIN
    SELECT RAISE(ABORT, 'Los movimientos de stock son inmutables: se corrigen con un AJUSTE');
END;

CREATE TRIGGER IF NOT EXISTS movimientos_caja_no_se_modifican
BEFORE UPDATE ON movimientos_caja
BEGIN
    SELECT RAISE(ABORT, 'Los movimientos de caja son inmutables');
END;

CREATE TRIGGER IF NOT EXISTS movimientos_caja_no_se_borran
BEFORE DELETE ON movimientos_caja
BEGIN
    SELECT RAISE(ABORT, 'Los movimientos de caja son inmutables');
END;