# Casos de uso de usuarios: alta, modificación, baja y contraseña (UsuarioService),
# y la autenticación: login con contraseña, sesión con token y logout (AuthService).
# Acá va lo que consulta la base (nombre repetido, que la ubicación exista y
# esté activa, que quede algún administrador) y el hash de las contraseñas.
# Acá NO va SQL (usa dao_usuarios) ni nada de HTTP: cómo viaja el token lo
# resuelve la api.
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from backend.config import HORAS_SESION, ITERACIONES_CONTRASENA
from backend.dominio.excepciones import DatoInvalido, EntidadDuplicada, NoAutenticado, NoEncontrado
from backend.dominio.usuarios import crear_usuario, validar_contrasena
from backend.persistencia.dao_maestros import UbicacionDAO
from backend.persistencia.dao_usuarios import SesionDAO, UsuarioDAO


# ------------------------------------------------------------- Contraseñas
# El hash se guarda como "iteraciones$hash": si algún día se suben las
# iteraciones, las contraseñas viejas se siguen pudiendo comprobar.

def hashear_contrasena(contrasena, sal=None, iteraciones=ITERACIONES_CONTRASENA):
    """(hash, sal) de una contraseña. Sal nueva y al azar si no se pasa una:
    así dos usuarios con la misma contraseña no tienen el mismo hash."""
    sal = sal or secrets.token_hex(16)
    clave = hashlib.pbkdf2_hmac("sha256", contrasena.encode("utf-8"), bytes.fromhex(sal), iteraciones)
    return f"{iteraciones}${clave.hex()}", sal


def contrasena_correcta(contrasena, hash_guardado, sal):
    if not hash_guardado or not sal:
        return False
    iteraciones = int(hash_guardado.split("$")[0])
    calculado, _ = hashear_contrasena(contrasena, sal, iteraciones)
    # compare_digest tarda lo mismo acierte o no: no da pistas por el tiempo
    return hmac.compare_digest(calculado, hash_guardado)


def hash_de_token(token):
    # En la base se guarda el hash del token: quien lea la base no puede entrar
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class UsuarioService:
    def __init__(self, dao=None, ubicacion_dao=None, sesion_dao=None):
        self.dao = dao or UsuarioDAO()
        self.ubicacion_dao = ubicacion_dao or UbicacionDAO(self.dao.db_path)
        self.sesion_dao = sesion_dao or SesionDAO(self.dao.db_path)

    def crear(self, perfil, nombre_usuario, nombre_completo, ubicacion_id, contrasena):
        usuario = crear_usuario(perfil, nombre_usuario, nombre_completo, ubicacion_id)
        validar_contrasena(contrasena)
        existente = self.dao.obtener_por_nombre_usuario(usuario.nombre_usuario)
        if existente:
            estado = "" if existente.activo else " (está dado de baja: se puede reactivar)"
            raise EntidadDuplicada(f"Ya existe el usuario '{existente.nombre_usuario}'{estado}")
        if usuario.trabaja_en_una_ubicacion():
            usuario.validar_ubicacion(self.ubicacion_de(usuario.ubicacion_id))
        hash_contrasena, sal = hashear_contrasena(contrasena)
        return self.dao.crear(usuario, hash_contrasena, sal)

    def ubicacion_de(self, ubicacion_id):
        ubicacion = self.ubicacion_dao.obtener_por_id(ubicacion_id)
        if ubicacion is None:
            raise NoEncontrado(f"No existe la ubicación {ubicacion_id}")
        return ubicacion

    def obtener(self, id):
        usuario = self.dao.obtener_por_id(id)
        if usuario is None:
            raise NoEncontrado(f"No existe el usuario {id}")
        return usuario

    def listar(self, incluir_bajas=False):
        return self.dao.listar(solo_activos=not incluir_bajas)

    # Solo el nombre completo: el nombre de usuario, el perfil y la ubicación no cambian
    def modificar(self, id, nombre_completo):
        usuario = self.obtener(id)
        usuario.nombre_completo = nombre_completo
        return self.dao.actualizar(usuario)

    def cambiar_contrasena(self, id, contrasena):
        usuario = self.obtener(id)
        validar_contrasena(contrasena)
        self.dao.cambiar_contrasena(usuario.id, *hashear_contrasena(contrasena))
        self.sesion_dao.borrar_de_usuario(usuario.id)  # tiene que volver a entrar con la nueva
        return usuario

    def dar_de_baja(self, id):
        usuario = self.obtener(id)
        if not usuario.activo:
            raise DatoInvalido(f"El usuario '{usuario.nombre_usuario}' ya está dado de baja")
        # Si se va el último administrador, nadie puede volver a crear usuarios
        if usuario.puede_gestionar_maestros() and self.administradores_activos() == 1:
            raise DatoInvalido("No se puede dar de baja al único administrador activo")
        usuario.dar_de_baja()
        self.dao.actualizar(usuario)
        self.sesion_dao.borrar_de_usuario(usuario.id)  # deja de poder usar el sistema ya mismo
        return usuario

    def administradores_activos(self):
        return sum(1 for u in self.dao.listar() if u.puede_gestionar_maestros())

    def reactivar(self, id):
        usuario = self.obtener(id)
        if usuario.activo:
            raise DatoInvalido(f"No hace falta reactivar al usuario '{usuario.nombre_usuario}': no se dio de baja")
        if usuario.trabaja_en_una_ubicacion():
            usuario.validar_ubicacion(self.ubicacion_de(usuario.ubicacion_id))  # su local puede haber cerrado
        usuario.reactivar()
        return self.dao.actualizar(usuario)


class AuthService:
    # Un solo mensaje para usuario inexistente, contraseña mala o usuario de
    # baja: así no se puede averiguar qué nombres de usuario existen
    CREDENCIALES_INVALIDAS = "Usuario o contraseña incorrectos"

    def __init__(self, dao=None, sesion_dao=None, reloj=datetime.now):
        self.dao = dao or UsuarioDAO()
        self.sesion_dao = sesion_dao or SesionDAO(self.dao.db_path)
        self.reloj = reloj  # los tests lo cambian para probar el vencimiento

    def login(self, nombre_usuario, contrasena):
        """Devuelve (token, usuario). El token se le da al usuario una sola vez:
        en la base queda solo su hash."""
        credenciales = self.dao.obtener_credenciales(nombre_usuario)
        if credenciales is None:
            raise NoAutenticado(self.CREDENCIALES_INVALIDAS)
        usuario, hash_guardado, sal = credenciales
        if not usuario.activo or not contrasena_correcta(contrasena or "", hash_guardado, sal):
            raise NoAutenticado(self.CREDENCIALES_INVALIDAS)
        ahora = self.reloj()
        self.sesion_dao.borrar_vencidas(ahora)
        token = secrets.token_urlsafe(32)
        self.sesion_dao.crear(hash_de_token(token), usuario.id, ahora + timedelta(hours=HORAS_SESION))
        return token, usuario

    def usuario_del_token(self, token):
        if not token:
            raise NoAutenticado("Tenés que entrar con tu usuario y contraseña")
        usuario_id = self.sesion_dao.usuario_de(hash_de_token(token), self.reloj())
        usuario = self.dao.obtener_por_id(usuario_id) if usuario_id else None
        if usuario is None or not usuario.activo:
            raise NoAutenticado("Tu sesión venció o ya no es válida: volvé a entrar")
        return usuario

    def logout(self, token):
        if token:
            self.sesion_dao.borrar(hash_de_token(token))
