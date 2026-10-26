# Tests de los casos de uso de usuarios y del login, contra un SQLite temporal:
# alta con contraseña (con hash, nunca en texto), lo que consulta la base
# (nombre repetido, ubicación, último administrador), y sesiones con token que
# vencen y se cierran. Acá NO se prueba la api.
from datetime import datetime, timedelta

import pytest

from backend.dominio.excepciones import DatoInvalido, EntidadDuplicada, NoAutenticado, NoEncontrado
from backend.persistencia.conexion import crear_tablas, get_conexion
from backend.persistencia.dao_maestros import UbicacionDAO
from backend.persistencia.dao_usuarios import UsuarioDAO
from backend.servicios.maestros_service import UbicacionService
from backend.servicios.usuarios_service import (
    AuthService, UsuarioService, contrasena_correcta, hashear_contrasena,
)

CLAVE = "secreta123"


@pytest.fixture
def db(tmp_path):
    ruta = tmp_path / "test.db"
    crear_tablas(ruta)
    ubicaciones = UbicacionService(UbicacionDAO(ruta))
    ubicaciones.crear("CD", "CD Central", "Ruta 9")          # id 1
    ubicaciones.crear("SUCURSAL", "Local Centro", "Calle 1")  # id 2
    return ruta


@pytest.fixture
def usuarios(db):
    return UsuarioService(UsuarioDAO(db))


class Reloj:
    """Un reloj que se adelanta a mano, para probar el vencimiento."""
    def __init__(self):
        self.ahora = datetime(2026, 10, 23, 9, 0)

    def __call__(self):
        return self.ahora


@pytest.fixture
def reloj():
    return Reloj()


@pytest.fixture
def auth(db, reloj):
    return AuthService(UsuarioDAO(db), reloj=reloj)


# --------------------------------------------------------------- El hash

def test_la_contrasena_se_guarda_con_hash_y_sal(db, usuarios):
    usuarios.crear("SUCURSAL", "beto", "Beto Gómez", 2, CLAVE)
    with get_conexion(db) as cx:
        fila = cx.execute("SELECT hash_contrasena, sal FROM usuarios").fetchone()
    assert CLAVE not in fila["hash_contrasena"]
    assert contrasena_correcta(CLAVE, fila["hash_contrasena"], fila["sal"])
    assert not contrasena_correcta("otra-clave", fila["hash_contrasena"], fila["sal"])


def test_la_misma_contrasena_da_hashes_distintos_por_la_sal():
    assert hashear_contrasena(CLAVE)[0] != hashear_contrasena(CLAVE)[0]


def test_se_comprueba_con_las_iteraciones_con_que_se_guardo():
    hash_viejo, sal = hashear_contrasena(CLAVE, iteraciones=500)
    assert hash_viejo.startswith("500$")
    assert contrasena_correcta(CLAVE, hash_viejo, sal)


# --------------------------------------------------------------- Alta

def test_crear_un_usuario_de_cada_perfil(usuarios):
    assert usuarios.crear("ADMIN", "dora", "Dora Admin", None, CLAVE).perfil == "ADMIN"
    assert usuarios.crear("CD", "ana", "Ana López", 1, CLAVE).ubicacion_id == 1
    assert usuarios.crear("SUCURSAL", "beto", "Beto Gómez", 2, CLAVE).ubicacion_id == 2


def test_nombre_de_usuario_repetido(usuarios):
    usuarios.crear("SUCURSAL", "beto", "Beto Gómez", 2, CLAVE)
    with pytest.raises(EntidadDuplicada, match="Ya existe el usuario 'beto'"):
        usuarios.crear("SUCURSAL", "BETO", "Otro Beto", 2, CLAVE)


@pytest.mark.parametrize("perfil, ubicacion_id, error", [
    ("CD", 2, DatoInvalido),          # usuario CD en un local
    ("SUCURSAL", 1, DatoInvalido),    # usuario de local en el CD
    ("SUCURSAL", 99, NoEncontrado),   # ubicación que no existe
])
def test_la_ubicacion_tiene_que_existir_y_corresponder_al_perfil(usuarios, perfil, ubicacion_id, error):
    with pytest.raises(error):
        usuarios.crear(perfil, "beto", "Beto Gómez", ubicacion_id, CLAVE)


def test_no_se_crea_en_una_ubicacion_dada_de_baja(db, usuarios):
    UbicacionService(UbicacionDAO(db)).dar_de_baja(2)
    with pytest.raises(DatoInvalido, match="dada de baja"):
        usuarios.crear("SUCURSAL", "beto", "Beto Gómez", 2, CLAVE)


def test_contrasena_corta(usuarios):
    with pytest.raises(DatoInvalido, match="al menos 8"):
        usuarios.crear("SUCURSAL", "beto", "Beto Gómez", 2, "corta")


# --------------------------------------------------------------- Login

def test_login_correcto_da_un_token_que_identifica_al_usuario(usuarios, auth):
    beto = usuarios.crear("SUCURSAL", "beto", "Beto Gómez", 2, CLAVE)
    token, usuario = auth.login(" Beto ", CLAVE)
    assert usuario.id == beto.id
    assert auth.usuario_del_token(token).id == beto.id


@pytest.mark.parametrize("nombre, clave", [("beto", "equivocada"), ("nadie", CLAVE), ("beto", ""), ("beto", None)])
def test_login_incorrecto_no_dice_que_fallo(usuarios, auth, nombre, clave):
    usuarios.crear("SUCURSAL", "beto", "Beto Gómez", 2, CLAVE)
    with pytest.raises(NoAutenticado, match="Usuario o contraseña incorrectos"):
        auth.login(nombre, clave)


def test_un_usuario_dado_de_baja_no_entra_y_pierde_su_sesion(usuarios, auth):
    beto = usuarios.crear("SUCURSAL", "beto", "Beto Gómez", 2, CLAVE)
    token, _ = auth.login("beto", CLAVE)
    usuarios.dar_de_baja(beto.id)
    with pytest.raises(NoAutenticado):
        auth.usuario_del_token(token)
    with pytest.raises(NoAutenticado, match="incorrectos"):
        auth.login("beto", CLAVE)


def test_un_usuario_sin_contrasena_no_entra(db, auth):
    # Como los que vienen de una base de antes del login
    with get_conexion(db) as cx:
        cx.execute("INSERT INTO usuarios (perfil, nombre_usuario, nombre_completo, ubicacion_id) "
                   "VALUES ('SUCURSAL', 'viejo', 'Viejo', 2)")
    with pytest.raises(NoAutenticado):
        auth.login("viejo", CLAVE)


def test_la_sesion_vence(usuarios, auth, reloj):
    usuarios.crear("SUCURSAL", "beto", "Beto Gómez", 2, CLAVE)
    token, _ = auth.login("beto", CLAVE)
    reloj.ahora += timedelta(hours=9, minutes=59)
    auth.usuario_del_token(token)                     # todavía vale
    reloj.ahora += timedelta(minutes=1)
    with pytest.raises(NoAutenticado, match="venció"):
        auth.usuario_del_token(token)


@pytest.mark.parametrize("token", [None, "", "inventado"])
def test_token_ausente_o_inventado(auth, token):
    with pytest.raises(NoAutenticado):
        auth.usuario_del_token(token)


def test_logout_cierra_solo_esa_sesion(usuarios, auth):
    usuarios.crear("SUCURSAL", "beto", "Beto Gómez", 2, CLAVE)
    en_la_caja, _ = auth.login("beto", CLAVE)
    en_el_celular, _ = auth.login("beto", CLAVE)
    auth.logout(en_la_caja)
    with pytest.raises(NoAutenticado):
        auth.usuario_del_token(en_la_caja)
    assert auth.usuario_del_token(en_el_celular).nombre_usuario == "beto"


def test_cambiar_la_contrasena_cierra_las_sesiones(usuarios, auth):
    beto = usuarios.crear("SUCURSAL", "beto", "Beto Gómez", 2, CLAVE)
    token, _ = auth.login("beto", CLAVE)
    usuarios.cambiar_contrasena(beto.id, "nueva-clave-1")
    with pytest.raises(NoAutenticado):
        auth.usuario_del_token(token)
    with pytest.raises(NoAutenticado):
        auth.login("beto", CLAVE)
    auth.login("beto", "nueva-clave-1")


# --------------------------------------------- Modificar, baja y reactivar

def test_modificar_solo_el_nombre_completo(usuarios):
    beto = usuarios.crear("SUCURSAL", "beto", "Beto Gómez", 2, CLAVE)
    assert usuarios.modificar(beto.id, "Roberto Gómez").nombre_completo == "Roberto Gómez"


def test_no_se_puede_dar_de_baja_al_unico_administrador(usuarios):
    dora = usuarios.crear("ADMIN", "dora", "Dora Admin", None, CLAVE)
    with pytest.raises(DatoInvalido, match="único administrador"):
        usuarios.dar_de_baja(dora.id)
    usuarios.crear("ADMIN", "eva", "Eva Admin", None, CLAVE)
    usuarios.dar_de_baja(dora.id)      # con otro administrador, sí


def test_reactivar(usuarios):
    beto = usuarios.crear("SUCURSAL", "beto", "Beto Gómez", 2, CLAVE)
    with pytest.raises(DatoInvalido, match="No hace falta"):
        usuarios.reactivar(beto.id)
    usuarios.dar_de_baja(beto.id)
    assert usuarios.reactivar(beto.id).activo


def test_no_se_reactiva_si_su_local_cerro(db, usuarios):
    beto = usuarios.crear("SUCURSAL", "beto", "Beto Gómez", 2, CLAVE)
    usuarios.dar_de_baja(beto.id)
    UbicacionService(UbicacionDAO(db)).dar_de_baja(2)
    with pytest.raises(DatoInvalido, match="dada de baja"):
        usuarios.reactivar(beto.id)


def test_listar_con_y_sin_bajas(usuarios):
    usuarios.crear("ADMIN", "dora", "Dora Admin", None, CLAVE)
    beto = usuarios.crear("SUCURSAL", "beto", "Beto Gómez", 2, CLAVE)
    usuarios.dar_de_baja(beto.id)
    assert [u.nombre_usuario for u in usuarios.listar()] == ["dora"]
    assert len(usuarios.listar(incluir_bajas=True)) == 2
