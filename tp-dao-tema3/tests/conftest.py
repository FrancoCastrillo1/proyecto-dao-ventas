# Configuración común de los tests. Corre antes de importar cualquier módulo
# del backend, porque config.py lee estas variables al importarse:
# - TP_DAO_ITERACIONES: pocas iteraciones del hash, si no cada login tarda.
# - TP_DAO_DB: la api de los tests de rutas usa una base temporal propia, así
#   ningún test toca la base local de desarrollo.
# Acá NO van tests ni datos de prueba.
import os
import tempfile
from pathlib import Path

os.environ["TP_DAO_ITERACIONES"] = "1000"
os.environ["TP_DAO_DB"] = str(Path(tempfile.mkdtemp(prefix="tp_dao_tests_")) / "api.db")
