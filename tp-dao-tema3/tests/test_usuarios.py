# Tests del dominio de usuarios: capacidades de cada perfil (polimorfismo),
# validaciones de los datos, la fábrica, a qué ubicación puede pertenecer cada
# perfil y la regla de pertenencia. Acá NO se prueba la base ni la api.
import pytest

from backend.dominio.excepciones import DatoInvalido
from backend.dominio.maestros import CentroDistribucion, Sucursal
from backend.dominio.usuarios import (
    Usuario, UsuarioAdministrador, UsuarioCD, UsuarioSucursal, crear_usuario, validar_contrasena,
)

CD = CentroDistribucion("CD Central", "Ruta 9", id=1)
LOCAL = Sucursal("Local Centro", "Calle 1", id=2)
OTRO_LOCAL = Sucursal("Local Norte", "Calle 2", id=3)


def un_admin(**cambios):
    datos = dict(nombre_usuario="admin", nombre_completo="Dora Admin")
    datos.update(cambios)
    return UsuarioAdministrador(**datos)


def un_cd(**cambios):
    datos = dict(nombre_usuario="ana.cd", nombre_completo="Ana López", ubicacion_id=CD.id)
    datos.update(cambios)
    return UsuarioCD(**datos)


def una_sucursal(**cambios):
    datos = dict(nombre_usuario="beto.centro", nombre_completo="Beto Gómez", ubicacion_id=LOCAL.id)
    datos.update(cambios)
    return UsuarioSucursal(**datos)


# ------------------------------------------------------------- Capacidades

def test_usuario_es_abstracto():
    with pytest.raises(TypeError):
        Usuario("ana", "Ana", 1)


CAPACIDADES = ["puede_gestionar_maestros", "puede_comprar", "puede_preparar_envios",
               "puede_pedir_reposicion", "puede_recibir", "puede_vender", "ve_toda_la_red", "ve_ventas",
               "ve_resultados_empresa"]
VER = {"ve_toda_la_red", "ve_ventas", "ve_resultados_empresa"}   # lo que se puede ver no es una tarea


@pytest.mark.parametrize("usuario, permitidas", [
    (un_admin(), {"puede_gestionar_maestros", "ve_toda_la_red", "ve_ventas", "ve_resultados_empresa"}),
    (un_cd(), {"puede_comprar", "puede_preparar_envios", "ve_toda_la_red"}),     # el CD no ve ventas
    (una_sucursal(), {"puede_pedir_reposicion", "puede_recibir", "puede_vender", "ve_ventas"}),
])
def test_cada_perfil_tiene_sus_funciones_y_ninguna_mas(usuario, permitidas):
    for capacidad in CAPACIDADES:
        assert getattr(usuario, capacidad)() is (capacidad in permitidas), capacidad


def test_ningun_perfil_hace_lo_del_otro():
    # Lo que se HACE está repartido sin repetir: administrar, abastecer y vender.
    # Ver (toda la red, las ventas) no es una tarea: lo comparten varios perfiles.
    tareas = [c for c in CAPACIDADES if c not in VER]
    perfiles = [un_admin(), un_cd(), una_sucursal()]
    for capacidad in tareas:
        assert sum(getattr(p, capacidad)() for p in perfiles) == 1, capacidad


@pytest.mark.parametrize("usuario, puede", [(un_admin(), True), (un_cd(), True), (una_sucursal(), False)])
def test_proveedores_los_ve_quien_los_administra_o_les_compra(usuario, puede):
    assert usuario.puede_consultar_proveedores() is puede


# ------------------------------------------------------------- Pertenencia

@pytest.mark.parametrize("usuario", [un_admin(), un_cd()])
def test_el_administrador_y_el_cd_ven_toda_la_red(usuario):
    assert all(usuario.puede_ver_ubicacion(u.id) for u in (CD, LOCAL, OTRO_LOCAL))


def test_la_sucursal_ve_solo_lo_suyo():
    usuario = una_sucursal()
    assert usuario.puede_ver_ubicacion(LOCAL.id)
    assert not usuario.puede_ver_ubicacion(OTRO_LOCAL.id)
    assert not usuario.puede_ver_ubicacion(CD.id)


# --------------------------------------- A qué ubicación puede pertenecer

def test_cada_perfil_pertenece_al_tipo_de_ubicacion_que_corresponde():
    un_cd().validar_ubicacion(CD)
    una_sucursal().validar_ubicacion(LOCAL)


@pytest.mark.parametrize("usuario, ubicacion", [
    (un_cd(ubicacion_id=LOCAL.id), LOCAL),        # un usuario CD en un local
    (una_sucursal(ubicacion_id=CD.id), CD),       # un usuario de sucursal en el CD
])
def test_perfil_y_ubicacion_incompatibles(usuario, ubicacion):
    with pytest.raises(DatoInvalido, match="no puede pertenecer"):
        usuario.validar_ubicacion(ubicacion)


def test_el_administrador_no_pertenece_a_ninguna_ubicacion():
    admin = un_admin()
    assert admin.ubicacion_id is None
    assert not admin.trabaja_en_una_ubicacion()
    with pytest.raises(DatoInvalido):
        admin.validar_ubicacion(CD)


def test_al_administrador_no_se_le_puede_asignar_ubicacion():
    with pytest.raises(DatoInvalido, match="ninguna ubicación"):
        un_admin(ubicacion_id=CD.id)


def test_ubicacion_dada_de_baja():
    local = Sucursal("Local Viejo", "Calle 9", id=7, activo=False)
    with pytest.raises(DatoInvalido, match="dada de baja"):
        una_sucursal(ubicacion_id=7).validar_ubicacion(local)


def test_la_ubicacion_tiene_que_ser_la_del_usuario():
    with pytest.raises(DatoInvalido, match="no es la del usuario"):
        una_sucursal().validar_ubicacion(OTRO_LOCAL)


# ------------------------------------------------------------- Validaciones

def test_el_nombre_de_usuario_se_normaliza():
    assert una_sucursal(nombre_usuario="  Beto.Centro ").nombre_usuario == "beto.centro"


def test_el_nombre_completo_se_limpia():
    assert una_sucursal(nombre_completo="  Beto   Gómez ").nombre_completo == "Beto Gómez"


@pytest.mark.parametrize("campo, valor", [
    ("nombre_usuario", ""), ("nombre_usuario", "ab"), ("nombre_usuario", "x" * 31),
    ("nombre_usuario", "con espacio"), ("nombre_usuario", "ñandú"), ("nombre_usuario", None),
    ("nombre_completo", ""), ("nombre_completo", "   "), ("nombre_completo", "N" * 101),
    ("ubicacion_id", 0), ("ubicacion_id", "abc"), ("ubicacion_id", None),
])
def test_datos_invalidos(campo, valor):
    with pytest.raises(DatoInvalido):
        una_sucursal(**{campo: valor})


def test_tambien_valida_al_modificar():
    usuario = una_sucursal()
    with pytest.raises(DatoInvalido):
        usuario.nombre_completo = ""
    assert usuario.nombre_completo == "Beto Gómez"


def test_el_perfil_no_se_puede_cambiar():
    with pytest.raises(AttributeError):
        una_sucursal().perfil = "CD"


# ------------------------------------------------------------------ Fábrica

@pytest.mark.parametrize("perfil, clase", [
    ("CD", UsuarioCD), ("SUCURSAL", UsuarioSucursal), (" sucursal ", UsuarioSucursal), ("cd", UsuarioCD),
])
def test_la_fabrica_arma_la_clase_segun_el_perfil(perfil, clase):
    usuario = crear_usuario(perfil, "ana.cd", "Ana López", 1)
    assert type(usuario) is clase
    assert usuario.perfil == perfil.strip().upper()


def test_la_fabrica_arma_un_administrador_sin_ubicacion():
    usuario = crear_usuario("admin", "dora", "Dora Admin")
    assert type(usuario) is UsuarioAdministrador
    assert usuario.ubicacion_id is None


@pytest.mark.parametrize("perfil", ["GERENTE", "", None])
def test_la_fabrica_rechaza_perfiles_invalidos(perfil):
    with pytest.raises(DatoInvalido, match="Perfil"):
        crear_usuario(perfil, "ana.cd", "Ana López", 1)


# -------------------------------------------------------------- Contraseña

def test_contrasena_valida():
    assert validar_contrasena("secreta123") == "secreta123"


@pytest.mark.parametrize("contrasena, mensaje", [
    ("", "al menos 8"), (None, "al menos 8"), ("corta", "al menos 8"),
    ("x" * 101, "más de 100"), (" secreta123", "espacios"), ("secreta123 ", "espacios"),
])
def test_contrasenas_invalidas(contrasena, mensaje):
    with pytest.raises(DatoInvalido, match=mensaje):
        validar_contrasena(contrasena)


# ------------------------------------------------------------- Baja lógica

def test_baja_y_reactivacion():
    usuario = una_sucursal()
    assert usuario.activo
    usuario.dar_de_baja()
    assert not usuario.activo
    usuario.reactivar()
    assert usuario.activo
