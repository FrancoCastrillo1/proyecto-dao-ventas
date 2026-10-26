# Bandeja de tareas de Inicio: qué tiene pendiente el usuario que entró. Cada
# grupo de tareas depende de una CAPACIDAD del usuario (polimorfismo de
# Usuario), nunca de su perfil con un if:
# - puede_preparar_envios (CD): pedidos sin preparar, remitos para armar,
#   precintar o despachar.
# - puede_recibir (local): envíos en camino a su local y bultos para verificar.
# - puede_pedir_reposicion (local): productos bajo el mínimo que todavía no pidió.
# Cada tarea dice a qué pantalla lleva; "reponer" trae lo que conviene pedir.
# Acá NO va SQL (usa los DAO) ni nada de HTTP.
from dataclasses import dataclass, field
from datetime import datetime

from backend.persistencia.dao_logistica import PedidoDAO, RemitoDAO
from backend.persistencia.dao_maestros import UbicacionDAO
from backend.persistencia.dao_stock import StockDAO


@dataclass(frozen=True)
class Tarea:
    tipo: str                 # para el ícono en el front
    titulo: str
    detalle: str
    pantalla: str             # a dónde lleva el botón
    accion: str               # el texto del botón
    urgente: bool = False     # ej: un envío demorado
    items: tuple = field(default_factory=tuple)   # (producto_id, cantidad) para precargar un pedido


def plural(cantidad, singular, plural_):
    return f"{cantidad} {singular if cantidad == 1 else plural_}"


class TareasService:
    def __init__(self, pedido_dao=None, remito_dao=None, stock_dao=None, ubicacion_dao=None, reloj=datetime.now):
        self.pedido_dao = pedido_dao or PedidoDAO()
        self.remito_dao = remito_dao or RemitoDAO(self.pedido_dao.db_path)
        self.stock_dao = stock_dao or StockDAO(self.pedido_dao.db_path)
        self.ubicacion_dao = ubicacion_dao or UbicacionDAO(self.pedido_dao.db_path)
        self.reloj = reloj   # los tests lo cambian para probar las demoras

    def para(self, usuario):
        tareas = []
        if usuario.puede_preparar_envios():
            tareas += self.preparar_envios()
        if usuario.puede_recibir():
            tareas += self.recibir(usuario.ubicacion_id)
        if usuario.puede_pedir_reposicion():
            tareas += self.reponer(usuario.ubicacion_id)
        # Lo urgente primero; el resto, en el orden del circuito
        return sorted(tareas, key=lambda t: not t.urgente)

    def nombre_local(self, ubicacion_id):
        ubicacion = self.ubicacion_dao.obtener_por_id(ubicacion_id)
        return ubicacion.nombre if ubicacion else f"Local {ubicacion_id}"

    # ------------------------------------------------------------------- CD
    def preparar_envios(self):
        tareas = []
        pendientes = self.pedido_dao.listar(estado="PENDIENTE")
        if pendientes:
            locales = sorted({self.nombre_local(p.local) for p in pendientes})
            tareas.append(Tarea("pedidos", f"Preparar {plural(len(pendientes), 'pedido', 'pedidos')} de locales",
                                ", ".join(locales), "logistica", "Preparar"))
        for remito in self.remito_dao.listar(estado="ABIERTO"):
            destino = self.nombre_local(remito.destino)
            sin_precintar = sum(1 for b in remito.bultos if b.estado == "PREPARADO")
            if not remito.bultos:
                tareas.append(Tarea("armar", f"Armar los bultos del remito #{remito.id_remito}", destino,
                                    "logistica", "Armar"))
            elif sin_precintar:
                tareas.append(Tarea("precintar", f"Precintar {plural(sin_precintar, 'bulto', 'bultos')} del remito "
                                    f"#{remito.id_remito}", destino, "logistica", "Precintar"))
            else:
                tareas.append(Tarea("despachar", f"Despachar el remito #{remito.id_remito}",
                                    f"{destino} · {plural(len(remito.bultos), 'bulto', 'bultos')} precintados",
                                    "logistica", "Despachar"))
        return tareas

    # ----------------------------------------------------- Local: lo que llega
    def recibir(self, local_id):
        tareas = []
        ahora = self.reloj()
        for remito in self.remito_dao.listar(destino_id=local_id, estado="EN_TRANSITO"):
            en_camino = sum(1 for b in remito.bultos if b.estado == "EN_TRANSITO")
            recibidos = sum(1 for b in remito.bultos if b.estado == "RECIBIDO")
            llegada = (f"llega {remito.llegada_estimada:%d/%m %H:%M}" if remito.llegada_estimada
                       else "sin llegada estimada")
            demorado = remito.esta_demorado(ahora)
            if en_camino:
                tareas.append(Tarea(
                    "recibir", f"Recibir el envío #{remito.id_remito} ({plural(en_camino, 'bulto', 'bultos')})",
                    f"Demorado: {llegada}" if demorado else llegada.capitalize(),
                    "logistica", "Recibir", urgente=demorado,
                ))
            if recibidos:
                tareas.append(Tarea("verificar", f"Verificar {plural(recibidos, 'bulto', 'bultos')} del envío "
                                    f"#{remito.id_remito}", "Revisá el precinto antes de que entre al stock",
                                    "logistica", "Verificar"))
        return tareas

    # ------------------------------------------------ Local: qué conviene pedir
    def reponer(self, local_id):
        # Lo que ya está en un pedido pendiente no se vuelve a sugerir
        ya_pedido = {d.producto for p in self.pedido_dao.listar(sucursal_id=local_id, estado="PENDIENTE")
                     for d in p.items}
        faltantes = [(producto, stock) for producto, stock in self.stock_dao.listar_por_ubicacion(local_id)
                     if producto.activo and stock.esta_bajo_minimo() and producto.id not in ya_pedido]
        if not faltantes:
            return []
        nombres = ", ".join(producto.nombre for producto, _ in faltantes[:3])
        if len(faltantes) > 3:
            nombres += f" y {len(faltantes) - 3} más"
        return [Tarea(
            "reponer", f"Pedir {plural(len(faltantes), 'producto', 'productos')} bajo el mínimo", nombres,
            "logistica", "Pedir", items=tuple((producto.id, stock.faltante_para_el_minimo()) for producto, stock in faltantes),
        )]
