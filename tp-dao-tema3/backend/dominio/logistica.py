# Todo lo de reposición CD → locales: PedidoReposicion (lo que pide el local),
# OrdenReposicion (lo que consolida el CD), Remito y Bulto.
# Los estados del bulto NO van acá, van en estados_bulto.py (patrón State).
# Solo se importa Preparado porque es el estado con el que nace todo bulto;
# los demás estados los crean los propios estados al hacer cada transición.
from backend.dominio.estados_bulto import Preparado


class Bulto():
    def __init__(self, id_bulto):
        self.id_bulto = id_bulto
        self.items = []  # Lista de items en el bulto
        self.nro_precinto = None
        self.estado_actual = Preparado()  # Empieza Siempre en PREPARADO

    def __str__(self):
        return f"Bulto {self.id_bulto} - Estado: {self.estado}, Precinto: {self.nro_precinto}, Items: {len(self.items)}"

    def agregar_item(self, item):
        self.estado_actual.agregar_item(self, item)

    def precintar(self, nro_precinto):
        self.estado_actual.precintar(self, nro_precinto)
    
    def cambiar_estado(self, nuevo_estado):
        self.estado_actual = nuevo_estado
    
    def despachar(self):
        self.estado_actual.despachar(self)

    def recibir(self):
        self.estado_actual.recibir(self)

    def verificar(self, precinto_leido):
        self.estado_actual.verificar(self, precinto_leido)

    @property
    def estado(self):
        return self.estado_actual.nombre