# Las clases "maestras" que casi no cambian: Producto, Categoria, Proveedor,
# Ubicacion, Sucursal y CentroDistribucion, con sus validaciones básicas.
# Acá NO va el stock ni los movimientos (eso está en stock.py) ni nada de base de datos.
import re

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


# Algoritmo "módulo 11" del CUIT: el último dígito se calcula a partir de los
# otros 10. Detecta la mayoría de los errores de tipeo.
def cuit_es_valido(cuit):
    if len(cuit) != 11 or not cuit.isdigit():
        return False
    pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    suma = sum(int(digito) * peso for digito, peso in zip(cuit[:10], pesos))
    verificador = 11 - suma % 11
    if verificador == 11:
        verificador = 0
    if verificador == 10:
        return False
    return verificador == int(cuit[10])


FORMATO_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Proveedor:
    # El CUIT identifica al proveedor y no se modifica después de crearlo.
    # Que no esté repetido lo valida el service, porque necesita consultar la base.
    def __init__(self, cuit, razon_social, telefono=None, email=None, id=None, activo=True):
        self.id = id
        self.cuit = cuit
        self.razon_social = razon_social
        self.telefono = telefono
        self.email = email
        self.activo = activo

    @property
    def cuit(self):
        return self._cuit

    @cuit.setter
    def cuit(self, valor):
        # Se guarda solo con los dígitos: "20-12345678-6" y "20123456789" son el mismo CUIT
        solo_digitos = re.sub(r"[\s-]", "", str(valor or ""))
        if not cuit_es_valido(solo_digitos):
            raise DatoInvalido(f"El CUIT '{valor}' no es válido")
        self._cuit = solo_digitos

    @property
    def cuit_formateado(self):
        return f"{self.cuit[:2]}-{self.cuit[2:10]}-{self.cuit[10]}"

    @property
    def razon_social(self):
        return self._razon_social

    @razon_social.setter
    def razon_social(self, valor):
        valor = (valor or "").strip()
        if not valor:
            raise DatoInvalido("La razón social del proveedor no puede estar vacía")
        if len(valor) > 100:
            raise DatoInvalido("La razón social no puede tener más de 100 caracteres")
        self._razon_social = valor

    # Teléfono y email son opcionales: vacío se guarda como None
    @property
    def telefono(self):
        return self._telefono

    @telefono.setter
    def telefono(self, valor):
        valor = (valor or "").strip()
        if len(valor) > 30:
            raise DatoInvalido("El teléfono no puede tener más de 30 caracteres")
        self._telefono = valor or None

    @property
    def email(self):
        return self._email

    @email.setter
    def email(self, valor):
        valor = (valor or "").strip().lower()
        if valor and not FORMATO_EMAIL.match(valor):
            raise DatoInvalido(f"El email '{valor}' no es válido")
        self._email = valor or None

    def dar_de_baja(self):
        self.activo = False

    def __str__(self):
        return f"Proveedor: ({self.id}, {self.cuit_formateado}, {self.razon_social})"