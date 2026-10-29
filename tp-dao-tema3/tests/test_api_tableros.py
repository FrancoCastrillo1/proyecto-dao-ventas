# Tests de permisos de los tableros por la api: cada perfil ve solo los suyos
# y un local ve solo lo de su local, aunque pida otro (el back lo controla, no
# alcanza con esconderlo en el front). Las cuentas se prueban en
# test_tableros.py. La base es la temporal de conftest.py, compartida con otros
# módulos: por eso no se comparan totales de toda la red.
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.dominio.excepciones import NoEncontrado
from backend.dominio.stock import TipoMovimiento
from backend.main import app
from backend.servicios.maestros_service import CategoriaService, ProductoService, UbicacionService
from backend.servicios.recepcion_service import RecepcionService
from backend.servicios.reposicion_service import ReposicionService
from backend.servicios.stock_service import StockService
from backend.servicios.usuarios_service import UsuarioService
from backend.servicios.ventas_service import VentasService

CLAVE = "secreta123"


@pytest.fixture(scope="module")
def red():
    """Un CD, dos locales con stock recibido, una venta en cada local, un pedido
    de cada local y un usuario de cada perfil."""
    ubicaciones = UbicacionService()
    # Hay un solo CD activo: si otro módulo de la base compartida ya lo creó, se usa ese
    try:
        cd = ubicaciones.obtener_cd()
    except NoEncontrado:
        cd = ubicaciones.crear("CD", "CD Tableros", "Ruta 2")
    local_a = ubicaciones.crear("SUCURSAL", "Local Tableros A", "Calle A")
    local_b = ubicaciones.crear("SUCURSAL", "Local Tableros B", "Calle B")
    categoria = CategoriaService().crear("Categoría Tableros")
    producto = ProductoService().crear("TAB-001", "Producto Tableros", categoria.id, 100, 60, 0)
    StockService().ingresar(cd.id, producto.id, 100, TipoMovimiento.COMPRA, "stock inicial")

    repo, recepcion = ReposicionService(), RecepcionService()
    pedidos = [repo.crear_pedido(local.id, [(producto.id, 10)]).id_pedido for local in (local_a, local_b)]
    orden = repo.crear_orden(pedidos)
    for local, precinto in ((local_a, "TAB-PA"), (local_b, "TAB-PB")):
        remito = repo.crear_remito(orden.id_orden, local.id)
        bulto = repo.agregar_bulto(remito.id_remito, [(producto.id, 10)])
        repo.precintar(bulto.id_bulto, precinto)
        repo.despachar(remito.id_remito, datetime.now() + timedelta(days=1))
        recepcion.recibir(bulto.id_bulto)
        recepcion.verificar(bulto.id_bulto, precinto, True)
        VentasService().vender(local.id, [(producto.id, 2)], "DEBITO")

    usuarios = UsuarioService()
    usuarios.crear("ADMIN", "tab.admin", "Admin", None, CLAVE)
    usuarios.crear("CD", "tab.cd", "Del CD", cd.id, CLAVE)
    usuarios.crear("SUCURSAL", "tab.a", "Del Local A", local_a.id, CLAVE)

    cliente = TestClient(app)
    tokens = {}
    for perfil, nombre in (("admin", "tab.admin"), ("cd", "tab.cd"), ("a", "tab.a")):
        respuesta = cliente.post("/auth/login", json={"nombre_usuario": nombre, "contrasena": CLAVE})
        assert respuesta.status_code == 200, respuesta.text
        tokens[perfil] = respuesta.json()["token"]
    return {"cliente": cliente, "tokens": tokens, "cd": cd.id, "a": local_a.id, "b": local_b.id}


def pedir(red, quien, ruta):
    return red["cliente"].get(ruta, headers={"Authorization": f"Bearer {red['tokens'][quien]}"})


@pytest.mark.parametrize("ruta, quienes_pueden", [
    ("/tableros/ejecutivo", {"admin"}),
    ("/tableros/ventas", {"admin", "a"}),
    ("/tableros/productos", {"admin", "cd", "a"}),
    ("/tableros/abastecimiento", {"admin", "cd", "a"}),
])
def test_cada_perfil_ve_sus_tableros(red, ruta, quienes_pueden):
    for quien in ("admin", "cd", "a"):
        respuesta = pedir(red, quien, ruta)
        assert respuesta.status_code == (200 if quien in quienes_pueden else 403), (quien, respuesta.text)


def test_el_ejecutivo_explica_quien_lo_ve(red):
    assert "administrador" in pedir(red, "a", "/tableros/ejecutivo").json()["detail"]


def test_solo_el_administrador_aparece_con_la_capacidad(red):
    assert "ve_resultados_empresa" in pedir(red, "admin", "/auth/yo").json()["capacidades"]
    assert "ve_resultados_empresa" not in pedir(red, "cd", "/auth/yo").json()["capacidades"]


def test_un_local_no_ve_los_tableros_de_otro(red):
    for ruta in (f"/tableros/ventas?sucursal_id={red['b']}", f"/tableros/productos?ubicacion_id={red['b']}",
                 f"/tableros/abastecimiento?sucursal_id={red['b']}"):
        respuesta = pedir(red, "a", ruta)
        assert respuesta.status_code == 403, ruta
        assert "no es de tu local" in respuesta.json()["detail"]


def test_un_local_ve_solo_lo_suyo_sin_pedirlo(red):
    ventas = pedir(red, "a", "/tableros/ventas").json()
    assert [c["categoria"] for c in ventas["categorias"]] == ["Categoría Tableros"]
    assert ventas["indicadores"][1]["valor"] == 1                     # un ticket: el de su local
    ranking = pedir(red, "a", "/tableros/productos").json()["ranking"]
    assert [f["codigo"] for f in ranking] == ["TAB-001"]
    abastecimiento = pedir(red, "a", "/tableros/abastecimiento").json()
    assert {p["sucursal"] for p in abastecimiento["pedidos"]} == {"Local Tableros A"}
    assert pedir(red, "a", "/tableros/abastecimiento").json()["demanda"] is None   # lo de toda la red, no


def test_el_cd_ve_el_inventario_pero_no_los_margenes(red):
    datos = pedir(red, "cd", "/tableros/productos").json()
    assert datos["matriz"] is None and datos["ranking"] is None
    assert all("Margen" not in i["titulo"] for i in datos["indicadores"])
    assert pedir(red, "admin", "/tableros/productos").json()["matriz"] is not None
    assert pedir(red, "cd", "/tableros/abastecimiento").json()["demanda"] is not None


@pytest.mark.parametrize("ruta, quien", [
    ("/tableros/ejecutivo", "admin"), ("/tableros/ventas", "a"),
    ("/tableros/productos", "cd"), ("/tableros/abastecimiento", "a"),
])
def test_cada_tablero_se_descarga_en_pdf(red, ruta, quien):
    respuesta = pedir(red, quien, f"{ruta}?formato=pdf")
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["content-type"] == "application/pdf"
    assert "reporte-tablero-" in respuesta.headers["content-disposition"]


def test_el_pdf_respeta_los_permisos(red):
    assert pedir(red, "cd", "/tableros/ejecutivo?formato=pdf").status_code == 403
    assert pedir(red, "a", f"/tableros/ventas?sucursal_id={red['b']}&formato=pdf").status_code == 403
    assert pedir(red, "admin", "/tableros/ventas?formato=excel").status_code == 422


def test_el_administrador_filtra_un_local_y_elige_la_comparacion(red):
    datos = pedir(red, "admin", f"/tableros/ejecutivo?sucursal_id={red['b']}&comparar=anio").json()
    assert [l["sucursal"] for l in datos["locales"]] == ["Local Tableros B"]
    assert datos["periodo"]["comparar"] == "anio"


@pytest.mark.parametrize("ruta", ["/tableros/ejecutivo?comparar=semana", "/tableros/ventas?desde=2026-10-10&hasta=2026-10-01"])
def test_parametros_invalidos(red, ruta):
    assert pedir(red, "admin", ruta).status_code in (400, 422)
