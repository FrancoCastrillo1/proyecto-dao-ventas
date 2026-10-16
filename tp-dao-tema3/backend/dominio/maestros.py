# Las clases "maestras" que casi no cambian: Producto, Categoria, Proveedor,
# Ubicacion, Sucursal y CentroDistribucion, con sus validaciones básicas.
# Acá NO va el stock ni los movimientos (eso está en stock.py) ni nada de base de datos.
from backend.dominio.excepciones import DatoInvalido

class Categoria:
    def __init__(self, nombre, id=None, activo=True):
        self.id = id
        self.nombre = nombre
        self.activo = activo


    @property
    def nombre(self):
        return self._nombre

    @nombre.setter
    def nombre(self, valor):
        valor = (valor or "").strip()
        if not valor:
            raise DatoInvalido("El nombre de la categoria no puede estar vacio")
        if len(valor) > 50:
            raise DatoInvalido("El nombre de la categoria no puede tener mas de 50 caracteres")
        self._nombre = valor

    def dar_de_baja(self):
        self.activo = False

    def __str__(self):
        return f"Categoria: ({self.id}, {self.nombre})"


# Conversiones compartidas por los setters: aceptan lo que llega (texto o
# número) y lanzan DatoInvalido si no se puede interpretar.
def convertir_a_monto(valor, campo):
    try:
        monto = float(valor)
    except (TypeError, ValueError):
        raise DatoInvalido(f"El {campo} debe ser un número")
    return round(monto, 2)


def convertir_a_entero(valor, campo):
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise DatoInvalido(f"El {campo} debe ser un número entero")
    if not numero.is_integer():
        raise DatoInvalido(f"El {campo} debe ser un número entero")
    return int(numero)


class Producto:
    # El código (SKU) identifica al producto y no se modifica después de crearlo.
    # La unicidad del código y que la categoría exista los valida el service,
    # porque necesitan consultar la base.
    def __init__(self, codigo, nombre, categoria_id, precio_venta, costo, stock_minimo=0, id=None, activo=True):
        self.id = id
        self.codigo = codigo
        self.nombre = nombre
        self.categoria_id = categoria_id
        self.precio_venta = precio_venta
        self.costo = costo
        self.stock_minimo = stock_minimo
        self.activo = activo

    @property
    def codigo(self):
        return self._codigo

    @codigo.setter
    def codigo(self, valor):
        valor = (valor or "").strip().upper()
        if not valor:
            raise DatoInvalido("El código del producto no puede estar vacío")
        if len(valor) > 20:
            raise DatoInvalido("El código del producto no puede tener más de 20 caracteres")
        self._codigo = valor

    @property
    def nombre(self):
        return self._nombre

    @nombre.setter
    def nombre(self, valor):
        valor = (valor or "").strip()
        if not valor:
            raise DatoInvalido("El nombre del producto no puede estar vacío")
        if len(valor) > 100:
            raise DatoInvalido("El nombre del producto no puede tener más de 100 caracteres")
        self._nombre = valor

    @property
    def categoria_id(self):
        return self._categoria_id

    @categoria_id.setter
    def categoria_id(self, valor):
        valor = convertir_a_entero(valor, "id de categoría")
        if valor <= 0:
            raise DatoInvalido("El producto debe tener una categoría válida")
        self._categoria_id = valor

    @property
    def precio_venta(self):
        return self._precio_venta

    @precio_venta.setter
    def precio_venta(self, valor):
        valor = convertir_a_monto(valor, "precio de venta")
        if valor <= 0:
            raise DatoInvalido("El precio de venta debe ser mayor a cero")
        self._precio_venta = valor

    @property
    def costo(self):
        return self._costo

    @costo.setter
    def costo(self, valor):
        valor = convertir_a_monto(valor, "costo")
        if valor < 0:
            raise DatoInvalido("El costo no puede ser negativo")
        self._costo = valor

    @property
    def stock_minimo(self):
        return self._stock_minimo

    @stock_minimo.setter
    def stock_minimo(self, valor):
        valor = convertir_a_entero(valor, "stock mínimo")
        if valor < 0:
            raise DatoInvalido("El stock mínimo no puede ser negativo")
        self._stock_minimo = valor

    # Puede dar negativo: vender por debajo del costo es válido (liquidación)
    # y el reporte de margen tiene que poder mostrar la pérdida.
    def margen_unitario(self):
        return round(self.precio_venta - self.costo, 2)

    def dar_de_baja(self):
        self.activo = False

    def __str__(self):
        return f"Producto: ({self.id}, {self.codigo}, {self.nombre}, ${self.precio_venta})"