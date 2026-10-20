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