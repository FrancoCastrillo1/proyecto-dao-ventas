# Tests de la descarga de comprobantes y notas de crédito por la api: el local
# baja los suyos (un PDF con el nombre de archivo correcto), otro local recibe
# 403 y quien ve toda la red los puede bajar. Usa la base temporal de
# conftest.py, compartida con otros tests de api: los nombres llevan "Docs"
# para no chocar. Acá NO se prueba qué dice el documento (test_comprobantes.py).
import pytest
from fastapi.testclient import TestClient

from backend.dominio.stock import TipoMovimiento
from backend.main import app
from backend.servicios.maestros_service import CategoriaService, ProductoService, UbicacionService
from backend.servicios.stock_service import StockService
from backend.servicios.usuarios_service import UsuarioService

CLAVE = "secreta123"


@pytest.fixture(scope="module")
def api():
    categoria = CategoriaService().crear("Categoría Docs")
    producto = ProductoService().crear("DOC-001", "Producto Docs", categoria.id, 1000, 500)
    ubicaciones = UbicacionService()
    local_a = ubicaciones.crear("SUCURSAL", "Local Docs A", "Calle A")
    local_b = ubicaciones.crear("SUCURSAL", "Local Docs B", "Calle B")
    StockService().ingresar(local_a.id, producto.id, 20, TipoMovimiento.RECEPCION, "Bulto de prueba")

    usuarios = UsuarioService()
    usuarios.crear("SUCURSAL", "doc.a", "Ana Docs", local_a.id, CLAVE)
    usuarios.crear("SUCURSAL", "doc.b", "Beto Docs", local_b.id, CLAVE)
    usuarios.crear("ADMIN", "doc.admin", "Admin Docs", None, CLAVE)
    cliente = TestClient(app)
    tokens = {}
    for quien in ("doc.a", "doc.b", "doc.admin"):
        tokens[quien] = cliente.post("/auth/login", json={"nombre_usuario": quien, "contrasena": CLAVE}).json()["token"]

    def pedir(quien, metodo, ruta, **kwargs):
        return cliente.request(metodo, ruta, headers={"Authorization": f"Bearer {tokens[quien]}"}, **kwargs)

    venta = pedir("doc.a", "POST", "/ventas", json={"items": [{"producto_id": producto.id, "cantidad": 3}],
                                                     "medio_pago": "DEBITO"}).json()
    devolucion = pedir("doc.a", "POST", f"/ventas/{venta['id']}/devoluciones",
                       json={"items": [{"producto_id": producto.id, "cantidad": 1}], "motivo": "Fallado"}).json()
    return {"pedir": pedir, "venta": venta, "devolucion": devolucion}


def test_el_local_baja_el_comprobante_de_su_venta(api):
    respuesta = api["pedir"]("doc.a", "GET", f"/ventas/{api['venta']['id']}/comprobante.pdf")
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "application/pdf"
    assert f'filename="comprobante-{api["venta"]["comprobante"]}.pdf"' in respuesta.headers["content-disposition"]
    assert respuesta.content.startswith(b"%PDF")
    assert b"Ana Docs" in respuesta.content            # quién atendió


def test_la_devolucion_sale_con_su_nota_de_credito_y_se_descarga(api):
    devolucion = api["devolucion"]
    assert devolucion["nota_credito"].endswith("-00000001")
    respuesta = api["pedir"]("doc.a", "GET",
                             f"/ventas/{api['venta']['id']}/devoluciones/{devolucion['id']}/nota-credito.pdf")
    assert respuesta.status_code == 200
    assert f'filename="nota-credito-{devolucion["nota_credito"]}.pdf"' in respuesta.headers["content-disposition"]
    assert b"Fallado" in respuesta.content


def test_otro_local_no_puede_bajar_los_documentos(api):
    venta_id = api["venta"]["id"]
    for ruta in (f"/ventas/{venta_id}/comprobante.pdf",
                 f"/ventas/{venta_id}/devoluciones/{api['devolucion']['id']}/nota-credito.pdf"):
        respuesta = api["pedir"]("doc.b", "GET", ruta)
        assert respuesta.status_code == 403
        assert respuesta.json()["detail"] == "Esa venta no es de tu local"


def test_quien_ve_toda_la_red_puede_bajarlos(api):
    assert api["pedir"]("doc.admin", "GET", f"/ventas/{api['venta']['id']}/comprobante.pdf").status_code == 200


@pytest.mark.parametrize("ruta", ["/ventas/99999/comprobante.pdf", "devolucion-ajena"])
def test_lo_que_no_existe_da_404(api, ruta):
    if ruta == "devolucion-ajena":
        ruta = f"/ventas/{api['venta']['id']}/devoluciones/99999/nota-credito.pdf"
    assert api["pedir"]("doc.a", "GET", ruta).status_code == 404
