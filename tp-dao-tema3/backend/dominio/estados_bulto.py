# Patrón State para el Bulto: una clase por cada estado (armado, despachado,
# recibido, etc.) y cada una sabe a qué estados puede pasar y a cuáles no.
# Acá NO va la clase Bulto en sí (está en logistica.py), solo sus estados.

from abc import ABC, abstractmethod

from backend.dominio.excepciones import DatoInvalido, TransicionDeEstadoInvalida

class EstadoBulto(ABC):
    # Lo único obligatorio para cada estado: decir cómo se llama
    @property
    @abstractmethod
    def nombre(self):
        pass

    # Por defecto ninguna acción está permitida. Cada estado redefine
    # solo las que sí puede hacer; el resto cae acá y lanza el error.
    def agregar_item(self, bulto, producto, cantidad):
        raise TransicionDeEstadoInvalida(f"No se pueden agregar items a un bulto en estado {self.nombre}")

    def quitar_item(self, bulto, producto):
        raise TransicionDeEstadoInvalida(f"No se pueden quitar items de un bulto en estado {self.nombre}")

    def precintar(self, bulto, nro_precinto):
        raise TransicionDeEstadoInvalida(f"No se puede precintar un bulto en estado {self.nombre}")

    def despachar(self, bulto):
        raise TransicionDeEstadoInvalida(f"No se puede despachar un bulto en estado {self.nombre}")

    def recibir(self, bulto):
        raise TransicionDeEstadoInvalida(f"No se puede recibir un bulto en estado {self.nombre}")

    def verificar(self, bulto, nro_leido, intacto):
        raise TransicionDeEstadoInvalida(f"No se puede verificar un bulto en estado {self.nombre}")

    # Por defecto un estado NO habilita la venta. Solo Verificado lo habilita:
    # el servicio de recepción suma stock al local únicamente si esto da True.
    def habilita_venta(self):
        return False

class Preparado(EstadoBulto):
    @property
    def nombre(self):
        return "PREPARADO"

    def agregar_item(self, bulto, producto, cantidad):
        bulto.sumar_detalle(producto, cantidad)

    def quitar_item(self, bulto, producto):
        bulto.sacar_detalle(producto)

    def precintar(self, bulto, nro_precinto):
        # Primero se valida todo, después se modifica el bulto
        if not bulto.items:
            raise DatoInvalido("No se puede precintar un bulto vacío")
        if not nro_precinto or not nro_precinto.strip():
            raise DatoInvalido("El número de precinto no puede estar vacío")

        bulto.nro_precinto = nro_precinto.strip()
        bulto.cambiar_estado(Precintado())

class Precintado(EstadoBulto):
    @property
    def nombre(self):
        return "PRECINTADO"

    def despachar(self, bulto):
        bulto.cambiar_estado(EnTransito())



class EnTransito(EstadoBulto):
    @property
    def nombre(self):
        return "EN_TRANSITO"

    def recibir(self, bulto):
        bulto.cambiar_estado(Recibido())


class Recibido(EstadoBulto):
    @property
    def nombre(self):
        return "RECIBIDO"

    def verificar(self, bulto, nro_leido, intacto):
        # Para aprobar tienen que cumplirse las dos cosas: el precinto llegó
        # intacto (lo informa quien recibe) y el número leído es el mismo que
        # se puso en el CD. Con eso el bulto no fue abierto en el camino y su
        # stock puede pasar a disponible.
        coincide = bool(nro_leido) and nro_leido.strip() == bulto.nro_precinto
        if intacto and coincide:
            bulto.cambiar_estado(Verificado())
        # Precinto roto, ausente o con otro número: rechazo logístico y la
        # mercadería NO habilita venta
        else:
            bulto.cambiar_estado(Rechazado(), "Precinto violado o no coincide")


class Verificado(EstadoBulto):
    @property
    def nombre(self):
        return "VERIFICADO"

    def habilita_venta(self):
        return True

class Rechazado(EstadoBulto):
    @property
    def nombre(self):
        return "RECHAZADO"
