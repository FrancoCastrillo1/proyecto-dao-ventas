# Casos de uso de los maestros: dar de alta/modificar/listar productos, categorías,
# proveedores, ubicaciones, sucursales y el CD.
# Acá NO va SQL (usa dao_maestros) ni nada de endpoints (eso está en api).
from backend.dominio.excepciones import EntidadDuplicada, NoEncontrado
from backend.dominio.maestros import Categoria
from backend.persistencia.dao_maestros import CategoriaDAO

class CategoriaService:
    def __init__(self, dao=None):
        self.dao = dao or CategoriaDAO()

    def crear(self, nombre):
        categoria = Categoria(nombre)
        if self.dao.obtener_por_nombre(categoria.nombre):
            raise EntidadDuplicada(f"Ya existe la categoría '{categoria.nombre}'")
        return self.dao.crear(categoria)

    def obtener(self, id):
        categoria = self.dao.obtener_por_id(id)
        if categoria is None:
            raise NoEncontrado(f"No se encontro la categoria {id}")
        return categoria

    def listar(self):
        return self.dao.listar()

    def modificar(self, id, nombre):
        categoria = self.obtener(id)
        categoria.nombre = nombre
        otra = self.dao.obtener_por_nombre(nombre)

        if otra and otra.id != id:
            raise EntidadDuplicada(f"Ya existe la categoría '{categoria.nombre}'")
        return self.dao.actualizar(categoria)

    def dar_de_baja(self, id):
        categoria = self.obtener(id)
        categoria.dar_de_baja()
        self.dao.actualizar(categoria)
