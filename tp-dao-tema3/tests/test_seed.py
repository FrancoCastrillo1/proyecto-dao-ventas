# Test del seed: corre el script real (como lo correría alguien del grupo)
# contra una base temporal y verifica que el escenario quede cargado y
# coherente. Se corre en otro proceso porque la ruta de la base se fija al
# importar los módulos (variable de entorno TP_DAO_DB).
import os
import subprocess
import sys
from pathlib import Path

from backend.persistencia.dao_logistica import RemitoDAO
from backend.persistencia.dao_maestros import ProductoDAO
from backend.persistencia.dao_reportes import ReporteDAO
from backend.persistencia.conexion import get_conexion
from backend.persistencia.dao_usuarios import UsuarioDAO
from backend.persistencia.dao_ventas import VentaDAO
from backend.servicios.reportes_service import ReportesService
from backend.servicios.usuarios_service import AuthService

RAIZ = Path(__file__).resolve().parent.parent


def correr_seed(db, *argumentos):
    resultado = subprocess.run(
        [sys.executable, "-m", "backend.datos.seed", *argumentos],
        cwd=RAIZ, env={**os.environ, "TP_DAO_DB": str(db)},
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert resultado.returncode == 0, resultado.stderr
    return resultado.stdout


def test_el_seed_carga_el_escenario_completo(tmp_path):
    db = tmp_path / "seed.db"
    correr_seed(db)
    assert len(ProductoDAO(db).listar()) == 10
    estados = sorted(r.estado for r in RemitoDAO(db).listar())
    assert estados == ["EN_TRANSITO", "VERIFICADO", "VERIFICADO_CON_RECHAZOS"]
    assert len(VentaDAO(db).listar()) == 8
    reportes = ReportesService(ReporteDAO(db))
    assert reportes.mermas()["filas"]                                   # hay un bulto rechazado
    margenes = {f["codigo"]: f["margen"] for f in reportes.productos_mas_vendidos(limite=20)["filas"]}
    assert margenes["LAC-002"] < 0                                      # el producto en promo pierde plata


def test_correr_el_seed_dos_veces_no_duplica(tmp_path):
    db = tmp_path / "seed.db"
    correr_seed(db)
    salida = correr_seed(db)
    assert "ya tiene datos" in salida
    assert len(VentaDAO(db).listar()) == 8


def test_reiniciar_borra_y_vuelve_a_cargar(tmp_path):
    db = tmp_path / "seed.db"
    correr_seed(db)
    correr_seed(db, "--reiniciar")
    assert len(VentaDAO(db).listar()) == 8


def test_el_seed_trae_un_usuario_de_cada_perfil_que_puede_entrar(tmp_path):
    db = tmp_path / "seed.db"
    salida = correr_seed(db)
    assert "tpdao2026" in salida                      # el seed muestra con qué entrar
    usuarios = {u.nombre_usuario: u for u in UsuarioDAO(db).listar()}
    assert {n: u.perfil for n, u in usuarios.items()} == {
        "admin": "ADMIN", "cd.central": "CD", "centro": "SUCURSAL", "norte": "SUCURSAL", "sur": "SUCURSAL",
    }
    for nombre in usuarios:
        AuthService(UsuarioDAO(db)).login(nombre, "tpdao2026")


def test_en_el_seed_cada_operacion_la_hizo_quien_corresponde(tmp_path):
    db = tmp_path / "seed.db"
    correr_seed(db)
    with get_conexion(db) as cx:
        def perfiles(tabla):
            return {f[0] for f in cx.execute(
                f"SELECT DISTINCT u.perfil FROM {tabla} t LEFT JOIN usuarios u ON u.id = t.usuario_id")}
        assert perfiles("pedidos_reposicion") == {"SUCURSAL"}
        assert perfiles("ordenes_reposicion") == {"CD"}
        assert perfiles("remitos") == {"CD"}
        assert perfiles("ventas") == {"SUCURSAL"}
        assert perfiles("devoluciones") == {"SUCURSAL"}
        assert perfiles("historial_bultos") == {"CD", "SUCURSAL"}   # el CD precinta y despacha; el local recibe
        assert perfiles("movimientos_stock") == {"CD", "SUCURSAL"}


def test_crear_el_primer_administrador(tmp_path):
    db = tmp_path / "vacia.db"
    resultado = subprocess.run(
        [sys.executable, "-c",
         "from backend.datos.crear_admin import crear_admin; print(crear_admin('jefa', 'La Jefa', 'clave-larga-1').perfil)"],
        cwd=RAIZ, env={**os.environ, "TP_DAO_DB": str(db)}, capture_output=True, text=True,
    )
    assert resultado.stdout.strip() == "ADMIN", resultado.stderr
    AuthService(UsuarioDAO(db)).login("jefa", "clave-larga-1")
