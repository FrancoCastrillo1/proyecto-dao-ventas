# Tests de Ubicacion (Sucursal y CentroDistribucion): herencia y polimorfismo
# de capacidades, la fábrica que arma la clase según el tipo, y en el service
# los nombres duplicados y la regla de un único CD activo. El service se prueba
# contra un SQLite temporal por test (tmp_path). Acá NO se prueba la api.
import sqlite3

import pytest

from backend.dominio.excepciones import DatoInvalido, EntidadDuplicada, NoEncontrado
from backend.dominio.maestros import CentroDistribucion, Sucursal, Ubicacion, crear_ubicacion
from backend.persistencia.conexion import crear_tablas
from backend.persistencia.dao_maestros import UbicacionDAO
from backend.servicios.maestros_service import UbicacionService


# ------------------------------------------------------------------ Dominio

def test_ubicacion_es_abstracta():
    with pytest.raises(TypeError):
        Ubicacion("Algo", "Calle 1")


@pytest.mark.parametrize("ubicacion, vender, despachar, recibir", [
    (Sucursal("Local Centro", "San Martín 100"), True, False, True),
    (CentroDistribucion("CD Central", "Ruta 9 km 5"), False, True, False),
])
def test_cada_tipo_tiene_sus_capacidades(ubicacion, vender, despachar, recibir):
    assert ubicacion.puede_vender() is vender
    assert ubicacion.puede_despachar() is despachar
    assert ubicacion.puede_recibir() is recibir


@pytest.mark.parametrize("tipo, clase", [
    ("SUCURSAL", Sucursal), ("CD", CentroDistribucion), (" sucursal ", Sucursal), ("cd", CentroDistribucion),
])
def test_la_fabrica_arma_la_clase_segun_el_tipo(tipo, clase):
    ubicacion = crear_ubicacion(tipo, "Nombre", "Dirección")
    assert type(ubicacion) is clase


@pytest.mark.parametrize("tipo", ["DEPOSITO", "", None])
def test_la_fabrica_rechaza_tipos_invalidos(tipo):
    with pytest.raises(DatoInvalido):
        crear_ubicacion(tipo, "Nombre", "Dirección")


def test_el_tipo_no_se_puede_cambiar():
    with pytest.raises(AttributeError):
        Sucursal("Local Centro", "San Martín 100").tipo = "CD"


@pytest.mark.parametrize("nombre, direccion", [
    ("", "Calle 1"), ("   ", "Calle 1"), ("N" * 51, "Calle 1"),
    ("Local", ""), ("Local", None), ("Local", "D" * 151),
])
def test_datos_invalidos(nombre, direccion):
    with pytest.raises(DatoInvalido):
        Sucursal(nombre, direccion)


# ------------------------------------------------------------------ Service

@pytest.fixture
def db(tmp_path):
    ruta = tmp_path / "test.db"
    crear_tablas(ruta)
    return ruta


@pytest.fixture
def service(db):
    return UbicacionService(UbicacionDAO(db))


def test_crear_y_leer_devuelve_la_clase_correcta(service):
    local = service.crear("SUCURSAL", "Local Centro", "San Martín 100")
    cd = service.crear("CD", "CD Central", "Ruta 9 km 5")
    assert type(service.obtener(local.id)) is Sucursal
    assert type(service.obtener(cd.id)) is CentroDistribucion


def test_nombre_duplicado_sin_distinguir_mayusculas(service):
    service.crear("SUCURSAL", "Local Centro", "San Martín 100")
    with pytest.raises(EntidadDuplicada):
        service.crear("SUCURSAL", "local centro", "Otra calle 200")


def test_no_puede_haber_dos_cd_activos(service):
    service.crear("CD", "CD Central", "Ruta 9 km 5")
    with pytest.raises(EntidadDuplicada):
        service.crear("CD", "CD Norte", "Ruta 34 km 2")


def test_dado_de_baja_el_cd_se_puede_crear_otro(service):
    viejo = service.crear("CD", "CD Central", "Ruta 9 km 5")
    service.dar_de_baja(viejo.id)
    nuevo = service.crear("CD", "CD Nuevo", "Ruta 34 km 2")
    assert service.obtener_cd().id == nuevo.id


def test_la_base_tambien_impide_dos_cd_activos(db, service):
    service.crear("CD", "CD Central", "Ruta 9 km 5")
    with pytest.raises(sqlite3.IntegrityError):
        UbicacionDAO(db).crear(CentroDistribucion("CD Trucho", "Calle 1"))  # salteando el service


def test_varias_sucursales_estan_permitidas(service):
    service.crear("SUCURSAL", "Local Centro", "San Martín 100")
    service.crear("SUCURSAL", "Local Norte", "Belgrano 900")
    assert len(service.listar("SUCURSAL")) == 2


def test_obtener_cd_sin_cd_activo(service):
    with pytest.raises(NoEncontrado):
        service.obtener_cd()


def test_listar_filtra_por_tipo(service):
    service.crear("SUCURSAL", "Local Centro", "San Martín 100")
    service.crear("CD", "CD Central", "Ruta 9 km 5")
    assert [u.nombre for u in service.listar("cd")] == ["CD Central"]
    assert len(service.listar()) == 2


def test_listar_con_tipo_invalido(service):
    with pytest.raises(DatoInvalido):
        service.listar("DEPOSITO")


def test_modificar_cambia_nombre_y_direccion_pero_no_el_tipo(service):
    local = service.crear("SUCURSAL", "Local Centro", "San Martín 100")
    service.modificar(local.id, "Local Centro II", "San Martín 150")
    leido = service.obtener(local.id)
    assert (type(leido), leido.nombre, leido.direccion) == (Sucursal, "Local Centro II", "San Martín 150")


def test_modificar_conservando_el_mismo_nombre_no_es_duplicado(service):
    local = service.crear("SUCURSAL", "Local Centro", "San Martín 100")
    service.modificar(local.id, "Local Centro", "San Martín 150")
    assert service.obtener(local.id).direccion == "San Martín 150"


def test_modificar_con_el_nombre_de_otra_es_duplicado(service):
    service.crear("SUCURSAL", "Local Centro", "San Martín 100")
    norte = service.crear("SUCURSAL", "Local Norte", "Belgrano 900")
    with pytest.raises(EntidadDuplicada):
        service.modificar(norte.id, "Local Centro", "Belgrano 900")


def test_baja_logica(service):
    local = service.crear("SUCURSAL", "Local Centro", "San Martín 100")
    service.dar_de_baja(local.id)
    assert service.listar() == []
    assert service.obtener(local.id).activo is False
