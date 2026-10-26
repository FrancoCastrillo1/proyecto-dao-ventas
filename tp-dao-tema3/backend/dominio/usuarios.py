# Usuarios del sistema y sus perfiles: UsuarioAdministrador, UsuarioCD y
# UsuarioSucursal (herencia, igual que Ubicacion). Cada perfil responde QUÉ
# PUEDE HACER: las rutas y los services preguntan por la capacidad
# (usuario.puede_vender()), nunca comparan el perfil con un if.
# También va acá el formato de una contraseña válida.
# Acá NO va nada de base de datos ni de cómo se identifica al usuario (hash de
# la contraseña, login, sesiones): eso es de los services y de la api.
import re
from abc import ABC, abstractmethod

from backend.dominio.excepciones import DatoInvalido
from backend.dominio.maestros import convertir_a_entero

# Nombre de usuario: minúsculas, números, punto, guion y guion bajo (ej: "ana.lopez")
FORMATO_NOMBRE_USUARIO = re.compile(r"^[a-z0-9._-]{3,30}$")

LARGO_MINIMO_CONTRASENA = 8


def validar_contrasena(contrasena):
    """Solo el formato: que sea lo bastante larga. Guardarla (con hash) y
    compararla en el login es del service."""
    contrasena = contrasena or ""
    if len(contrasena) < LARGO_MINIMO_CONTRASENA:
        raise DatoInvalido(f"La contraseña tiene que tener al menos {LARGO_MINIMO_CONTRASENA} caracteres")
    if len(contrasena) > 100:
        raise DatoInvalido("La contraseña no puede tener más de 100 caracteres")
    if contrasena != contrasena.strip():
        raise DatoInvalido("La contraseña no puede empezar ni terminar con espacios")
    return contrasena


class Usuario(ABC):
    """Una persona que usa el sistema. Los perfiles que operan pertenecen a UNA
    ubicación (el CD o una sucursal); el administrador, a ninguna. El perfil
    define qué funciones tiene: por defecto no puede nada y cada perfil
    redefine solo sus capacidades."""

    def __init__(self, nombre_usuario, nombre_completo, ubicacion_id=None, id=None, activo=True):
        self.id = id
        self.nombre_usuario = nombre_usuario
        self.nombre_completo = nombre_completo
        self.ubicacion_id = ubicacion_id
        self.activo = activo

    # Lo único obligatorio para cada hija: el texto que se guarda en la base.
    # No tiene setter: un usuario no cambia de perfil.
    @property
    @abstractmethod
    def perfil(self):
        pass

    @property
    def nombre_usuario(self):
        return self._nombre_usuario

    @nombre_usuario.setter
    def nombre_usuario(self, valor):
        # Se guarda normalizado: "Ana.Lopez " y "ana.lopez" son el mismo usuario
        valor = (valor or "").strip().lower()
        if not FORMATO_NOMBRE_USUARIO.match(valor):
            raise DatoInvalido(
                "El nombre de usuario tiene que tener entre 3 y 30 caracteres: "
                "letras, números, punto, guion o guion bajo (ej: ana.lopez)"
            )
        self._nombre_usuario = valor

    @property
    def nombre_completo(self):
        return self._nombre_completo

    @nombre_completo.setter
    def nombre_completo(self, valor):
        valor = " ".join((valor or "").split())
        if not valor:
            raise DatoInvalido("El nombre completo no puede estar vacío")
        if len(valor) > 100:
            raise DatoInvalido("El nombre completo no puede tener más de 100 caracteres")
        self._nombre_completo = valor

    @property
    def ubicacion_id(self):
        return self._ubicacion_id

    @ubicacion_id.setter
    def ubicacion_id(self, valor):
        if not self.trabaja_en_una_ubicacion():
            if valor not in (None, ""):
                raise DatoInvalido("El administrador no pertenece a ninguna ubicación")
            self._ubicacion_id = None
            return
        valor = convertir_a_entero(valor, "id de ubicación")
        if valor <= 0:
            raise DatoInvalido("El usuario tiene que pertenecer a una ubicación")
        self._ubicacion_id = valor

    # ---------------------------------------------- A qué ubicación pertenece

    def trabaja_en_una_ubicacion(self):
        """Los perfiles que operan (CD y sucursal) pertenecen a una ubicación;
        el administrador no: maneja los datos de toda la red."""
        return True

    def validar_ubicacion(self, ubicacion):
        """Que la ubicación exista y esté activa lo controla el service (necesita
        la base); acá se valida que sea del tipo que corresponde al perfil."""
        if ubicacion.id != self.ubicacion_id:
            raise DatoInvalido("La ubicación no es la del usuario")
        if not ubicacion.activo:
            raise DatoInvalido(f"La ubicación '{ubicacion.nombre}' está dada de baja")
        if not self.puede_pertenecer_a(ubicacion):
            raise DatoInvalido(f"Un usuario {self.perfil} no puede pertenecer a '{ubicacion.nombre}'")

    @abstractmethod
    def puede_pertenecer_a(self, ubicacion):
        """Cada perfil decide con qué ubicaciones es compatible, preguntándole a
        la ubicación qué puede hacer (polimorfismo de los dos lados)."""

    def puede_ver_ubicacion(self, ubicacion_id):
        # Pertenencia: el CD ve toda la red; una sucursal, solo lo suyo
        return self.ve_toda_la_red() or ubicacion_id == self.ubicacion_id

    # ------------------------------------- Capacidades (por defecto, ninguna)

    def puede_gestionar_maestros(self):
        """Productos, categorías, proveedores, ubicaciones y usuarios."""
        return False

    def puede_consultar_proveedores(self):
        """Ver los proveedores y qué productos vende cada uno."""
        return self.puede_gestionar_maestros() or self.puede_comprar()

    def puede_comprar(self):
        """Registrar compras a proveedores (ingreso de stock al CD)."""
        return False

    def puede_preparar_envios(self):
        """Consolidar pedidos, armar remitos y bultos, precintar y despachar."""
        return False

    def puede_pedir_reposicion(self):
        return False

    def puede_recibir(self):
        """Recibir y verificar los bultos que llegan a su sucursal."""
        return False

    def puede_vender(self):
        """Vender, devolver y ver la caja de su sucursal."""
        return False

    def ve_toda_la_red(self):
        """Stock y reportes de todas las ubicaciones (si no, solo de la suya)."""
        return False

    def ve_ventas(self):
        """Ventas, caja, comprobantes y reportes de ventas. El CD no: solo abastece."""
        return False

    # ----------------------------------------------------------- Baja lógica

    def dar_de_baja(self):
        self.activo = False

    def reactivar(self):
        self.activo = True

    def __str__(self):
        return f"{self.perfil}: ({self.id}, {self.nombre_usuario})"


class UsuarioAdministrador(Usuario):
    # Maneja los datos de la red (locales, CD, productos, proveedores, usuarios)
    # y ve sus reportes, pero no opera: no compra, no despacha, no vende
    @property
    def perfil(self):
        return "ADMIN"

    def trabaja_en_una_ubicacion(self):
        return False

    def puede_pertenecer_a(self, ubicacion):
        return False

    def puede_gestionar_maestros(self):
        return True

    def ve_toda_la_red(self):
        return True

    def ve_ventas(self):
        return True


class UsuarioCD(Usuario):
    # Trabaja en el Centro de Distribución: compra y abastece a la red
    @property
    def perfil(self):
        return "CD"

    def puede_pertenecer_a(self, ubicacion):
        return ubicacion.puede_despachar()

    def puede_comprar(self):
        return True

    def puede_preparar_envios(self):
        return True

    def ve_toda_la_red(self):
        return True


class UsuarioSucursal(Usuario):
    # Trabaja en un local: pide mercadería, la recibe y vende
    @property
    def perfil(self):
        return "SUCURSAL"

    def puede_pertenecer_a(self, ubicacion):
        return ubicacion.puede_vender()

    def puede_pedir_reposicion(self):
        return True

    def puede_recibir(self):
        return True

    def puede_vender(self):
        return True

    def ve_ventas(self):
        return True


# Fábrica simple, igual que TIPOS_UBICACION: el único lugar que sabe qué clase
# corresponde a cada perfil. La usan el DAO (al leer) y el service (al crear).
PERFILES = {"ADMIN": UsuarioAdministrador, "CD": UsuarioCD, "SUCURSAL": UsuarioSucursal}


def crear_usuario(perfil, nombre_usuario, nombre_completo, ubicacion_id=None, id=None, activo=True):
    clase = PERFILES.get((perfil or "").strip().upper())
    if clase is None:
        raise DatoInvalido(f"Perfil '{perfil}' inválido. Opciones: {', '.join(PERFILES)}")
    return clase(nombre_usuario, nombre_completo, ubicacion_id, id, activo)
