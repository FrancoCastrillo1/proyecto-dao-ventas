# Tests del paso 6:
# - Llegada estimada del envío: el dominio la exige al despachar y la valida
#   (futura, a no más de 30 días), sabe si el envío viene demorado, el DAO la
#   guarda y la base no deja despachar sin ella (trigger).
# - Bandeja de tareas: cada usuario ve lo que le toca según sus capacidades
#   (CD: preparar; local: recibir, verificar y reponer).
# Acá NO se prueba la api (salvo GET /tareas al final, con su propio cliente).
import sqlite3
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from backend.dominio.excepciones import DatoInvalido
from backend.dominio.logistica import Bulto, Remito
from backend.dominio.stock import TipoMovimiento
from backend.dominio.usuarios import UsuarioAdministrador, UsuarioCD, UsuarioSucursal
from backend.persistencia.conexion import columnas_de, crear_tablas, get_conexion
from backend.persistencia.dao_logistica import BultoDAO, OrdenDAO, PedidoDAO, RemitoDAO
from backend.persistencia.dao_maestros import CategoriaDAO, ProductoDAO, UbicacionDAO
from backend.persistencia.dao_stock import StockDAO
from backend.servicios.maestros_service import CategoriaService, ProductoService, UbicacionService
from backend.servicios.recepcion_service import RecepcionService
from backend.servicios.reposicion_service import ReposicionService
from backend.servicios.stock_service import StockService
from backend.servicios.tareas_service import TareasService

AHORA = datetime(2026, 10, 23, 10, 0)


def remito_precintado():
    remito = Remito(1, origen=1, destino=2)
    bulto = Bulto(1)
    bulto.agregar_item(5, 3)
    bulto.precintar("P-1")
    remito.agregar_bulto(bulto)
    return remito


# =========================================== Llegada estimada en el dominio

def test_despachar_registra_la_llegada_estimada():
    remito = remito_precintado()
    remito.despachar(AHORA + timedelta(hours=20), ahora=AHORA)
    assert (remito.estado, remito.llegada_estimada) == ("EN_TRANSITO", AHORA + timedelta(hours=20))


@pytest.mark.parametrize("llegada, mensaje", [
    (None, "Indicá el día y la hora"),
    ("mañana", "Indicá el día y la hora"),
    (AHORA, "posterior al despacho"),
    (AHORA - timedelta(hours=1), "posterior al despacho"),
    (AHORA + timedelta(days=31), "más de 30 días"),
])
def test_llegadas_estimadas_invalidas_no_despachan_nada(llegada, mensaje):
    remito = remito_precintado()
    with pytest.raises(DatoInvalido, match=mensaje):
        remito.despachar(llegada, ahora=AHORA)
    assert remito.estado == "ABIERTO"                      # se valida antes de cambiar algo
    assert remito.bultos[0].estado == "PRECINTADO"


def test_un_envio_esta_demorado_si_paso_la_hora_y_sigue_en_camino():
    remito = remito_precintado()
    llegada = AHORA + timedelta(hours=5)
    remito.despachar(llegada, ahora=AHORA)
    assert not remito.esta_demorado(ahora=llegada)
    assert remito.esta_demorado(ahora=llegada + timedelta(minutes=1))
    remito.estado = Remito.VERIFICADO                       # ya llegó: no está demorado
    assert not remito.esta_demorado(ahora=llegada + timedelta(days=2))


# ===================================================== Escenario con base

@pytest.fixture
def e(tmp_path):
    """Un CD con stock, dos locales con stock bajo el mínimo y los services."""
    db = tmp_path / "test.db"
    crear_tablas(db)
    categoria = CategoriaService(CategoriaDAO(db)).crear("Bebidas")
    productos = ProductoService(ProductoDAO(db))
    coca = productos.crear("BEB-1", "Coca", categoria.id, 1000, 600, stock_minimo=10)
    agua = productos.crear("BEB-2", "Agua", categoria.id, 500, 200, stock_minimo=5)
    jugo = productos.crear("BEB-3", "Jugo", categoria.id, 800, 400, stock_minimo=0)
    ubicaciones = UbicacionService(UbicacionDAO(db))
    cd = ubicaciones.crear("CD", "CD Central", "Ruta 9")
    centro = ubicaciones.crear("SUCURSAL", "Local Centro", "Calle 1")
    norte = ubicaciones.crear("SUCURSAL", "Local Norte", "Calle 2")
    stock = StockService(StockDAO(db), ProductoDAO(db), UbicacionDAO(db))
    for producto in (coca, agua, jugo):
        stock.ingresar(cd.id, producto.id, 100, TipoMovimiento.COMPRA, "Factura 1")
    stock.ingresar(centro.id, coca.id, 4, TipoMovimiento.RECEPCION, "Bulto viejo")   # bajo el mínimo (10)
    stock.ingresar(centro.id, agua.id, 9, TipoMovimiento.RECEPCION, "Bulto viejo")   # sobre el mínimo (5)
    repo = ReposicionService(PedidoDAO(db), OrdenDAO(db), RemitoDAO(db), BultoDAO(db),
                             ProductoDAO(db), UbicacionDAO(db), stock)
    recepcion = RecepcionService(BultoDAO(db), RemitoDAO(db), stock)
    reloj = SimpleNamespace(ahora=datetime.now())
    tareas = TareasService(PedidoDAO(db), RemitoDAO(db), StockDAO(db), UbicacionDAO(db), reloj=lambda: reloj.ahora)
    return SimpleNamespace(db=db, coca=coca, agua=agua, jugo=jugo, cd=cd, centro=centro, norte=norte, repo=repo,
                           recepcion=recepcion, tareas=tareas, reloj=reloj,
                           cd_usuario=UsuarioCD("ana", "Ana", cd.id),
                           del_centro=UsuarioSucursal("beto", "Beto", centro.id),
                           del_norte=UsuarioSucursal("carla", "Carla", norte.id))


def remito_para(e, destino, bultos=1, precintar=True):
    pedido = e.repo.crear_pedido(destino.id, [(e.agua.id, 2 * bultos)])
    orden = e.repo.crear_orden([pedido.id_pedido])
    remito = e.repo.crear_remito(orden.id_orden, destino.id)
    for i in range(bultos):
        bulto = e.repo.agregar_bulto(remito.id_remito, [(e.agua.id, 2)])
        if precintar:
            e.repo.precintar(bulto.id_bulto, f"P-{remito.id_remito}-{i}")
    return remito.id_remito


def titulos(tareas):
    return [t.titulo for t in tareas]


# ========================================= Llegada estimada en la persistencia

def test_la_llegada_estimada_se_guarda_y_vuelve(e):
    remito_id = remito_para(e, e.centro)
    llegada = (datetime.now() + timedelta(days=1)).replace(microsecond=0)
    e.repo.despachar(remito_id, llegada)
    assert e.repo.obtener_remito(remito_id).llegada_estimada == llegada


def test_el_service_no_despacha_sin_llegada(e):
    remito_id = remito_para(e, e.centro)
    with pytest.raises(DatoInvalido, match="Indicá el día y la hora"):
        e.repo.despachar(remito_id)
    assert e.repo.obtener_remito(remito_id).estado == "ABIERTO"


def test_la_base_no_deja_pasar_a_en_transito_sin_llegada(e):
    remito_id = remito_para(e, e.centro)
    with get_conexion(e.db) as cx, pytest.raises(sqlite3.IntegrityError, match="sin la llegada estimada"):
        cx.execute("UPDATE remitos SET estado = 'EN_TRANSITO' WHERE id = ?", (remito_id,))   # salteando el service


def test_migra_remitos_sin_la_columna(tmp_path):
    ruta = tmp_path / "vieja.db"
    with sqlite3.connect(ruta) as cx:
        cx.execute("CREATE TABLE remitos (id INTEGER PRIMARY KEY AUTOINCREMENT, orden_id INTEGER, origen_id INTEGER, "
                   "destino_id INTEGER, fecha TEXT, estado TEXT, usuario_id INTEGER)")
    crear_tablas(ruta)
    with get_conexion(ruta) as cx:
        assert "llegada_estimada" in columnas_de(cx, "remitos")


# ============================================================ Bandeja: CD

def test_el_cd_ve_lo_que_tiene_que_preparar(e):
    e.repo.crear_pedido(e.norte.id, [(e.coca.id, 5)])                            # pendiente
    sin_bultos = e.repo.crear_remito(
        e.repo.crear_orden([e.repo.crear_pedido(e.centro.id, [(e.agua.id, 1)]).id_pedido]).id_orden, e.centro.id,
    ).id_remito
    para_precintar = remito_para(e, e.norte, bultos=2, precintar=False)
    para_despachar = remito_para(e, e.centro)

    assert titulos(e.tareas.para(e.cd_usuario)) == [
        "Preparar 1 pedido de locales",
        f"Armar los bultos del remito #{sin_bultos}",
        f"Precintar 2 bultos del remito #{para_precintar}",
        f"Despachar el remito #{para_despachar}",
    ]


def test_el_cd_no_ve_tareas_de_local_ni_el_administrador_ninguna(e):
    remito_id = remito_para(e, e.centro)
    e.repo.despachar(remito_id, datetime.now() + timedelta(days=1))
    assert all(t.tipo not in ("recibir", "verificar", "reponer") for t in e.tareas.para(e.cd_usuario))
    assert e.tareas.para(UsuarioAdministrador("dora", "Dora")) == []


# ========================================================= Bandeja: local

def test_el_local_ve_lo_que_le_llega_y_lo_que_falta_verificar(e):
    remito_id = remito_para(e, e.centro, bultos=2)
    e.repo.despachar(remito_id, datetime.now() + timedelta(days=1))
    tareas = e.tareas.para(e.del_centro)
    assert f"Recibir el envío #{remito_id} (2 bultos)" in titulos(tareas)

    primero = e.repo.obtener_remito(remito_id).bultos[0]
    e.recepcion.recibir(primero.id_bulto)
    tareas = titulos(e.tareas.para(e.del_centro))
    assert f"Recibir el envío #{remito_id} (1 bulto)" in tareas
    assert f"Verificar 1 bulto del envío #{remito_id}" in tareas
    assert not any("envío" in t for t in titulos(e.tareas.para(e.del_norte)))   # el otro local no lo ve


def test_un_envio_demorado_sale_primero_y_marcado(e):
    remito_id = remito_para(e, e.centro)
    llegada = datetime.now() + timedelta(hours=2)
    e.repo.despachar(remito_id, llegada)
    e.reloj.ahora = llegada + timedelta(hours=1)
    primera = e.tareas.para(e.del_centro)[0]
    assert primera.urgente and primera.tipo == "recibir"
    assert primera.detalle.startswith("Demorado: llega")


def test_reponer_trae_lo_que_falta_para_el_minimo(e):
    reponer = next(t for t in e.tareas.para(e.del_centro) if t.tipo == "reponer")
    # Coca: hay 4 y el mínimo es 10. El agua está bien; el jugo no tiene mínimo.
    assert reponer.titulo == "Pedir 1 producto bajo el mínimo"
    assert reponer.items == ((e.coca.id, 6),)
    assert (reponer.pantalla, reponer.accion) == ("logistica", "Pedir")


def test_lo_que_ya_se_pidio_no_se_vuelve_a_sugerir(e):
    e.repo.crear_pedido(e.centro.id, [(e.coca.id, 6)])
    assert all(t.tipo != "reponer" for t in e.tareas.para(e.del_centro))


# ================================================================== API

def test_get_tareas_devuelve_las_del_usuario():
    from fastapi.testclient import TestClient

    from backend.main import app
    from backend.servicios.usuarios_service import UsuarioService
    local = UbicacionService().crear("SUCURSAL", "Local Tareas", "Calle T")
    UsuarioService().crear("SUCURSAL", "tar.local", "Local Tareas", local.id, "secreta123")
    cliente = TestClient(app)
    assert cliente.get("/tareas").status_code == 401
    token = cliente.post("/auth/login", json={"nombre_usuario": "tar.local", "contrasena": "secreta123"}).json()["token"]
    respuesta = cliente.get("/tareas", headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code == 200
    assert isinstance(respuesta.json(), list)


# ============================================================ Remito en PDF

def documentos_de(e):
    from backend.persistencia.dao_ventas import VentaDAO
    from backend.servicios.comprobantes_service import ComprobantesService
    return ComprobantesService(VentaDAO(e.db), UbicacionDAO(e.db), ProductoDAO(e.db), RemitoDAO(e.db))


def test_el_remito_se_descarga_recien_despachado(e):
    from backend.dominio.documentos import ContextoDocumento, DatosComercio, RemitoDocumento
    remito_id = remito_para(e, e.centro)
    abierto = e.repo.obtener_remito(remito_id)
    contexto = ContextoDocumento(DatosComercio("Comercio", "30-71111111-1", "Calle"), "CD Central", "Ruta 9", None)
    with pytest.raises(DatoInvalido, match="una vez despachado"):
        RemitoDocumento(abierto, contexto, "Local Centro", "Calle 1")


def test_el_remito_lista_cada_bulto_con_su_precinto(e):
    remito_id = remito_para(e, e.centro, bultos=2)
    llegada = (datetime.now() + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
    e.repo.despachar(remito_id, llegada)
    remito = e.repo.obtener_remito(remito_id)

    from backend.dominio.documentos import ContextoDocumento, DatosComercio, RemitoDocumento
    contexto = ContextoDocumento(DatosComercio("Comercio", "30-71111111-1", "Calle"), "CD Central", "Ruta 9", "Carlos",
                                 {e.agua.id: "Agua"})
    contenido = RemitoDocumento(remito, contexto, "Local Centro", "Calle 1").armar()
    assert contenido.columnas == ("Producto", "Cant.", "Bulto", "Precinto")      # gancho redefinido
    assert [(r.descripcion, r.cantidad, r.precio_unitario, r.importe) for r in contenido.renglones] == [
        ("Agua", 2, f"#{b.id_bulto}", b.nro_precinto) for b in remito.bultos]
    assert [(t.etiqueta, t.importe) for t in contenido.totales] == [("Bultos", 2), ("Unidades", 4)]
    assert contenido.notas[0] == "Destino: Local Centro · Calle 1"
    assert contenido.notas[1] == f"Llegada estimada: {llegada:%d/%m/%Y %H:%M}"
    assert contenido.notas[-1] == "Preparó: Carlos"                               # el otro gancho
    assert contenido.nombre_archivo == f"remito-{e.cd.id:04d}-{remito_id:08d}.pdf"


def test_el_pdf_del_remito_tiene_los_precintos(e):
    remito_id = remito_para(e, e.centro)
    e.repo.despachar(remito_id, datetime.now() + timedelta(days=1))
    documentos = documentos_de(e)
    nombre, contenido = documentos.remito(documentos.obtener_remito(remito_id))
    assert nombre.startswith("remito-") and contenido.startswith(b"%PDF")
    precinto = e.repo.obtener_remito(remito_id).bultos[0].nro_precinto
    assert precinto.encode("latin-1") in contenido
    assert b"Local Centro" in contenido and b"Precinto" in contenido
