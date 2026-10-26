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
# Uso (desde tp-dao-tema3):
#   .venv\Scripts\python -m backend.datos.seed              carga solo si la base está vacía
#   .venv\Scripts\python -m backend.datos.seed --reiniciar  BORRA la base local y la vuelve a cargar
import sys
from datetime import datetime, timedelta

from backend.config import DB_PATH
from backend.dominio.stock import TipoMovimiento
from backend.persistencia.conexion import crear_tablas
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


# Llegada estimada de los envíos del seed: mañana a las 12
MANANA_AL_MEDIODIA = (datetime.now() + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)


def base_vacia():
    return not ProductoDAO().listar(solo_activos=False)


def cargar_datos_prueba():
    crear_tablas()
    if not base_vacia():
        print("La base ya tiene datos: no se cargó nada. Para empezar de cero usá --reiniciar.")
        return

    # ------------------------------------------------------------ Maestros
    categorias = CategoriaService()
    ids_categoria = {nombre: categorias.crear(nombre).id for nombre in ("Bebidas", "Almacén", "Limpieza", "Lácteos")}

    productos_service = ProductoService()
    p = {}  # código → id
    for codigo, nombre, categoria, precio, costo, minimo in PRODUCTOS:
        p[codigo] = productos_service.crear(codigo, nombre, ids_categoria[categoria], precio, costo, minimo).id

    proveedores = ProveedorService()
    for cuit, razon_social, telefono, email, prefijos in PROVEEDORES:
        proveedor = proveedores.crear(cuit, razon_social, telefono, email)
        for codigo, producto_id in p.items():
            if codigo.startswith(prefijos):
                proveedores.asignar_producto(proveedor.id, producto_id)

    ubicaciones = UbicacionService()
    cd = ubicaciones.crear("CD", "CD Central", "Av. Colón 1000").id
    centro = ubicaciones.crear("SUCURSAL", "Sucursal Centro", "San Martín 250").id
    norte = ubicaciones.crear("SUCURSAL", "Sucursal Norte", "Belgrano 1800").id
    sur = ubicaciones.crear("SUCURSAL", "Sucursal Sur", "Mitre 75").id

    # ------------------------------------------------------------- Usuarios
    ids_ubicacion = {"CD Central": cd, "Sucursal Centro": centro, "Sucursal Norte": norte, "Sucursal Sur": sur}
    usuarios = UsuarioService()
    u = {}  # usuario → id
    for perfil, nombre_usuario, nombre_completo, ubicacion in USUARIOS:
        u[nombre_usuario] = usuarios.crear(perfil, nombre_usuario, nombre_completo, ids_ubicacion.get(ubicacion),
                                           CLAVE_DE_PRUEBA).id
    del_local = {centro: u["centro"], norte: u["norte"], sur: u["sur"]}

    # --------------------------------------------------- Compras al CD
    stock = StockService()
    for codigo, producto_id in p.items():
        stock.ingresar(cd, producto_id, 300, TipoMovimiento.COMPRA, f"Factura compra inicial {codigo}",
                       usuario_id=u["cd.central"])

    # ------------------------------------------------------- Reposición
    reposicion = ReposicionService()
    recepcion = RecepcionService()
    pedido_centro = reposicion.crear_pedido(centro, [
        (p["BEB-001"], 60), (p["BEB-002"], 40), (p["ALM-001"], 50), (p["ALM-002"], 30),
        (p["LIM-001"], 20), (p["LAC-001"], 50), (p["LAC-002"], 20),
    ], u["centro"])
    pedido_norte = reposicion.crear_pedido(norte, [
        (p["BEB-001"], 30), (p["BEB-003"], 20), (p["ALM-003"], 15), (p["LIM-002"], 15),
    ], u["norte"])
    pedido_sur = reposicion.crear_pedido(sur, [(p["BEB-002"], 25), (p["LAC-001"], 40)], u["sur"])
    orden = reposicion.crear_orden([pedido_centro.id_pedido, pedido_norte.id_pedido, pedido_sur.id_pedido], u["cd.central"])

    def armar(destino, bultos, prefijo):
        remito = reposicion.crear_remito(orden.id_orden, destino, u["cd.central"])
        ids = []
        for i, items in enumerate(bultos, start=1):
            bulto = reposicion.agregar_bulto(remito.id_remito, [(p[codigo], cantidad) for codigo, cantidad in items],
                                             u["cd.central"])
            reposicion.precintar(bulto.id_bulto, f"{prefijo}-{i:03d}", u["cd.central"])
            ids.append((bulto.id_bulto, f"{prefijo}-{i:03d}"))
        reposicion.despachar(remito.id_remito, MANANA_AL_MEDIODIA, u["cd.central"])
        return ids

    # Centro: todo llega bien
    for bulto_id, precinto in armar(centro, [
        [("BEB-001", 60), ("BEB-002", 40)],
        [("ALM-001", 50), ("ALM-002", 30), ("LIM-001", 20)],
        [("LAC-001", 50), ("LAC-002", 20)],
    ], "PC"):
        recepcion.recibir(bulto_id, u["centro"])
        recepcion.verificar(bulto_id, precinto, True, u["centro"])

    # Norte: un bulto llega con el precinto roto → rechazo logístico (merma)
    norte_bultos = armar(norte, [
        [("BEB-001", 30), ("BEB-003", 20)],
        [("ALM-003", 15), ("LIM-002", 15)],
    ], "PN")
    (bueno, precinto_bueno), (roto, precinto_roto) = norte_bultos
    recepcion.recibir(bueno, u["norte"])
    recepcion.verificar(bueno, precinto_bueno, True, u["norte"])
    recepcion.recibir(roto, u["norte"])
    recepcion.verificar(roto, precinto_roto, False, u["norte"])

    # Sur: despachado y todavía en camino (para ver un remito En tránsito)
    armar(sur, [[("BEB-002", 25), ("LAC-001", 40)]], "PS")

    # ------------------------------------------------------------- Ventas
    ventas = VentasService()

    def vender(local, items, medio, entregado=None):
        return ventas.vender(local, items, medio, entregado, del_local[local])

    ventas_hechas = [
        vender(centro, [(p["BEB-001"], 6), (p["ALM-001"], 10)], "DEBITO"),
        vender(centro, [(p["LAC-001"], 12), (p["LAC-002"], 8)], "EFECTIVO", 40000),
        vender(centro, [(p["ALM-002"], 5), (p["LIM-001"], 3)], "CREDITO"),
        vender(centro, [(p["BEB-002"], 15), (p["BEB-001"], 20)], "TRANSFERENCIA"),
        vender(centro, [(p["LAC-001"], 30)], "EFECTIVO"),
        vender(norte, [(p["BEB-001"], 10), (p["BEB-003"], 4)], "DEBITO"),
        vender(norte, [(p["BEB-003"], 12)], "CREDITO"),
        vender(norte, [(p["BEB-001"], 8)], "EFECTIVO", 20000),
    ]
    # Devoluciones: solo de ventas registradas y de lo que se vendió
    ventas.devolver(ventas_hechas[1].id, [(p["LAC-002"], 2)], "Producto vencido", u["centro"])
    ventas.devolver(ventas_hechas[5].id, [(p["BEB-003"], 1)], "Envase dañado", u["norte"])

    print("Datos de prueba cargados:")
    print(f"  {len(PRODUCTOS)} productos, {len(PROVEEDORES)} proveedores, CD + 3 sucursales")
    print("  1 orden de reposición: Centro verificado, Norte con un bulto rechazado, Sur en tránsito")
    print(f"  {len(ventas_hechas)} ventas y 2 devoluciones")
    print(f"Usuarios (contraseña de todos: {CLAVE_DE_PRUEBA}):")
    for perfil, nombre_usuario, nombre_completo, ubicacion in USUARIOS:
        print(f"  {nombre_usuario:<11} {perfil:<9} {ubicacion or 'toda la red':<16} {nombre_completo}")


def reiniciar():
    # Borra SOLO la base local de desarrollo (está en .gitignore)
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"Base borrada: {DB_PATH}")


if __name__ == "__main__":
    if "--reiniciar" in sys.argv:
        reiniciar()
    cargar_datos_prueba()
