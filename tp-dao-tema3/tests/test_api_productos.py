# Tests de GET /productos con filtros contra la api real: los parámetros
# llegan al filtro, un valor sin sentido da 400, y filtrar por proveedor es
# solo para quien puede ver los proveedores (un local recibe 403). Usa la base
# temporal de conftest.py, compartida con otros tests de api: los nombres
# llevan "Filtro" para no chocar. Acá NO se prueban las reglas (están en
# test_reglas_producto.py).
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.servicios.maestros_service import CategoriaService, ProductoService, ProveedorService, UbicacionService
from backend.servicios.usuarios_service import UsuarioService

CLAVE = "secreta123"


@pytest.fixture(scope="module")
def api():
    categoria = CategoriaService().crear("Categoría Filtro")
    productos = ProductoService()
    barato = productos.crear("FIL-001", "Filtro Barato", categoria.id, 100, 50)
    caro = productos.crear("FIL-002", "Filtro Caro", categoria.id, 900, 500)
    proveedor = ProveedorService().crear("30-71234567-1", "Proveedor Filtro SA")
    ProveedorService().asignar_producto(proveedor.id, caro.id)
    local = UbicacionService().crear("SUCURSAL", "Local Filtro", "Calle F")

    usuarios = UsuarioService()
    usuarios.crear("ADMIN", "fil.admin", "Admin Filtro", None, CLAVE)
    usuarios.crear("SUCURSAL", "fil.local", "Local Filtro", local.id, CLAVE)
    cliente = TestClient(app)

    def token(nombre):
        return cliente.post("/auth/login", json={"nombre_usuario": nombre, "contrasena": CLAVE}).json()["token"]

    return {"cliente": cliente, "admin": token("fil.admin"), "local": token("fil.local"),
            "categoria": categoria.id, "proveedor": proveedor.id, "barato": barato.codigo, "caro": caro.codigo}


def productos(api, quien, **parametros):
    return api["cliente"].get("/productos", params=parametros, headers={"Authorization": f"Bearer {api[quien]}"})


def codigos(respuesta):
    return [p["codigo"] for p in respuesta.json()]


def test_filtrar_por_texto_categoria_y_precio(api):
    assert codigos(productos(api, "local", texto="filtro")) == ["FIL-001", "FIL-002"]
    assert codigos(productos(api, "local", categoria_id=api["categoria"], precio_desde=500)) == ["FIL-002"]
    assert codigos(productos(api, "local", texto="fil-00", precio_hasta=100)) == ["FIL-001"]


def test_un_rango_de_precio_al_reves_da_400(api):
    respuesta = productos(api, "admin", precio_desde=900, precio_hasta=100)
    assert respuesta.status_code == 400
    assert "«desde» no puede ser mayor" in respuesta.json()["detail"]


def test_el_administrador_filtra_por_proveedor(api):
    assert codigos(productos(api, "admin", proveedor_id=api["proveedor"])) == ["FIL-002"]


def test_un_local_no_puede_filtrar_por_proveedor(api):
    respuesta = productos(api, "local", proveedor_id=api["proveedor"])
    assert respuesta.status_code == 403
    assert respuesta.json()["detail"] == "Tu perfil no puede ver los proveedores"


def test_un_proveedor_que_no_existe_da_404(api):
    assert productos(api, "admin", proveedor_id=99999).status_code == 404


def test_sin_token_no_se_listan_productos(api):
    assert api["cliente"].get("/productos").status_code == 401
