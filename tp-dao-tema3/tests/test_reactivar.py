# Tests de la reactivación de maestros dados de baja. La baja es lógica: el
# registro sigue existiendo y su nombre/código/CUIT sigue ocupado, así que en
# vez de dejar crear un duplicado se avisa y se permite reactivarlo.
# Acá NO se prueba la api.
import pytest

from backend.dominio.excepciones import DatoInvalido, EntidadDuplicada
from backend.persistencia.conexion import crear_tablas
from backend.persistencia.dao_maestros import CategoriaDAO, ProductoDAO, ProveedorDAO, UbicacionDAO
from backend.servicios.maestros_service import (
    CategoriaService, ProductoService, ProveedorService, UbicacionService,
)


@pytest.fixture
def db(tmp_path):
    ruta = tmp_path / "test.db"
    crear_tablas(ruta)
    return ruta


@pytest.fixture
def categorias(db):
    return CategoriaService(CategoriaDAO(db))


@pytest.fixture
def productos(db):
    return ProductoService(ProductoDAO(db), CategoriaDAO(db))


# ------------------------------------------------------------- Categorías

def test_crear_una_categoria_dada_de_baja_avisa_que_se_puede_reactivar(categorias):
    bebidas = categorias.crear("Bebidas")
    categorias.dar_de_baja(bebidas.id)
    with pytest.raises(EntidadDuplicada, match="se dio de baja.*reactivar"):
        categorias.crear("Bebidas")


def test_el_duplicado_de_una_activa_no_menciona_la_reactivacion(categorias):
    categorias.crear("Bebidas")
    with pytest.raises(EntidadDuplicada) as error:
        categorias.crear("bebidas")
    assert "reactivar" not in str(error.value)


def test_reactivar_conserva_el_mismo_id_y_vuelve_al_listado(categorias):
    bebidas = categorias.crear("Bebidas")
    categorias.dar_de_baja(bebidas.id)
    assert categorias.listar() == []

    reactivada = categorias.reactivar(bebidas.id)
    assert reactivada.id == bebidas.id
    assert [c.nombre for c in categorias.listar()] == ["Bebidas"]


def test_listar_incluyendo_bajas(categorias):
    bebidas = categorias.crear("Bebidas")
    categorias.crear("Limpieza")
    categorias.dar_de_baja(bebidas.id)
    assert [c.nombre for c in categorias.listar()] == ["Limpieza"]
    assert [(c.nombre, c.activo) for c in categorias.listar(incluir_bajas=True)] == \
        [("Bebidas", False), ("Limpieza", True)]


def test_no_se_reactiva_algo_que_esta_activo(categorias):
    bebidas = categorias.crear("Bebidas")
    with pytest.raises(DatoInvalido):
        categorias.reactivar(bebidas.id)


# -------------------------------------------------------------- Productos

def test_producto_con_codigo_dado_de_baja(categorias, productos):
    cat = categorias.crear("Bebidas")
    coca = productos.crear("BEB-001", "Coca", cat.id, 1500, 900)
    productos.dar_de_baja(coca.id)
    with pytest.raises(EntidadDuplicada, match="reactivar"):
        productos.crear("BEB-001", "Otra Coca", cat.id, 1500, 900)
    assert productos.reactivar(coca.id).activo is True


def test_no_se_reactiva_un_producto_si_su_categoria_sigue_de_baja(categorias, productos):
    cat = categorias.crear("Bebidas")
    coca = productos.crear("BEB-001", "Coca", cat.id, 1500, 900)
    productos.dar_de_baja(coca.id)
    categorias.dar_de_baja(cat.id)
    with pytest.raises(DatoInvalido, match="dada de baja"):
        productos.reactivar(coca.id)
    categorias.reactivar(cat.id)
    assert productos.reactivar(coca.id).activo is True


def test_productos_listar_incluyendo_bajas(categorias, productos):
    cat = categorias.crear("Bebidas")
    coca = productos.crear("BEB-001", "Coca", cat.id, 1500, 900)
    productos.dar_de_baja(coca.id)
    assert productos.listar() == []
    assert len(productos.listar(incluir_bajas=True)) == 1


# ------------------------------------------------------------ Proveedores

def test_proveedor_con_cuit_dado_de_baja(db):
    service = ProveedorService(ProveedorDAO(db), ProductoDAO(db))
    sur = service.crear("20-12345678-6", "Distribuidora Sur SA")
    service.dar_de_baja(sur.id)
    with pytest.raises(EntidadDuplicada, match="reactivar"):
        service.crear("20123456786", "Otra")
    assert service.reactivar(sur.id).activo is True
    assert len(service.listar()) == 1


# ------------------------------------------------------------ Ubicaciones

def test_ubicacion_dada_de_baja(db):
    service = UbicacionService(UbicacionDAO(db))
    local = service.crear("SUCURSAL", "Local Centro", "Calle 1")
    service.dar_de_baja(local.id)
    with pytest.raises(EntidadDuplicada, match="reactivar"):
        service.crear("SUCURSAL", "local centro", "Calle 2")
    assert service.reactivar(local.id).activo is True


def test_no_se_reactiva_un_cd_si_ya_hay_otro_activo(db):
    service = UbicacionService(UbicacionDAO(db))
    viejo = service.crear("CD", "CD Central", "Ruta 9")
    service.dar_de_baja(viejo.id)
    service.crear("CD", "CD Nuevo", "Ruta 34")
    with pytest.raises(EntidadDuplicada, match="Centro de Distribución activo"):
        service.reactivar(viejo.id)


def test_ubicaciones_listar_incluyendo_bajas_con_filtro_de_tipo(db):
    service = UbicacionService(UbicacionDAO(db))
    cd = service.crear("CD", "CD Central", "Ruta 9")
    service.crear("SUCURSAL", "Local Centro", "Calle 1")
    service.dar_de_baja(cd.id)
    assert service.listar("CD") == []
    assert [u.nombre for u in service.listar("CD", incluir_bajas=True)] == ["CD Central"]
