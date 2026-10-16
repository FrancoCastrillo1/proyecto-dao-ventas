# Tests del maestro Proveedor: validación del CUIT (dígito verificador) y datos
# de contacto en el dominio; CUIT duplicado y la relación muchos a muchos con
# Producto en el service, contra un SQLite temporal por test (tmp_path).
# Acá NO se prueba la api.
import pytest

from backend.dominio.excepciones import DatoInvalido, EntidadDuplicada, NoEncontrado
from backend.dominio.maestros import Proveedor, cuit_es_valido
from backend.persistencia.conexion import crear_tablas
from backend.persistencia.dao_maestros import CategoriaDAO, ProductoDAO, ProveedorDAO
from backend.servicios.maestros_service import CategoriaService, ProductoService, ProveedorService

# CUIT con dígito verificador correcto
CUIT_A = "20-12345678-6"
CUIT_B = "30-71234567-1"


# ------------------------------------------------------------------ Dominio

@pytest.mark.parametrize("cuit", ["20123456786", "30712345671", "27345678900"])
def test_cuit_validos(cuit):
    assert cuit_es_valido(cuit)


@pytest.mark.parametrize("cuit", ["20123456785", "2012345678", "201234567866", "2012345678X", ""])
def test_cuit_invalidos(cuit):
    assert not cuit_es_valido(cuit)


def test_el_cuit_se_guarda_sin_guiones_y_se_muestra_formateado():
    p = Proveedor(" 20-12345678-6 ", "Distribuidora Sur SA")
    assert p.cuit == "20123456786"
    assert p.cuit_formateado == "20-12345678-6"


@pytest.mark.parametrize("cuit", ["20-12345678-5", "123", None, ""])
def test_cuit_invalido_es_dato_invalido(cuit):
    with pytest.raises(DatoInvalido):
        Proveedor(cuit, "Distribuidora Sur SA")


@pytest.mark.parametrize("razon_social", ["", "   ", None, "R" * 101])
def test_razon_social_invalida(razon_social):
    with pytest.raises(DatoInvalido):
        Proveedor(CUIT_A, razon_social)


def test_contacto_es_opcional_y_vacio_queda_en_none():
    p = Proveedor(CUIT_A, "Distribuidora Sur SA", telefono="  ", email="")
    assert p.telefono is None
    assert p.email is None


def test_email_se_normaliza_en_minusculas():
    assert Proveedor(CUIT_A, "Sur", email=" Ventas@Sur.COM ").email == "ventas@sur.com"


@pytest.mark.parametrize("email", ["sin-arroba.com", "a@b", "a @b.com", "a@@b.com"])
def test_email_invalido(email):
    with pytest.raises(DatoInvalido):
        Proveedor(CUIT_A, "Sur", email=email)


# ------------------------------------------------------------------ Service

@pytest.fixture
def db(tmp_path):
    ruta = tmp_path / "test.db"
    crear_tablas(ruta)
    return ruta


@pytest.fixture
def service(db):
    return ProveedorService(ProveedorDAO(db), ProductoDAO(db))


@pytest.fixture
def productos(db):
    categoria = CategoriaService(CategoriaDAO(db)).crear("Bebidas")
    ps = ProductoService(ProductoDAO(db), CategoriaDAO(db))
    return [
        ps.crear("BEB-001", "Coca 500ml", categoria.id, 1500, 900),
        ps.crear("BEB-002", "Agua 1L", categoria.id, 800, 400),
    ]


def test_crear_y_obtener(service):
    creado = service.crear(CUIT_A, "Distribuidora Sur SA", "11-4444-5555", "ventas@sur.com")
    leido = service.obtener(creado.id)
    assert (leido.cuit, leido.razon_social, leido.telefono, leido.email) == \
        ("20123456786", "Distribuidora Sur SA", "11-4444-5555", "ventas@sur.com")


def test_cuit_duplicado_aunque_se_escriba_distinto(service):
    service.crear(CUIT_A, "Distribuidora Sur SA")
    with pytest.raises(EntidadDuplicada):
        service.crear("20123456786", "Otra razón social")


def test_misma_razon_social_con_otro_cuit_esta_permitida(service):
    service.crear(CUIT_A, "Distribuidora Sur SA")
    service.crear(CUIT_B, "Distribuidora Sur SA")
    assert len(service.listar()) == 2


def test_modificar_cambia_los_datos_pero_no_el_cuit(service):
    p = service.crear(CUIT_A, "Distribuidora Sur SA")
    service.modificar(p.id, "Sur Distribuciones SRL", "11-1111-2222", None)
    leido = service.obtener(p.id)
    assert (leido.cuit, leido.razon_social, leido.telefono, leido.email) == \
        ("20123456786", "Sur Distribuciones SRL", "11-1111-2222", None)


def test_baja_logica(service):
    p = service.crear(CUIT_A, "Distribuidora Sur SA")
    service.dar_de_baja(p.id)
    assert service.listar() == []
    assert service.obtener(p.id).activo is False


def test_obtener_inexistente(service):
    with pytest.raises(NoEncontrado):
        service.obtener(999)


# ---- Relación con productos

def test_asignar_y_listar_en_los_dos_sentidos(service, productos):
    sur = service.crear(CUIT_A, "Distribuidora Sur SA")
    norte = service.crear(CUIT_B, "Mayorista Norte SA")
    coca, agua = productos
    service.asignar_producto(sur.id, coca.id)
    service.asignar_producto(sur.id, agua.id)
    service.asignar_producto(norte.id, coca.id)

    assert [p.codigo for p in service.listar_productos(sur.id)] == ["BEB-002", "BEB-001"]  # por nombre
    assert [p.razon_social for p in service.listar_proveedores_de_producto(coca.id)] == \
        ["Distribuidora Sur SA", "Mayorista Norte SA"]


def test_asignar_dos_veces_es_duplicado(service, productos):
    sur = service.crear(CUIT_A, "Distribuidora Sur SA")
    service.asignar_producto(sur.id, productos[0].id)
    with pytest.raises(EntidadDuplicada):
        service.asignar_producto(sur.id, productos[0].id)


def test_no_se_asigna_a_un_proveedor_dado_de_baja(service, productos):
    sur = service.crear(CUIT_A, "Distribuidora Sur SA")
    service.dar_de_baja(sur.id)
    with pytest.raises(DatoInvalido):
        service.asignar_producto(sur.id, productos[0].id)


def test_no_se_asigna_un_producto_dado_de_baja(db, service, productos):
    sur = service.crear(CUIT_A, "Distribuidora Sur SA")
    ProductoService(ProductoDAO(db), CategoriaDAO(db)).dar_de_baja(productos[0].id)
    with pytest.raises(DatoInvalido):
        service.asignar_producto(sur.id, productos[0].id)


@pytest.mark.parametrize("proveedor_id, producto_id", [(999, 1), (1, 999)])
def test_asignar_con_ids_inexistentes(service, productos, proveedor_id, producto_id):
    service.crear(CUIT_A, "Distribuidora Sur SA")
    with pytest.raises(NoEncontrado):
        service.asignar_producto(proveedor_id, producto_id)


def test_quitar_producto(service, productos):
    sur = service.crear(CUIT_A, "Distribuidora Sur SA")
    service.asignar_producto(sur.id, productos[0].id)
    service.quitar_producto(sur.id, productos[0].id)
    assert service.listar_productos(sur.id) == []


def test_quitar_una_asignacion_que_no_existe(service, productos):
    sur = service.crear(CUIT_A, "Distribuidora Sur SA")
    with pytest.raises(NoEncontrado):
        service.quitar_producto(sur.id, productos[0].id)


def test_los_productos_dados_de_baja_no_aparecen_en_el_listado_del_proveedor(db, service, productos):
    sur = service.crear(CUIT_A, "Distribuidora Sur SA")
    service.asignar_producto(sur.id, productos[0].id)
    ProductoService(ProductoDAO(db), CategoriaDAO(db)).dar_de_baja(productos[0].id)
    assert service.listar_productos(sur.id) == []
