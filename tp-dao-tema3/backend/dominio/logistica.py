# Todo lo de reposición CD → locales: PedidoReposicion (lo que pide el local),
# OrdenReposicion (lo que consolida el CD), Remito y Bulto.
# Los estados del bulto NO van acá, van en estados_bulto.py (patrón State).
# Solo se importa Preparado porque es el estado con el que nace todo bulto;
# los demás estados los crean los propios estados al hacer cada transición.
from dataclasses import dataclass
from datetime import datetime, timedelta

from backend.dominio.estados_bulto import ESTADOS_FINALES, Preparado
from backend.dominio.excepciones import DatoInvalido, TransicionDeEstadoInvalida
from backend.dominio.stock import _validar_entero


@dataclass(frozen=True)
class CambioEstadoBulto:
    """Un registro del historial del bulto. Es inmutable (frozen): una vez
    creado no se puede modificar, solo se agregan registros nuevos."""
    fecha_hora: datetime
    estado_anterior: str
    estado_nuevo: str
    observacion: str = ""


class Bulto():
    def __init__(self, id_bulto):
        self.id_bulto = id_bulto
        self.items = []  # Lista de items en el bulto
        self.nro_precinto = None
        self.estado_actual = Preparado()  # Empieza Siempre en PREPARADO
        self.registros_historial = []  # Trazabilidad: solo se agrega, nunca se edita ni se borra
        self.remito_id = None  # remito en el que viaja (lo completa el DAO al leerlo)

    def __str__(self):
        return f"Bulto {self.id_bulto} - Estado: {self.estado}, Precinto: {self.nro_precinto}, Items: {len(self.items)}"

    def agregar_item(self, producto, cantidad):
        self.estado_actual.agregar_item(self, producto, cantidad)

    def quitar_item(self, producto):
        self.estado_actual.quitar_item(self, producto)
        
    def sumar_detalle(self, producto, cantidad):
        # Se valida ANTES de sumar: si no, sumar 0 a una línea existente
        # daría un total válido y pasaría sin error
        _validar_entero(cantidad, "La cantidad", 1)
        for i, detalle in enumerate(self.items):
            if detalle.producto == producto:
                self.items[i] = DetalleBulto(producto, detalle.cantidad + cantidad)
                return
        self.items.append(DetalleBulto(producto, cantidad))

    def sacar_detalle(self, producto):
        for detalle in self.items:
            if detalle.producto == producto:
                self.items.remove(detalle)
                return
        raise DatoInvalido("El producto no está en el bulto")

    def precintar(self, nro_precinto):
        self.estado_actual.precintar(self, nro_precinto)

    def cambiar_estado(self, nuevo_estado, observacion=""):
        # Único lugar donde cambia el estado: siempre deja un registro en el historial
        self.registros_historial.append(
            CambioEstadoBulto(datetime.now(), self.estado, nuevo_estado.nombre, observacion)
        )
        self.estado_actual = nuevo_estado

    def despachar(self):
        self.estado_actual.despachar(self)

    def recibir(self):
        self.estado_actual.recibir(self)

    def verificar(self, nro_leido, intacto):
        self.estado_actual.verificar(self, nro_leido, intacto)

    def habilita_venta(self):
        return self.estado_actual.habilita_venta()

    @property
    def historial(self):
        # Se devuelve como tupla para que desde afuera no se pueda modificar
        return tuple(self.registros_historial)

    @property
    def estado(self):
        return self.estado_actual.nombre


    #juan _______

@dataclass(frozen=True)
class DetallePedido:
    """Una línea del pedido: qué producto pide el local y cuántas unidades.
    Es lo que se PIDE; lo que se ENVÍA es el DetalleBulto (pueden diferir si
    el CD no tiene stock suficiente)."""
    producto: object
    cantidad: int

    def __post_init__(self):
        _validar_entero(self.cantidad, "La cantidad", 1)


class PedidoReposicion:
    """Lo que pide UN local al Centro de Distribución. Mientras está PENDIENTE
    se puede editar; al consolidarse pasa a CONSOLIDADO y queda cerrado."""
    PENDIENTE = "PENDIENTE"
    CONSOLIDADO = "CONSOLIDADO"

    def __init__(self, id_pedido, local):
        if local is None or (isinstance(local, str) and not local.strip()):
            raise DatoInvalido("El pedido tiene que indicar el local que lo solicita")
        self.id_pedido = id_pedido
        self.local = local
        self.items = []  # Lista de DetallePedido
        self.estado = self.PENDIENTE
        self.fecha = datetime.now()
        self.orden_id = None  # orden en la que se consolidó

    def _validar_pendiente(self, accion):
        if self.estado != self.PENDIENTE:
            raise TransicionDeEstadoInvalida(
                f"No se puede {accion} un pedido en estado {self.estado}"
            )

    def agregar_item(self, producto, cantidad):
        self._validar_pendiente("modificar")
        # Se valida ANTES de sumar, igual que en el Bulto
        _validar_entero(cantidad, "La cantidad", 1)
        for i, detalle in enumerate(self.items):
            if detalle.producto == producto:
                self.items[i] = DetallePedido(producto, detalle.cantidad + cantidad)
                return
        self.items.append(DetallePedido(producto, cantidad))

    def quitar_item(self, producto):
        self._validar_pendiente("modificar")
        for detalle in self.items:
            if detalle.producto == producto:
                self.items.remove(detalle)
                return
        raise DatoInvalido("El producto no está en el pedido")

    def consolidar(self):
        self._validar_pendiente("consolidar")
        if not self.items:
            raise DatoInvalido("No se puede consolidar un pedido vacío")
        self.estado = self.CONSOLIDADO

class OrdenReposicion:
    """Lo que arma el Centro de Distribución juntando pedidos de varios locales
    para prepararlos de una vez. Mientras está ABIERTA admite pedidos; al
    cerrarse queda fija."""
    ABIERTA = "ABIERTA"
    CERRADA = "CERRADA"

    def __init__(self, id_orden, origen):
        if origen is None or (isinstance(origen, str) and not origen.strip()):
            raise DatoInvalido("La orden tiene que indicar el origen (Centro de Distribución)")
        self.id_orden = id_orden
        self.origen = origen
        self.pedidos = []  # Lista de PedidoReposicion
        self.estado = self.ABIERTA
        self.fecha = datetime.now()

    def _validar_abierta(self, accion):
        if self.estado != self.ABIERTA:
            raise TransicionDeEstadoInvalida(
                f"No se puede {accion} una orden en estado {self.estado}"
            )

    def agregar_pedido(self, pedido):
        self._validar_abierta("modificar")
        if pedido.estado != PedidoReposicion.CONSOLIDADO:
            raise DatoInvalido("Solo se pueden agregar pedidos consolidados")
        if pedido in self.pedidos:
            raise DatoInvalido("El pedido ya está en la orden")
        self.pedidos.append(pedido)

    def cerrar(self):
        self._validar_abierta("cerrar")
        if not self.pedidos:
            raise DatoInvalido("No se puede cerrar una orden sin pedidos")
        self.estado = self.CERRADA

    def total_por_producto(self):
        # Lo que el CD necesita juntar en total, sumando todos los pedidos
        totales = {}
        for pedido in self.pedidos:
            for detalle in pedido.items:
                totales[detalle.producto] = totales.get(detalle.producto, 0) + detalle.cantidad
        return totales
    
class Remito:
    """Documento de despacho: agrupa los bultos que viajan del Centro de
    Distribución a UN mismo local. Mientras está ABIERTO admite bultos; al
    cerrarse queda fijo y listo para despachar.

    Después del despacho: EN_TRANSITO hasta que todos sus bultos llegan a un
    estado final. Ahí pasa a VERIFICADO (todos verificados) o a
    VERIFICADO_CON_RECHAZOS (al menos uno rechazado). La consigna pide que el
    stock no quede disponible hasta que "el remito y el contenedor" estén
    verificados: el servicio de recepción suma stock recién en ese momento y
    solo de los bultos verificados."""
    ABIERTO = "ABIERTO"
    CERRADO = "CERRADO"
    EN_TRANSITO = "EN_TRANSITO"
    VERIFICADO = "VERIFICADO"
    VERIFICADO_CON_RECHAZOS = "VERIFICADO_CON_RECHAZOS"

    # Un viaje del CD a un local no puede estimarse a más de esto
    MAXIMO_DIAS_DE_VIAJE = 30

    def __init__(self, id_remito, origen, destino, orden_id=None):
        for valor, nombre in ((origen, "el origen"), (destino, "el destino")):
            if valor is None or (isinstance(valor, str) and not valor.strip()):
                raise DatoInvalido(f"El remito tiene que indicar {nombre}")
        if origen == destino:
            raise DatoInvalido("El origen y el destino del remito no pueden ser el mismo")
        self.id_remito = id_remito
        self.origen = origen
        self.destino = destino
        self.orden_id = orden_id  # orden de reposición de la que sale
        self.bultos = []  # Lista de Bulto
        self.estado = self.ABIERTO
        self.fecha = datetime.now()
        self.llegada_estimada = None  # día y hora en que se espera que llegue al local

    def _validar_abierto(self, accion):
        if self.estado != self.ABIERTO:
            raise TransicionDeEstadoInvalida(
                f"No se puede {accion} un remito en estado {self.estado}"
            )

    def agregar_bulto(self, bulto):
        self._validar_abierto("modificar")
        # Solo bultos que todavía no salieron del CD
        if bulto.estado not in ("PREPARADO", "PRECINTADO"):
            raise DatoInvalido(
                f"No se puede agregar un bulto en estado {bulto.estado}: ya salió del CD"
            )
        if bulto in self.bultos:
            raise DatoInvalido("El bulto ya está en el remito")
        self.bultos.append(bulto)

    def cerrar(self):
        self._validar_abierto("cerrar")
        if not self.bultos:
            raise DatoInvalido("No se puede cerrar un remito sin bultos")
        # Un bulto sin precinto no puede salir del CD
        if any(bulto.estado != "PRECINTADO" for bulto in self.bultos):
            raise DatoInvalido("Todos los bultos del remito tienen que estar precintados")
        self.estado = self.CERRADO

    def validar_llegada_estimada(self, llegada_estimada, ahora):
        if not isinstance(llegada_estimada, datetime):
            raise DatoInvalido("Indicá el día y la hora estimados de llegada al local")
        if llegada_estimada <= ahora:
            raise DatoInvalido("La llegada estimada tiene que ser posterior al despacho")
        if llegada_estimada > ahora + timedelta(days=self.MAXIMO_DIAS_DE_VIAJE):
            raise DatoInvalido(f"La llegada estimada no puede ser a más de {self.MAXIMO_DIAS_DE_VIAJE} días")

    def despachar(self, llegada_estimada, ahora=None):
        """Sale del CD: si todavía está abierto se cierra (eso valida que todos
        los bultos estén precintados) y cada bulto pasa a EN_TRANSITO. Se
        registra cuándo se espera que llegue (lo informa el CD al despachar).
        Se valida todo antes de cambiar algo."""
        self.validar_llegada_estimada(llegada_estimada, ahora or datetime.now())
        if self.estado == self.ABIERTO:
            self.cerrar()
        if self.estado != self.CERRADO:
            raise TransicionDeEstadoInvalida(f"No se puede despachar un remito en estado {self.estado}")
        for bulto in self.bultos:
            bulto.despachar()
        self.estado = self.EN_TRANSITO
        self.llegada_estimada = llegada_estimada

    def esta_demorado(self, ahora=None):
        """Sigue en camino y ya pasó la hora en que tenía que llegar."""
        return (self.estado == self.EN_TRANSITO and self.llegada_estimada is not None
                and (ahora or datetime.now()) > self.llegada_estimada)

    def registrar_verificacion(self):
        """Se llama cada vez que se verifica un bulto. Si ya no queda ninguno
        pendiente, el remito pasa a su estado final y devuelve True (es el
        momento de sumar el stock al local). Si quedan, devuelve False."""
        if self.estado != self.EN_TRANSITO:
            raise TransicionDeEstadoInvalida(f"No se puede verificar un remito en estado {self.estado}")
        if any(bulto.estado not in ESTADOS_FINALES for bulto in self.bultos):
            return False
        if all(bulto.habilita_venta() for bulto in self.bultos):
            self.estado = self.VERIFICADO
        else:
            self.estado = self.VERIFICADO_CON_RECHAZOS
        return True

    def bultos_verificados(self):
        # Polimorfismo del State: no se compara el texto del estado, se le pregunta
        return [bulto for bulto in self.bultos if bulto.habilita_venta()]

    def total_por_producto(self):
        # Lo que lleva el remito en total, para compararlo contra lo pedido
        totales = {}
        for bulto in self.bultos:
            for detalle in bulto.items:
                totales[detalle.producto] = totales.get(detalle.producto, 0) + detalle.cantidad
        return totales

@dataclass(frozen=True)
class DetalleBulto:
    """Una línea del bulto: qué producto lleva y cuántas unidades. Es inmutable,
    igual que el registro del historial. Para cambiar una cantidad se reemplaza
    la línea por otra."""
    producto: object
    cantidad: int

    def __post_init__(self):
        # Una línea con cantidad 0 no tiene sentido: el mínimo es 1
        _validar_entero(self.cantidad, "La cantidad", 1)