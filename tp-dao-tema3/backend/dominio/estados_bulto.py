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
    def agregar_item(self, bulto, item):
        raise TransicionDeEstadoInvalida(f"No se pueden agregar items a un bulto en estado {self.nombre}")

    def precintar(self, bulto, nro_precinto):
        raise TransicionDeEstadoInvalida(f"No se puede precintar un bulto en estado {self.nombre}")

    def despachar(self, bulto):
        raise TransicionDeEstadoInvalida(f"No se puede despachar un bulto en estado {self.nombre}")

    def recibir(self, bulto):
        raise TransicionDeEstadoInvalida(f"No se puede recibir un bulto en estado {self.nombre}")

    def verificar(self, bulto, precinto_leido):
        raise TransicionDeEstadoInvalida(f"No se puede verificar un bulto en estado {self.nombre}")

class Preparado(EstadoBulto):
    @property
    def nombre(self):
        return "PREPARADO"
    
    def agregar_item(self, bulto, item):
        bulto.items.append(item)
        
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
    
    def verificar(self, bulto, precinto_leido):
        # Valida que llegó un precinto y que es el mismo que se puso en el CD:
        # el bulto no fue abierto en el camino, su stock puede pasar a disponible
        if precinto_leido and precinto_leido.strip() == bulto.nro_precinto:
            bulto.cambiar_estado(Verificado())
        # Llegó sin precinto o con uno distinto: el precinto fue violado,
        # rechazo logístico y la mercadería NO habilita venta
        else:
            bulto.cambiar_estado(Rechazado())


class Verificado(EstadoBulto):
    @property
    def nombre(self):
        return "VERIFICADO"

class Rechazado(EstadoBulto):
    @property
    def nombre(self):
        return "RECHAZADO"
