# Endpoints de autenticación (/auth: entrar, salir, quién soy) y de gestión de
# usuarios (/usuarios, solo el administrador). Llaman a usuarios_service.
# Acá NO va lógica de negocio ni acceso a la base. La contraseña nunca sale en
# ninguna respuesta (ni su hash).
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.api.dependencias import ADMINISTRADOR, auth_service, token_actual, usuario_actual
from backend.servicios.usuarios_service import UsuarioService

service = UsuarioService()


class UsuarioSalida(BaseModel):
    id: int
    nombre_usuario: str
    nombre_completo: str
    perfil: str
    ubicacion_id: int | None
    activo: bool
    # Lo que puede hacer, para que el front arme el menú sin repetir las reglas
    capacidades: list[str]


CAPACIDADES = [
    "puede_gestionar_maestros", "puede_consultar_proveedores", "puede_comprar", "puede_preparar_envios",
    "puede_pedir_reposicion", "puede_recibir", "puede_vender", "ve_toda_la_red",
]


def usuario_a_salida(usuario):
    return UsuarioSalida(
        id=usuario.id, nombre_usuario=usuario.nombre_usuario, nombre_completo=usuario.nombre_completo,
        perfil=usuario.perfil, ubicacion_id=usuario.ubicacion_id, activo=usuario.activo,
        capacidades=[c for c in CAPACIDADES if getattr(usuario, c)()],
    )


# ------------------------------------------------------------------- /auth
router_auth = APIRouter(prefix="/auth", tags=["Autenticación"])


class LoginEntrada(BaseModel):
    nombre_usuario: str
    contrasena: str


class LoginSalida(BaseModel):
    token: str
    usuario: UsuarioSalida


@router_auth.post("/login", response_model=LoginSalida)
def login(datos: LoginEntrada):
    token, usuario = auth_service.login(datos.nombre_usuario, datos.contrasena)
    return LoginSalida(token=token, usuario=usuario_a_salida(usuario))


@router_auth.get("/yo", response_model=UsuarioSalida)
def quien_soy(usuario=Depends(usuario_actual)):
    return usuario_a_salida(usuario)


@router_auth.post("/logout", status_code=204)
def logout(token: str | None = Depends(token_actual)):
    auth_service.logout(token)


# --------------------------------------------------------------- /usuarios
router_usuarios = APIRouter(prefix="/usuarios", tags=["Usuarios"])


class UsuarioEntrada(BaseModel):
    perfil: str
    nombre_usuario: str
    nombre_completo: str
    ubicacion_id: int | None = None   # vacío para un administrador
    contrasena: str


class UsuarioModificacion(BaseModel):
    nombre_completo: str


class ContrasenaEntrada(BaseModel):
    contrasena: str


@router_usuarios.get("", response_model=list[UsuarioSalida], dependencies=[ADMINISTRADOR])
def listar_usuarios(incluir_bajas: bool = False):
    return [usuario_a_salida(u) for u in service.listar(incluir_bajas)]


@router_usuarios.get("/{id}", response_model=UsuarioSalida, dependencies=[ADMINISTRADOR])
def obtener_usuario(id: int):
    return usuario_a_salida(service.obtener(id))


@router_usuarios.post("", response_model=UsuarioSalida, status_code=201, dependencies=[ADMINISTRADOR])
def crear_usuario(datos: UsuarioEntrada):
    return usuario_a_salida(service.crear(
        datos.perfil, datos.nombre_usuario, datos.nombre_completo, datos.ubicacion_id, datos.contrasena,
    ))


@router_usuarios.put("/{id}", response_model=UsuarioSalida, dependencies=[ADMINISTRADOR])
def modificar_usuario(id: int, datos: UsuarioModificacion):
    return usuario_a_salida(service.modificar(id, datos.nombre_completo))


@router_usuarios.put("/{id}/contrasena", status_code=204, dependencies=[ADMINISTRADOR])
def cambiar_contrasena(id: int, datos: ContrasenaEntrada):
    service.cambiar_contrasena(id, datos.contrasena)


@router_usuarios.delete("/{id}", status_code=204, dependencies=[ADMINISTRADOR])
def dar_de_baja_usuario(id: int):
    service.dar_de_baja(id)


@router_usuarios.post("/{id}/reactivar", response_model=UsuarioSalida, dependencies=[ADMINISTRADOR])
def reactivar_usuario(id: int):
    return usuario_a_salida(service.reactivar(id))
