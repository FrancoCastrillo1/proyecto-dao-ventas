# Dependencias de FastAPI que comparten todas las rutas: quién es el usuario
# (usuario_actual, a partir del token del login), si su perfil puede hacer lo
# que pide la ruta (requiere) y si lo que pide es de su local (pertenencia).
# Es el ÚNICO lugar de la api que sabe cómo viaja el token: si cambia la forma
# de entrar, cambia solo este archivo.
# Acá NO van reglas de negocio: se pregunta al usuario por su capacidad
# (polimorfismo), nunca por su perfil con un if.
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.dominio.excepciones import SinPermiso
from backend.servicios.usuarios_service import AuthService

auth_service = AuthService()

# "Authorization: Bearer <token>". auto_error=False: si falta, el mensaje lo da
# el service ("Tenés que entrar..."), igual que cualquier otro error del negocio.
# Además agrega el botón "Authorize" en /docs para probar con un token.
esquema_bearer = HTTPBearer(auto_error=False, description="El token que devuelve POST /auth/login")


def token_actual(credenciales: HTTPAuthorizationCredentials | None = Depends(esquema_bearer)):
    return credenciales.credentials if credenciales else None


def usuario_actual(token: str | None = Depends(token_actual)):
    return auth_service.usuario_del_token(token)


# Qué decir cuando un perfil no tiene una capacidad: explica quién sí puede
MENSAJES_SIN_PERMISO = {
    "puede_gestionar_maestros": "Solo un administrador puede cambiar los datos maestros y los usuarios",
    "puede_consultar_proveedores": "Tu perfil no puede ver los proveedores",
    "puede_comprar": "Solo el Centro de Distribución registra compras",
    "puede_preparar_envios": "Solo el Centro de Distribución prepara y despacha los envíos",
    "puede_pedir_reposicion": "Solo un local puede pedir reposición",
    "puede_recibir": "Solo un local recibe y verifica los envíos",
    "puede_vender": "Solo un local vende y hace devoluciones",
    "ve_ventas": "Tu perfil no ve las ventas: el Centro de Distribución solo abastece a los locales",
    "ve_toda_la_red": "Esto es de toda la red: lo ven el Centro de Distribución y el administrador",
    "ve_resultados_empresa": "Los resultados de toda la empresa los ve solo el administrador",
}


def requiere(capacidad):
    """Dependencia para una ruta: deja pasar solo a los usuarios cuyo perfil
    tiene esa capacidad, y devuelve el usuario para usarlo en la ruta.
    Uso: usuario=Depends(requiere("puede_vender"))."""
    def controlar(usuario=Depends(usuario_actual)):
        if not getattr(usuario, capacidad)():
            raise SinPermiso(MENSAJES_SIN_PERMISO.get(capacidad, "Tu perfil no puede hacer esto"))
        return usuario
    return controlar


# Atajos para las rutas que solo necesitan saber que hay alguien adentro, o
# que es un administrador (se usan en dependencies=[...] cuando la ruta no
# necesita el usuario para nada más)
LOGUEADO = Depends(usuario_actual)
ADMINISTRADOR = Depends(requiere("puede_gestionar_maestros"))


# ------------------------------------------------------------- Pertenencia

def exigir_que_sea_suyo(usuario, ubicacion_id, que):
    """El CD y el administrador ven toda la red; un local, solo lo suyo. Si
    no es suyo: 403 con un mensaje claro (ej: "Ese remito no es de tu local")."""
    if not usuario.puede_ver_ubicacion(ubicacion_id):
        raise SinPermiso(f"{que} no es de tu local")


def ubicacion_para_filtrar(usuario, pedida):
    """Para listados y reportes: quien ve toda la red filtra por lo que pidió
    (o nada = todo); un local siempre ve solo lo suyo, y si pide otro, 403."""
    if usuario.ve_toda_la_red():
        return pedida
    if pedida is not None:
        exigir_que_sea_suyo(usuario, pedida, "Esa ubicación")
    return usuario.ubicacion_id
