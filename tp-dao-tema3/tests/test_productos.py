# Tests del maestro Producto: validaciones de formato en el dominio y reglas que
# necesitan la base en el service (código duplicado, categoría existente y activa).
# El service se prueba contra un SQLite temporal por test (tmp_path), así se
# prueba también el SQL y las restricciones de la tabla. Acá NO se prueba la api.
import pytest

from backend.dominio.excepciones import DatoInvalido, EntidadDuplicada, NoEncontrado
from backend.dominio.maestros import Producto
from backend.persistencia.conexion import crear_tablas
from backend.persistencia.dao_maestros import CategoriaDAO, ProductoDAO
from backend.servicios.maestros_service import CategoriaService, ProductoService


def un_producto(**cambios):
    datos = dict(codigo="BEB-001", nombre="Coca 500ml", categoria_id=1, precio_venta=1500, costo=900, stock_minimo=10)
    datos.update(cambios)
    return Producto(**datos)


# ------------------------------------------------------------------ Dominio

def test_producto_valido_normaliza_codigo_y_nombre():
    p = un_producto(codigo="  beb-001 ", nombre="  Coca 500ml  ")
    assert p.codigo == "BEB-001"
    assert p.nombre == "Coca 500ml"
    assert p.activo is True


def test_los_montos_se_redondean_a_dos_decimales_y_aceptan_texto():
    p = un_producto(precio_venta="1500.456", costo=899.999)
    assert p.precio_venta == 1500.46
    assert p.costo == 900.0


@pytest.mark.parametrize("campo, valor", [
    ("codigo", ""), ("codigo", "   "), ("codigo", None), ("codigo", "X" * 21),
    ("nombre", ""), ("nombre", "N" * 101),
    ("categoria_id", 0), ("categoria_id", "abc"),
    ("precio_venta", 0), ("precio_venta", -10), ("precio_venta", "caro"),
    ("costo", -1),
    ("stock_minimo", -1), ("stock_minimo", 2.5),
])
def test_datos_invalidos_al_crear(campo, valor):
    with pytest.raises(DatoInvalido):
        un_producto(**{campo: valor})


def test_tambien_valida_al_modificar_un_atributo():
    p = un_producto()
    with pytest.raises(DatoInvalido):
        p.precio_venta = -5
    assert p.precio_venta == 1500


def test_costo_cero_es_valido():
    assert un_producto(costo=0).costo == 0


def test_margen_unitario_puede_ser_negativo():
    assert un_producto(precio_venta=1500, costo=900).margen_unitario() == 600
    assert un_producto(precio_venta=800, costo=900).margen_unitario() == -100


def test_dar_de_baja():
    p = un_producto()
    p.dar_de_baja()
    assert p.activo is False


# ------------------------------------------------------------------ Service

@pytest.fixture
def db(tmp_path):
    ruta = tmp_path / "test.db"
    crear_tablas(ruta)
    return ruta


@pytest.fixture
def categoria(db):
    return CategoriaService(CategoriaDAO(db)).crear("Bebidas")


@pytest.fixture
def service(db):
    return ProductoService(ProductoDAO(db), CategoriaDAO(db))


def crear(service, categoria, **cambios):
    datos = dict(codigo="BEB-001", nombre="Coca 500ml", categoria_id=categoria.id, precio_venta=1500, costo=900, stock_minimo=10)
    datos.update(cambios)
    return service.crear(**datos)


def test_crear_y_obtener(service, categoria):
    creado = crear(service, categoria)
    leido = service.obtener(creado.id)
    assert leido.codigo == "BEB-001"
    assert leido.precio_venta == 1500
    assert leido.categoria_id == categoria.id


def test_codigo_duplicado_sin_distinguir_mayusculas(service, categoria):
    crear(service, categoria, codigo="BEB-001")
    with pytest.raises(EntidadDuplicada):
        crear(service, categoria, codigo="beb-001", nombre="Otro")


def test_dos_productos_activos_no_pueden_llamarse_igual(service, categoria):
    crear(service, categoria, codigo="BEB-001", nombre="Coca 500ml")
    with pytest.raises(EntidadDuplicada, match="Ya existe el producto 'Coca 500ml' \(código BEB-001\)"):
        crear(service, categoria, codigo="BEB-002", nombre="  COCA   500ML ")


def test_categoria_inexistente(service, categoria):
    with pytest.raises(NoEncontrado):
        crear(service, categoria, categoria_id=999)


def test_categoria_dada_de_baja(db, service, categoria):
    CategoriaService(CategoriaDAO(db)).dar_de_baja(categoria.id)
    with pytest.raises(DatoInvalido):
        crear(service, categoria)


def test_obtener_inexistente(service):
    with pytest.raises(NoEncontrado):
        service.obtener(999)


def test_modificar_cambia_los_datos_pero_no_el_codigo(service, categoria):
    p = crear(service, categoria)
    service.modificar(p.id, "Coca 1L", categoria.id, 2500, 1600, 5)
    leido = service.obtener(p.id)
    assert (leido.codigo, leido.nombre, leido.precio_venta, leido.costo, leido.stock_minimo) == \
        ("BEB-001", "Coca 1L", 2500, 1600, 5)


def test_modificar_con_dato_invalido_no_guarda_nada(service, categoria):
    p = crear(service, categoria)
    with pytest.raises(DatoInvalido):
        service.modificar(p.id, "Coca 1L", categoria.id, -1, 1600, 5)
    assert service.obtener(p.id).nombre == "Coca 500ml"


def test_baja_logica_lo_saca_del_listado_pero_sigue_existiendo(service, categoria):
    p = crear(service, categoria)
    service.dar_de_baja(p.id)
    assert service.listar() == []
    assert service.obtener(p.id).activo is False


def test_listar_filtra_por_categoria(db, service, categoria):
    otra = CategoriaService(CategoriaDAO(db)).crear("Limpieza")
    crear(service, categoria, codigo="BEB-001")
    crear(service, otra, codigo="LIM-001", nombre="Lavandina")
    assert [p.codigo for p in service.listar(categoria_id=otra.id)] == ["LIM-001"]
