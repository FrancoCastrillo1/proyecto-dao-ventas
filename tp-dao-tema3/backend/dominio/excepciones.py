# Los errores propios del negocio: transición de estado inválida, stock insuficiente,
# pago que no cubre el total, etc. Así los servicios y la api saben qué pasó.
# Acá NO van errores técnicos de la base ni de la web, solo los del negocio.
class ErrorDeNegocio(Exception):
    """Base de todos los errores de las reglas del negocio"""

class NoEncontrado(ErrorDeNegocio):
    pass

class EntidadDuplicada(ErrorDeNegocio):
    pass

class DatoInvalido(ErrorDeNegocio):
    pass

class TransicionDeEstadoInvalida(ErrorDeNegocio):
    pass

class StockInsuficiente(ErrorDeNegocio):
    pass