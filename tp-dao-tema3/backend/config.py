# Configuración general: ruta de la base de datos, puerto, flags de debug, etc.
# Si algo cambia según la máquina o el entorno, se define acá y en ningún otro lado.
# Acá NO va lógica, solo valores de configuración.
from pathlib import Path

CARPETA_BACKEND = Path(__file__).parent

DB_PATH = CARPETA_BACKEND / "tp_dao.db"

ESQUEMA_PATH = CARPETA_BACKEND / "persistencia" / "esquema.sql"