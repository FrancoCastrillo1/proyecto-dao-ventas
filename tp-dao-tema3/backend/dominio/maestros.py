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