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
referencia TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS movimientos_stock_por_stock
ON movimientos_stock (stock_id);

-- ---------- Logística: reposición CD -> locales ----------

-- Lo que pide UN local al CD. Mientras está PENDIENTE se edita; al consolidarse
-- queda cerrado. La ubicación es siempre una sucursal.
CREATE TABLE IF NOT EXISTS pedidos_reposicion (
id INTEGER PRIMARY KEY AUTOINCREMENT,
ubicacion_id INTEGER NOT NULL REFERENCES ubicaciones(id),
fecha TEXT NOT NULL DEFAULT (datetime('now')),
estado TEXT NOT NULL DEFAULT 'PENDIENTE' CHECK (estado IN ('PENDIENTE', 'CONSOLIDADO'))
);

-- Líneas de lo PEDIDO (distinto de lo enviado, que va en detalles_bulto).
CREATE TABLE IF NOT EXISTS detalles_pedido (
id INTEGER PRIMARY KEY AUTOINCREMENT,
pedido_id INTEGER NOT NULL REFERENCES pedidos_reposicion(id),
producto_id INTEGER NOT NULL REFERENCES productos(id),
cantidad INTEGER NOT NULL CHECK (cantidad >= 1),
UNIQUE (pedido_id, producto_id)
);

-- Lo que arma el CD juntando pedidos de varios locales.
CREATE TABLE IF NOT EXISTS ordenes_reposicion (
id INTEGER PRIMARY KEY AUTOINCREMENT,
origen_id INTEGER NOT NULL REFERENCES ubicaciones(id),
fecha TEXT NOT NULL DEFAULT (datetime('now')),
estado TEXT NOT NULL DEFAULT 'ABIERTA' CHECK (estado IN ('ABIERTA', 'CERRADA'))
);

-- Qué pedidos consolida cada orden. pedido_id es la clave primaria: un pedido
-- solo puede estar en UNA orden. El dominio no puede saberlo, lo garantiza la base.
CREATE TABLE IF NOT EXISTS orden_pedido (
orden_id INTEGER NOT NULL REFERENCES ordenes_reposicion(id),
pedido_id INTEGER PRIMARY KEY REFERENCES pedidos_reposicion(id)
);

-- Documento de despacho del CD hacia UN local.
CREATE TABLE IF NOT EXISTS remitos (
id INTEGER PRIMARY KEY AUTOINCREMENT,
origen_id INTEGER NOT NULL REFERENCES ubicaciones(id),
destino_id INTEGER NOT NULL REFERENCES ubicaciones(id),
fecha TEXT NOT NULL DEFAULT (datetime('now')),
estado TEXT NOT NULL DEFAULT 'ABIERTO' CHECK (estado IN ('ABIERTO', 'CERRADO')),
CHECK (origen_id <> destino_id)
);

-- El estado se guarda como texto y el DAO lo convierte al objeto State al leer.
-- Solo un bulto PREPARADO puede no tener precinto.
CREATE TABLE IF NOT EXISTS bultos (
id INTEGER PRIMARY KEY AUTOINCREMENT,
remito_id INTEGER REFERENCES remitos(id),
nro_precinto TEXT,
estado TEXT NOT NULL DEFAULT 'PREPARADO'
CHECK (estado IN ('PREPARADO', 'PRECINTADO', 'EN_TRANSITO', 'RECIBIDO', 'VERIFICADO', 'RECHAZADO')),
CHECK (estado = 'PREPARADO' OR (nro_precinto IS NOT NULL AND length(trim(nro_precinto)) > 0))
);

CREATE TABLE IF NOT EXISTS detalles_bulto (
id INTEGER PRIMARY KEY AUTOINCREMENT,
bulto_id INTEGER NOT NULL REFERENCES bultos(id),
producto_id INTEGER NOT NULL REFERENCES productos(id),
cantidad INTEGER NOT NULL CHECK (cantidad >= 1),
UNIQUE (bulto_id, producto_id)
);

-- Trazabilidad inmutable: solo se insertan filas. Los triggers de abajo
-- rechazan cualquier UPDATE o DELETE, así que la regla vale aunque falle el DAO.
CREATE TABLE IF NOT EXISTS historial_bulto (
id INTEGER PRIMARY KEY AUTOINCREMENT,
bulto_id INTEGER NOT NULL REFERENCES bultos(id),
fecha_hora TEXT NOT NULL,
estado_anterior TEXT NOT NULL,
estado_nuevo TEXT NOT NULL,
observacion TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS historial_bulto_por_bulto
ON historial_bulto (bulto_id);

CREATE TRIGGER IF NOT EXISTS historial_bulto_no_update
BEFORE UPDATE ON historial_bulto
BEGIN
SELECT RAISE(ABORT, 'El historial del bulto es inmutable: no se puede modificar');
END;

CREATE TRIGGER IF NOT EXISTS historial_bulto_no_delete
BEFORE DELETE ON historial_bulto
BEGIN
SELECT RAISE(ABORT, 'El historial del bulto es inmutable: no se puede borrar');
END;