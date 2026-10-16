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