# Tests de la api con un cliente de cada perfil (administrador, CD y dos
# locales): sin token no se entra, cada perfil hace solo lo suyo, un local no
# toca lo de otro local (403 con mensaje claro), el local de un pedido o una
# venta sale del usuario y no del formulario, y queda grabado quién hizo cada
# operación. La base es la temporal de conftest.py (TP_DAO_DB), compartida
# por este módulo. Acá NO se prueban las reglas del negocio: eso ya lo
# prueban los tests de cada service.
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.config import DB_PATH
from backend.main import app
from backend.persistencia.conexion import get_conexion
from backend.servicios.maestros_service import CategoriaService, ProductoService, UbicacionService
from backend.servicios.stock_service import StockService
from backend.dominio.stock import TipoMovimiento
from backend.servicios.usuarios_service import UsuarioService

CLAVE = "secreta123"


@pytest.fixture(scope="module")
def red():
    """Un CD, dos locales, un producto con stock en el CD y un usuario de cada perfil."""
    ubicaciones = UbicacionService()
    cd = ubicaciones.crear("CD", "CD Permisos", "Ruta 1")
    local_a = ubicaciones.crear("SUCURSAL", "Local Permisos A", "Calle A")
    local_b = ubicaciones.crear("SUCURSAL", "Local Permisos B", "Calle B")
    categoria = CategoriaService().crear("Categoría Permisos")
    producto = ProductoService().crear("PER-001", "Producto Permisos", categoria.id, 100, 60, 0)
    StockService().ingresar(cd.id, producto.id, 500, TipoMovimiento.COMPRA, "stock inicial")

    usuarios = UsuarioService()
    usuarios.crear("ADMIN", "per.admin", "Admin", None, CLAVE)
    usuarios.crear("CD", "per.cd", "Del CD", cd.id, CLAVE)
    usuarios.crear("SUCURSAL", "per.a", "Del Local A", local_a.id, CLAVE)
    usuarios.crear("SUCURSAL", "per.b", "Del Local B", local_b.id, CLAVE)

    cliente = TestClient(app)
    tokens = {}
    for perfil, nombre in (("admin", "per.admin"), ("cd", "per.cd"), ("a", "per.a"), ("b", "per.b")):
        respuesta = cliente.post("/auth/login", json={"nombre_usuario": nombre, "contrasena": CLAVE})
        assert respuesta.status_code == 200, respuesta.text
        tokens[perfil] = respuesta.json()["token"]
    return {"cliente": cliente, "tokens": tokens, "cd": cd.id, "a": local_a.id, "b": local_b.id,
            "producto": producto.id, "categoria": categoria.id}


def pedir(red, quien, metodo, ruta, **kwargs):
    headers = {"Authorization": f"Bearer {red['tokens'][quien]}"} if quien else {}
    return red["cliente"].request(metodo, ruta, headers=headers, **kwargs)


def quien_hizo(tabla, id):
    with get_conexion(DB_PATH) as cx:
        fila = cx.execute(
            f"SELECT u.nombre_usuario FROM {tabla} t JOIN usuarios u ON u.id = t.usuario_id WHERE t.id = ?", (id,)
        ).fetchone()
    return fila[0] if fila else None


# ------------------------------------------------------------ Autenticación

def test_sin_token_no_se_entra(red):
    respuesta = pedir(red, None, "GET", "/productos")
    assert respuesta.status_code == 401
    assert "entrar" in respuesta.json()["detail"]


def test_un_token_inventado_no_sirve(red):
    respuesta = red["cliente"].get("/productos", headers={"Authorization": "Bearer inventado"})
    assert respuesta.status_code == 401


def test_login_incorrecto(red):
    respuesta = red["cliente"].post("/auth/login", json={"nombre_usuario": "per.a", "contrasena": "otra-clave"})
    assert respuesta.status_code == 401
    assert respuesta.json()["detail"] == "Usuario o contraseña incorrectos"


def test_yo_dice_quien_soy_y_que_puedo_hacer(red):
    yo = pedir(red, "a", "GET", "/auth/yo").json()
    assert (yo["nombre_usuario"], yo["perfil"], yo["ubicacion_id"]) == ("per.a", "SUCURSAL", red["a"])
    assert set(yo["capacidades"]) == {"puede_pedir_reposicion", "puede_recibir", "puede_vender", "ve_ventas"}
    assert "contrasena" not in yo and "hash_contrasena" not in yo


def test_logout_invalida_el_token(red):
    token = red["cliente"].post("/auth/login", json={"nombre_usuario": "per.b", "contrasena": CLAVE}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert red["cliente"].post("/auth/logout", headers=headers).status_code == 204
    assert red["cliente"].get("/auth/yo", headers=headers).status_code == 401


# ------------------------------------------------- Cada perfil hace lo suyo

@pytest.mark.parametrize("quien, permitido", [("admin", True), ("cd", False), ("a", False)])
def test_los_maestros_los_cambia_solo_el_administrador(red, quien, permitido):
    respuesta = pedir(red, quien, "POST", "/categorias", json={"nombre": f"Nueva de {quien}"})
    assert respuesta.status_code == (201 if permitido else 403)
    if not permitido:
        assert respuesta.json()["detail"] == "Solo un administrador puede cambiar los datos maestros y los usuarios"


@pytest.mark.parametrize("quien", ["admin", "cd", "a"])
def test_los_maestros_los_consultan_todos(red, quien):
    assert pedir(red, quien, "GET", "/productos").status_code == 200
    assert pedir(red, quien, "GET", "/ubicaciones").status_code == 200


@pytest.mark.parametrize("quien, permitido", [("admin", True), ("cd", True), ("a", False)])
def test_los_proveedores_los_ven_el_administrador_y_el_cd(red, quien, permitido):
    assert pedir(red, quien, "GET", "/proveedores").status_code == (200 if permitido else 403)


@pytest.mark.parametrize("quien, permitido", [("admin", True), ("cd", False), ("a", False)])
def test_los_usuarios_los_maneja_el_administrador(red, quien, permitido):
    assert pedir(red, quien, "GET", "/usuarios").status_code == (200 if permitido else 403)


@pytest.mark.parametrize("quien", ["admin", "a"])
def test_solo_el_cd_compra(red, quien):
    respuesta = pedir(red, quien, "POST", "/stock/ingresar", json={"producto_id": red["producto"], "cantidad": 5})
    assert respuesta.status_code == 403
    assert "Centro de Distribución" in respuesta.json()["detail"]


def test_la_compra_entra_al_cd_del_usuario_y_registra_quien_fue(red):
    respuesta = pedir(red, "cd", "POST", "/stock/ingresar",
                      json={"producto_id": red["producto"], "cantidad": 5, "ubicacion_id": red["a"]})
    assert respuesta.status_code == 201
    assert respuesta.json()["ubicacion_id"] == red["cd"]   # el ubicacion_id del formulario no cuenta
    with get_conexion(DB_PATH) as cx:
        usuario = cx.execute(
            "SELECT u.nombre_usuario FROM movimientos_stock m JOIN usuarios u ON u.id = m.usuario_id "
            "WHERE m.tipo = 'COMPRA' ORDER BY m.id DESC LIMIT 1"
        ).fetchone()[0]
    assert usuario == "per.cd"


@pytest.mark.parametrize("quien", ["admin", "cd"])
def test_solo_un_local_pide_y_vende(red, quien):
    items = [{"producto_id": red["producto"], "cantidad": 1}]
    assert pedir(red, quien, "POST", "/pedidos", json={"items": items}).status_code == 403
    venta = pedir(red, quien, "POST", "/ventas", json={"items": items, "medio_pago": "DEBITO"})
    assert venta.status_code == 403
    assert venta.json()["detail"] == "Solo un local vende y hace devoluciones"


@pytest.mark.parametrize("quien", ["admin", "a"])
def test_solo_el_cd_prepara_envios(red, quien):
    assert pedir(red, quien, "GET", "/ordenes").status_code == 403
    assert pedir(red, quien, "POST", "/ordenes", json={"pedido_ids": [1]}).status_code == 403


# ------------------------------------------------------------- Pertenencia

def test_un_local_ve_su_stock_pero_no_el_de_otro(red):
    assert pedir(red, "a", "GET", f"/stock/{red['a']}").status_code == 200
    respuesta = pedir(red, "a", "GET", f"/stock/{red['b']}")
    assert respuesta.status_code == 403
    assert respuesta.json()["detail"] == "Ese stock no es de tu local"


@pytest.mark.parametrize("quien", ["admin", "cd"])
def test_el_administrador_y_el_cd_ven_el_stock_de_toda_la_red(red, quien):
    assert pedir(red, quien, "GET", f"/stock/{red['b']}").status_code == 200


def test_las_ventas_las_ve_el_administrador_pero_no_el_cd(red):
    assert pedir(red, "admin", "GET", f"/caja/{red['b']}").status_code == 200
    assert pedir(red, "admin", "GET", "/reportes/ventas").status_code == 200
    for ruta in (f"/caja/{red['b']}", "/ventas", "/reportes/ventas", "/reportes/productos-mas-vendidos"):
        respuesta = pedir(red, "cd", "GET", ruta)
        assert respuesta.status_code == 403, ruta
        assert "no ve las ventas" in respuesta.json()["detail"]
    assert pedir(red, "cd", "GET", "/reportes/mermas").status_code == 200   # los de logística, sí


def test_un_local_no_ve_reportes_ni_caja_de_otro(red):
    assert pedir(red, "a", "GET", f"/reportes/ventas?sucursal_id={red['b']}").status_code == 403
    assert pedir(red, "a", "GET", f"/caja/{red['b']}").status_code == 403
    assert pedir(red, "a", "GET", "/reportes/ventas").status_code == 200   # sin filtro: solo lo suyo
    assert pedir(red, "a", "GET", f"/reportes/devoluciones?sucursal_id={red['b']}").status_code == 403


@pytest.mark.parametrize("quien, permitido", [("admin", True), ("cd", True), ("a", False)])
def test_los_mas_pedidos_los_ven_el_cd_y_el_administrador(red, quien, permitido):
    # Es la demanda de toda la red: le sirve al que abastece, no a un local
    respuesta = pedir(red, quien, "GET", "/reportes/productos-mas-pedidos")
    assert (respuesta.status_code == 200) is permitido
    if not permitido:
        assert "toda la red" in respuesta.json()["detail"]


@pytest.mark.parametrize("quien, permitido", [("admin", True), ("a", True), ("cd", False)])
def test_las_devoluciones_las_ven_el_local_y_el_administrador(red, quien, permitido):
    assert (pedir(red, quien, "GET", "/reportes/devoluciones").status_code == 200) is permitido


@pytest.mark.parametrize("ruta", [
    "/reportes/ventas", "/reportes/productos-mas-vendidos", "/reportes/existencias", "/reportes/mermas",
    "/reportes/tiempos-transito", "/reportes/devoluciones",
])
def test_cada_reporte_se_descarga_en_pdf(red, ruta):
    respuesta = pedir(red, "a", "GET", f"{ruta}?formato=pdf")
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "application/pdf"
    assert respuesta.headers["content-disposition"].startswith('attachment; filename="reporte-')
    assert respuesta.content.startswith(b"%PDF")


def test_el_pdf_respeta_los_permisos_y_el_formato_tiene_que_ser_valido(red):
    assert pedir(red, "cd", "GET", "/reportes/ventas?formato=pdf").status_code == 403
    assert pedir(red, "cd", "GET", "/reportes/productos-mas-pedidos?formato=pdf").status_code == 200
    assert pedir(red, "a", "GET", "/reportes/ventas?formato=excel").status_code == 422


# ------------------------------- Circuito completo con quién hizo cada cosa

def test_circuito_completo_cada_uno_en_lo_suyo(red):
    item = [{"producto_id": red["producto"], "cantidad": 3}]

    # El local A pide (aunque el formulario diga otro local, cuenta el suyo)
    pedido = pedir(red, "a", "POST", "/pedidos", json={"sucursal_id": red["b"], "items": item}).json()
    assert pedido["sucursal_id"] == red["a"]
    assert quien_hizo("pedidos_reposicion", pedido["id"]) == "per.a"

    # El local B no ve ese pedido, ni en el listado ni por id
    assert all(p["sucursal_id"] == red["b"] for p in pedir(red, "b", "GET", "/pedidos").json())
    assert pedir(red, "b", "GET", f"/pedidos/{pedido['id']}").json()["detail"] == "Ese pedido no es de tu local"

    # El CD consolida, arma el remito y el bulto, precinta y despacha
    orden = pedir(red, "cd", "POST", "/ordenes", json={"pedido_ids": [pedido["id"]]}).json()
    remito = pedir(red, "cd", "POST", "/remitos", json={"orden_id": orden["id"], "destino_id": red["a"]}).json()
    bulto = pedir(red, "cd", "POST", f"/remitos/{remito['id']}/bultos", json={"items": item}).json()
    assert pedir(red, "cd", "POST", f"/bultos/{bulto['id']}/precintar", json={"nro_precinto": "PER-P1"}).status_code == 200
    manana = (datetime.now() + timedelta(days=1)).isoformat(timespec="minutes")
    despacho = pedir(red, "cd", "POST", f"/remitos/{remito['id']}/despachar", json={"llegada_estimada": manana})
    assert despacho.status_code == 200
    assert despacho.json()["llegada_estimada"].startswith(manana) and not despacho.json()["demorado"]
    assert quien_hizo("ordenes_reposicion", orden["id"]) == "per.cd"
    assert quien_hizo("remitos", remito["id"]) == "per.cd"

    # El local B no puede recibir un bulto que va al local A
    ajeno = pedir(red, "b", "POST", f"/bultos/{bulto['id']}/recibir")
    assert ajeno.status_code == 403
    assert ajeno.json()["detail"] == "Ese bulto no es de tu local"
    assert pedir(red, "b", "GET", f"/remitos/{remito['id']}").status_code == 403

    # El remito en PDF lo baja el local destino (y el CD), no otro local
    pdf = pedir(red, "a", "GET", f"/remitos/{remito['id']}/remito.pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert 'filename="remito-' in pdf.headers["content-disposition"]
    assert pedir(red, "cd", "GET", f"/remitos/{remito['id']}/remito.pdf").status_code == 200
    assert pedir(red, "b", "GET", f"/remitos/{remito['id']}/remito.pdf").status_code == 403

    # El local A lo recibe y lo verifica: el stock entra a su local
    assert pedir(red, "a", "POST", f"/bultos/{bulto['id']}/recibir").status_code == 200
    verificacion = pedir(red, "a", "POST", f"/bultos/{bulto['id']}/verificar",
                         json={"nro_leido": "PER-P1", "intacto": True}).json()
    assert verificacion["stock_ingresado"]

    # El historial del bulto dice quién hizo cada cambio de estado
    with get_conexion(DB_PATH) as cx:
        historial = cx.execute(
            "SELECT h.estado_nuevo, u.nombre_usuario FROM historial_bultos h "
            "JOIN usuarios u ON u.id = h.usuario_id WHERE h.bulto_id = ? ORDER BY h.id", (bulto["id"],)
        ).fetchall()
    assert [tuple(f) for f in historial] == [
        ("PRECINTADO", "per.cd"), ("EN_TRANSITO", "per.cd"), ("RECIBIDO", "per.a"), ("VERIFICADO", "per.a"),
    ]

    # El local A vende en su local; el B no puede devolverle esa venta
    venta = pedir(red, "a", "POST", "/ventas", json={"items": [{"producto_id": red["producto"], "cantidad": 2}],
                                                     "medio_pago": "DEBITO"}).json()
    assert venta["sucursal_id"] == red["a"]
    assert quien_hizo("ventas", venta["id"]) == "per.a"
    devolucion = {"items": [{"producto_id": red["producto"], "cantidad": 1}], "motivo": "Fallado"}
    assert pedir(red, "b", "POST", f"/ventas/{venta['id']}/devoluciones", json=devolucion).json()["detail"] == \
        "Esa venta no es de tu local"
    hecha = pedir(red, "a", "POST", f"/ventas/{venta['id']}/devoluciones", json=devolucion).json()
    assert quien_hizo("devoluciones", hecha["id"]) == "per.a"
