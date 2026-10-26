# Configuración general: ruta de la base de datos, puerto, flags de debug, etc.
# Si algo cambia según la máquina o el entorno, se define acá y en ningún otro lado.
# Acá NO va lógica, solo valores de configuración.
import os
from pathlib import Path

CARPETA_BACKEND = Path(__file__).parent

# Se puede apuntar a otra base con la variable de entorno TP_DAO_DB (la usan
# los tests del seed para no tocar la base local de desarrollo)
DB_PATH = Path(os.environ.get("TP_DAO_DB") or CARPETA_BACKEND / "tp_dao.db")

ESQUEMA_PATH = CARPETA_BACKEND / "persistencia" / "esquema.sql"

# Contraseñas: PBKDF2-SHA256. Más iteraciones = más lento probar contraseñas a
# lo bruto. Los tests bajan el número con TP_DAO_ITERACIONES para no tardar.
ITERACIONES_CONTRASENA = int(os.environ.get("TP_DAO_ITERACIONES") or 300_000)

# Cuánto dura una sesión desde el login (un turno de trabajo)
HORAS_SESION = 10

# Datos del comercio que salen en los comprobantes y notas de crédito
# (ficticios: el CUIT es válido pero no es de nadie)
COMERCIO = {
    "razon_social": "Minorista del Centro S.A.",
    "cuit": "30-71111111-1",
    "direccion": "Av. Colón 1000, Córdoba",
}