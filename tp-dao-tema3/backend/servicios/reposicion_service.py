# Casos de uso de reposición del lado del CD: un local pide, el CD consolida
# los pedidos en una orden, arma un remito por destino con sus bultos, los
# precinta y los despacha (ahí se descuenta el stock del CD).
# La recepción en el local NO va acá, va en recepcion_service.py.
# Cada operación recibe usuario_id (quién la hizo) y lo pasa al DAO; qué
# usuario puede hacer qué lo controla la api.
# Acá NO va SQL (usa dao_logistica) ni nada de endpoints.
from backend.dominio.excepciones import DatoInvalido, EntidadDuplicada, NoEncontrado, StockInsuficiente
from backend.dominio.logistica import Bulto, OrdenReposicion, PedidoReposicion, Remito
from backend.dominio.stock import TipoMovimiento
from backend.persistencia.dao_logistica import BultoDAO, OrdenDAO, PedidoDAO, RemitoDAO
from backend.persistencia.dao_maestros import ProductoDAO, UbicacionDAO
from backend.servicios.stock_service import StockService


class ReposicionService:
    def __init__(self, pedido_dao=None, orden_dao=None, remito_dao=None, bulto_dao=None,
                 producto_dao=None, ubicacion_dao=None, stock_service=None):
        self.pedido_dao = pedido_dao or PedidoDAO()
        self.orden_dao = orden_dao or OrdenDAO()
        self.remito_dao = remito_dao or RemitoDAO()
        self.bulto_dao = bulto_dao or BultoDAO()
        self.producto_dao = producto_dao or ProductoDAO()
        self.ubicacion_dao = ubicacion_dao or UbicacionDAO()
        self.stock_service = stock_service or StockService()

    # ---------------------------------------------------------- Validaciones

    def obtener_ubicacion(self, ubicacion_id):
        ubicacion = self.ubicacion_dao.obtener_por_id(ubicacion_id)
        if ubicacion is None:
            raise NoEncontrado(f"No se encontro la ubicación {ubicacion_id}")
        if not ubicacion.activo:
            raise DatoInvalido(f"La ubicación '{ubicacion.nombre}' está dada de baja")
        return ubicacion

    def validar_sucursal(self, sucursal_id):
        # Se pregunta por la capacidad (polimorfismo), no por el tipo
        sucursal = self.obtener_ubicacion(sucursal_id)
        if not sucursal.puede_recibir():
            raise DatoInvalido(f"'{sucursal.nombre}' no es una sucursal: no puede pedir ni recibir reposición")
        return sucursal

    def validar_items(self, items):
        """items: pares (producto_id, cantidad). Los productos tienen que
        existir y estar activos. Devuelve {producto_id: producto}."""
        if not items:
            raise DatoInvalido("Hay que indicar al menos un producto")
        productos = {}
        for producto_id, _ in items:
            producto = self.producto_dao.obtener_por_id(producto_id)
            if producto is None:
                raise NoEncontrado(f"No se encontro el producto {producto_id}")
            if not producto.activo:
                raise DatoInvalido(f"El producto '{producto.nombre}' está dado de baja")
            productos[producto_id] = producto
        return productos

    # ---------------------------------------------------------------- Pedidos

    def crear_pedido(self, sucursal_id, items, usuario_id=None):
        self.validar_sucursal(sucursal_id)
        self.validar_items(items)
        pedido = PedidoReposicion(None, sucursal_id)
        for producto_id, cantidad in items:
            pedido.agregar_item(producto_id, cantidad)
        with self.pedido_dao.transaccion() as cx:
            return self.pedido_dao.crear(cx, pedido, usuario_id)

    def obtener_pedido(self, id):
        pedido = self.pedido_dao.obtener(id)
        if pedido is None:
            raise NoEncontrado(f"No se encontro el pedido {id}")
        return pedido

    def listar_pedidos(self, sucursal_id=None, estado=None):
        return self.pedido_dao.listar(sucursal_id, estado)

    # ---------------------------------------------------------------- Órdenes

    def crear_orden(self, pedido_ids, usuario_id=None):
        """Consolida pedidos PENDIENTES en una orden del CD activo. La orden
        queda CERRADA: fija lo que el CD tiene que preparar."""
        if not pedido_ids:
            raise DatoInvalido("La orden tiene que consolidar al menos un pedido")
        # Cada lectura arma un objeto nuevo: el dominio no detectaría el mismo
        # pedido dos veces, por eso se controla acá con los ids
        if len(set(pedido_ids)) != len(pedido_ids):
            raise DatoInvalido("Hay pedidos repetidos en la lista")
        cd = self.ubicacion_dao.obtener_cd_activo()
        if cd is None:
            raise NoEncontrado("No hay un Centro de Distribución activo")

        orden = OrdenReposicion(None, cd.id)
        for pedido_id in pedido_ids:
            pedido = self.obtener_pedido(pedido_id)
            pedido.consolidar()  # el dominio rechaza si ya estaba consolidado
            orden.agregar_pedido(pedido)
        orden.cerrar()

        with self.orden_dao.transaccion() as cx:
            self.orden_dao.crear(cx, orden, usuario_id)
            for pedido in orden.pedidos:
                pedido.orden_id = orden.id_orden
                self.pedido_dao.actualizar(cx, pedido)
        return orden

    def obtener_orden(self, id):
        orden = self.orden_dao.obtener(id)
        if orden is None:
            raise NoEncontrado(f"No se encontro la orden {id}")
        return orden

    def listar_ordenes(self):
        return self.orden_dao.listar()

    # ---------------------------------------------------------------- Remitos

    def crear_remito(self, orden_id, destino_id, usuario_id=None):
        """Un remito por cada sucursal de la orden. Va del CD de la orden a una
        sucursal que haya pedido algo en esa orden."""
        orden = self.obtener_orden(orden_id)
        origen = self.obtener_ubicacion(orden.origen)
        if not origen.puede_despachar():
            raise DatoInvalido(f"'{origen.nombre}' no puede despachar mercadería")
        self.validar_sucursal(destino_id)
        if not any(pedido.local == destino_id for pedido in orden.pedidos):
            raise DatoInvalido(f"La sucursal {destino_id} no tiene pedidos en la orden {orden_id}")
        if self.remito_dao.obtener_por_orden_y_destino(orden_id, destino_id):
            raise EntidadDuplicada(f"Ya existe un remito de la orden {orden_id} para la sucursal {destino_id}")

        remito = Remito(None, orden.origen, destino_id, orden_id)
        with self.remito_dao.transaccion() as cx:
            return self.remito_dao.crear(cx, remito, usuario_id)

    def obtener_remito(self, id, cx=None):
        remito = self.remito_dao.obtener(id, cx)
        if remito is None:
            raise NoEncontrado(f"No se encontro el remito {id}")
        return remito

    def listar_remitos(self, destino_id=None, estado=None):
        return self.remito_dao.listar(destino_id, estado)

    def pedido_del_destino(self, remito):
        """Lo que pidió la sucursal destino en la orden del remito: {producto: cantidad}."""
        orden = self.obtener_orden(remito.orden_id)
        totales = {}
        for pedido in orden.pedidos:
            if pedido.local == remito.destino:
                for detalle in pedido.items:
                    totales[detalle.producto] = totales.get(detalle.producto, 0) + detalle.cantidad
        return totales

    # ----------------------------------------------------------------- Bultos

    def agregar_bulto(self, remito_id, items, usuario_id=None):
        """Arma un bulto nuevo (Preparado) dentro del remito. No se puede
        mandar algo que la sucursal no pidió ni más de lo que pidió."""
        productos = self.validar_items(items)
        remito = self.obtener_remito(remito_id)

        bulto = Bulto(None)
        for producto_id, cantidad in items:
            bulto.agregar_item(producto_id, cantidad)

        pedido = self.pedido_del_destino(remito)
        ya_enviado = remito.total_por_producto()
        for detalle in bulto.items:
            nombre = productos[detalle.producto].nombre
            pedido_total = pedido.get(detalle.producto, 0)
            if pedido_total == 0:
                raise DatoInvalido(f"'{nombre}' no fue pedido por la sucursal destino")
            if ya_enviado.get(detalle.producto, 0) + detalle.cantidad > pedido_total:
                raise DatoInvalido(
                    f"'{nombre}': se pidieron {pedido_total} y con este bulto se mandarían "
                    f"{ya_enviado.get(detalle.producto, 0) + detalle.cantidad}"
                )

        remito.agregar_bulto(bulto)  # el dominio valida que el remito siga abierto
        bulto.remito_id = remito.id_remito
        with self.bulto_dao.transaccion() as cx:
            return self.bulto_dao.guardar(cx, bulto, usuario_id)

    def obtener_bulto(self, id):
        bulto = self.bulto_dao.obtener(id)
        if bulto is None:
            raise NoEncontrado(f"No se encontro el bulto {id}")
        return bulto

    def precintar(self, bulto_id, nro_precinto, usuario_id=None):
        bulto = self.obtener_bulto(bulto_id)
        otro = self.bulto_dao.obtener_por_precinto((nro_precinto or "").strip())
        if otro and otro.id_bulto != bulto_id:
            raise EntidadDuplicada(f"El precinto '{nro_precinto.strip()}' ya está usado en el bulto {otro.id_bulto}")
        bulto.precintar(nro_precinto)  # el State valida el estado y que no esté vacío
        with self.bulto_dao.transaccion() as cx:
            return self.bulto_dao.guardar(cx, bulto, usuario_id)

    # --------------------------------------------------------------- Despacho

    def despachar(self, remito_id, llegada_estimada=None, usuario_id=None):
        """Sale el remito del CD: todos los bultos pasan a EN_TRANSITO y se
        descuenta del CD lo que llevan (decisión del grupo: al despachar, no al
        preparar). Si un producto no alcanza no se despacha nada. El CD informa
        cuándo se espera que llegue (el dominio la exige y la valida)."""
        with self.remito_dao.transaccion() as cx:
            remito = self.obtener_remito(remito_id, cx)
            remito.despachar(llegada_estimada)  # valida la llegada, que esté abierto y todo precintado
            for bulto in remito.bultos:
                for detalle in bulto.items:
                    try:
                        self.stock_service.egresar(
                            remito.origen, detalle.producto, detalle.cantidad, TipoMovimiento.DESPACHO,
                            f"Remito {remito.id_remito} · Bulto {bulto.id_bulto}", cx=cx, usuario_id=usuario_id,
                        )
                    except StockInsuficiente as error:
                        nombre = self.producto_dao.obtener_por_id(detalle.producto).nombre
                        raise StockInsuficiente(f"{nombre} (bulto {bulto.id_bulto}): {error}") from error
            return self.remito_dao.guardar(cx, remito, usuario_id)
