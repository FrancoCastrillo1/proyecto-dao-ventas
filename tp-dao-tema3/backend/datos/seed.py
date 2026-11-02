# Datos de prueba: carga un escenario completo para probar el sistema y los
# reportes desde /docs o el front.
#
# Todo se carga A TRAVÉS DE LOS SERVICES (no con INSERT directos): así se
# respetan todas las reglas de negocio, cada unidad de stock deja su
# movimiento y cada bulto su historial. Si un dato violara una regla, el seed
# fallaría en vez de dejar la base inconsistente.
#
# Trae un usuario de cada perfil (ver USUARIOS), todos con la contraseña
# CLAVE_DE_PRUEBA, y cada operación queda hecha por quien corresponde.
#
# Para que los reportes y los tableros tengan qué mostrar, se cargan además
# DIAS_DE_HISTORIAL días de operación DE PRUEBA, hasta hoy (nunca a futuro):
# ventas a distintas horas, devoluciones, y los pedidos de reposición de cada
# local con su envío (el CD los consolida, arma los bultos, los despacha y el
# local los recibe al otro día; alguno llega demorado o con el precinto roto).
# Son inventados (con una semilla fija: siempre salen iguales) y solo existen
# en la base de desarrollo. Para fecharlos se atrasa el reloj del dominio
# (dominio/reloj.py) mientras se cargan; la api nunca lo hace.
#
# Uso (desde tp-dao-tema3):
#   .venv\Scripts\python -m backend.datos.seed              carga solo si la base está vacía
#   .venv\Scripts\python -m backend.datos.seed --reiniciar  BORRA la base local y la vuelve a cargar
import random
import sys
from datetime import datetime, time, timedelta

from backend.dominio.excepciones import StockInsuficiente
from backend.dominio.reloj import a_las
from backend.dominio.stock import TipoMovimiento
from backend.persistencia.conexion import BaseDeDatos
from backend.persistencia.dao_maestros import ProductoDAO
from backend.servicios.maestros_service import (
    CategoriaService, ProductoService, ProveedorService, UbicacionService,
)
from backend.servicios.recepcion_service import RecepcionService
from backend.servicios.reposicion_service import ReposicionService
from backend.servicios.stock_service import StockService
from backend.servicios.usuarios_service import UsuarioService
from backend.servicios.ventas_service import VentasService

# (código, nombre, categoría, precio, costo, stock mínimo)
PRODUCTOS = [
    ("BEB-001", "Gaseosa Cola 2.25L", "Bebidas", 2500, 1600, 20),
    ("BEB-002", "Agua Mineral 1.5L", "Bebidas", 1200, 650, 15),
    ("BEB-003", "Jugo de Naranja 1L", "Bebidas", 1800, 1100, 10),
    ("ALM-001", "Fideos Spaghetti 500g", "Almacén", 1500, 900, 25),
    ("ALM-002", "Arroz Largo Fino 1kg", "Almacén", 2100, 1300, 20),
    ("ALM-003", "Aceite de Girasol 1.5L", "Almacén", 4200, 2900, 10),
    ("LIM-001", "Lavandina 1L", "Limpieza", 1100, 600, 12),
    ("LIM-002", "Detergente 750ml", "Limpieza", 1900, 1150, 10),
    ("LAC-001", "Leche Entera 1L", "Lácteos", 1400, 950, 30),
    # En promoción por debajo del costo: el reporte de margen muestra la pérdida
    ("LAC-002", "Yogur Bebible 1L (promo)", "Lácteos", 1400, 1500, 8),
]

# (CUIT, razón social, teléfono, email, prefijos de código que provee)
PROVEEDORES = [
    ("20-12345678-6", "Distribuidora Sur SA", "11-4444-5555", "ventas@distsur.com", ("BEB",)),
    ("30-71234567-1", "Mayorista Norte SA", "11-5555-6666", "pedidos@mayoristanorte.com", ("ALM", "LIM")),
    ("27-34567890-0", "Láctea del Valle SRL", None, "comercial@lacteadelvalle.com", ("LAC", "BEB-003")),
]


# Solo para probar: en una instalación real cada uno elige la suya
CLAVE_DE_PRUEBA = "tpdao2026"

# (perfil, usuario, nombre completo, ubicación: None para el administrador)
USUARIOS = [
    ("ADMIN", "admin", "Dora Administradora", None),
    ("CD", "cd.central", "Carlos del CD", "CD Central"),
    ("SUCURSAL", "centro", "Lucía de Centro", "Sucursal Centro"),
    ("SUCURSAL", "norte", "Nico de Norte", "Sucursal Norte"),
    ("SUCURSAL", "sur", "Sofía de Sur", "Sucursal Sur"),
]

# ------------------------------------------------------- Historial de prueba
DIAS_DE_HISTORIAL = 90
SEMILLA = 2026                   # misma semilla → mismo historial cada vez
COMPRA_INICIAL = 1500            # unidades de cada producto que compra el CD antes de empezar

# Cuánto se elige cada producto en un ticket (lo más vendido, más seguido)
POPULARIDAD = {"BEB-001": 5, "BEB-002": 4, "LAC-001": 4, "ALM-001": 3, "BEB-003": 2, "ALM-002": 2,
               "LAC-002": 2, "LIM-001": 1.5, "ALM-003": 1, "LIM-002": 1}
# Tickets por día en cada local (antes de la tendencia y el día de la semana)
TICKETS_POR_DIA = {"Sucursal Centro": 5, "Sucursal Norte": 3.5, "Sucursal Sur": 2.5}
# Lunes a domingo: el fin de semana se vende más
SEGUN_EL_DIA = [0.9, 0.85, 0.9, 1.0, 1.25, 1.4, 0.8]
# Qué tan seguido se vende a cada hora (8 a 21): media mañana, mediodía y salida del trabajo
SEGUN_LA_HORA = {8: 1, 9: 2, 10: 4, 11: 5, 12: 4, 13: 3, 14: 1.5, 15: 1.5, 16: 2, 17: 3, 18: 5, 19: 5, 20: 3, 21: 1}
MEDIOS = {"EFECTIVO": 4, "DEBITO": 3, "TRANSFERENCIA": 2, "CREDITO": 1}
# Productos que un local dejó de vender hace tantos días (para ver stock parado)
DEJO_DE_VENDERSE = {("Sucursal Centro", "ALM-003"): 35, ("Sucursal Norte", "LIM-002"): 40,
                    ("Sucursal Sur", "ALM-003"): 50, ("Sucursal Norte", "LIM-001"): DIAS_DE_HISTORIAL + 1}

# Reposición: hasta cuántas unidades de cada producto quiere tener cada local,
# cada cuántos días pide y desde qué nivel pide (por debajo del 70 % de su nivel)
NIVEL_DEL_LOCAL = {"Sucursal Centro": 60, "Sucursal Norte": 45, "Sucursal Sur": 35}
PIDE_CADA = {"Sucursal Centro": 4, "Sucursal Norte": 5, "Sucursal Sur": 6}
PIDE_POR_DEBAJO_DE = 0.7
# Horarios del circuito: el local pide a la mañana, el CD prepara y despacha a
# la tarde, y llega al otro día (estimado al mediodía)
HORA_DEL_PEDIDO, HORA_DE_LA_ORDEN, HORA_DEL_DESPACHO, HORA_ESTIMADA = time(8, 30), time(14, 0), time(17, 0), time(12, 0)
DEMORADOS = 0.12                 # parte de los envíos que llega un día tarde
RECHAZADOS = 0.05                # parte de los bultos que llega con el precinto roto
# Devoluciones: parte de las ventas que se devuelve unos días después, y por qué
DEVUELTAS = 0.04
MOTIVOS = {"Producto vencido": 3, "Envase dañado": 3, "No era lo que buscaba": 2, "Se cobró de más": 1,
           "Falla de fábrica": 1}


def base_vacia():
    return not ProductoDAO().listar(solo_activos=False)


def a_la_hora(dia, hora, minutos=0):
    return datetime.combine(dia, hora) + timedelta(minutes=minutos)


class Escenario:
    """Lo que se va armando y los services con que se carga (para no pasar diez
    parámetros entre los pasos)."""

    def __init__(self):
        self.reposicion = ReposicionService()
        self.recepcion = RecepcionService()
        self.ventas = VentasService()
        self.stock = StockService()
        self.p = {}               # código → id del producto
        self.u = {}               # nombre de usuario → id
        self.locales = {}         # nombre del local → id
        self.del_local = {}       # id del local → id de su usuario
        self.cd = None
        self.precintos = 0        # para que cada precinto sea único


def cargar_datos_prueba():
    BaseDeDatos.instancia().crear_tablas()
    if not base_vacia():
        print("La base ya tiene datos: no se cargó nada. Para empezar de cero usá --reiniciar.")
        return

    ahora = datetime.now().replace(microsecond=0)
    inicio = ahora.date() - timedelta(days=DIAS_DE_HISTORIAL)
    e = Escenario()

    # Los maestros, las compras y el envío inicial, el día antes del historial
    with a_las(a_la_hora(inicio - timedelta(days=1), time(7, 0))):
        cargar_maestros(e)
        for codigo, producto_id in e.p.items():
            e.stock.ingresar(e.cd, producto_id, COMPRA_INICIAL, TipoMovimiento.COMPRA,
                             f"Factura compra inicial {codigo}", usuario_id=e.u["cd.central"])
    envio_inicial(e, inicio - timedelta(days=1))

    historial = cargar_historial(e, inicio, ahora)
    hoy = cargar_hoy(e)

    print("Datos de prueba cargados:")
    print(f"  {len(PRODUCTOS)} productos, {len(PROVEEDORES)} proveedores, CD + 3 sucursales")
    print(f"  {historial['ventas']} ventas DE PRUEBA de los últimos {DIAS_DE_HISTORIAL} días, hasta hoy (para los tableros)")
    print(f"  {historial['devoluciones']} devoluciones y {historial['pedidos']} pedidos de reposición en ese tiempo "
          f"({historial['rechazados']} bultos rechazados, {historial['demorados']} envíos demorados)")
    print(f"  Hoy: {hoy['ventas']} ventas, 2 devoluciones, un envío a Sur en camino, un pedido de Sur sin preparar")
    print("  y uno de Norte que el CD está armando")
    print(f"Usuarios (contraseña de todos: {CLAVE_DE_PRUEBA}):")
    for perfil, nombre_usuario, nombre_completo, ubicacion in USUARIOS:
        print(f"  {nombre_usuario:<11} {perfil:<9} {ubicacion or 'toda la red':<16} {nombre_completo}")


def cargar_maestros(e):
    categorias = CategoriaService()
    ids_categoria = {nombre: categorias.crear(nombre).id for nombre in ("Bebidas", "Almacén", "Limpieza", "Lácteos")}
    productos_service = ProductoService()
    for codigo, nombre, categoria, precio, costo, minimo in PRODUCTOS:
        e.p[codigo] = productos_service.crear(codigo, nombre, ids_categoria[categoria], precio, costo, minimo).id

    proveedores = ProveedorService()
    for cuit, razon_social, telefono, email, prefijos in PROVEEDORES:
        proveedor = proveedores.crear(cuit, razon_social, telefono, email)
        for codigo, producto_id in e.p.items():
            if codigo.startswith(prefijos):
                proveedores.asignar_producto(proveedor.id, producto_id)

    ubicaciones = UbicacionService()
    e.cd = ubicaciones.crear("CD", "CD Central", "Av. Colón 1000").id
    e.locales = {"Sucursal Centro": ubicaciones.crear("SUCURSAL", "Sucursal Centro", "San Martín 250").id,
                 "Sucursal Norte": ubicaciones.crear("SUCURSAL", "Sucursal Norte", "Belgrano 1800").id,
                 "Sucursal Sur": ubicaciones.crear("SUCURSAL", "Sucursal Sur", "Mitre 75").id}

    ids_ubicacion = {"CD Central": e.cd, **e.locales}
    usuarios = UsuarioService()
    for perfil, nombre_usuario, nombre_completo, ubicacion in USUARIOS:
        e.u[nombre_usuario] = usuarios.crear(perfil, nombre_usuario, nombre_completo, ids_ubicacion.get(ubicacion),
                                             CLAVE_DE_PRUEBA).id
    e.del_local = {e.locales["Sucursal Centro"]: e.u["centro"], e.locales["Sucursal Norte"]: e.u["norte"],
                   e.locales["Sucursal Sur"]: e.u["sur"]}


# ------------------------------------------------------------ El circuito
def bultos_por_categoria(items, e):
    """Lo que va a un local, en un bulto por familia de productos (como se arma
    en un depósito): bebidas, almacén y limpieza, lácteos."""
    codigo_de = {producto_id: codigo for codigo, producto_id in e.p.items()}
    grupos = {}
    for producto_id, cantidad in items:
        familia = {"BEB": 0, "ALM": 1, "LIM": 1, "LAC": 2}[codigo_de[producto_id][:3]]
        grupos.setdefault(familia, []).append((producto_id, cantidad))
    return [grupos[f] for f in sorted(grupos)]


def preparar_y_despachar(e, pedidos, dia, llegada_estimada):
    """El CD consolida los pedidos en una orden, arma un remito por local con sus
    bultos precintados y lo despacha. Devuelve {remito: [(bulto, precinto)]}."""
    cd = e.u["cd.central"]
    with a_las(a_la_hora(dia, HORA_DE_LA_ORDEN)):
        orden = e.reposicion.crear_orden([pedido.id_pedido for pedido in pedidos], cd)
    remitos = {}
    for minutos, pedido in enumerate(pedidos):
        with a_las(a_la_hora(dia, HORA_DE_LA_ORDEN, 20 + 10 * minutos)):
            remito = e.reposicion.crear_remito(orden.id_orden, pedido.local, cd)
            bultos = []
            for items in bultos_por_categoria([(d.producto, d.cantidad) for d in pedido.items], e):
                bulto = e.reposicion.agregar_bulto(remito.id_remito, items, cd)
                e.precintos += 1
                precinto = f"PR-{e.precintos:05d}"
                e.reposicion.precintar(bulto.id_bulto, precinto, cd)
                bultos.append((bulto.id_bulto, precinto))
        with a_las(a_la_hora(dia, HORA_DEL_DESPACHO, minutos)):
            e.reposicion.despachar(remito.id_remito, llegada_estimada, cd)
        remitos[(remito.id_remito, pedido.local)] = bultos
    return remitos


def recibir(e, local, bultos, momento, rotos=()):
    """El local recibe y verifica cada bulto (los de rotos, con el precinto roto)."""
    for i, (bulto_id, precinto) in enumerate(bultos):
        with a_las(momento + timedelta(minutes=5 * i)):
            e.recepcion.recibir(bulto_id, e.del_local[local])
        with a_las(momento + timedelta(minutes=15 + 5 * i)):
            e.recepcion.verificar(bulto_id, precinto, bulto_id not in rotos, e.del_local[local])


def envio_inicial(e, dia):
    """Cada local arranca con su nivel de todos los productos. A Norte le llega
    un bulto con el precinto roto: esa mercadería no entra (merma) y la vuelve a
    pedir en la próxima reposición."""
    pedidos = []
    for nombre, local in e.locales.items():
        with a_las(a_la_hora(dia, time(8, 0))):
            items = [(producto_id, NIVEL_DEL_LOCAL[nombre]) for producto_id in e.p.values()]
            pedidos.append(e.reposicion.crear_pedido(local, items, e.del_local[local]))
    remitos = preparar_y_despachar(e, pedidos, dia, a_la_hora(dia + timedelta(days=1), HORA_ESTIMADA))
    for (_, local), bultos in remitos.items():
        rotos = {bultos[1][0]} if local == e.locales["Sucursal Norte"] else set()
        recibir(e, local, bultos, a_la_hora(dia, time(19, 0)), rotos)


def pedido_de_reposicion(e, nombre, momento):
    """Lo que le falta al local para volver a su nivel, de lo que está por debajo
    del 70 %. Si no le falta nada, no pide."""
    local = e.locales[nombre]
    nivel = NIVEL_DEL_LOCAL[nombre]
    hay = {producto.id: stock.cantidad for producto, stock in e.stock.listar_por_ubicacion(local)}
    items = [(producto_id, nivel - hay.get(producto_id, 0)) for producto_id in e.p.values()
             if hay.get(producto_id, 0) < nivel * PIDE_POR_DEBAJO_DE]
    if not items:
        return None
    with a_las(momento):
        return e.reposicion.crear_pedido(local, items, e.del_local[local])


def cargar_historial(e, inicio, ahora):
    """Día por día, desde inicio hasta hoy (lo de hoy, solo hasta la hora
    actual): a la mañana llegan los envíos y los locales que les toca piden; se
    vende todo el día; a la tarde el CD prepara y despacha lo pedido. Al final,
    las devoluciones de algunas ventas. Las ventas venden un poco más a medida
    que pasan los días (para ver crecimiento contra el período anterior)."""
    azar = random.Random(SEMILLA)
    codigos, pesos = list(POPULARIDAD), list(POPULARIDAD.values())
    horas, pesos_hora = list(SEGUN_LA_HORA), list(SEGUN_LA_HORA.values())
    medios, pesos_medio = list(MEDIOS), list(MEDIOS.values())
    motivos, pesos_motivo = list(MOTIVOS), list(MOTIVOS.values())
    cuenta = {"ventas": 0, "devoluciones": 0, "pedidos": 0, "rechazados": 0, "demorados": 0}
    en_camino = []                # (cuándo llega, local, bultos)
    a_devolver = []               # (cuándo, venta, local, producto)

    for numero in range(DIAS_DE_HISTORIAL + 1):
        dia = inicio + timedelta(days=numero)

        # A la mañana: llega lo despachado
        for llegada, local, bultos in [envio for envio in en_camino if envio[0].date() == dia and envio[0] <= ahora]:
            rotos = {bulto for bulto, _ in bultos if azar.random() < RECHAZADOS}
            cuenta["rechazados"] += len(rotos)
            recibir(e, local, bultos, llegada, rotos)
            en_camino.remove((llegada, local, bultos))

        # Los locales que les toca, piden
        pedidos = []
        for orden_local, nombre in enumerate(e.locales):
            momento = a_la_hora(dia, HORA_DEL_PEDIDO, 10 * orden_local)
            if numero % PIDE_CADA[nombre] == orden_local % PIDE_CADA[nombre] and momento <= ahora:
                pedido = pedido_de_reposicion(e, nombre, momento)
                if pedido:
                    pedidos.append(pedido)
        cuenta["pedidos"] += len(pedidos)

        # Se vende todo el día
        tendencia = 0.75 + 0.4 * numero / DIAS_DE_HISTORIAL
        for nombre, local in e.locales.items():
            esperados = TICKETS_POR_DIA[nombre] * tendencia * SEGUN_EL_DIA[dia.weekday()]
            tickets = int(esperados) + (azar.random() < esperados % 1)
            momentos = sorted(a_la_hora(dia, time(azar.choices(horas, pesos_hora)[0], azar.randrange(60)))
                              for _ in range(tickets))
            for momento in momentos:
                dias_atras = (ahora.date() - dia).days
                elegidos = {c for c in azar.choices(codigos, pesos, k=azar.choice((1, 1, 2, 2, 3)))
                            if dias_atras >= DEJO_DE_VENDERSE.get((nombre, c), 0)}
                if not elegidos or momento > ahora:
                    continue
                items = [(e.p[c], azar.randint(1, 3)) for c in sorted(elegidos)]
                try:
                    venta = e.ventas.vender(local, items, azar.choices(medios, pesos_medio)[0], None,
                                            e.del_local[local], fecha=momento)
                except StockInsuficiente:
                    continue        # si un producto se agotó en ese local, ese ticket no se hace
                cuenta["ventas"] += 1
                if azar.random() < DEVUELTAS:
                    cuando = momento + timedelta(days=azar.randint(0, 3), hours=azar.randint(1, 5))
                    a_devolver.append((cuando, venta, local, azar.choice(items)[0],
                                       azar.choices(motivos, pesos_motivo)[0]))

        # A la tarde: el CD prepara y despacha lo que se pidió hoy
        despacho = a_la_hora(dia, HORA_DEL_DESPACHO)
        if pedidos and despacho <= ahora:
            estimada = a_la_hora(dia + timedelta(days=1), HORA_ESTIMADA)
            for (_, local), bultos in preparar_y_despachar(e, pedidos, dia, estimada).items():
                demorado = azar.random() < DEMORADOS
                cuenta["demorados"] += demorado
                llega = a_la_hora(dia + timedelta(days=2 if demorado else 1), time(azar.randint(9, 11), azar.randrange(60)))
                en_camino.append((llega, local, bultos))

    # Las devoluciones, en orden (solo las que ya pasaron)
    for cuando, venta, local, producto_id, motivo in sorted(a_devolver, key=lambda d: d[0]):
        if cuando <= ahora:
            with a_las(cuando):
                e.ventas.devolver(venta.id, [(producto_id, 1)], motivo, e.del_local[local])
            cuenta["devoluciones"] += 1
    return cuenta


def cargar_hoy(e):
    """Lo de este momento (con la hora real), para ver cada estado en las
    pantallas: ventas recién hechas, dos devoluciones, un envío a Sur en camino,
    un pedido de Sur sin preparar y uno de Norte que el CD está armando."""
    p, u = e.p, e.u
    centro, norte, sur = e.locales["Sucursal Centro"], e.locales["Sucursal Norte"], e.locales["Sucursal Sur"]
    manana_al_mediodia = (datetime.now() + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)

    # Sur: despachado y todavía en camino (para ver un remito En tránsito)
    pedido_sur = e.reposicion.crear_pedido(sur, [(p["BEB-002"], 25), (p["LAC-001"], 30)], u["sur"])
    orden = e.reposicion.crear_orden([pedido_sur.id_pedido], u["cd.central"])
    remito = e.reposicion.crear_remito(orden.id_orden, sur, u["cd.central"])
    bulto = e.reposicion.agregar_bulto(remito.id_remito, [(p["BEB-002"], 25), (p["LAC-001"], 30)], u["cd.central"])
    e.reposicion.precintar(bulto.id_bulto, "PS-HOY-001", u["cd.central"])
    e.reposicion.despachar(remito.id_remito, manana_al_mediodia, u["cd.central"])

    def vender(local, items, medio, entregado=None):
        return e.ventas.vender(local, items, medio, entregado, e.del_local[local])

    ventas_hechas = [
        vender(centro, [(p["BEB-001"], 3), (p["ALM-001"], 4)], "DEBITO"),
        vender(centro, [(p["LAC-001"], 4), (p["LAC-002"], 3)], "EFECTIVO", 20000),
        vender(centro, [(p["ALM-002"], 2), (p["LIM-001"], 1)], "CREDITO"),
        vender(centro, [(p["BEB-002"], 4), (p["BEB-001"], 2)], "TRANSFERENCIA"),
        vender(centro, [(p["LAC-001"], 3)], "EFECTIVO"),
        vender(norte, [(p["BEB-001"], 3), (p["BEB-003"], 2)], "DEBITO"),
        vender(norte, [(p["BEB-003"], 2)], "CREDITO"),
        vender(norte, [(p["BEB-001"], 2)], "EFECTIVO", 10000),
    ]
    # Devoluciones: solo de ventas registradas y de lo que se vendió
    e.ventas.devolver(ventas_hechas[1].id, [(p["LAC-002"], 2)], "Producto vencido", u["centro"])
    e.ventas.devolver(ventas_hechas[5].id, [(p["BEB-003"], 1)], "Envase dañado", u["norte"])

    # Pedidos en curso, para ver todos los estados en Abastecimiento
    e.reposicion.crear_pedido(sur, [(p["ALM-001"], 20), (p["LIM-001"], 10)], u["sur"])
    pedido_en_preparacion = e.reposicion.crear_pedido(norte, [(p["LAC-001"], 30), (p["BEB-002"], 20)], u["norte"])
    orden_en_curso = e.reposicion.crear_orden([pedido_en_preparacion.id_pedido], u["cd.central"])
    e.reposicion.crear_remito(orden_en_curso.id_orden, norte, u["cd.central"])
    return {"ventas": len(ventas_hechas)}


def reiniciar():
    # Borra SOLO la base local de desarrollo (está en .gitignore). Dónde está lo
    # sabe la única BaseDeDatos.
    ruta = BaseDeDatos.instancia().ruta
    if ruta.exists():
        ruta.unlink()
        print(f"Base borrada: {ruta}")


if __name__ == "__main__":
    if "--reiniciar" in sys.argv:
        reiniciar()
    cargar_datos_prueba()
