-- Acá van los CREATE TABLE de todas las tablas del sistema (maestros, stock,
-- logística y ventas), con sus claves primarias, foráneas y restricciones.
-- Acá NO van datos de prueba: eso lo carga backend/datos/seed.py.
CREATE TABLE IF NOT EXISTS categorias (
id INTEGER PRIMARY KEY AUTOINCREMENT,
nombre TEXT NOT NULL UNIQUE COLLATE NOCASE,
activo INTEGER NOT NULL DEFAULT 1
);

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