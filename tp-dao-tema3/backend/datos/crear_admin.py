# Crea el primer administrador en una base sin usuarios (por ejemplo, una
# instalación nueva sin el seed). Sin un administrador nadie puede crear los
# demás usuarios, porque /usuarios exige serlo. La contraseña se pide por
# teclado sin mostrarla, para que no quede en el historial de la consola.
# Pasa por UsuarioService, así se aplican las mismas reglas que en la api.
# Acá NO van datos de prueba (eso es seed.py).
#
# Uso (desde tp-dao-tema3):
#   .venv\Scripts\python -m backend.datos.crear_admin <usuario> "<Nombre completo>"
import sys
from getpass import getpass

from backend.dominio.excepciones import ErrorDeNegocio
from backend.persistencia.conexion import crear_tablas
from backend.servicios.usuarios_service import UsuarioService


def crear_admin(nombre_usuario, nombre_completo, contrasena):
    crear_tablas()
    return UsuarioService().crear("ADMIN", nombre_usuario, nombre_completo, None, contrasena)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print('Uso: python -m backend.datos.crear_admin <usuario> "<Nombre completo>"')
        sys.exit(1)
    contrasena = getpass("Contraseña: ")
    if getpass("Repetila: ") != contrasena:
        print("Las contraseñas no coinciden: no se creó nada.")
        sys.exit(1)
    try:
        admin = crear_admin(sys.argv[1], sys.argv[2], contrasena)
    except ErrorDeNegocio as error:
        print(f"No se pudo crear: {error}")
        sys.exit(1)
    print(f"Administrador '{admin.nombre_usuario}' creado. Ya puede entrar y crear los demás usuarios.")
